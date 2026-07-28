"""Единый runtime-слой для локальных Ollama-пресетов и онлайн API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ai_runtime_service import AiRuntimeService

from core.ai_provider_catalog import get_preset, validate_provider_id
from core.gemini_models import normalize_gemini_model_name

LlmMode = Literal["local", "online"]


@dataclass(frozen=True)
class ActiveLlm:
    client: Any
    mode: LlmMode
    provider_id: str
    provider_name: str
    model_name: str
    api_type: str
    model_tier: str = "medium"


def resolve_active_llm(
    runtime_service: AiRuntimeService,
    local_client: Any,
    online_client: Any,
) -> ActiveLlm:
    applied = runtime_service.apply_active_client(local_client, online_client)
    mode = runtime_service.get_mode()

    if mode == "online":
        provider = applied.get("provider") or runtime_service.online_service.get_selected_provider() or {}
        api_type = str(provider.get("api_type") or getattr(online_client, "api_type", "openai"))
        model_name = str(provider.get("model_name") or getattr(online_client, "model_name", ""))
        if api_type == "gemini":
            model_name = normalize_gemini_model_name(model_name)
        return ActiveLlm(
            client=online_client,
            mode="online",
            provider_id=str(provider.get("id") or ""),
            provider_name=str(provider.get("name") or "Онлайн API"),
            model_name=model_name,
            api_type=api_type,
        )

    preset_dict = applied.get("preset")
    if not preset_dict:
        preset_dict = runtime_service.local_service.get_selected_preset().to_dict()

    provider_id = str(preset_dict.get("id") or "")
    preset = get_preset(provider_id) if validate_provider_id(provider_id) else None
    model_tier = preset.tier if preset else "medium"

    return ActiveLlm(
        client=local_client,
        mode="local",
        provider_id=provider_id,
        provider_name=str(preset_dict.get("name") or "Локальная модель"),
        model_name=str(preset_dict.get("model_name") or getattr(local_client, "model_name", "")),
        api_type="ollama",
        model_tier=model_tier,
    )


async def ensure_llm_ready(active: ActiveLlm) -> bool:
    ensure = getattr(active.client, "ensure_ready", None)
    if callable(ensure):
        ready = bool(await ensure())
        if not ready:
            return False
    else:
        legacy = getattr(active.client, "ensure_daemon_running", None)
        if callable(legacy):
            ready = bool(await legacy())
            if not ready:
                return False
        else:
            ready = True

    prepare = getattr(active.client, "prepare_for_generation", None)
    if callable(prepare):
        return bool(await prepare())
    return ready


def llm_readiness_error(active: ActiveLlm) -> str:
    if active.mode == "online":
        if not active.model_name or not getattr(active.client, "api_key", ""):
            return "Онлайн API не настроен. Добавьте провайдера и выберите модель в чате."
        return (
            f"Не удалось подключиться к онлайн API «{active.provider_name}». "
            "Проверьте ключ, URL и имя модели."
        )
    last_error = str(getattr(active.client, "last_error", "") or "").strip()
    if last_error:
        return last_error
    return (
        f"Локальная модель «{active.model_name}» недоступна. "
        "Запустите Ollama и скачайте модель кнопкой «Скачать» в помощнике."
    )


def llm_thinking_label(active: ActiveLlm) -> str:
    if active.mode == "online":
        return f"{active.provider_name} · {active.model_name}"
    return active.model_name or active.provider_name
