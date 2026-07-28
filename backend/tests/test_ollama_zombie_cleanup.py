"""TDD: зомби llama-server после падения Ollama CoreX."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.ollama_lifecycle import (
    cleanup_zombie_llama_workers,
    collect_descendant_pids,
    reset_ollama_lifecycle_state,
)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_ollama_lifecycle_state()
    yield
    reset_ollama_lifecycle_state()


def test_collect_descendant_pids_finds_nested_children():
    rows = [
        {"name": "ollama.exe", "parent_pid": 100, "pid": 200},
        {"name": "llama-server.exe", "parent_pid": 200, "pid": 300},
    ]
    descendants = collect_descendant_pids(200, rows)
    assert descendants == {300}


@pytest.mark.asyncio
async def test_cleanup_zombie_llama_workers_skips_when_corex_server_running(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(return_value=True),
    )
    terminate = MagicMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle._terminate_pid", terminate)

    killed = await cleanup_zombie_llama_workers()

    assert killed is False
    terminate.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_zombie_llama_workers_kills_orphans_not_under_desktop_ollama(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr("core.ollama_lifecycle._find_listener_pid", lambda port: 9001 if port == 11434 else None)
    monkeypatch.setattr(
        "core.ollama_lifecycle._list_process_rows",
        lambda: [
            {"name": "ollama.exe", "parent_pid": 1, "pid": 9001},
            {"name": "llama-server.exe", "parent_pid": 9001, "pid": 9002},
            {"name": "llama-server.exe", "parent_pid": 5000, "pid": 7777},
        ],
    )
    terminate = MagicMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle._terminate_pid", terminate)

    killed = await cleanup_zombie_llama_workers()

    assert killed is True
    terminate.assert_called_once_with(7777)


@pytest.mark.asyncio
async def test_ensure_ollama_cleans_zombies_before_start(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(side_effect=[False, False, True]),
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle.cleanup_zombie_llama_workers", cleanup)
    popen = MagicMock()
    popen.poll.return_value = None
    monkeypatch.setattr("core.ollama_lifecycle.subprocess.Popen", MagicMock(return_value=popen))

    from core.ollama_lifecycle import ensure_ollama_serve_running

    ok = await ensure_ollama_serve_running()

    assert ok is True
    cleanup.assert_awaited_once()
