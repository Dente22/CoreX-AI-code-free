"""Структурированные события для визуальной нейротрассы (admin panel)."""

from __future__ import annotations

import time
import uuid
from typing import Any


def new_task_id() -> str:
    return uuid.uuid4().hex[:10]


def build_trace_payload(
    *,
    task_id: str,
    phase: str,
    kind: str,
    label: str,
    node: str,
    status: str = "active",
    meta: dict[str, Any] | None = None,
    parent: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": uuid.uuid4().hex[:10],
        "task_id": task_id,
        "ts": time.time(),
        "phase": phase,
        "kind": kind,
        "label": label,
        "status": status,
        "node": node,
        "parent": parent,
        "meta": meta or {},
    }
    if detail:
        payload["detail"] = detail
    return payload
