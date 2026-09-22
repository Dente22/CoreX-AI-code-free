"""Поэтапная запись кода: чистые куски, без служебных инструкций и дублей."""

from __future__ import annotations

import re

_LEAK_LINE = re.compile(
    r"next chunk only|fence with the|do not rewrite|continue with append_file|"
    r"json header|не копируй эту|следующий ход:\s*append|system error:|"
    r"короткий json-заголовок|"
    r"blocked done attempt|"
    r"auto-repair applied|"
    r"do not return done|"
    r"tool result:|"
    r'"unchanged"\s*:|'
    r'"success"\s*:|'
    r'"status"\s*:\s*"(?:act|done)"|'
    r"^\s*```",
    re.I,
)
_CODEISH = re.compile(
    r"^\s*(import |from |def |class |function |const |let |var |#include |"
    r"<!doctype|<html|pygame\.|print\(|if __name__)",
    re.I | re.M,
)


def is_protocol_leak(text: str) -> bool:
    blob = (text or "").strip()
    if not blob:
        return True
    if _LEAK_LINE.search(blob) and not _CODEISH.search(blob):
        return True
    if blob.lower().startswith("system:") or blob.lower().startswith("system error"):
        return True
    return False


def sanitize_code_chunk(text: str) -> str:
    blob = (text or "").replace("\r\n", "\n")
    blob = re.sub(r"^```[a-zA-Z0-9_+-]*[ \t]*\r?\n?", "", blob)
    blob = re.sub(r"\n?```[ \t]*$", "", blob)
    kept: list[str] = []
    for line in blob.splitlines():
        low = line.strip().lower()
        if _LEAK_LINE.search(line):
            continue
        if low.startswith("system:") or low.startswith("system error"):
            continue
        if '{"status"' in low or '"tool":"append_file"' in low:
            continue
        if low.startswith("```"):
            continue
        kept.append(line.rstrip())
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    if not kept:
        return ""
    return "\n".join(kept) + "\n"


def merge_append(existing: str, chunk: str) -> str:
    """Дописать кусок: выкинуть утечки протокола, повторные import и повторные def."""
    from core.file_outline import drop_duplicate_top_level_blocks

    piece = sanitize_code_chunk(chunk)
    if is_protocol_leak(piece) or not piece.strip():
        return existing or ""
    old = existing or ""
    piece = drop_duplicate_top_level_blocks(old, piece)
    if not piece.strip():
        return old
    compact_new = "\n".join(ln.strip() for ln in piece.splitlines() if ln.strip())
    compact_old = "\n".join(ln.strip() for ln in old.splitlines() if ln.strip())
    if compact_new and compact_new in compact_old:
        return old
    old_imports = {
        ln.strip()
        for ln in old.splitlines()
        if ln.strip().startswith(("import ", "from "))
    }
    kept: list[str] = []
    for ln in piece.splitlines():
        stripped = ln.strip()
        if stripped.startswith(("import ", "from ")) and stripped in old_imports:
            continue
        kept.append(ln)
    piece = "\n".join(kept).strip("\n")
    if not piece.strip():
        return old
    if old and not old.endswith("\n"):
        old += "\n"
    return old + piece + ("" if piece.endswith("\n") else "\n")


def numbered_snapshot(content: str, *, path: str = "main.py", max_lines: int = 160) -> str:
    from core.file_outline import numbered_snapshot as _snapshot

    return _snapshot(content, path=path, max_lines=max_lines)
