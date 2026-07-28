"""Прогресс скачивания моделей Ollama (память процесса + парсинг stream)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

_PROGRESS: dict[str, dict[str, Any]] = {}
_RUNNING: dict[str, asyncio.Task] = {}


def format_bytes(num: int) -> str:
    value = float(max(0, int(num)))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(num)} B"


def format_eta(seconds: int) -> str:
    sec = max(0, int(seconds))
    if sec < 60:
        return f"~{sec} сек"
    if sec < 3600:
        mins = sec // 60
        rem = sec % 60
        return f"~{mins} мин {rem} сек" if rem else f"~{mins} мин"
    hours = sec // 3600
    mins = (sec % 3600) // 60
    return f"~{hours} ч {mins} мин" if mins else f"~{hours} ч"


def _status_message_ru(status: str) -> str:
    mapping = {
        "pulling manifest": "Загрузка манифеста…",
        "downloading": "Скачивание файлов…",
        "verifying sha256 digest": "Проверка целостности…",
        "writing manifest": "Сохранение…",
        "removing any unused layers": "Очистка…",
        "success": "Готово",
        "error": "Ошибка",
    }
    return mapping.get(status, status or "Подготовка…")


def friendly_pull_error(message: str) -> str:
    lowered = (message or "").lower()
    if "contentlengtherror" in lowered or "not enough data to satisfy content length" in lowered:
        return (
            "Загрузка оборвалась (нестабильная сеть или VPN). "
            "Нажмите «Скачать» снова — CoreX продолжит с места остановки."
        )
    if "forcibly closed" in lowered or "wsarecv" in lowered or "connection reset" in lowered:
        return "Сеть оборвала загрузку. Проверьте интернет/VPN (Tailscale и др.) и нажмите «Скачать» снова."
    if "pull model manifest" in lowered or "registry.ollama.ai" in lowered:
        return "Не удалось связаться с сервером Ollama. Проверьте интернет/VPN и повторите."
    if "huggingface" in lowered or "hugging face" in lowered:
        return "Не удалось скачать с Hugging Face. Проверьте интернет/VPN и повторите."
    return message or "Ошибка скачивания"


def apply_http_download_progress(
    state: dict[str, Any],
    completed: int,
    total: int,
    *,
    resumed: bool = False,
) -> None:
    state["status"] = "downloading"
    state["phase"] = "download"
    state["indeterminate"] = False
    state["completed_bytes"] = int(completed)
    state["total_bytes"] = int(total)
    state["completed_label"] = format_bytes(completed)
    state["total_label"] = format_bytes(total) if total > 0 else "?"
    if total > 0:
        percent = round(100.0 * completed / total, 1)
        state["percent"] = percent
        state["percent_label"] = f"{percent:g}%"
    if resumed and completed > 0:
        state["resumed"] = True
        state["message"] = "Продолжение загрузки…"
    else:
        state["message"] = "Скачивание с Hugging Face…"
    _update_speed_eta(state)


def apply_import_progress_start(state: dict[str, Any], file_bytes: int) -> None:
    state["status"] = "importing"
    state["phase"] = "import"
    state["indeterminate"] = True
    state["completed_bytes"] = 0
    state["total_bytes"] = int(file_bytes)
    state["completed_label"] = "0 B"
    state["total_label"] = format_bytes(file_bytes) if file_bytes > 0 else "?"
    state["percent"] = 0.0
    state["percent_label"] = "0%"
    state["message"] = "Регистрация модели в Ollama…"
    state["_import_started_at"] = time.monotonic()
    state["_last_completed_bytes"] = 0
    state["_speed_at"] = time.monotonic()


def apply_ollama_import_progress(
    state: dict[str, Any],
    completed: int,
    total: int,
    *,
    percent: float | None = None,
) -> None:
    state["status"] = "importing"
    state["phase"] = "import"
    state["indeterminate"] = False
    state["completed_bytes"] = int(completed)
    state["total_bytes"] = int(total)
    state["completed_label"] = format_bytes(completed)
    state["total_label"] = format_bytes(total) if total > 0 else "?"
    if percent is not None:
        pct = round(float(percent), 1)
    elif total > 0:
        pct = round(100.0 * completed / total, 1)
    else:
        pct = 0.0
    state["percent"] = pct
    state["percent_label"] = f"{pct:g}%"
    state["message"] = f"Копирование в Ollama… {pct:g}%"
    _update_speed_eta(state)


def _update_speed_eta(state: dict[str, Any]) -> None:
    now = time.monotonic()
    completed = int(state.get("completed_bytes") or 0)
    total = int(state.get("total_bytes") or 0)
    last_completed = int(state.get("_last_completed_bytes") or 0)
    last_at = float(state.get("_speed_at") or now)
    delta_t = max(now - last_at, 0.05)
    delta_b = completed - last_completed

    if delta_b > 0:
        speed = delta_b / delta_t
        state["speed_bps"] = speed
        state["speed_label"] = f"{format_bytes(int(speed))}/с"
        if total > completed and speed > 0:
            state["eta_sec"] = int((total - completed) / speed)
            state["eta_label"] = format_eta(state["eta_sec"])
        state["_last_completed_bytes"] = completed
        state["_speed_at"] = now
    elif total > completed and state.get("speed_bps"):
        speed = float(state["speed_bps"])
        if speed > 0:
            state["eta_sec"] = int((total - completed) / speed)
            state["eta_label"] = format_eta(state["eta_sec"])


def init_pull_progress(
    job_id: str,
    model_name: str,
    provider_id: str | None = None,
    *,
    download_method: str = "registry",
) -> dict[str, Any]:
    now = time.monotonic()
    state = {
        "job_id": job_id,
        "provider_id": provider_id,
        "model_name": model_name,
        "download_method": download_method,
        "status": "starting",
        "message": "Запуск скачивания…",
        "layers": {},
        "completed_bytes": 0,
        "total_bytes": 0,
        "percent": 0.0,
        "percent_label": "0%",
        "completed_label": "0 B",
        "total_label": "?",
        "speed_bps": 0.0,
        "speed_label": "",
        "eta_sec": 0,
        "eta_label": "",
        "elapsed_sec": 0,
        "indeterminate": True,
        "done": False,
        "success": False,
        "error": "",
        "resumed": False,
        "_started_at": now,
        "_speed_at": now,
        "_last_completed_bytes": 0,
    }
    _PROGRESS[job_id] = state
    return state


def get_pull_progress_state(job_id: str) -> dict[str, Any] | None:
    """Мутабельное состояние прогресса (только для backend)."""
    return _PROGRESS.get(job_id)


def get_pull_progress(job_id: str) -> dict[str, Any] | None:
    state = _PROGRESS.get(job_id)
    if not state:
        return None
    if state.get("status") == "downloading" and not state.get("done"):
        _update_speed_eta(state)
    return dict(state)


def is_pull_running(job_id: str) -> bool:
    task = _RUNNING.get(job_id)
    return task is not None and not task.done()


def apply_pull_event(state: dict[str, Any], data: dict[str, Any]) -> None:
    status = str(data.get("status") or "").strip()
    if status:
        state["status"] = status
        state["message"] = _status_message_ru(status)

    if status == "downloading":
        state["indeterminate"] = False
        digest = str(data.get("digest") or "layer")
        total = int(data.get("total") or 0)
        completed = int(data.get("completed") or 0)
        layers: dict[str, dict[str, int]] = state.setdefault("layers", {})
        layers[digest] = {"total": total, "completed": completed}
        completed_bytes = sum(layer["completed"] for layer in layers.values())
        total_bytes = sum(layer["total"] for layer in layers.values())
        state["completed_bytes"] = completed_bytes
        state["total_bytes"] = total_bytes
        state["completed_label"] = format_bytes(completed_bytes)
        state["total_label"] = format_bytes(total_bytes) if total_bytes > 0 else "?"
        if total_bytes > 0:
            percent = round(100.0 * completed_bytes / total_bytes, 1)
            state["percent"] = percent
            state["percent_label"] = f"{percent:g}%"
        if completed_bytes > 0 and not state.get("_had_download"):
            state["resumed"] = True
            state["message"] = "Продолжение загрузки…"
        state["_had_download"] = True
        _update_speed_eta(state)
        return

    if status == "success":
        state["done"] = True
        state["success"] = True
        state["indeterminate"] = False
        state["percent"] = 100.0
        state["percent_label"] = "100%"
        if state.get("total_bytes", 0) > 0:
            state["completed_bytes"] = state["total_bytes"]
            state["completed_label"] = format_bytes(state["completed_bytes"])
        state["eta_label"] = ""
        state["message"] = _status_message_ru("success")
        return

    if status == "error" or data.get("error"):
        state["done"] = True
        state["success"] = False
        state["error"] = friendly_pull_error(str(data.get("error") or "Ошибка скачивания"))
        state["message"] = _status_message_ru("error")
        return

    if status in {"pulling manifest", "starting"} and not state.get("total_bytes"):
        state["indeterminate"] = True
        state["percent"] = 0.0
        state["percent_label"] = ""
        state["total_label"] = "?"
        state["completed_label"] = "0 B"
        state["eta_label"] = ""


async def heartbeat_pull_progress(job_id: str) -> None:
    """Пока идёт pull — обновлять таймер на этапе манифеста."""
    while is_pull_running(job_id):
        state = _PROGRESS.get(job_id)
        if state and not state.get("done"):
            elapsed = int(time.monotonic() - float(state.get("_started_at") or time.monotonic()))
            state["elapsed_sec"] = elapsed
            is_direct = state.get("download_method") == "direct"
            if (
                state.get("indeterminate")
                and not state.get("total_bytes")
                and state.get("status") != "downloading"
            ):
                if is_direct:
                    state["message"] = f"Подготовка загрузки с Hugging Face… ({elapsed} с)"
                else:
                    state["message"] = f"Загрузка манифеста… ({elapsed} с)"
            elif state.get("status") == "downloading":
                if is_direct and not state.get("message"):
                    state["message"] = "Скачивание с Hugging Face…"
                _update_speed_eta(state)
            elif state.get("status") == "importing":
                if state.get("indeterminate"):
                    state["message"] = f"Регистрация модели в Ollama… ({elapsed} с)"
                elif not str(state.get("message") or "").startswith("Копирование"):
                    state["message"] = f"Копирование в Ollama… ({elapsed} с)"
                _update_speed_eta(state)
        await asyncio.sleep(1)


def mark_pull_error(job_id: str, message: str) -> dict[str, Any]:
    state = _PROGRESS.get(job_id) or init_pull_progress(job_id, "")
    state["done"] = True
    state["success"] = False
    state["error"] = friendly_pull_error(message)
    state["status"] = "error"
    state["message"] = _status_message_ru("error")
    _PROGRESS[job_id] = state
    return state


def register_pull_task(job_id: str, task: asyncio.Task) -> None:
    _RUNNING[job_id] = task

    def _cleanup(_task: asyncio.Task) -> None:
        _RUNNING.pop(job_id, None)

    task.add_done_callback(_cleanup)


def clear_pull_progress(job_id: str) -> None:
    _PROGRESS.pop(job_id, None)
