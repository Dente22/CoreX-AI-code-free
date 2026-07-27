"""Управление локальными моделями Ollama в папке установки CoreX."""

from __future__ import annotations

import asyncio
import json
import contextlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import aiohttp

from core.ai_provider_catalog import (
    DEFAULT_OLLAMA_URL,
    get_preset,
    list_preset_dicts,
    validate_provider_id,
)
from core.core_x_library import COREX_ROOT
from core.ollama_pull_progress import (
    apply_pull_event,
    format_bytes,
    get_pull_progress,
    get_pull_progress_state,
    heartbeat_pull_progress,
    init_pull_progress,
    is_pull_running,
    mark_pull_error,
    register_pull_task,
)
from core.model_direct_download import (
    cleanup_direct_download,
    direct_download_curl_command,
    download_and_import_direct,
    get_direct_source,
    has_direct_source,
    resolve_gguf_path,
    resolve_models_storage_dir,
)
from core.desktop_ollama_bridge import (
    DESKTOP_OLLAMA_BASE_URL,
    detect_desktop_models_from_disk,
    import_model_from_desktop,
    list_desktop_ollama_models,
)
from core.ollama_lifecycle import (
    COREX_OLLAMA_BASE_URL,
    COREX_OLLAMA_HOST,
    COREX_OLLAMA_PORT,
    detect_installed_models_from_disk,
    ensure_ollama_serve_running,
    get_ollama_state,
    merge_ollama_runtime_env,
    note_ollama_activity,
    stop_ollama_serve,
)
from core.terminal_output import append_ollama_pull_hints, sanitize_terminal_output

PULL_TIMEOUT_SEC = 3600
RM_TIMEOUT_SEC = 120
LIST_TIMEOUT_SEC = 15

_LIST_NAME_RE = re.compile(r"^([^\s]+)")


def resolve_ollama_models_dir() -> Path:
    """Каталог моделей рядом с установкой CoreX (не в папке пользователя)."""
    path = COREX_ROOT / "ollama_models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_partial_downloads() -> dict[str, Any]:
    """Удалить оборванные *-partial-* файлы после незавершённого pull."""
    blobs_dir = resolve_ollama_models_dir() / "blobs"
    removed: list[str] = []
    if blobs_dir.is_dir():
        for path in blobs_dir.glob("*-partial-*"):
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                continue
    return {"removed": removed, "count": len(removed)}


