"""TDD: завершение CoreX и Ollama при закрытии приложения."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.shutdown_service import shutdown_corex_runtime


@pytest.mark.asyncio
async def test_shutdown_corex_runtime_stops_ollama_and_cancels_pulls(monkeypatch):
    task = MagicMock()
    task.done.return_value = False
    monkeypatch.setattr("core.ollama_pull_progress._RUNNING", {"job": task})

    stop = AsyncMock(return_value=True)
    monkeypatch.setattr("core.shutdown_service.stop_ollama_serve", stop)
    clear = MagicMock()
    monkeypatch.setattr("core.ollama_model_session.clear_active_ollama_model", clear)

    monkeypatch.setattr("core.ollama_lifecycle._watchdog_task", None)

    result = await shutdown_corex_runtime()

    assert result["success"] is True
    assert result["ollama_stopped"] is True
    task.cancel.assert_called_once()
    stop.assert_awaited_once_with(reason="shutdown")
    clear.assert_called_once()


@pytest.mark.asyncio
async def test_stop_ollama_serve_shutdown_kills_port_listener(monkeypatch):
    from core.ollama_lifecycle import stop_ollama_serve

    monkeypatch.setattr("core.ollama_lifecycle._serve_process", None)
    monkeypatch.setattr("core.ollama_lifecycle._we_started_process", False)
    monkeypatch.setattr("core.ollama_lifecycle._is_server_running", AsyncMock(return_value=True))
    monkeypatch.setattr("core.ollama_lifecycle._find_listener_pid", lambda _port: 4242)
    terminate = MagicMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle._terminate_pid", terminate)

    stopped = await stop_ollama_serve(reason="shutdown")
    assert stopped is True
    terminate.assert_called_once_with(4242)
