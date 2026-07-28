"""История диалога и контекст проекта для CoreX."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MEMORY_DIR = "chat"
HISTORY_FILENAME = "conversation.json"
MAX_MESSAGES = 40


def _history_path(project_root: Path) -> Path:
    return project_root / MEMORY_DIR / HISTORY_FILENAME


def load_history(project_root: Path) -> list[dict[str, str]]:
    path = _history_path(project_root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return []
        return [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")
        ][-MAX_MESSAGES:]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


def save_history(project_root: Path, messages: list[dict[str, str]]) -> None:
    path = _history_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = messages[-MAX_MESSAGES:]
    path.write_text(
        json.dumps({"messages": trimmed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def merge_history(
    stored: list[dict[str, str]],
    incoming: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Объединить сохранённую историю с сообщениями из UI (UI приоритетнее при конфликте длины)."""
    cleaned: list[dict[str, str]] = []
    if incoming:
        for item in incoming:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = str(item.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                cleaned.append({"role": role, "content": content})

    if len(cleaned) >= len(stored):
        return cleaned[-MAX_MESSAGES:]
    return stored[-MAX_MESSAGES:]


def format_history_for_prompt(messages: list[dict[str, str]], limit: int = 12) -> str:
    if not messages:
        return ""
    recent = messages[-limit:]
    lines = ["=== ИСТОРИЯ ДИАЛОГА ==="]
    for msg in recent:
        label = "Пользователь" if msg["role"] == "user" else "CoreX"
        lines.append(f"{label}: {msg['content']}")
    lines.append("=== КОНЕЦ ИСТОРИИ ===\n")
    return "\n".join(lines)


def trim_history_for_llm(
    messages: list[dict[str, str]] | None,
    *,
    max_turns: int = 8,
    max_chars: int = 2500,
) -> list[dict[str, str]]:
    """Keep recent turns and clip oversized messages (token saver for online APIs)."""
    if not messages:
        return []
    trimmed: list[dict[str, str]] = []
    for item in messages[-max(1, max_turns) :]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if len(content) > max_chars:
            half = max_chars // 2
            content = content[:half] + "\n…\n" + content[-half:]
        trimmed.append({"role": role, "content": content})
    return trimmed
