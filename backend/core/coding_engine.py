"""Движок правок кода: Aider или встроенный JSON-агент CoreX."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

CodingEngineId = Literal["aider", "corex"]
DEFAULT_CODING_ENGINE: CodingEngineId = "aider"
CONFIG_FILENAME = "coding_engine.json"

CODING_ENGINES: tuple[dict[str, str], ...] = (
    {
        "id": "aider",
        "name": "Aider",
        "description": "Правки кода без JSON tool-calls",
    },
    {
        "id": "corex",
        "name": "CoreX агент",
        "description": "Встроенный цикл с инструментами",
    },
)

_ALLOWED = {item["id"] for item in CODING_ENGINES}


def validate_coding_engine(engine_id: str | None) -> CodingEngineId:
    value = (engine_id or "").strip().lower()
    if value in _ALLOWED:
        return value  # type: ignore[return-value]
    return DEFAULT_CODING_ENGINE


def list_engine_dicts() -> list[dict[str, str]]:
    return [dict(item) for item in CODING_ENGINES]


def _config_path(app_root: Path) -> Path:
    return (app_root.resolve() / "chat" / CONFIG_FILENAME)


def get_coding_engine(app_root: Path) -> CodingEngineId:
    path = _config_path(app_root)
    if not path.is_file():
        return DEFAULT_CODING_ENGINE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CODING_ENGINE
    return validate_coding_engine(str(data.get("engine") or ""))


def set_coding_engine(app_root: Path, engine_id: str) -> CodingEngineId:
    engine = validate_coding_engine(engine_id)
    path = _config_path(app_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"engine": engine}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return engine


def coding_engine_snapshot(app_root: Path) -> dict[str, Any]:
    engine = get_coding_engine(app_root)
    return {
        "engine": engine,
        "engines": list_engine_dicts(),
        "default": DEFAULT_CODING_ENGINE,
    }
