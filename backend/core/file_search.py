"""Поиск текста внутри файлов открытого проекта."""

from __future__ import annotations

import os
from pathlib import Path

from core.project_paths import should_skip_for_analysis

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".pdf",
    ".zip",
    ".gz",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".wasm",
    ".mp3",
    ".mp4",
    ".webm",
    ".ogg",
    ".pyc",
    ".pyo",
    ".class",
}

MIN_QUERY_LEN = 2
DEFAULT_LIMIT = 80
MAX_LIMIT = 200
MAX_FILES = 800
MAX_FILE_BYTES = 512_000
MAX_PER_FILE = 12
SNIPPET_MAX = 160


def _rel_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _snippet(line: str, query: str, max_len: int = SNIPPET_MAX) -> str:
    stripped = line.replace("\t", " ").rstrip()
    if len(stripped) <= max_len:
        return stripped.strip()
    lowered = stripped.lower()
    needle = query.lower()
    idx = lowered.find(needle)
    if idx < 0:
        return stripped[: max_len - 1].strip() + "…"
    pad = max(0, (max_len - len(query)) // 2)
    start = max(0, idx - pad)
    end = min(len(stripped), start + max_len)
    start = max(0, end - max_len)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(stripped) else ""
    return prefix + stripped[start:end].strip() + suffix


def search_project_files(
    project_root: Path,
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    q = (query or "").strip()
    cap = min(max(int(limit or DEFAULT_LIMIT), 1), MAX_LIMIT)
    if len(q) < MIN_QUERY_LEN:
        return {"success": True, "matches": [], "truncated": False, "query": q}

    root = project_root.resolve()
    if not root.is_dir():
        return {"error": "Папка проекта не найдена"}

    needle = q.lower()
    matches: list[dict] = []
    files_seen = 0
    truncated = False

    for dirpath, dirnames, filenames in os_walk_filtered(root):
        for name in filenames:
            if len(matches) >= cap:
                truncated = True
                break
            if files_seen >= MAX_FILES:
                truncated = True
                break

            path = Path(dirpath) / name
            rel = _rel_posix(root, path)
            if should_skip_for_analysis(name, rel):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue

            files_seen += 1
            file_hits = 0
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES or size == 0:
                continue

            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:8192]:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                if needle not in line.lower():
                    continue
                matches.append(
                    {
                        "path": rel,
                        "name": name,
                        "line": line_no,
                        "text": _snippet(line, q),
                    }
                )
                file_hits += 1
                if file_hits >= MAX_PER_FILE or len(matches) >= cap:
                    break

            if len(matches) >= cap:
                truncated = True
                break
        if truncated:
            break

    return {
        "success": True,
        "matches": matches,
        "truncated": truncated,
        "query": q,
    }


def os_walk_filtered(root: Path):
    """os.walk that prunes ignored directories in-place."""
    root_resolved = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_resolved):
        current = Path(dirpath).resolve()
        try:
            rel_dir = current.relative_to(root_resolved).as_posix()
        except ValueError:
            dirnames[:] = []
            continue
        if rel_dir == ".":
            rel_dir = ""
        kept: list[str] = []
        for name in dirnames:
            entry_rel = name if not rel_dir else f"{rel_dir}/{name}"
            if should_skip_for_analysis(name, entry_rel):
                continue
            kept.append(name)
        dirnames[:] = kept
        yield dirpath, dirnames, filenames
