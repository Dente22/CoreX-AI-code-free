"""Авто-исправление синтаксических ошибок Python (orphan else, мусорные строки)."""

from __future__ import annotations

import py_compile
import re
import tempfile
from pathlib import Path
from typing import Any

_SYNTAX_LINE_RE = re.compile(r"line\s+(\d+)", re.IGNORECASE)


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _extract_error_line(detail: str) -> int | None:
    match = _SYNTAX_LINE_RE.search(detail or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _compile_lines(lines: list[str]) -> str | None:
    text = "\n".join(lines) + ("\n" if lines else "")
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(text)
            path = handle.name
        py_compile.compile(path, doraise=True)
        Path(path).unlink(missing_ok=True)
        return None
    except py_compile.PyCompileError as exc:
        Path(path).unlink(missing_ok=True)
        return str(exc)


def _delete_block_at(lines: list[str], index: int) -> list[dict]:
    if index < 0 or index >= len(lines):
        return []
    highlights: list[dict] = []
    base_indent = _line_indent(lines[index])
    old = lines[index]
    del lines[index]
    highlights.append({"line": index + 1, "type": "delete", "old": old})
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            old = lines[index]
            del lines[index]
            highlights.append({"line": index + 1, "type": "delete", "old": old})
            continue
        if _line_indent(line) > base_indent:
            old = lines[index]
            del lines[index]
            highlights.append({"line": index + 1, "type": "delete", "old": old})
            continue
        break
    return highlights


def auto_repair_python_source(content: str, error_hint: str = "") -> dict[str, Any]:
    """
    Итеративно чинит типичные SyntaxError:
    - лишние else без if
    - pygame.quit() без import pygame
  - дублирующиеся else/print в конце файла
    """
    lines = content.splitlines()
    all_highlights: list[dict] = []
    max_rounds = 24

    for _ in range(max_rounds):
        error = _compile_lines(lines)
        if error is None:
            if "import pygame" not in "\n".join(lines):
                remove_idx = [
                    index
                    for index, line in enumerate(lines)
                    if "pygame." in line
                ]
                for index in reversed(remove_idx):
                    old = lines[index]
                    del lines[index]
                    all_highlights.append(
                        {"line": index + 1, "type": "delete", "old": old}
                    )
                error = _compile_lines(lines)
                if error is None:
                    pass
                else:
                    continue

            new_content = "\n".join(lines) + ("\n" if lines else "")
            if new_content == content:
                return {"ok": False, "reason": "already_valid", "content": content}
            return {
                "ok": True,
                "content": new_content,
                "highlights": all_highlights,
                "message": f"Синтаксис восстановлен ({len(all_highlights)} правок)",
            }

        line_no = _extract_error_line(error) or _extract_error_line(error_hint)
        if not line_no or line_no < 1 or line_no > len(lines):
            break

        idx = line_no - 1
        stripped = lines[idx].strip()

        if stripped.startswith("else:") or stripped == "else:":
            all_highlights.extend(_delete_block_at(lines, idx))
            continue

        if "pygame" in stripped and "import pygame" not in content:
            old = lines[idx]
            del lines[idx]
            all_highlights.append({"line": line_no, "type": "delete", "old": old})
            continue

        if stripped.startswith("elif ") and idx > 0:
            prev = lines[idx - 1].strip()
            if not prev.endswith(":") and "if " not in prev:
                all_highlights.extend(_delete_block_at(lines, idx))
                continue

        break

    last_error = _compile_lines(lines) or error_hint
    return {
        "ok": False,
        "reason": "could_not_repair",
        "content": content,
        "last_error": last_error,
    }


def repair_file_on_disk(project_root: Path, rel_path: str, error_hint: str = "") -> dict[str, Any]:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    full = (project_root / normalized).resolve()
    if not full.is_file():
        return {"ok": False, "reason": "file_not_found"}

    original = full.read_text(encoding="utf-8", errors="replace")
    result = auto_repair_python_source(original, error_hint)
    if not result.get("ok"):
        return result

    full.write_text(result["content"], encoding="utf-8")
    return {
        "ok": True,
        "path": normalized,
        "content": result["content"],
        "highlights": result.get("highlights") or [],
        "message": result.get("message", "Синтаксис восстановлен"),
    }
