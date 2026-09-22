"""Режим доступа агента в интернет: never / ask / always."""

from __future__ import annotations

import json
import re
from pathlib import Path

from core.core_x_library import COREX_ROOT

CONFIG_FILENAME = "web_access.json"
MODES = ("never", "ask", "always")
DEFAULT_MODE = "ask"

_ASK_RE = re.compile(
    r"интернет|в\s+сети|погугл|гугл|google|duckduckgo|"
    r"найди\s+(как|пример|код)|посмотри\s+(в\s+)?(интернет|сети|онлайн)|"
    r"из\s+интернет|онлайн\s+пример|stackoverflow|документац|"
    r"look\s+up|search\s+(online|the\s+web)|web\s+search",
    re.IGNORECASE,
)


def _config_path() -> Path:
    return Path(COREX_ROOT) / "chat" / CONFIG_FILENAME


def normalize_web_mode(value: str | None) -> str:
    key = (value or "").strip().lower()
    aliases = {
        "off": "never",
        "none": "never",
        "on": "always",
        "on_request": "ask",
        "when_asked": "ask",
        "only": "ask",
    }
    key = aliases.get(key, key)
    return key if key in MODES else DEFAULT_MODE


def get_web_access_mode() -> str:
    path = _config_path()
    if not path.is_file():
        return DEFAULT_MODE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return DEFAULT_MODE
    if isinstance(data, dict):
        return normalize_web_mode(str(data.get("mode") or ""))
    return DEFAULT_MODE


def set_web_access_mode(mode: str) -> dict:
    normalized = normalize_web_mode(mode)
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"mode": normalized}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return web_access_snapshot()


def web_access_snapshot() -> dict:
    mode = get_web_access_mode()
    labels = {
        "never": "Никогда",
        "ask": "Только когда просите",
        "always": "Всегда можно искать",
    }
    return {
        "ok": True,
        "mode": mode,
        "label": labels[mode],
        "modes": [
            {"id": "never", "label": "Никогда"},
            {"id": "ask", "label": "Когда просите"},
            {"id": "always", "label": "Всегда"},
        ],
    }


def user_asked_for_web(user_task: str) -> bool:
    return bool(_ASK_RE.search(user_task or ""))


def should_search_web(user_task: str, *, conversational: bool = False, is_question: bool = False) -> bool:
    if conversational:
        return False
    mode = get_web_access_mode()
    if mode == "never":
        return False
    if mode == "ask":
        return user_asked_for_web(user_task)
    if is_question and not user_asked_for_web(user_task):
        return False
    task = (user_task or "").strip()
    return len(task) >= 8
