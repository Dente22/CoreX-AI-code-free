"""Unit tests for unified active LLM resolution (local presets + online API)."""

import pytest

from core.ai_online_provider_service import AiOnlineProviderService
from core.ai_provider_service import AiProviderService
from core.ai_runtime_service import AiRuntimeService
from core.llm_runtime import (
    ensure_llm_ready,
    llm_readiness_error,
    llm_thinking_label,
    resolve_active_llm,
)


class _LocalClient:
    def __init__(self):
        self.model_name = ""
        self.root_url = ""
        self.chat_url = ""
        self.ready = True

    async def ensure_ready(self) -> bool:
        return self.ready

    async def ensure_daemon_running(self) -> bool:
        return self.ready


class _OnlineClient:
    def __init__(self):
        self.model_name = ""
        self.base_url = ""
        self.api_key = ""
        self.api_type = "openai"
        self.chat_url = ""
        self.ready = True

    async def ensure_ready(self) -> bool:
        return self.ready


@pytest.fixture
def runtime_stack(tmp_path):
    local_service = AiProviderService(config_path=tmp_path / "chat" / "ai_provider.json")
    online_service = AiOnlineProviderService(store_path=tmp_path / "chat" / "ai_online_providers.json")
    runtime_service = AiRuntimeService(
        config_path=tmp_path / "chat" / "ai_runtime.json",
        local_service=local_service,
        online_service=online_service,
    )
    return runtime_service, _LocalClient(), _OnlineClient()


@pytest.mark.unit
class TestLlmRuntime:
    def test_resolve_local_qwen_preset(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        runtime_service.select_local("ollama-qwen")
        active = resolve_active_llm(runtime_service, local, online)
        assert active.mode == "local"
        assert active.provider_id == "ollama-qwen"
        assert active.model_name == "qwen2.5-coder:7b"
        assert active.api_type == "ollama"
        assert active.client is local

    def test_resolve_local_llama_preset(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        runtime_service.select_local("ollama-claude")
        active = resolve_active_llm(runtime_service, local, online)
        assert active.model_name == "llama3.1:8b"

    def test_resolve_local_phi_preset(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        runtime_service.select_local("ollama-lite")
        active = resolve_active_llm(runtime_service, local, online)
        assert active.model_name == "phi3:mini"

    def test_resolve_online_openai_provider(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        created = runtime_service.online_service.create_provider(
            name="OpenAI",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model_name="gpt-4o-mini",
            api_type="openai",
        )
        runtime_service.set_mode("online")
        runtime_service.select_online(created["provider"]["id"])
        active = resolve_active_llm(runtime_service, local, online)
        assert active.mode == "online"
        assert active.provider_name == "OpenAI"
        assert active.model_name == "gpt-4o-mini"
        assert active.api_type == "openai"
        assert active.client is online

    def test_resolve_online_gemini_provider(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        created = runtime_service.online_service.create_provider(
            name="Gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key="google-key",
            model_name="gemini-1.5-flash",
            api_type="gemini",
        )
        runtime_service.set_mode("online")
        active = resolve_active_llm(runtime_service, local, online)
        assert active.api_type == "gemini"
        assert active.model_name == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_ensure_llm_ready_uses_client(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        runtime_service.select_local("ollama-qwen")
        active = resolve_active_llm(runtime_service, local, online)
        local.ready = True
        assert await ensure_llm_ready(active) is True
        local.ready = False
        assert await ensure_llm_ready(active) is False

    def test_readiness_error_messages_are_provider_specific(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        runtime_service.select_local("ollama-lite")
        local_active = resolve_active_llm(runtime_service, local, online)
        assert "phi3:mini" in llm_readiness_error(local_active)

        runtime_service.set_mode("online")
        online_active = resolve_active_llm(runtime_service, local, online)
        assert "Онлайн API" in llm_readiness_error(online_active)

    def test_thinking_label_for_local_and_online(self, runtime_stack):
        runtime_service, local, online = runtime_stack
        runtime_service.select_local("ollama-qwen")
        assert "qwen2.5-coder:7b" in llm_thinking_label(resolve_active_llm(runtime_service, local, online))

        created = runtime_service.online_service.create_provider(
            name="Groq",
            base_url="https://api.groq.com/openai/v1",
            api_key="gsk_test",
            model_name="llama-3.1-8b-instant",
        )
        runtime_service.set_mode("online")
        runtime_service.select_online(created["provider"]["id"])
        label = llm_thinking_label(resolve_active_llm(runtime_service, local, online))
        assert "Groq" in label
        assert "llama-3.1-8b-instant" in label
