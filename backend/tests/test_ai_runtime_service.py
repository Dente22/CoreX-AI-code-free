"""Unit tests for local/online AI runtime mode."""

import pytest

from core.ai_online_provider_service import AiOnlineProviderService
from core.ai_provider_service import AiProviderService
from core.ai_runtime_service import AiRuntimeService


@pytest.fixture
def runtime_paths(tmp_path):
    return {
        "runtime": tmp_path / "chat" / "ai_runtime.json",
        "local": tmp_path / "chat" / "ai_provider.json",
        "online": tmp_path / "chat" / "ai_online_providers.json",
    }


@pytest.fixture
def runtime_service(runtime_paths):
    return AiRuntimeService(
        config_path=runtime_paths["runtime"],
        local_service=AiProviderService(config_path=runtime_paths["local"]),
        online_service=AiOnlineProviderService(store_path=runtime_paths["online"]),
    )


@pytest.mark.unit
class TestAiRuntimeService:
    def test_default_mode_is_local(self, runtime_service):
        assert runtime_service.get_mode() == "local"

    def test_set_mode_online(self, runtime_service):
        result = runtime_service.set_mode("online")
        assert result["success"] is True
        assert runtime_service.get_mode() == "online"

    def test_snapshot_includes_both_sections(self, runtime_service):
        snapshot = runtime_service.get_snapshot()
        assert snapshot["mode"] == "local"
        assert len(snapshot["local"]["providers"]) == 5
        assert snapshot["online"]["providers"] == []

    def test_select_local_provider(self, runtime_service):
        result = runtime_service.select_local("ollama-lite")
        assert result["success"] is True
        assert runtime_service.get_snapshot()["local"]["selected_id"] == "ollama-lite"

    def test_select_online_provider(self, runtime_service, runtime_paths):
        online = AiOnlineProviderService(store_path=runtime_paths["online"])
        created = online.create_provider(
            name="API",
            base_url="https://api.example.com/v1",
            api_key="secret",
            model_name="gpt-4o-mini",
        )
        runtime_service.set_mode("online")
        result = runtime_service.select_online(created["provider"]["id"])
        assert result["success"] is True
        assert runtime_service.get_snapshot()["online"]["selected_id"] == created["provider"]["id"]

    def test_apply_active_client_keeps_online_mode_without_provider(self, runtime_service):
        class _Ollama:
            model_name = ""
            base_url = ""

        class _Online:
            model_name = ""
            base_url = ""
            api_key = ""
            api_type = ""
            chat_url = ""

        runtime_service.set_mode("online")
        result = runtime_service.apply_active_client(_Ollama(), _Online())
        assert result["mode"] == "online"
        assert result.get("warning") == "online_provider_missing"
        assert runtime_service.get_mode() == "online"

    def test_normalize_startup_mode_falls_back_to_local(self, runtime_service):
        runtime_service.set_mode("online")
        changed = runtime_service.normalize_startup_mode()
        assert changed is True
        assert runtime_service.get_mode() == "local"
