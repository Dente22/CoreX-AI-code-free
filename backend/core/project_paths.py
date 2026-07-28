"""Служебные пути CoreX и обход проекта для анализа AI."""

from __future__ import annotations

from pathlib import Path

COREX_INTERNAL_DIRS = {"chat"}
MEMORY_REL_PATH = "chat/project_memory.md"

_SKIP_NAMES = {
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


def normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("/")


def is_corex_internal_path(rel_path: str) -> bool:
    norm = normalize_rel_path(rel_path)
    if not norm or norm == ".":
        return False
    top = norm.split("/")[0]
    return top in COREX_INTERNAL_DIRS


def is_allowed_internal_read(rel_path: str) -> bool:
    norm = normalize_rel_path(rel_path)
    return norm == MEMORY_REL_PATH or norm.endswith("/project_memory.md")


def should_skip_for_analysis(name: str, rel_path: str) -> bool:
    if name in _SKIP_NAMES or name.startswith("."):
        return True
    return is_corex_internal_path(rel_path)


def collect_analysis_entries(
    project_root: Path,
    *,
    max_depth: int = 4,
    max_files: int = 80,
) -> list[str]:
    root = project_root.resolve()
    lines: list[str] = []

    def walk(directory: Path, rel: str, depth: int) -> None:
        if len(lines) >= max_files or depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return

        for entry in entries:
            if len(lines) >= max_files:
                return
            entry_rel = entry.name if not rel else f"{rel}/{entry.name}"
            if should_skip_for_analysis(entry.name, entry_rel):
                continue
            if entry.is_dir():
                lines.append(f"  [dir] {entry_rel}/")
                walk(entry, entry_rel, depth + 1)
            else:
                lines.append(f"  [file] {entry_rel}")

    walk(root, "", 0)
    return lines


def collect_mentionable_files(
    project_root: Path,
    query: str = "",
    *,
    limit: int = 30,
    max_depth: int = 6,
) -> list[str]:
    root = project_root.resolve()
    q = query.strip().lower().replace("\\", "/")
    matches: list[str] = []

    def walk(directory: Path, rel: str, depth: int) -> None:
        if len(matches) >= limit or depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return

        for entry in entries:
            if len(matches) >= limit:
                return
            entry_rel = entry.name if not rel else f"{rel}/{entry.name}"
            if should_skip_for_analysis(entry.name, entry_rel):
                continue
            if entry.is_dir():
                walk(entry, entry_rel, depth + 1)
            elif not q or q in entry_rel.lower():
                matches.append(entry_rel.replace("\\", "/"))

    walk(root, "", 0)
    return matches[:limit]
