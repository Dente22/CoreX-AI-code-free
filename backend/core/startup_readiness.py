"""Проверка готовности CoreX к работе (splash / launch gate).

Splash не должен ждать скачивание тяжёлой модели: достаточно, чтобы
Ollama-сервер поднялся. Модель грузится при первом чате или через помощник.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from core.ai_provider_catalog import list_presets
from core.llm_runtime import llm_readiness_error, resolve_active_llm
from core.ollama_model_session import verify_model_installed

if TYPE_CHECKING:
    from core.orchestrator import CoreXOrchestrator

_ready_cache: dict[str, Any] | None = None

_FALLBACK_ORDER = ("ollama-lite", "ollama-qwen", "ollama-claude")


def clear_startup_readiness_cache() -> None:
    global _ready_cache
    _ready_cache = None


async def _model_is_installed(model_name: str, base_url: str) -> bool:
    result = await verify_model_installed(model_name, base_url)
    return bool(result.get("installed"))


async def _try_fallback_to_installed_local(
    orchestrator: CoreXOrchestrator,
    *,
    base_url: str,
    current_provider_id: str,
) -> dict[str, Any] | None:
    local_service = getattr(orchestrator, "ai_runtime_service", None)
    if local_service is None:
        return None
    provider_service = getattr(local_service, "local_service", None)
    if provider_service is None:
        return None

    presets_by_id = {preset.id: preset for preset in list_presets()}
    ordered_ids = [pid for pid in _FALLBACK_ORDER if pid in presets_by_id]
    for preset in list_presets():
        if preset.id not in ordered_ids:
            ordered_ids.append(preset.id)

    for provider_id in ordered_ids:
        if provider_id == current_provider_id:
            continue
        preset = presets_by_id[provider_id]
        if not await _model_is_installed(preset.model_name, base_url):
            continue
        switched = provider_service.set_selected_id(provider_id)
        if not switched.get("success"):
            continue
        provider_service.apply_to_client(orchestrator.ollama)
        clear_startup_readiness_cache()
        return {
            "ready": True,
            "phase": "ready",
            "message": (
                f"Выбрана установленная модель {preset.model_name} "
                f"(вместо недоступной). Можно работать."
            ),
            "mode": "local",
            "model": preset.model_name,
            "fallback_from": current_provider_id,
            "fallback_to": provider_id,
        }
    return None


async def evaluate_startup_readiness(orchestrator: CoreXOrchestrator) -> dict[str, Any]:
    global _ready_cache
    if _ready_cache and _ready_cache.get("ready"):
        return dict(_ready_cache)

    runtime = orchestrator.get_ai_runtime_snapshot()
    mode = str(runtime.get("mode") or "local").strip().lower()
    active = resolve_active_llm(
        orchestrator.ai_runtime_service,
        orchestrator.ollama,
        orchestrator.online,
    )

    if mode == "online":
        if not await active.client.ensure_ready():
            return {
                "ready": False,
                "phase": "online_config",
                "message": llm_readiness_error(active),
                "mode": mode,
                "model": active.model_name or "",
            }
        payload = {
            "ready": True,
            "phase": "ready",
            "message": f"Онлайн API · {active.model_name}",
            "mode": mode,
            "model": active.model_name,
        }
        _ready_cache = payload
        return payload

    from core.ollama_lifecycle import ensure_ollama_serve_running

    if not await ensure_ollama_serve_running():
        err = str(getattr(orchestrator.ollama, "last_error", "") or "").strip()
        return {
            "ready": False,
            "phase": "ollama_server",
            "message": err or "Запуск Ollama…",
            "mode": mode,
            "model": active.model_name or "",
        }

    base_url = str(getattr(active.client, "root_url", "") or "http://127.0.0.1:11435")
    model_name = str(active.model_name or "").strip()
    provider_id = str(active.provider_id or "").strip()

    if model_name and await _model_is_installed(model_name, base_url):
        payload = {
            "ready": True,
            "phase": "ready",
            "message": f"Ollama готова · {model_name} (загрузка в память при первом чате)",
            "mode": mode,
            "model": model_name,
        }
        _ready_cache = payload
        return payload

    fallback = await _try_fallback_to_installed_local(
        orchestrator,
        base_url=base_url,
        current_provider_id=provider_id,
    )
    if fallback:
        _ready_cache = fallback
        return fallback

    payload = {
        "ready": True,
        "phase": "model_pending",
        "message": (
            f"Ollama запущена. Модель «{model_name or 'не выбрана'}» ещё не скачана — "
            "откройте помощник и нажмите «Скачать», либо переключитесь на Онлайн (OpenRouter Free)."
        ),
        "mode": mode,
        "model": model_name,
        "model_installed": False,
    }
    _ready_cache = payload
    return payload
