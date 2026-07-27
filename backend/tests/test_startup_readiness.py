"""TDD: /api/system/ready — gate для splash до полной готовности AI."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

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
