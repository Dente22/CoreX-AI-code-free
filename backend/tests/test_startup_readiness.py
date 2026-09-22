"""TDD: /api/system/ready — gate для splash до полной готовности AI."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from core.startup_readiness import clear_startup_readiness_cache, evaluate_startup_readiness
from core.ws_server import WebSocketServer


@pytest.fixture
async def ready_client():
    orchestrator = MagicMock()
    orchestrator.register_websocket_server = MagicMock()
    ws_server = WebSocketServer(orchestrator=orchestrator, file_service=None)
    app = web.Application()
    app.router.add_get("/api/system/ready", ws_server.handle_system_ready)
    async with TestClient(TestServer(app)) as client:
        yield client, orchestrator


@pytest.mark.asyncio
async def test_system_ready_reports_not_ready_while_model_loading(ready_client, monkeypatch):
    client, orchestrator = ready_client
    monkeypatch.setattr(
        "core.startup_readiness.evaluate_startup_readiness",
        AsyncMock(
            return_value={
                "ready": False,
                "phase": "model",
                "message": "Загрузка модели…",
                "mode": "local",
                "model": "qwen2.5-coder:7b",
            }
        ),
    )

    response = await client.get("/api/system/ready")
    assert response.status == 200
    payload = json.loads(await response.text())
    assert payload["ready"] is False
    assert payload["phase"] == "model"


@pytest.mark.asyncio
async def test_system_ready_reports_ready_when_ai_available(ready_client, monkeypatch):
    client, orchestrator = ready_client
    monkeypatch.setattr(
        "core.startup_readiness.evaluate_startup_readiness",
        AsyncMock(
            return_value={
                "ready": True,
                "phase": "ready",
                "message": "Модель qwen2.5-coder:7b готова",
                "mode": "local",
                "model": "qwen2.5-coder:7b",
            }
        ),
    )

    response = await client.get("/api/system/ready")
    payload = json.loads(await response.text())
    assert payload["ready"] is True
    assert payload["model"] == "qwen2.5-coder:7b"


def _local_orchestrator() -> MagicMock:
    orchestrator = MagicMock()
    orchestrator.get_ai_runtime_snapshot.return_value = {"mode": "local"}
    orchestrator.ai_runtime_service = MagicMock()
    orchestrator.ollama = MagicMock()
    orchestrator.ollama.last_error = ""
    orchestrator.online = MagicMock()
    return orchestrator


def _local_active(orchestrator: MagicMock) -> MagicMock:
    active = MagicMock()
    active.model_name = "phi3:mini"
    active.provider_id = "ollama-lite"
    active.client = orchestrator.ollama
    active.client.root_url = "http://127.0.0.1:11435"
    return active


@pytest.mark.asyncio
async def test_local_mode_without_running_ollama_is_skippable(monkeypatch):
    orchestrator = _local_orchestrator()
    monkeypatch.setattr(
        "core.startup_readiness.resolve_active_llm",
        lambda *_args, **_kwargs: _local_active(orchestrator),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle.attach_if_already_running",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr("core.ollama_lifecycle.should_skip_desktop_ollama", lambda: False)
    ensure = AsyncMock(return_value=False)
    monkeypatch.setattr("core.ollama_lifecycle.ensure_ollama_serve_running", ensure)

    clear_startup_readiness_cache()
    payload = await evaluate_startup_readiness(orchestrator)

    assert payload["ready"] is False
    assert payload["phase"] == "ollama_server"
    assert payload["skippable"] is True
    assert "Ollama" in payload["message"]
    ensure.assert_not_called()


@pytest.mark.asyncio
async def test_local_mode_with_running_ollama_is_ready(monkeypatch):
    orchestrator = _local_orchestrator()
    monkeypatch.setattr(
        "core.startup_readiness.resolve_active_llm",
        lambda *_args, **_kwargs: _local_active(orchestrator),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle.attach_if_already_running",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle.resolve_ollama_base_url",
        lambda: "http://127.0.0.1:11434",
    )
    installed = AsyncMock(return_value=True)
    monkeypatch.setattr("core.startup_readiness._model_is_installed", installed)

    clear_startup_readiness_cache()
    payload = await evaluate_startup_readiness(orchestrator)

    assert payload["ready"] is True
    assert payload["phase"] == "ready"
    assert payload.get("skippable") is None
    installed.assert_awaited()
    assert installed.await_args.args[1] == "http://127.0.0.1:11434"
    assert orchestrator.ollama.root_url == "http://127.0.0.1:11434"
    assert orchestrator.ollama.chat_url == "http://127.0.0.1:11434/api/chat"


@pytest.mark.asyncio
async def test_hybrid_splash_starts_managed_ollama(monkeypatch):
    orchestrator = _local_orchestrator()
    monkeypatch.setattr(
        "core.startup_readiness.resolve_active_llm",
        lambda *_args, **_kwargs: _local_active(orchestrator),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle.attach_if_already_running",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr("core.ollama_lifecycle.should_skip_desktop_ollama", lambda: True)
    monkeypatch.setattr(
        "core.ollama_lifecycle.ensure_ollama_serve_running",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle.resolve_ollama_base_url",
        lambda: "http://127.0.0.1:11435",
    )
    monkeypatch.setattr(
        "core.startup_readiness._model_is_installed",
        AsyncMock(return_value=True),
    )

    clear_startup_readiness_cache()
    payload = await evaluate_startup_readiness(orchestrator)

    assert payload["ready"] is True
    assert payload["phase"] == "ready"
    assert orchestrator.ollama.root_url == "http://127.0.0.1:11435"
