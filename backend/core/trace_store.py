"""Персистентное хранение нейротрассы и журнала ошибок (chat/trace/)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

TRACE_DIR = "trace"
ERRORS_FILE = "errors.jsonl"
TASKS_DIR = "tasks"
WS_BODY_LIMIT = 6_000
STORE_BODY_LIMIT = 80_000


def _trace_root(project_root: Path) -> Path:
    return project_root / "chat" / TRACE_DIR


def _ensure_dirs(project_root: Path) -> Path:
    root = _trace_root(project_root)
    (root / TASKS_DIR).mkdir(parents=True, exist_ok=True)
    return root


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def trim_detail_for_ws(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detail:
        return None
    trimmed = dict(detail)
    body = trimmed.get("body")
    if isinstance(body, str) and len(body) > WS_BODY_LIMIT:
        trimmed["body"] = body[:WS_BODY_LIMIT] + "\n… [обрезано для WS]"
        trimmed["truncated"] = True
    for key in ("request", "response", "arguments", "result"):
        val = trimmed.get(key)
        if isinstance(val, (dict, list)):
            text = json.dumps(val, ensure_ascii=False)
            if len(text) > WS_BODY_LIMIT:
                trimmed[key] = {"_preview": text[:WS_BODY_LIMIT] + "…", "_truncated": True}
    return trimmed


def _clip_body(text: str, limit: int = STORE_BODY_LIMIT) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n… [обрезано при сохранении]", True


def make_detail(
    kind: str,
    *,
    title: str = "",
    body: str = "",
    language: str = "text",
    path: str = "",
    request: dict | None = None,
    response: dict | None = None,
    arguments: dict | None = None,
    result: dict | None = None,
) -> dict[str, Any]:
    clipped, truncated = _clip_body(body) if body else ("", False)
    detail: dict[str, Any] = {"kind": kind}
    if title:
        detail["title"] = title
    if clipped:
        detail["body"] = clipped
        detail["language"] = language
    if path:
        detail["path"] = path
    if truncated:
        detail["truncated"] = True
    if request is not None:
        detail["request"] = request
    if response is not None:
        detail["response"] = response
    if arguments is not None:
        detail["arguments"] = arguments
    if result is not None:
        detail["result"] = result
    return detail


def append_event(project_root: Path, event: dict[str, Any]) -> None:
    if not project_root.is_dir():
        return
    task_id = str(event.get("task_id") or "unknown")
    root = _ensure_dirs(project_root)
    path = root / TASKS_DIR / f"{task_id}.jsonl"
    _append_jsonl(path, event)


def append_error(
    project_root: Path,
    *,
    task_id: str,
    event_id: str,
    label: str,
    message: str,
    kind: str,
    node: str,
    ts: float | None = None,
) -> dict[str, Any]:
    record = {
        "id": uuid.uuid4().hex[:10],
        "task_id": task_id,
        "event_id": event_id,
        "ts": ts or 0,
        "label": label,
        "message": message,
        "kind": kind,
        "node": node,
    }
    if not project_root.is_dir():
        return record
    root = _ensure_dirs(project_root)
    _append_jsonl(root / ERRORS_FILE, record)
    return record


def list_errors(project_root: Path, *, task_id: str | None = None, limit: int = 200) -> list[dict]:
    path = _trace_root(project_root) / ERRORS_FILE
    if not path.is_file():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if task_id and row.get("task_id") != task_id:
                continue
            rows.append(row)
    except OSError:
        return []
    return rows[-limit:]


def load_task_events(project_root: Path, task_id: str, *, limit: int = 500) -> list[dict]:
    path = _trace_root(project_root) / TASKS_DIR / f"{task_id}.jsonl"
    if not path.is_file():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-limit:]


def load_event(project_root: Path, task_id: str, event_id: str) -> dict | None:
    for row in load_task_events(project_root, task_id, limit=500):
        if row.get("id") == event_id:
            return row
    return None
