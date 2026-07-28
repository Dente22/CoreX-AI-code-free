"""TDD: health endpoint отдаёт версию и флаг маршрутизации."""

import json
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from core.app_version import COREX_BACKEND_VERSION
from core.ws_server import WebSocketServer


@pytest.fixture
async def health_client():
    orchestrator = MagicMock()
    orchestrator.register_websocket_server = MagicMock()
    ws_server = WebSocketServer(orchestrator=orchestrator, file_service=None)
    app = web.Application()
    app.router.add_get("/health", ws_server.handle_health)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
async def test_health_reports_task_routing(health_client: TestClient):
    response = await health_client.get("/health")
    assert response.status == 200
    payload = json.loads(await response.text())
    assert payload["ok"] is True
    assert payload["task_routing"] is True
    assert payload["backend_version"] == COREX_BACKEND_VERSION
    assert payload["library_agents"] >= 5
    assert payload["library_teams"] >= 2
