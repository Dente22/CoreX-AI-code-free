"""Integration tests for AI provider HTTP API."""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from core.ai_online_provider_service import AiOnlineProviderService
from core.ai_provider_service import AiProviderService
from core.ai_runtime_service import AiRuntimeService
from core.file_service import FileService
from core.mcp_manager import MCPManager
from core.ollama_client import OllamaClient
from core.online_api_client import OnlineApiClient
from core.orchestrator import CoreXOrchestrator
from core.ws_server import WebSocketServer


class _FakeGui:
    project_dir = "."

    def print_log(self, source: str, text: str) -> None:
        pass


@pytest.fixture
async def api_client(tmp_path):
    provider_service = AiProviderService(
        config_path=tmp_path / "chat" / "ai_provider.json",
        project_root=tmp_path,
    )
    online_service = AiOnlineProviderService(
        store_path=tmp_path / "chat" / "ai_online_providers.json",
        project_root=tmp_path,
    )
    runtime_service = AiRuntimeService(
        config_path=tmp_path / "chat" / "ai_runtime.json",
        project_root=tmp_path,
        local_service=provider_service,
        online_service=online_service,
    )
    ollama = OllamaClient()
    online = OnlineApiClient()
    runtime_service.apply_active_client(ollama, online)
    orchestrator = CoreXOrchestrator(
        ollama,
        MCPManager(),
        _FakeGui(),
        FileService(MCPManager(), str(tmp_path), use_mcp=False),
        provider_service,
        runtime_service,
        online,
    )
    ws_server = WebSocketServer(orchestrator, orchestrator.file_service)
    app = ws_server.create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


@pytest.mark.integration
class TestAiProviderApi:
    async def test_list_providers(self, api_client):
        response = await api_client.get("/api/ai/providers")
        assert response.status == 200
        data = await response.json()
        assert data["success"] is True
        assert data["selected_id"] == "ollama-qwen"
        assert len(data["providers"]) == 5

    async def test_set_provider(self, api_client):
        response = await api_client.post(
            "/api/ai/provider",
            json={"provider_id": "ollama-lite"},
        )
        assert response.status == 200
        data = await response.json()
        assert data["success"] is True
        assert data["selected_id"] == "ollama-lite"

        runtime_response = await api_client.get("/api/ai/runtime")
        runtime = await runtime_response.json()
        assert runtime["local"]["selected_id"] == "ollama-lite"

    async def test_set_invalid_provider(self, api_client):
        response = await api_client.post(
            "/api/ai/provider",
            json={"provider_id": "unknown"},
        )
        assert response.status == 400
        data = await response.json()
        assert data["success"] is False

    async def test_runtime_and_online_provider(self, api_client):
        created = await api_client.post(
            "/api/ai/online/providers",
            json={
                "name": "Gemini API",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "api_key": "secret",
                "model_name": "gemini-1.5-flash",
                "api_type": "gemini",
            },
        )
        assert created.status == 200
        payload = await created.json()
        provider_id = payload["provider"]["id"]
        assert payload["provider"]["api_type"] == "gemini"

        mode = await api_client.post("/api/ai/mode", json={"mode": "online"})
        assert mode.status == 200

        selected = await api_client.post(
            "/api/ai/online/provider",
            json={"provider_id": provider_id},
        )
        assert selected.status == 200

        runtime = await api_client.get("/api/ai/runtime")
        data = await runtime.json()
        assert data["mode"] == "online"
        assert data["online"]["selected_id"] == provider_id

    async def test_set_online_mode_without_provider_keeps_online(self, api_client):
        response = await api_client.post("/api/ai/mode", json={"mode": "online"})
        assert response.status == 200
        payload = await response.json()
        assert payload["success"] is True
        assert payload["mode"] == "online"

        runtime = await api_client.get("/api/ai/runtime")
        data = await runtime.json()
        assert data["mode"] == "online"