def scrub_orphan_blobs() -> dict[str, Any]:
    """Удалить blob-файлы, если ни одна модель не установлена (хвосты оборванного pull)."""
    blobs_dir = resolve_ollama_models_dir() / "blobs"
    removed: list[str] = []
    if not blobs_dir.is_dir():
        return {"removed": removed, "count": 0}
    for path in list(blobs_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            continue
    return {"removed": removed, "count": len(removed)}


def merge_ollama_env(base: dict[str, str] | None = None) -> dict[str, str]:
    return merge_ollama_runtime_env(base)


def resolve_ollama_base_url() -> str:
    return COREX_OLLAMA_BASE_URL


def model_name_matches(installed_name: str, target_name: str) -> bool:
    left = (installed_name or "").strip().lower()
    right = (target_name or "").strip().lower()
    if not left or not right:
        return False
    if left == right:
        return True
    return left.split(":")[0] == right.split(":")[0] and (
        ":" not in right or left == right
    )


def _parse_ollama_list_output(output: str) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        match = _LIST_NAME_RE.match(line)
        if not match:
            continue
        models.append({"name": match.group(1)})
    return models


async def _is_server_running(base_url: str | None = None) -> bool:
    root = (base_url or resolve_ollama_base_url()).rstrip("/")
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(root) as response:
                return response.status < 500
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return False


async def prepare_pull(model_name: str) -> dict[str, Any]:
    """Перед pull через registry.ollama.ai: очистка хвостов Ollama."""
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    partial = cleanup_partial_downloads()
    if not await ensure_corex_ollama_running():
        return {"success": False, "error": "Ollama недоступна"}

    listed = await list_installed_models()
    installed = listed.get("models") or []
    if any(model_name_matches(str(m.get("name") or ""), normalized) for m in installed):
        return {"success": True, "already_installed": True}

    await asyncio.to_thread(
        _run_ollama_sync,
        ["ollama", "rm", normalized],
        timeout=RM_TIMEOUT_SEC,
    )
    await asyncio.to_thread(
        _run_ollama_sync,
        ["ollama", "prune"],
        timeout=120,
    )
    partial_after = cleanup_partial_downloads()

    scrubbed = {"count": 0}
    if not installed:
        scrubbed = scrub_orphan_blobs()

    return {
        "success": True,
        "partial_removed": partial.get("count", 0) + partial_after.get("count", 0),
        "scrubbed_blobs": scrubbed.get("count", 0),
    }


async def prepare_direct_provider_download(provider_id: str, model_name: str) -> dict[str, Any]:
    """Перед прямой загрузкой GGUF: только проверка файла на диске (без Ollama API)."""
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}
    if not has_direct_source(provider_id):
        return {"success": False, "error": f"Нет прямой ссылки для {provider_id}"}

    gguf_path = resolve_gguf_path(provider_id)
    if gguf_path.is_file():
        try:
            if gguf_path.stat().st_size > 10_000_000:
                return {"success": True, "file_ready": True, "path": str(gguf_path)}
        except OSError:
            pass

    part_path = gguf_path.with_suffix(gguf_path.suffix + ".part")
    if part_path.is_file():
        try:
            if part_path.stat().st_size > 0:
                return {"success": True, "partial_bytes": part_path.stat().st_size}
        except OSError:
            pass

    return {"success": True}


async def ensure_corex_ollama_running() -> bool:
    cleanup_partial_downloads()
    return await ensure_ollama_serve_running()


async def list_installed_models(*, start_if_down: bool = False) -> dict[str, Any]:
    if await _is_server_running():
        note_ollama_activity()
        root = resolve_ollama_base_url().rstrip("/")
        try:
            timeout = aiohttp.ClientTimeout(total=LIST_TIMEOUT_SEC)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{root}/api/tags") as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"Ollama вернула статус {response.status}",
                            "models": [],
                        }
                    data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            return {
                "success": False,
                "error": str(exc),
                "models": [],
            }

        models = [
            {"name": str(item.get("name") or item.get("model") or "").strip()}
            for item in data.get("models") or []
            if str(item.get("name") or item.get("model") or "").strip()
        ]
        return {
            "success": True,
            "models": models,
            "models_dir": str(resolve_ollama_models_dir()),
            "base_url": resolve_ollama_base_url(),
            "ollama_state": get_ollama_state(),
        }

    disk_models = detect_installed_models_from_disk()
    if not start_if_down:
        return {
            "success": True,
            "models": disk_models,
            "models_dir": str(resolve_ollama_models_dir()),
            "base_url": resolve_ollama_base_url(),
            "ollama_state": "sleeping",
            "warning": "ollama_sleeping" if not disk_models else None,
        }

    if not await ensure_corex_ollama_running():
        return {
            "success": True,
            "models": disk_models,
            "models_dir": str(resolve_ollama_models_dir()),
            "base_url": resolve_ollama_base_url(),
            "warning": "ollama_not_available",
            "ollama_state": "sleeping",
        }

    return await list_installed_models(start_if_down=False)


def _installed_names(models: list[dict[str, str]]) -> set[str]:
    return {str(item.get("name") or "").strip().lower() for item in models if item.get("name")}


