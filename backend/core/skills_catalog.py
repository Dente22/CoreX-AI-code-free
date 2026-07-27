"""Справочник скиллов из everything-claude-code и claude-code-best-practice."""

from __future__ import annotations

import json
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "skills_catalog.json"


def load_catalog() -> list[dict]:
    if not _CATALOG_PATH.is_file():
        return []
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        return data.get("skills", []) if isinstance(data, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def list_by_category() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for skill in load_catalog():
        category = skill.get("category", "Прочее")
        grouped.setdefault(category, []).append(skill)
    return grouped
