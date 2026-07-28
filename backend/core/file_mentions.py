"""Ссылки на файлы через /path в сообщениях чата."""

from __future__ import annotations

import re
from pathlib import Path

from core.project_paths import is_corex_internal_path, is_allowed_internal_read, normalize_rel_path

MENTION_PATTERN = re.compile(
    r"(?:^|[\s(«\"'])"
    r"/"
    r"([^\s/][^\s,.)»\"']*)",
    re.UNICODE,
)

MAX_INLINE_BYTES = 80_000
MAX_MENTIONS = 8


def extract_mention_paths(text: str) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for match in MENTION_PATTERN.finditer(text):
        raw = normalize_rel_path(match.group(1))
        if not raw or raw in seen:
            continue
        seen.add(raw)
        paths.append(raw)
        if len(paths) >= MAX_MENTIONS:
            break
    return paths


async def expand_file_mentions(
    user_task: str,
    file_service,
    *,
    max_bytes: int = MAX_INLINE_BYTES,
) -> tuple[str, list[str]]:
    """Подставить содержимое /file в промпт для AI."""
    paths = extract_mention_paths(user_task)
    if not paths or file_service is None:
        return user_task, []

    blocks: list[str] = []
    attached: list[str] = []

    for rel_path in paths:
        if is_corex_internal_path(rel_path) and not is_allowed_internal_read(rel_path):
            blocks.append(
                f"--- FILE: {rel_path} ---\n"
                f"(папка chat/ служебная — прямое чтение недоступно через /ссылку)\n"
                f"--- END ---"
            )
            continue

        result = await file_service.read_file(rel_path)
        if not isinstance(result, dict) or result.get("error"):
            err = result.get("error", "не найден") if isinstance(result, dict) else "ошибка"
            blocks.append(f"--- FILE: {rel_path} ---\n(ошибка чтения: {err})\n--- END ---")
            continue

        content = result.get("content", "")
        if len(content.encode("utf-8")) > max_bytes:
            content = content[: max_bytes // 2] + "\n... [файл обрезан] ..."

        blocks.append(f"--- FILE: {rel_path} ---\n{content}\n--- END ---")
        attached.append(rel_path)

    if not blocks:
        return user_task, attached

    expanded = (
        f"{user_task}\n\n"
        "[Прикреплённые файлы из /ссылок]\n"
        + "\n\n".join(blocks)
    )
    return expanded, attached