def catalog_install_status(
    installed: list[dict[str, str]],
    *,
    desktop_installed: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    corex_names = _installed_names(installed)
    desktop_names = _installed_names(desktop_installed or [])
    rows: list[dict[str, Any]] = []
    for preset in list_preset_dicts():
        model_name = preset["model_name"]
        installed_in_corex = any(
            model_name_matches(name, model_name) for name in corex_names
        )
        installed_in_desktop = any(
            model_name_matches(name, model_name) for name in desktop_names
        )
        row = {
            **preset,
            "installed": installed_in_corex or installed_in_desktop,
            "installed_in_corex": installed_in_corex,
            "installed_in_desktop": installed_in_desktop,
            "needs_import": installed_in_desktop and not installed_in_corex,
        }
        if has_direct_source(preset["id"]):
            row["pull_command"] = direct_download_curl_command(preset["id"])
        rows.append(row)
    return rows


async def get_models_snapshot() -> dict[str, Any]:
    listed = await list_installed_models(start_if_down=False)
    installed = listed.get("models") or []
    desktop = await list_desktop_ollama_models()
    desktop_models = desktop.get("models") or []
    warning = listed.get("warning")
    if desktop_models and any(
        row.get("needs_import") for row in catalog_install_status(installed, desktop_installed=desktop_models)
    ):
        warning = warning or "desktop_models_need_import"
    return {
        "success": listed.get("success", False),
        "models": installed,
        "desktop_models": desktop_models,
        "desktop_ollama_url": DESKTOP_OLLAMA_BASE_URL,
        "catalog": catalog_install_status(installed, desktop_installed=desktop_models),
        "models_dir": listed.get("models_dir") or str(resolve_ollama_models_dir()),
        "download_dir": str(resolve_models_storage_dir()),
        "base_url": listed.get("base_url") or resolve_ollama_base_url(),
        "ollama_state": listed.get("ollama_state") or get_ollama_state(),
        "error": listed.get("error"),
        "warning": warning,
    }


async def _import_desktop_model_job(model_name: str, job_id: str) -> dict[str, Any]:
    init_pull_progress(job_id, model_name)
    state = get_pull_progress_state(job_id)
    if state is not None:
        state["message"] = "Импорт из системной Ollama (без повторной загрузки)…"
        state["status"] = "importing"
        state["indeterminate"] = True

    result = await asyncio.to_thread(import_model_from_desktop, model_name)
    if not result.get("success"):
        mark_pull_error(job_id, str(result.get("error") or "Импорт не удался"))
        return get_pull_progress(job_id) or {"success": False, **result}

    await stop_ollama_serve(reason="manual")
    if not await ensure_corex_ollama_running():
        mark_pull_error(job_id, "Модель скопирована, но Ollama CoreX не запустилась.")
        return get_pull_progress(job_id) or {"success": False}

    if state is not None:
        state["message"] = str(result.get("message") or "Импорт завершён")
        state["status"] = "success"
        state["indeterminate"] = False
        state["done"] = True
        state["success"] = True
        state["percent"] = 100
        state["percent_label"] = "100%"

    return {
        "success": True,
        "model_name": model_name,
        "job_id": job_id,
        "imported_from_desktop": True,
        "progress": get_pull_progress(job_id),
    }


async def _model_present_in_corex(model_name: str) -> bool:
    listed = await list_installed_models(start_if_down=False)
    installed = listed.get("models") or []
    return any(model_name_matches(str(item.get("name") or ""), model_name) for item in installed)


async def _model_present_on_desktop(model_name: str) -> bool:
    desktop = await list_desktop_ollama_models()
    models = desktop.get("models") or []
    if any(model_name_matches(str(item.get("name") or ""), model_name) for item in models):
        return True
    return any(
        model_name_matches(str(item.get("name") or ""), model_name)
        for item in detect_desktop_models_from_disk()
    )


def _run_ollama_sync(argv: list[str], *, timeout: int) -> dict[str, Any]:
    env = merge_ollama_env()
    run_kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "env": env,
        "cwd": str(COREX_ROOT),
    }
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        completed = subprocess.run(argv, shell=False, **run_kwargs)
    except FileNotFoundError:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": "Команда ollama не найдена. Установите Ollama с ollama.com",
            "command": " ".join(argv),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": f"Превышен лимит времени ({timeout} с)",
            "command": " ".join(argv),
        }
    except OSError as exc:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": str(exc),
            "command": " ".join(argv),
        }

    output = sanitize_terminal_output((completed.stdout or "") + (completed.stderr or ""))
    code = completed.returncode if completed.returncode is not None else -1
    result = {
        "success": code == 0,
        "exit_code": code,
        "output": output,
        "error": "" if code == 0 else f"Код выхода: {code}",
        "command": " ".join(argv),
        "models_dir": str(resolve_ollama_models_dir()),
    }
    if "pull" in argv:
        result = append_ollama_pull_hints(result)
    return result


