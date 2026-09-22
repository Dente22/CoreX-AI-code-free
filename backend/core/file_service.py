import os
import json
import asyncio
from pathlib import Path
from typing import Optional

from core.file_patch import apply_file_patch, number_file_content
from core.project_paths import collect_mentionable_files, is_corex_internal_path
from core.file_search import search_project_files

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

    def _should_exclude(self, name: str, rel_path: str = "") -> bool:
        if name in EXCLUDED_DIR_NAMES or name.startswith("."):
            return True
        return is_corex_internal_path(rel_path)

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
            from core.project_paths import is_corex_internal_path
            from core.file_outline import prepare_source_write

            from core.write_target import NO_EXTENSION_ERROR, filename_has_extension

            refused = self._directory_write_error(normalized)
            if refused:
                return refused
            if not filename_has_extension(normalized):
                return {"error": NO_EXTENSION_ERROR}

            if not is_corex_internal_path(normalized):
                existing = ""
                disk = self._resolve_path(normalized)
                if disk.is_file() and normalized.lower().endswith(".py"):
                    try:
                        existing = disk.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        existing = ""
                gated = prepare_source_write(normalized, content, existing=existing)
                if gated.get("error"):
                    return {"error": gated["error"]}
                content = str(gated.get("content") if gated.get("content") is not None else content)
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

    async def append_file(self, path: str, content: str) -> dict:
        """Дописать кусок в конец файла. Служебный текст и повторные import отбрасываются."""
        from core.staged_write import is_protocol_leak, merge_append, sanitize_code_chunk

        normalized = (path or "").replace("\\", "/").lstrip("/")
        chunk = sanitize_code_chunk(content or "")
        if is_protocol_leak(chunk) or not chunk.strip():
            return {
                "error": (
                    "Кусок не похож на код (служебный текст или пусто). "
                    "Пришлите только исходник — без инструкций."
                )
            }
        existing = await self._read_file_local(normalized)
        old = ""
        if isinstance(existing, dict) and "error" not in existing:
            old = str(existing.get("content") or "")
        merged = merge_append(old, chunk)
        if merged == old:
            full_path = self._resolve_path(normalized)
            return {
                "success": True,
                "path": normalized,
                "absolute_path": str(full_path),
                "unchanged": True,
            }
        return await self.write_file(normalized, merged)

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
            normalized = (path or ".").replace("\\", "/").strip().lstrip("/")
            if is_corex_internal_path(normalized):
                return {"contents": []}
            full_path = self._resolve_path(path)
            if not full_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}
            
            contents = []
            for item in sorted(full_path.iterdir()):
                item_rel = (
                    str(item.relative_to(self.project_root)).replace("\\", "/")
                    if item != self.project_root
                    else "."
                )
                if self._should_exclude(item.name, item_rel):
                    continue
                contents.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": item_rel,
                })
            
            return {"contents": contents}
        except Exception as e:
            return {"error": str(e)}

    async def _read_file_local(self, path: str) -> dict:
        """Локальное чтение файла (без MCP)."""
        try:
            full_path = self._resolve_path(path)
            if full_path.is_dir():
                return {
                    "error": (
                        f"Path is a directory, not a file: {path}. "
                        "Use list_directory for folders."
                    )
                }
            if not full_path.is_file():
                return {"error": f"Path is not a file: {path}"}
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return {"content": content}
        except Exception as e:
            return {"error": str(e)}

    def _directory_write_error(self, path: str) -> Optional[dict]:
        cleaned = (path or "").replace("\\", "/").strip()
        if not cleaned or cleaned in (".", "./"):
            return {
                "error": (
                    "Path is a directory, not a file. "
                    "Specify a file name such as main.py."
                )
            }
        target = self._resolve_path(cleaned)
        if target.is_dir():
            return {
                "error": (
                    f"Path is a directory, not a file: {path}. "
                    "Specify a file inside the project."
                )
            }
        return None

    def _ensure_parent_dirs(self, full_path: Path) -> Optional[dict]:
        """Создать родительские папки. Файл без расширения на месте папки — убрать."""
        from core.write_target import filename_has_extension

        root = self.project_root.resolve()
        cursor = full_path.parent
        chain: list[Path] = []
        while True:
            try:
                resolved = cursor.resolve()
                resolved.relative_to(root)
            except ValueError:
                break
            if resolved == root:
                break
            chain.append(cursor)
            cursor = cursor.parent
        for folder in reversed(chain):
            if folder.is_file():
                rel = str(folder.relative_to(root)).replace("\\", "/")
                if filename_has_extension(rel):
                    return {"error": f"Нельзя создать папку: {rel} уже файл с расширением."}
                try:
                    folder.unlink()
                except OSError as exc:
                    return {"error": f"Не удалось убрать файл без расширения {rel}: {exc}"}
            if not folder.exists():
                try:
                    folder.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    return {"error": str(exc)}
        return None

    async def _write_file_local(self, path: str, content: str) -> dict:
        """Локальная запись файла (без MCP)."""
        refused = self._directory_write_error(path)
        if refused:
            return refused
        from core.write_target import NO_EXTENSION_ERROR, filename_has_extension

        if not filename_has_extension(path):
            return {"error": NO_EXTENSION_ERROR}
        try:
            full_path = self._resolve_path(path)
            blocked = self._ensure_parent_dirs(full_path)
            if blocked:
                return blocked
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    async def list_mention_candidates(self, query: str = "", limit: int = 30) -> list[str]:
        return collect_mentionable_files(self.project_root, query, limit=limit)

    async def search_contents(self, query: str, limit: int = 80) -> dict:
        try:
            return await asyncio.to_thread(
                search_project_files,
                self.project_root,
                query,
                limit=limit,
            )
        except Exception as e:
            return {"error": str(e)}

    async def create_directory(self, path: str) -> dict:
        """Создать директорию внутри project_root."""
        try:
            target = self._resolve_path(path)
            from core.write_target import filename_has_extension

            if target.is_file() and not filename_has_extension(path):
                target.unlink()
            blocked = self._ensure_parent_dirs(target)
            if blocked:
                return blocked
            if target.is_file():
                return {"error": f"Нельзя создать папку: {path} уже файл."}
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
