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


_STRUCTURAL_PREFIXES = (
    "def ",
    "class ",
    "if ",
    "elif ",
    "else",
    "for ",
    "while ",
    "try",
    "except",
    "finally",
    "with ",
    "match ",
    "case ",
    "return ",
    "import ",
    "from ",
)


def _is_structural(stripped: str) -> bool:
    text = (stripped or "").lstrip()
    if text in {"else:", "try:", "finally:", "except:", "pass"}:
        return True
    return text.startswith(_STRUCTURAL_PREFIXES)


def _prev_code_index(lines: list[str], idx: int) -> int | None:
    for index in range(idx - 1, -1, -1):
        if lines[index].strip():
            return index
    return None


def _dedent_to_peer(lines: list[str], idx: int) -> bool:
    """Убрать лишний отступ до уровня предыдущей непустой строки."""
    if idx < 0 or idx >= len(lines):
        return False
    prev = _prev_code_index(lines, idx)
    target = 0 if prev is None else _line_indent(lines[prev])
    current = _line_indent(lines[idx])
    if current <= target:
        return False
    stripped = lines[idx].lstrip(" \t")
    lines[idx] = (" " * target) + stripped
    return True


def _fix_indent_error(lines: list[str], idx: int, error: str) -> bool:
    lowered = (error or "").lower()
    if idx < 0 or idx >= len(lines):
        return False

    if "unexpected indent" in lowered:
        if _dedent_to_peer(lines, idx):
            return True
        stripped = lines[idx].strip()
        if stripped.startswith(("import ", "from ")):
            lines[idx] = stripped
            return True
        if stripped and not _is_structural(stripped):
            del lines[idx]
            return True
        return False

    if "expected an indented block" in lowered:
        base = _line_indent(lines[idx])
        if lines[idx].rstrip().endswith(":"):
            next_idx = idx + 1
            indent = base + 4
            if next_idx < len(lines) and lines[next_idx].strip():
                if _line_indent(lines[next_idx]) <= base:
                    lines[next_idx] = (" " * indent) + lines[next_idx].lstrip(" \t")
                    return True
            lines.insert(next_idx, f"{' ' * indent}pass")
            return True
        return False

    if "unindent does not match" in lowered:
        return _dedent_to_peer(lines, idx)

    return False


def _close_open_brackets(text: str) -> str:
    for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
        text += closer * max(0, text.count(opener) - text.count(closer))
    return text


def _fix_truncated_syntax_line(lines: list[str], idx: int, error: str) -> bool:
    """Дописать оборванный хвост: кавычки, скобки, двоеточие."""
    if idx < 0 or idx >= len(lines):
        return False
    lowered = (error or "").lower()
    line = lines[idx]
    changed = False
    if "unterminated" in lowered or "eof while scanning" in lowered:
        odd_double = line.count('"') % 2 == 1
        odd_single = line.count("'") % 2 == 1
        if odd_double:
            line += '"'
            changed = True
        elif odd_single:
            line += "'"
            changed = True
        elif '"' in line:
            line += '"'
            changed = True
        elif "'" in line:
            line += "'"
            changed = True
    if changed or "never closed" in lowered or "unexpected eof" in lowered:
        line = _close_open_brackets(line)
        changed = True
    if "expected ':'" in lowered and not line.rstrip().endswith(":"):
        cut = re.sub(r"\s+(and|or)\s+[\w.]*$", "", line.rstrip())
        line = cut.rstrip() + ":"
        changed = True
    if not changed:
        return False
    lines[idx] = line
    return True


def _drop_incomplete_last_line(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    if _compile_lines(lines[:-1]) is None:
        del lines[-1]
        return True
    return False


def auto_repair_python_source(content: str, error_hint: str = "") -> dict[str, Any]:
    """
    Итеративно чинит типичные SyntaxError:
    - лишние else без if
    - pygame.quit() без import pygame
    - дублирующиеся else/print в конце файла
    - оборванный хвост (кавычки, скобки, двоеточие)
    """
    from core.staged_write import sanitize_code_chunk

    cleaned = sanitize_code_chunk(content or "")
    start = cleaned if cleaned.strip() else (content or "")
    lines = start.splitlines()
    all_highlights: list[dict] = []
    max_rounds = 24

    for _ in range(max_rounds):
        error = _compile_lines(lines)
        if error is None:
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
            if _drop_incomplete_last_line(lines):
                all_highlights.append({"line": len(lines) + 1, "type": "delete", "old": ""})
                continue
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

        if _fix_indent_error(lines, idx, error):
            all_highlights.append(
                {"line": line_no, "type": "replace", "old": stripped}
            )
            continue

        if _fix_truncated_syntax_line(lines, idx, error):
            all_highlights.append(
                {"line": line_no, "type": "replace", "old": stripped}
            )
            continue

        if idx == len(lines) - 1 and _drop_incomplete_last_line(lines):
            all_highlights.append({"line": line_no, "type": "delete", "old": stripped})
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
    from core.python_deps import rewrite_tkinter_gui_mistakes

    rewritten = rewrite_tkinter_gui_mistakes(original)
    if rewritten != original:
        full.write_text(rewritten, encoding="utf-8")
        return {
            "ok": True,
            "path": normalized,
            "content": rewritten,
            "highlights": [{"line": 1, "type": "replace", "old": "tkinter"}],
            "message": "Исправлен типичный сбой tkinter (импорт или winfo_keysym → bind)",
        }
    result = auto_repair_python_source(original, error_hint)
    if not result.get("ok"):
        return result

    repaired = str(result.get("content") or "")
    from core.file_outline import is_stub_python

    if is_stub_python(repaired) and not is_stub_python(original):
        return {"ok": False, "reason": "repair_would_stub", "content": original}
    if len(original) > 120 and len(repaired) < max(40, int(len(original) * 0.35)):
        return {"ok": False, "reason": "repair_too_destructive", "content": original}

    full.write_text(repaired, encoding="utf-8")
    return {
        "ok": True,
        "path": normalized,
        "content": result["content"],
        "highlights": result.get("highlights") or [],
        "message": result.get("message", "Синтаксис восстановлен"),
    }
