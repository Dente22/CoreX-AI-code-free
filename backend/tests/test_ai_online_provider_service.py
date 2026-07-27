"""Unit tests for user-managed online API providers."""

import json

import pytest

from core.ai_online_provider_service import (
    AiOnlineProviderService,
    default_online_providers_store_path,
    resolve_local_secrets_dir,
)


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "secrets" / "ai_online_providers.json"


@pytest.fixture
def service(store_path):
    return AiOnlineProviderService(store_path=store_path, migrate_legacy=False)


@pytest.mark.unit
class TestAiOnlineProviderService:
    def test_empty_list_by_default(self, service):
        data = service.list_with_selection()
        assert data["providers"] == []
        assert data["selected_id"] == ""
        assert data["storage"] == "local_machine"

    def test_create_provider(self, service, store_path):
        result = service.create_provider(
            name="OpenAI",
            base_url="https://api.openai.com/v1",
            api_key="sk-test-key",
            model_name="gpt-4o-mini",
        )
        assert result["success"] is True
        provider = result["provider"]
        assert provider["name"] == "OpenAI"
        assert provider["api_key_masked"].endswith("key")
        assert provider["source"] == "local_machine"
        assert store_path.is_file()
        raw = json.loads(store_path.read_text(encoding="utf-8"))
        assert raw["providers"][0]["api_key"] == "sk-test-key"

    def test_create_requires_fields(self, service):
        result = service.create_provider(name="", base_url="", api_key="", model_name="")
        assert result["success"] is False

    def test_refuses_to_save_into_project_chat(self, tmp_path):
        project = tmp_path / "project"
        legacy = project / "chat" / "ai_online_providers.json"
        service = AiOnlineProviderService(
            store_path=legacy,
            project_root=project,
            migrate_legacy=False,
        )
        with pytest.raises(RuntimeError, match="нельзя сохранять API-ключи"):
            service.create_provider(
                name="Bad",
                base_url="https://api.example.com/v1",
                api_key="leak-me",
                model_name="demo",
            )

    def test_migrates_legacy_project_secrets_and_scrubs_file(self, tmp_path, monkeypatch):
        project = tmp_path / "project"
        secrets = tmp_path / "secrets"
        monkeypatch.setenv("COREX_SECRETS_DIR", str(secrets))

        legacy = project / "chat" / "ai_online_providers.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            json.dumps(
                {
                    "version": 1,
                    "selected_id": "p1",
                    "providers": [
                        {
                            "id": "p1",
                            "name": "Gemini",
                            "base_url": "https://generativelanguage.googleapis.com/v1beta",
                            "api_key": "AIzaSy-secret-should-leave-project",
                            "model_name": "gemini-1.5-flash",
                            "api_type": "gemini",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        service = AiOnlineProviderService(project_root=project, migrate_legacy=True)
        full = service.get_selected_provider(include_secret=True)
        assert full is not None
        assert full["api_key"] == "AIzaSy-secret-should-leave-project"
        scrubbed = json.loads(legacy.read_text(encoding="utf-8"))
        assert scrubbed["providers"] == []
        assert "AIzaSy" not in legacy.read_text(encoding="utf-8")

    def test_default_store_is_outside_project(self, tmp_path, monkeypatch):
        secrets = tmp_path / "machine-secrets"
        monkeypatch.setenv("COREX_SECRETS_DIR", str(secrets))
        assert resolve_local_secrets_dir() == secrets.resolve()
        assert default_online_providers_store_path() == (secrets / "ai_online_providers.json").resolve()

    def test_rewrites_retired_openrouter_free_model(self, service, store_path):
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "selected_id": "p1",
                    "providers": [
                        {
                            "id": "p1",
                            "name": "OpenRouter Free",
                            "base_url": "https://openrouter.ai/api/v1",
                            "api_key": "sk-or-v1-test",
                            "model_name": "meta-llama/llama-3.3-70b-instruct:free",
                            "api_type": "openai",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        selected = service.get_selected_provider(include_secret=True)
        assert selected is not None
        assert selected["model_name"] == "openrouter/free"
        raw = json.loads(store_path.read_text(encoding="utf-8"))
        assert raw["providers"][0]["model_name"] == "openrouter/free"

    def test_create_rewrites_retired_free_model(self, service):
        result = service.create_provider(
            name="OpenRouter Free",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test",
            model_name="meta-llama/llama-3.3-70b-instruct:free",
        )
        assert result["success"] is True
        assert result["provider"]["model_name"] == "openrouter/free"

    def test_update_selected_model(self, service):
        created = service.create_provider(
            name="OpenRouter Free",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test",
            model_name="openrouter/free",
        )
        assert created["success"] is True
        result = service.update_selected_model("google/gemma-4-31b-it:free")
        assert result["success"] is True
        assert result["model_name"] == "google/gemma-4-31b-it:free"
        selected = service.get_selected_provider(include_secret=True)
        assert selected["model_name"] == "google/gemma-4-31b-it:free"