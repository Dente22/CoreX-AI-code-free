"""Полное завершение процессов CoreX (Ollama, фоновые задачи)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from core.ollama_lifecycle import COREX_OLLAMA_PORT, stop_ollama_serve


async def shutdown_corex_runtime() -> dict[str, Any]:
    from core import ollama_lifecycle
    from core.ollama_model_session import clear_active_ollama_model
    from core.ollama_pull_progress import _RUNNING

    cancelled_pulls = 0
    for task in list(_RUNNING.values()):
        if task is not None and not task.done():
            task.cancel()
            cancelled_pulls += 1

    watchdog = ollama_lifecycle._watchdog_task
    if watchdog is not None and not watchdog.done():
        watchdog.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watchdog
    ollama_lifecycle._watchdog_task = None

    ollama_stopped = await stop_ollama_serve(reason="shutdown")
    clear_active_ollama_model()

    return {
        "success": True,
        "ollama_stopped": ollama_stopped,
        "ollama_port": COREX_OLLAMA_PORT,
        "cancelled_pulls": cancelled_pulls,
    }
