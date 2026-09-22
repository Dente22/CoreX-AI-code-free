"""Короткие уроки по задачам: общее хранилище машины, без исходников."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_MAX_LESSONS = 80
_MAX_TASK = 160
_MAX_ERROR = 120
_STOP = {
    "создай",
    "сделай",
    "напиши",
    "добавь",
    "исправь",
    "мне",
    "что",
    "это",
    "для",
    "или",
    "как",
    "the",
    "and",
    "with",
}


def resolve_lessons_path() -> Path:
    override = (os.environ.get("COREX_LESSONS_PATH") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    override_dir = (os.environ.get("COREX_LESSONS_DIR") or "").strip()
    if override_dir:
        return (Path(override_dir).expanduser().resolve() / "lessons.json")
    secrets_override = (os.environ.get("COREX_SECRETS_DIR") or "").strip()
    if secrets_override:
        return (Path(secrets_override).expanduser().resolve().parent / "lessons.json")
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
        base = Path(xdg).expanduser() if xdg else (Path.home() / ".local" / "share")
    return (base / "CoreX" / "lessons.json").resolve()


def _clip(text: str, limit: int) -> str:
    blob = re.sub(r"\s+", " ", (text or "").strip())
    if len(blob) <= limit:
        return blob
    return blob[: limit - 1].rstrip() + "…"


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9_]{3,}", (text or "").lower())
    return {word for word in words if word not in _STOP}


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("lessons") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _save(path: Path, lessons: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"lessons": lessons[-_MAX_LESSONS:]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def remember_task_outcome(
    *,
    task: str,
    ok: bool,
    how: str,
    files: list[str] | None = None,
    error: str = "",
    path: Path | None = None,
) -> dict[str, Any] | None:
    """Записать исход кодовой задачи. Молча. Без исходников."""
    task_text = _clip(task, _MAX_TASK)
    if not task_text:
        return None
    lowered = task_text.lower()
    if re.fullmatch(r"(привет|здравствуй|спасибо|пока|hello|hi|thanks)[!?. ]*", lowered):
        return None
    names = [
        item.replace("\\", "/")
        for item in (files or [])
        if item and "project_memory" not in item.replace("\\", "/")
        and not str(item).replace("\\", "/").startswith("chat/")
    ][:4]
    lesson = {
        "task": task_text,
        "ok": bool(ok),
        "how": _clip(how or ("ok" if ok else "fail"), 40),
        "files": names,
        "error": _clip(re.sub(r"[`]+", " ", error), _MAX_ERROR),
    }
    store = path or resolve_lessons_path()
    lessons = _load(store)
    if lessons:
        last = lessons[-1]
        if (
            last.get("task") == lesson["task"]
            and last.get("ok") == lesson["ok"]
            and last.get("how") == lesson["how"]
            and last.get("files") == lesson["files"]
        ):
            return last
    lessons.append(lesson)
    try:
        _save(store, lessons)
    except OSError:
        return None
    return lesson


def similar_lessons(
    task: str,
    *,
    limit: int = 2,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    wanted = _tokens(task)
    if not wanted:
        return []
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(_load(path or resolve_lessons_path())):
        overlap = len(wanted & _tokens(str(item.get("task") or "")))
        if overlap < 1:
            continue
        bonus = 2 if item.get("ok") else 0
        scored.append((overlap + bonus, index, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _, _, item in scored[: max(1, min(3, limit))]]


def format_lessons_for_prompt(task: str, *, path: Path | None = None) -> str:
    hits = similar_lessons(task, limit=2, path=path)
    if not hits:
        return ""
    lines = ["Lessons from past tasks (follow + , avoid -):"]
    for item in hits:
        mark = "+" if item.get("ok") else "-"
        how = item.get("how") or ""
        files = ", ".join(item.get("files") or [])
        err = re.sub(r"[`]+", " ", str(item.get("error") or ""))
        bit = f"{mark} {item.get('task')}: {how}"
        if files:
            bit += f" -> {files}"
        if err and not item.get("ok"):
            bit += f" [{err}]"
        lines.append(_clip(bit, 180))
    return "\n".join(lines) + "\n"