async def _pull_model_via_api(model_name: str, job_id: str) -> dict[str, Any]:
    state = init_pull_progress(job_id, model_name)
    root = resolve_ollama_base_url().rstrip("/")
    timeout = aiohttp.ClientTimeout(total=PULL_TIMEOUT_SEC)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{root}/api/pull",
                json={"name": model_name, "stream": True},
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    mark_pull_error(job_id, f"Ollama вернула статус {response.status}: {body[:200]}")
                    return get_pull_progress(job_id) or {"success": False}

                buffer = b""
                async for chunk in response.content.iter_any():
                    if not chunk:
                        continue
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        text = line.decode("utf-8", errors="replace").strip()
                        if not text:
                            continue
                        try:
                            event = json.loads(text)
                        except json.JSONDecodeError:
                            continue
                        apply_pull_event(state, event)
                        if state.get("done"):
                            break
                    if state.get("done"):
                        break
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        mark_pull_error(job_id, str(exc))
        return get_pull_progress(job_id) or {"success": False}

    final = get_pull_progress(job_id) or state
    return {
        "success": bool(final.get("success")),
        "model_name": model_name,
        "job_id": job_id,
        "output": final.get("message") or "",
        "error": final.get("error") or ("" if final.get("success") else "Не удалось скачать модель"),
        "progress": final,
    }


async def start_pull_model(model_name: str, *, provider_id: str | None = None) -> dict[str, Any]:
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    job_id = (provider_id or normalized).strip()
    if is_pull_running(job_id):
        progress = get_pull_progress(job_id)
        return {
            "success": True,
            "started": False,
            "already_running": True,
            "job_id": job_id,
            "model_name": normalized,
            "provider_id": provider_id,
            "progress": progress,
        }

    if not await ensure_corex_ollama_running():
        return {
            "success": False,
            "error": "Ollama недоступна. Установите с ollama.com и повторите.",
        }

    prep = await prepare_pull(normalized)
    if not prep.get("success"):
        return prep
    if prep.get("already_installed"):
        return {
            "success": True,
            "already_installed": True,
            "job_id": job_id,
            "model_name": normalized,
            "provider_id": provider_id,
        }

    if await _model_present_on_desktop(normalized) and not await _model_present_in_corex(normalized):
        init_pull_progress(job_id, normalized, provider_id)

        async def _run_import() -> None:
            heartbeat = asyncio.create_task(heartbeat_pull_progress(job_id))
            try:
                await _import_desktop_model_job(normalized, job_id)
            finally:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat

        task = asyncio.create_task(_run_import())
        register_pull_task(job_id, task)
        return {
            "success": True,
            "started": True,
            "import_from_desktop": True,
            "job_id": job_id,
            "model_name": normalized,
            "provider_id": provider_id,
            "progress": get_pull_progress(job_id),
        }

    init_pull_progress(job_id, normalized, provider_id)

    async def _run() -> None:
        heartbeat = asyncio.create_task(heartbeat_pull_progress(job_id))
        try:
            await _pull_model_via_api(normalized, job_id)
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    task = asyncio.create_task(_run())
    register_pull_task(job_id, task)
    return {
        "success": True,
        "started": True,
        "job_id": job_id,
        "model_name": normalized,
        "provider_id": provider_id,
        "progress": get_pull_progress(job_id),
    }


