"""TDD: спячка Ollama и обнаружение моделей без запуска сервера."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ollama_lifecycle import (
    IDLE_SLEEP_SEC,
    begin_ollama_generation,
    detect_installed_models_from_disk,
    end_ollama_generation,
    merge_ollama_runtime_env,
    note_ollama_activity,
    reset_ollama_lifecycle_state,
    seconds_until_idle_sleep,
    should_sleep_ollama,
)


@pytest.fixture(autouse=True)
def _reset_lifecycle():
    reset_ollama_lifecycle_state()
    yield
    reset_ollama_lifecycle_state()


def test_merge_ollama_runtime_env_sets_low_memory_flags(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.COREX_ROOT", tmp_path)
    env = merge_ollama_runtime_env({"PATH": "/bin"})
    assert env["PATH"] == "/bin"
    assert env["OLLAMA_KEEP_ALIVE"] == "10m"
    assert env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert "11435" in env["OLLAMA_HOST"]


def test_detect_installed_models_from_disk_reads_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.COREX_ROOT", tmp_path)
    manifests = (
        tmp_path
        / "ollama_models"
        / "manifests"
        / "registry.ollama.ai"
        / "library"
        / "llama3.1"
    )
    manifests.mkdir(parents=True)
    (manifests / "8b").write_text("{}", encoding="utf-8")
    (manifests / "latest").write_text("{}", encoding="utf-8")

    models = detect_installed_models_from_disk()
    names = {m["name"] for m in models}
    assert "llama3.1:8b" in names
    assert "llama3.1:latest" in names


def test_should_sleep_ollama_after_idle_without_pull():
    note_ollama_activity()
    with patch("core.ollama_lifecycle.is_any_pull_active", return_value=False):
        assert should_sleep_ollama(now=time.monotonic() + IDLE_SLEEP_SEC + 1) is True


def test_should_not_sleep_ollama_while_generation_active():
    note_ollama_activity()
    begin_ollama_generation()
    with patch("core.ollama_lifecycle.is_any_pull_active", return_value=False):
        assert should_sleep_ollama(now=time.monotonic() + IDLE_SLEEP_SEC + 60) is False
    end_ollama_generation()


def test_should_not_sleep_ollama_while_pull_active():
    note_ollama_activity()
    with patch("core.ollama_lifecycle.is_any_pull_active", return_value=True):
        assert should_sleep_ollama(now=time.monotonic() + IDLE_SLEEP_SEC + 60) is False


def test_seconds_until_idle_sleep_counts_down():
    now = time.monotonic()
    note_ollama_activity()
    remaining = seconds_until_idle_sleep(now=now + 10)
    assert IDLE_SLEEP_SEC - 11 <= remaining <= IDLE_SLEEP_SEC - 9


@pytest.mark.asyncio
async def test_list_installed_models_does_not_start_ollama_when_sleeping(monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", MagicMock())
    monkeypatch.setattr(
        "core.ollama_model_service._is_server_running",
        AsyncMock(return_value=False),
    )
    ensure = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_model_service.ensure_corex_ollama_running", ensure)
    monkeypatch.setattr(
        "core.ollama_model_service.detect_installed_models_from_disk",
        lambda: [{"name": "phi3:mini"}],
    )

    from core.ollama_model_service import list_installed_models

    result = await list_installed_models(start_if_down=False)
    ensure.assert_not_called()
    assert result["models"] == [{"name": "phi3:mini"}]
    assert result.get("ollama_state") == "sleeping"


@pytest.mark.asyncio
async def test_stop_ollama_serve_terminates_tracked_process(monkeypatch):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 4242

    from core import ollama_lifecycle

    ollama_lifecycle._serve_process = proc
    ollama_lifecycle._we_started_process = True

    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(return_value=False),
    )

    from core.ollama_lifecycle import stop_ollama_serve

    stopped = await stop_ollama_serve()
    assert stopped is True
    proc.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_stop_ollama_idle_does_not_kill_unmanaged_listener(monkeypatch):
    from core import ollama_lifecycle
    from core.ollama_lifecycle import stop_ollama_serve

    ollama_lifecycle._serve_process = None
    ollama_lifecycle._we_started_process = False

    monkeypatch.setattr("core.ollama_lifecycle._is_server_running", AsyncMock(return_value=True))
    monkeypatch.setattr("core.ollama_lifecycle._find_listener_pid", lambda _port: 9999)
    terminate = MagicMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle._terminate_pid", terminate)
    monkeypatch.setattr("core.ollama_lifecycle.cleanup_zombie_llama_workers", AsyncMock(return_value=False))

    stopped = await stop_ollama_serve(reason="idle")

    assert stopped is False
    terminate.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_ollama_serve_starts_watchdog(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(side_effect=[False, True]),
    )
    popen = MagicMock()
    popen.poll.return_value = None
    monkeypatch.setattr("core.ollama_lifecycle.subprocess.Popen", MagicMock(return_value=popen))

    import core.ollama_lifecycle as lifecycle

    ok = await lifecycle.ensure_ollama_serve_running()
    assert ok is True
    assert lifecycle._watchdog_task is not None
