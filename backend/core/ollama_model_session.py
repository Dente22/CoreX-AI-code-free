"""Загрузка и переключение моделей Ollama (одна активная модель в памяти)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from core.ollama_lifecycle import MODEL_KEEP_ALIVE, note_ollama_activity

WARMUP_TIMEOUT_SEC = 180
UNLOAD_TIMEOUT_SEC = 30
TAGS_TIMEOUT_SEC = 15

_active_model: str | None = None
_session_lock = asyncio.Lock()


def reset_ollama_model_session() -> None:
    global _active_model
    _active_model = None


def clear_active_ollama_model() -> None:
    global _active_model
    _active_model = None


def get_active_ollama_model() -> str | None:
    return _active_model


async def _is_ollama_reachable(base_url: str) -> bool:
    from core.ollama_lifecycle import _is_server_running

    return await _is_server_running(base_url)


async def unload_ollama_model(model_name: str, base_url: str) -> bool:
    normalized = (model_name or "").strip()
    if not normalized:
        return False
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {"model": normalized, "keep_alive": 0}
    timeout = aiohttp.ClientTimeout(total=UNLOAD_TIMEOUT_SEC)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                await response.read()
                return response.status < 500
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return False


async def verify_model_installed(model_name: str, base_url: str) -> dict[str, Any]:
    from core.ollama_model_service import detect_installed_models_from_disk, model_name_matches

    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "installed": False, "error": "Не указано имя модели"}

    tags_url = f"{base_url.rstrip('/')}/api/tags"
    timeout = aiohttp.ClientTimeout(total=TAGS_TIMEOUT_SEC)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(tags_url) as response:
                if response.status == 200:
                    data = await response.json()
                    for item in data.get("models") or []:
                        name = str(item.get("name") or item.get("model") or "").strip()
                        if model_name_matches(name, normalized):
                            return {"success": True, "installed": True, "source": "tags"}
                elif response.status >= 500:
                    return {
                        "success": False,
                        "installed": False,
                        "error": f"Ollama вернула ошибку {response.status}. Перезапустите CoreX.",
                    }
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        from core.ollama_client import format_ollama_connection_error

        return {
            "success": False,
            "installed": False,
            "error": format_ollama_connection_error(exc, model_name=normalized),
        }

    disk_models = detect_installed_models_from_disk()
    if any(model_name_matches(str(item.get("name") or ""), normalized) for item in disk_models):
        return {
            "success": False,
            "installed": False,
            "error": (
                f"Модель «{normalized}» есть в папке CoreX, но Ollama её не видит. "
                "Перезапустите CoreX или скачайте модель заново кнопкой «Скачать»."
            ),
        }

    from core.desktop_ollama_bridge import detect_desktop_models_from_disk

    desktop_models = detect_desktop_models_from_disk()
    if any(model_name_matches(str(item.get("name") or ""), normalized) for item in desktop_models):
        return {
            "success": False,
            "installed": False,
            "error": (
                f"Модель «{normalized}» найдена в системной Ollama (ollama pull), "
                "но не импортирована в CoreX. Откройте помощник локальных моделей "
                "и нажмите «Импортировать»."
            ),
        }

    return {
        "success": False,
        "installed": False,
        "error": (
            f"Модель «{normalized}» не скачана. "
            "Откройте помощник локальных моделей и нажмите «Скачать»."
        ),
    }


async def warmup_ollama_model(model_name: str, base_url: str) -> dict[str, Any]:
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": normalized,
        "prompt": " ",
        "stream": False,
        "keep_alive": MODEL_KEEP_ALIVE,
        "options": {"num_predict": 1},
    }
    timeout = aiohttp.ClientTimeout(total=WARMUP_TIMEOUT_SEC)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                body = await response.text()
                if response.status == 404:
                    return {
                        "success": False,
                        "error": (
                            f"Модель «{normalized}» не установлена. "
                            "Скачайте её кнопкой «Скачать» в помощнике локальных моделей."
                        ),
                    }
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"Ollama вернула {response.status}: {body[:200]}",
                    }
                note_ollama_activity()
                return {"success": True, "model_name": normalized}
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        from core.ollama_client import format_ollama_connection_error

        return {"success": False, "error": format_ollama_connection_error(exc, model_name=normalized)}


async def activate_ollama_model(
    model_name: str,
    base_url: str,
    *,
    preload: bool = False,
) -> dict[str, Any]:
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    async with _session_lock:
        global _active_model
        if _active_model == normalized:
            if await _is_ollama_reachable(base_url):
                note_ollama_activity()
                return {"success": True, "already_loaded": True, "model_name": normalized}
            _active_model = None
            return {
                "success": False,
                "error": (
                    "Ollama не запущена на 127.0.0.1:11435. "
                    "Отправьте сообщение ещё раз — CoreX перезапустит сервер."
                ),
            }

        previous = _active_model
        if _active_model and _active_model != normalized:
            await unload_ollama_model(_active_model, base_url)

        if preload:
            loaded = await warmup_ollama_model(normalized, base_url)
            if not loaded.get("success"):
                return loaded

        _active_model = normalized
        note_ollama_activity()
        return {
            "success": True,
            "model_name": normalized,
            "switched": previous is not None and previous != normalized,
            "preloaded": preload,
        }
