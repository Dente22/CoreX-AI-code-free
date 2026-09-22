"""Выбранный язык программирования проекта (чат + пайплайн агента)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE_ID = "auto"
CONFIG_FILENAME = "coding_language.json"

CODING_LANGUAGES: tuple[dict[str, str], ...] = (
    {"id": "auto", "name": "Авто", "description": "По сообщению"},
    {"id": "python", "name": "Python", "description": "файлы .py"},
    {"id": "javascript", "name": "JavaScript", "description": "файлы .js"},
    {"id": "html", "name": "HTML", "description": "страницы / сайт"},
    {"id": "css", "name": "CSS", "description": "стили"},
    {"id": "typescript", "name": "TypeScript", "description": "файлы .ts"},
    {"id": "react", "name": "React", "description": "JSX / TSX"},
)

_ALLOWED = {item["id"] for item in CODING_LANGUAGES}
WEB_LANGUAGE_IDS = frozenset({"html", "css"})
CODE_LANGUAGE_IDS = frozenset({"python", "javascript", "typescript", "react"})

_INFER_ORDER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python", re.compile(r"python|\.py\b|питон|змейк|pygame|django|flask", re.I)),
    ("react", re.compile(r"\breact\b|\.jsx\b|\.tsx\b|next\.js", re.I)),
    ("typescript", re.compile(r"typescript|\.ts\b", re.I)),
    ("javascript", re.compile(r"javascript|\.js\b|node\.js|\bна js\b", re.I)),
    ("html", re.compile(r"html|сайт|landing|лендинг|страниц|веб|website", re.I)),
    ("css", re.compile(r"\bcss\b|стили", re.I)),
)

_PROMPT_BY_ID = {
    "python": (
        "Пиши на Python (.py, например main.py). "
        "Не делай HTML/сайт и не читай design-system/, если явно не просили веб."
    ),
    "javascript": (
        "Пиши на JavaScript (.js). Не делай HTML-сайт и не читай design-system/, "
        "если явно не просили веб-страницу."
    ),
    "typescript": (
        "Пиши на TypeScript (.ts). Не делай HTML-сайт и не читай design-system/, "
        "если явно не просили веб-страницу."
    ),
    "react": (
        "Пиши React (JSX/TSX, например App.tsx). Не уходи в design-system/ HTML-спеку, "
        "если не просили статичный сайт."
    ),
    "html": "Делай HTML-страницу (index.html). Стили — style.css, скрипты — script.js.",
    "css": "Фокус на CSS (style.css). HTML трогай только если без него нельзя.",
}


def validate_language_id(language_id: str | None) -> str:
    value = (language_id or "").strip().lower()
    if value in _ALLOWED:
        return value
    return DEFAULT_LANGUAGE_ID


def list_language_dicts() -> list[dict[str, str]]:
    return [dict(item) for item in CODING_LANGUAGES]


def language_forces_web(language_id: str) -> bool:
    return validate_language_id(language_id) in WEB_LANGUAGE_IDS


def language_forces_code(language_id: str) -> bool:
    return validate_language_id(language_id) in CODE_LANGUAGE_IDS


def infer_coding_language(*texts: str) -> str:
    blob = " ".join(t for t in texts if t)
    if not blob.strip():
        return DEFAULT_LANGUAGE_ID
    for language_id, pattern in _INFER_ORDER:
        if pattern.search(blob):
            return language_id
    return DEFAULT_LANGUAGE_ID


def resolve_effective_language(stored: str | None, *texts: str) -> str:
    pinned = validate_language_id(stored)
    if pinned != DEFAULT_LANGUAGE_ID:
        return pinned
    inferred = infer_coding_language(*texts)
    return inferred if inferred != DEFAULT_LANGUAGE_ID else DEFAULT_LANGUAGE_ID


def language_prompt_ru(language_id: str) -> str:
    effective = validate_language_id(language_id)
    extra = _PROMPT_BY_ID.get(effective)
    if not extra:
        return ""
    label = next((item["name"] for item in CODING_LANGUAGES if item["id"] == effective), effective)
    return f"=== ЯЗЫК: {label} ===\n{extra}\n"


def _config_path(project_root: Path) -> Path:
    return Path(project_root) / "chat" / CONFIG_FILENAME


def get_coding_language(project_root: Path | None) -> str:
    if project_root is None:
        return DEFAULT_LANGUAGE_ID
    path = _config_path(project_root)
    if not path.is_file():
        return DEFAULT_LANGUAGE_ID
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_LANGUAGE_ID
    if not isinstance(data, dict):
        return DEFAULT_LANGUAGE_ID
    return validate_language_id(str(data.get("language") or ""))


def set_coding_language(project_root: Path, language_id: str) -> dict[str, Any]:
    normalized = validate_language_id(language_id)
    path = _config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"language": normalized}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"success": True, "language": normalized, "languages": list_language_dicts()}


def coding_language_snapshot(project_root: Path | None) -> dict[str, Any]:
    language = get_coding_language(project_root)
    return {
        "success": True,
        "language": language,
        "languages": list_language_dicts(),
    }
