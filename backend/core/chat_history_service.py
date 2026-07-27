"""Сохранение и загрузка истории чата UI (проект/chat/)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.conversation_memory import HISTORY_FILENAME, MEMORY_DIR, load_history

UI_MESSAGES_FILENAME = "ui_messages.json"
SESSIONS_DIRNAME = "sessions"
MAX_UI_MESSAGES = 200
MAX_SESSIONS = 50


def _chat_dir(project_root: Path) -> Path:
    return project_root / MEMORY_DIR


def _ui_messages_path(project_root: Path) -> Path:
    return _chat_dir(project_root) / UI_MESSAGES_FILENAME


def _sessions_dir(project_root: Path) -> Path:
    return _chat_dir(project_root) / SESSIONS_DIRNAME


def _slugify(text: str, limit: int = 48) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    cleaned = re.sub(r"[\s_]+", "-", cleaned.strip().lower())
    return (cleaned[:limit] or "chat").strip("-")


def _session_title(messages: list[dict[str, Any]]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            text = str(msg.get("content") or "").strip()
            if text:
                return text[:80] + ("…" if len(text) > 80 else "")
    return "Чат без названия"


def _normalize_ui_messages(raw: list[Any] | None) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if out and out[-1]["role"] == role and out[-1]["content"] == content:
            continue
        out.append({
            "id": str(item.get("id") or ""),
            "role": role,
            "content": content,
            "timestamp": str(item.get("timestamp") or ""),
        })
    return out[-MAX_UI_MESSAGES:]


def _messages_fingerprint(messages: list[dict[str, str]]) -> str:
    import hashlib

    payload = json.dumps(
        [(m.get("role"), m.get("content")) for m in messages],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_ui_messages(project_root: Path) -> list[dict[str, str]]:
    path = _ui_messages_path(project_root)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _normalize_ui_messages(data.get("messages"))
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback: conversation.json (однократная миграция, если UI-файла ещё не было)
    legacy = load_history(project_root)
    return [
        {
            "id": "",
            "role": m["role"],
            "content": m["content"],
            "timestamp": "",
        }
        for m in legacy
    ]


def save_ui_messages(project_root: Path, messages: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = _normalize_ui_messages(messages)
    path = _ui_messages_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": normalized,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"success": True, "count": len(normalized)}


def list_chat_sessions(project_root: Path) -> list[dict[str, Any]]:
    sessions_dir = _sessions_dir(project_root)
    if not sessions_dir.is_dir():
        return []

    items: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    for path in sorted(sessions_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        messages = _normalize_ui_messages(data.get("messages"))
        if not messages:
            continue
        fingerprint = _messages_fingerprint(messages)
        if fingerprint in seen_fingerprints:
            try:
                path.unlink()
            except OSError:
                pass
            continue
        seen_fingerprints.add(fingerprint)
        items.append({
            "id": data.get("id") or path.stem,
            "title": data.get("title") or _session_title(messages),
            "created_at": data.get("created_at") or "",
            "message_count": len(messages),
            "preview": _session_title(messages),
        })
        if len(items) >= MAX_SESSIONS:
            break
    return items


def load_chat_session(project_root: Path, session_id: str) -> dict[str, Any]:
    safe_id = re.sub(r"[^\w.-]", "", session_id or "")
    if not safe_id:
        return {"error": "Некорректный id сессии"}

    path = _sessions_dir(project_root) / f"{safe_id}.json"
    if not path.is_file():
        return {"error": "Сессия не найдена"}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"error": "Не удалось прочитать сессию"}

    messages = _normalize_ui_messages(data.get("messages"))
    return {
        "success": True,
        "session": {
            "id": data.get("id") or safe_id,
            "title": data.get("title") or _session_title(messages),
            "created_at": data.get("created_at") or "",
            "messages": messages,
        },
    }


def archive_current_chat(project_root: Path, messages: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = _normalize_ui_messages(messages)
    if not normalized:
        return {"error": "Нет сообщений для сохранения"}

    fingerprint = _messages_fingerprint(normalized)
    sessions_dir = _sessions_dir(project_root)
    if sessions_dir.is_dir():
        for path in sorted(sessions_dir.glob("*.json"), reverse=True)[:3]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            existing = _normalize_ui_messages(data.get("messages"))
            if existing and _messages_fingerprint(existing) == fingerprint:
                return {
                    "success": True,
                    "duplicate": True,
                    "session": {
                        "id": data.get("id") or path.stem,
                        "title": data.get("title") or _session_title(existing),
                    },
                }

    now = datetime.now(timezone.utc)
    session_id = now.strftime("%Y%m%d-%H%M%S")
    title = _session_title(normalized)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "id": session_id,
        "title": title,
        "created_at": now.isoformat(),
        "messages": normalized,
    }
    path = sessions_dir / f"{session_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Обрезать старые сессии
    existing = sorted(sessions_dir.glob("*.json"), reverse=True)
    for old in existing[MAX_SESSIONS:]:
        try:
            old.unlink()
        except OSError:
            pass

    return {"success": True, "session": {"id": session_id, "title": title}}


def clear_ui_messages(project_root: Path) -> dict[str, Any]:
    path = _ui_messages_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": [],
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return {"error": str(exc)}
    return {"success": True}
