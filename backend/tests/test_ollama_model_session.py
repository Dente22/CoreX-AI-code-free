"""TDD: активация и переключение моделей Ollama."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.ollama_client import OllamaClient
from core.ollama_model_session import (
    activate_ollama_model,
    clear_active_ollama_model,
    get_active_ollama_model,
    reset_ollama_model_session,
)


@pytest.fixture(autouse=True)
def _reset_session():
    reset_ollama_model_session()
    yield
    reset_ollama_model_session()


@pytest.mark.asyncio
async def test_activate_ollama_model_loads_when_empty(monkeypatch):
    warmup = AsyncMock(return_value={"success": True})
    reachable = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_model_session.warmup_ollama_model", warmup)
    monkeypatch.setattr("core.ollama_model_session._is_ollama_reachable", reachable)

    result = await activate_ollama_model("qwen2.5-coder:7b", "http://127.0.0.1:11435", preload=True)
    assert result["success"] is True
    warmup.assert_awaited_once_with("qwen2.5-coder:7b", "http://127.0.0.1:11435")
    assert get_active_ollama_model() == "qwen2.5-coder:7b"


@pytest.mark.asyncio
async def test_activate_ollama_model_switches_and_unloads_previous(monkeypatch):
    unload = AsyncMock(return_value=True)
    warmup = AsyncMock(return_value={"success": True})
    reachable = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_model_session.unload_ollama_model", unload)
    monkeypatch.setattr("core.ollama_model_session.warmup_ollama_model", warmup)
    monkeypatch.setattr("core.ollama_model_session._is_ollama_reachable", reachable)

    await activate_ollama_model("phi3:mini", "http://127.0.0.1:11435", preload=True)
    await activate_ollama_model("llama3.1:8b", "http://127.0.0.1:11435", preload=True)

    unload.assert_awaited_once_with("phi3:mini", "http://127.0.0.1:11435")
    assert warmup.await_count == 2
    assert get_active_ollama_model() == "llama3.1:8b"


@pytest.mark.asyncio
async def test_activate_ollama_model_skips_reload_for_same_model(monkeypatch):
    warmup = AsyncMock(return_value={"success": True})
    reachable = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_model_session.warmup_ollama_model", warmup)
    monkeypatch.setattr("core.ollama_model_session._is_ollama_reachable", reachable)

    await activate_ollama_model("phi3:mini", "http://127.0.0.1:11435", preload=True)
    result = await activate_ollama_model("phi3:mini", "http://127.0.0.1:11435", preload=True)

    assert result.get("already_loaded") is True
    warmup.assert_awaited_once()


@pytest.mark.asyncio
async def test_activate_without_preload_does_not_warmup(monkeypatch):
    warmup = AsyncMock(return_value={"success": True})
    reachable = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_model_session.warmup_ollama_model", warmup)
    monkeypatch.setattr("core.ollama_model_session._is_ollama_reachable", reachable)

    result = await activate_ollama_model("phi3:mini", "http://127.0.0.1:11435", preload=False)
    assert result["success"] is True
    warmup.assert_not_called()


@pytest.mark.asyncio
async def test_ollama_client_prepare_for_generation_activates_model(monkeypatch):
    ensure = AsyncMock(return_value=True)
    verify = AsyncMock(return_value={"success": True, "installed": True})
    activate = AsyncMock(return_value={"success": True})
    monkeypatch.setattr("core.ollama_client.ensure_ollama_serve_running", ensure)
    monkeypatch.setattr("core.ollama_client.verify_model_installed", verify)
    monkeypatch.setattr("core.ollama_client.activate_ollama_model", activate)

    client = OllamaClient()
    client.model_name = "qwen2.5-coder:7b"
    ok = await client.prepare_for_generation()

    assert ok is True
    verify.assert_awaited_once_with("qwen2.5-coder:7b", client.root_url)
    activate.assert_awaited_once_with("qwen2.5-coder:7b", client.root_url, preload=False)
