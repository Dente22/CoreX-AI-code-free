"""Unit tests for AI provider selection persistence."""

import json

import pytest

from core.ai_provider_catalog import DEFAULT_PROVIDER_ID
from core.ai_provider_service import AiProviderService


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "ai_provider.json"


@pytest.fixture
def service(config_path):
    return AiProviderService(config_path=config_path)


@pytest.mark.unit
class TestAiProviderService:
    def test_default_selection_when_no_config(self, service):
        assert service.get_selected_id() == DEFAULT_PROVIDER_ID

    def test_list_providers_includes_selection(self, service):
        data = service.list_with_selection()
        assert data["selected_id"] == DEFAULT_PROVIDER_ID
        assert len(data["providers"]) == 5
        for provider in data["providers"]:
            assert provider["selected"] == (provider["id"] == DEFAULT_PROVIDER_ID)

    def test_set_valid_provider(self, service, config_path):
        result = service.set_selected_id("ollama-lite")
        assert result["success"] is True
        assert result["selected_id"] == "ollama-lite"
        assert service.get_selected_id() == "ollama-lite"
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved["provider_id"] == "ollama-lite"

    def test_set_invalid_provider(self, service, config_path):
        result = service.set_selected_id("fake-model")
        assert result["success"] is False
        assert "error" in result
        assert service.get_selected_id() == DEFAULT_PROVIDER_ID
        assert not config_path.exists()

    def test_get_selected_preset(self, service):
        service.set_selected_id("ollama-claude")
        preset = service.get_selected_preset()
        assert preset.id == "ollama-claude"

    def test_resolve_ollama_config(self, service):
        service.set_selected_id("ollama-lite")
        config = service.resolve_ollama_config()
        assert config["model_name"]
        assert config["base_url"].startswith("http")
        assert config["provider_id"] == "ollama-lite"

    def test_persists_across_instances(self, config_path):
        first = AiProviderService(config_path=config_path)
        first.set_selected_id("ollama-claude")
        second = AiProviderService(config_path=config_path)
        assert second.get_selected_id() == "ollama-claude"