def get_pull_job_progress(job_id: str) -> dict[str, Any]:
    progress = get_pull_progress(job_id)
    if not progress:
        return {"found": False, "error": "Задача не найдена", "job_id": job_id}
    return {"found": True, **progress}


async def pull_model(model_name: str) -> dict[str, Any]:
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    if not await ensure_corex_ollama_running():
        return {
            "success": False,
            "error": "Ollama недоступна. Установите с ollama.com и повторите.",
        }

    job_id = normalized
    result = await _pull_model_via_api(normalized, job_id)
    return result


async def delete_model(model_name: str) -> dict[str, Any]:
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    if not await ensure_corex_ollama_running():
        return {
            "success": False,
            "error": "Ollama недоступна. Установите с ollama.com и повторите.",
        }

    result = await asyncio.to_thread(
        _run_ollama_sync,
        ["ollama", "rm", normalized],
        timeout=RM_TIMEOUT_SEC,
    )
    result["model_name"] = normalized
    return result


async def pull_provider_model(provider_id: str) -> dict[str, Any]:
    if not validate_provider_id(provider_id):
        return {"success": False, "error": f"Неизвестная модель: {provider_id}"}
    preset = get_preset(provider_id)
    result = await pull_model(preset.model_name)
    result["provider_id"] = provider_id
    return result


async def start_direct_provider_pull(provider_id: str) -> dict[str, Any]:
    source = get_direct_source(provider_id) if has_direct_source(provider_id) else None
    if source is None:
        return {"success": False, "error": f"Нет прямой ссылки для {provider_id}"}

    job_id = provider_id.strip()
    if is_pull_running(job_id):
        progress = get_pull_progress(job_id)
        return {
            "success": True,
            "started": False,
            "already_running": True,
            "job_id": job_id,
            "model_name": source.model_name,
            "provider_id": provider_id,
            "progress": progress,
        }

    from core.ollama_pull_progress import clear_pull_progress

    clear_pull_progress(job_id)
    init_pull_progress(job_id, source.model_name, provider_id, download_method="direct")
    state = get_pull_progress_state(job_id)
    if state is not None:
        state["message"] = "Скачивание с Hugging Face…"
        state["status"] = "downloading"
        state["indeterminate"] = False
        state["total_bytes"] = source.size_hint
        state["total_label"] = format_bytes(source.size_hint)

    async def _run() -> None:
        heartbeat = asyncio.create_task(heartbeat_pull_progress(job_id))
        try:
            await download_and_import_direct(
                provider_id,
                job_id,
                prepare_pull=prepare_direct_provider_download,
            )
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    task = asyncio.create_task(_run())
    register_pull_task(job_id, task)
    return {
        "success": True,
        "started": True,
        "job_id": job_id,
        "model_name": source.model_name,
        "provider_id": provider_id,
        "download_method": "direct",
        "progress": get_pull_progress(job_id),
    }


async def start_pull_provider_model(provider_id: str) -> dict[str, Any]:
    if not validate_provider_id(provider_id):
        return {"success": False, "error": f"Неизвестная модель: {provider_id}"}
    if has_direct_source(provider_id):
        result = await start_direct_provider_pull(provider_id)
        result["provider_id"] = provider_id
        return result
    preset = get_preset(provider_id)
    result = await start_pull_model(preset.model_name, provider_id=provider_id)
    result["provider_id"] = provider_id
    return result


async def delete_provider_model(provider_id: str) -> dict[str, Any]:
    if not validate_provider_id(provider_id):
        return {"success": False, "error": f"Неизвестная модель: {provider_id}"}
    preset = get_preset(provider_id)
    result = await delete_model(preset.model_name)
    if result.get("success") and has_direct_source(provider_id):
        cleanup = cleanup_direct_download(provider_id)
        result["download_cleanup"] = cleanup
    result["provider_id"] = provider_id
    return result


# Для обратной совместимости в тестах/импортах
DEFAULT_OLLAMA_URL_FALLBACK = DEFAULT_OLLAMA_URL
