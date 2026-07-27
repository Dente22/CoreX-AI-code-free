import os
import json
import asyncio
from pathlib import Path
from typing import Optional

from core.file_patch import apply_file_patch, number_file_content
from core.project_paths import collect_mentionable_files

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".env",
    "node_modules",
    ".venv",
    ".venv-1",
    "dist",
    ".cursor",
    ".idea",
}


class FileService:
    def __init__(self, mcp_manager, project_root: str, use_mcp: bool = False):
        self.mcp = mcp_manager
        self.project_root = Path(project_root).resolve()
        self.use_mcp = use_mcp

    def _should_exclude(self, name: str) -> bool:
        return name in EXCLUDED_DIR_NAMES or name.startswith(".")

    async def list_directory(self, path: str = ".") -> dict:
        """Список файлов в активном project_root (всегда локально — для UI и дерева)."""
        try:
            return await self._list_directory_local(path)
        except Exception as e:
            return {"error": str(e)}

    async def read_file(self, path: str) -> dict:
        """Прочитать содержимое файла (всегда локально — надёжнее MCP)."""
        try:
            result = await self._read_file_local(path)
            if isinstance(result, dict) and "content" in result and "error" not in result:
                content = result.get("content", "")
                result["line_count"] = len(content.splitlines()) if content else 0
                result["numbered_content"] = number_file_content(content)
            return result
        except Exception as e:
            return {"error": str(e)}

    async def patch_file(self, path: str, operations: list) -> dict:
        """Построчное изменение файла."""
        try:
            normalized = path.replace("\\", "/").lstrip("/")
            read_result = await self._read_file_local(normalized)
            if read_result.get("error"):
                return read_result

            old_content = read_result.get("content", "")
            new_content, highlights, errors = apply_file_patch(old_content, operations or [])
            if errors and not highlights:
                return {"error": "; ".join(errors)}

            write_result = await self._write_file_local(normalized, new_content)
            if write_result.get("error"):
                return write_result

            full_path = self._resolve_path(normalized)
            return {
                "success": True,
                "path": normalized,
                "absolute_path": str(full_path),
                "content": new_content,
                "highlights": highlights,
                "warnings": errors,
                "operations_applied": len(operations or []),
            }
        except Exception as e:
            return {"error": str(e)}

    async def write_file(self, path: str, content: str) -> dict:
        """Записать содержимое в файл. Always returns {success: True} or {error: ...}."""
        try:
            normalized = path.replace("\\", "/").lstrip("/")
            local_result = await self._write_file_local(normalized, content)
            if isinstance(local_result, dict) and local_result.get("error"):
                return local_result

            full_path = self._resolve_path(normalized)
            if not full_path.is_file():
                return {
                    "error": (
                        f"Write failed: file not found after write: {normalized} "
                        f"(root: {self.project_root})"
                    ),
                }

            return {
                "success": True,
                "path": normalized,
                "absolute_path": str(full_path),
            }
        except Exception as e:
            return {"error": str(e)}

    async def get_file_tree(self, path: str = ".", max_depth: int = 3) -> dict:
        """Получить дерево файлов для фронтенда."""
        async def build_tree(current_path: str, depth: int) -> Optional[dict]:
            if depth > max_depth:
                return None
            
            try:
                list_result = await self.list_directory(current_path)
                
                if "error" in list_result:
                    return None
                
                contents = list_result.get("contents", [])
                children = []
                
                for item in contents:
                    item_path = item.get("path", "")
                    item_type = item.get("type", "file")
                    item_name = item.get("name", "")
                    
                    if item_type == "directory":
                        subtree = await build_tree(item_path, depth + 1)
                        children.append({
                            "name": item_name,
                            "type": "folder",
                            "path": item_path,
                            "children": subtree.get("children", []) if subtree else []
                        })
                    else:
                        children.append({
                            "name": item_name,
                            "type": "file",
                            "path": item_path
                        })
                
                return {"name": Path(current_path).name or "root", "children": children}
            except Exception as e:
                return None
        
        tree = await build_tree(path, 0)
        return {"success": True, "tree": tree} if tree else {"error": "Failed to build tree"}

    # === FALLBACK МЕТОДЫ ДЛЯ ЛОКАЛЬНОЙ РАБОТЫ ===

    async def _list_directory_local(self, path: str) -> dict:
        """Локальное чтение директории (без MCP)."""
        try:
            full_path = self._resolve_path(path)
            if not full_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}
            
            contents = []
            for item in sorted(full_path.iterdir()):
                if self._should_exclude(item.name):
                    continue
                contents.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item.relative_to(self.project_root)).replace("\\", "/")
                    if item != self.project_root
                    else ".",
                })
            
            return {"contents": contents}
        except Exception as e:
            return {"error": str(e)}

    async def _read_file_local(self, path: str) -> dict:
        """Локальное чтение файла (без MCP)."""
        try:
            full_path = self._resolve_path(path)
            if not full_path.is_file():
                return {"error": f"Path is not a file: {path}"}
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return {"content": content}
        except Exception as e:
            return {"error": str(e)}

    async def _write_file_local(self, path: str, content: str) -> dict:
        """Локальная запись файла (без MCP)."""
        try:
            full_path = self._resolve_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    async def list_mention_candidates(self, query: str = "", limit: int = 30) -> list[str]:
        return collect_mentionable_files(self.project_root, query, limit=limit)

    async def create_directory(self, path: str) -> dict:
        """Создать директорию внутри project_root."""
        try:
            target = self._resolve_path(path)
            target.mkdir(parents=True, exist_ok=True)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    async def delete_file(self, path: str) -> dict:
        """Удалить файл или директорию внутри project_root."""
        try:
            target = self._resolve_path(path)
            if target.is_dir():
                # remove directory recursively
                for child in sorted(target.rglob('*'), reverse=True):
                    if child.is_file():
                        child.unlink()
                    else:
                        try:
                            child.rmdir()
                        except Exception:
                            pass
                try:
                    target.rmdir()
                except Exception:
                    pass
            elif target.is_file():
                target.unlink()
            else:
                return {"error": "Path does not exist"}

            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    # === УТИЛИТЫ ===

    def _resolve_path(self, path: str) -> Path:
        """Безопасное разрешение пути (защита от path traversal)."""
        root = self.project_root.resolve()
        if path in (".", ""):
            return root

        normalized = (path or "").replace("\\", "/").strip()
        candidate = Path(normalized)
        if candidate.is_absolute():
            target = candidate.resolve()
        else:
            target = (root / normalized.lstrip("/")).resolve()

        if not self._is_within_root(target, root):
            raise ValueError(f"Path traversal attempt: {path}")

        return target

    @staticmethod
    def _is_within_root(target: Path, root: Path) -> bool:
        try:
            target.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    async def set_project_root(self, path: str) -> dict:
        """Поменять корневой каталог проекта."""
        try:
            new_root = Path(path).resolve()
            if not new_root.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            self.project_root = new_root
            # Файловые операции всегда локальные; MCP не используется для записи.
            self.use_mcp = False

            return {
                "success": True,
                "root": str(new_root),
                "mcp_connected": False,
            }
        except Exception as e:
            return {"error": str(e)}

    def _format_result(self, mcp_result) -> dict:
        """Форматирование результата MCP в единый формат."""
        if hasattr(mcp_result, 'model_dump'):
            data = mcp_result.model_dump()
        elif isinstance(mcp_result, dict):
            data = mcp_result
        else:
            return {"error": "Invalid result format"}
        
        # Преобразуем MCP формат в наш формат
        if "contents" in data:
            return {"contents": data["contents"]}
        elif "text" in data:
            return {"content": data["text"]}
        else:
            return data
