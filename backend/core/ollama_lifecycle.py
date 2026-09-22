"""Жизненный цикл Ollama CoreX: ленивый старт и сон при простое."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import aiohttp

from core.core_x_library import COREX_ROOT
from core.ollama_pull_progress import is_pull_running

COREX_OLLAMA_PORT = 11435
DESKTOP_OLLAMA_PORT = 11434
COREX_OLLAMA_HOST = f"127.0.0.1:{COREX_OLLAMA_PORT}"
COREX_OLLAMA_BASE_URL = f"http://{COREX_OLLAMA_HOST}"
DESKTOP_OLLAMA_HOST = f"127.0.0.1:{DESKTOP_OLLAMA_PORT}"
DESKTOP_OLLAMA_BASE_URL = f"http://{DESKTOP_OLLAMA_HOST}"
MODEL_KEEP_ALIVE = "10m"
IDLE_SLEEP_SEC = 300
WATCHDOG_INTERVAL_SEC = 30
STARTUP_WAIT_ROUNDS = 20
STARTUP_WAIT_SEC = 0.5
STARTUP_MAX_RESTARTS = 2

_serve_process: subprocess.Popen | None = None
_we_started_process = False
_last_activity = 0.0
_watchdog_task: asyncio.Task | None = None
_start_lock = asyncio.Lock()
_last_start_error = ""
_generation_active = 0
_active_base_url = COREX_OLLAMA_BASE_URL
_using_desktop = False

_NETSTAT_PID_RE = re.compile(r"^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$", re.I)


def reset_ollama_lifecycle_state() -> None:
    global _serve_process, _we_started_process, _last_activity, _watchdog_task, _last_start_error, _generation_active
    global _active_base_url, _using_desktop
    if _watchdog_task is not None:
        _watchdog_task.cancel()
        _watchdog_task = None
    _serve_process = None
    _we_started_process = False
    _last_activity = 0.0
    _last_start_error = ""
    _generation_active = 0
    _active_base_url = COREX_OLLAMA_BASE_URL
    _using_desktop = False


def get_ollama_start_error() -> str:
    if _last_start_error:
        return _last_start_error
    return (
        "Не удалось запустить Ollama. Установите с https://ollama.com/download "
        "и перезапустите CoreX."
    )


def resolve_ollama_executable() -> str:
    found = shutil.which("ollama")
    if found:
        return found
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local_app) / "Programs" / "Ollama" / "ollama.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return "ollama"


def resolve_ollama_models_dir() -> Path:
    path = COREX_ROOT / "ollama_models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_ollama_base_url() -> str:
    return _active_base_url


def is_using_desktop_ollama() -> bool:
    return _using_desktop


def bind_client_to_live_endpoint(client: Any) -> str:
    """Перенаправить клиент на живой endpoint (11434 или 11435)."""
    live = resolve_ollama_base_url().rstrip("/")
    if client is None:
        return live
    if hasattr(client, "root_url"):
        client.root_url = live
    if hasattr(client, "chat_url"):
        client.chat_url = f"{live}/api/chat"
    return live


def _attach_endpoint(url: str, *, desktop: bool) -> None:
    global _active_base_url, _using_desktop
    _active_base_url = url.rstrip("/")
    _using_desktop = desktop


def should_skip_desktop_ollama() -> bool:
    """На нескольких GPU не цепляться к приложению Ollama: оно игнорирует CUDA_VISIBLE_DEVICES CoreX."""
    from core.gpu_preference import should_isolate_ollama_serve

    return should_isolate_ollama_serve()


def merge_ollama_runtime_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    env["OLLAMA_MODELS"] = str(resolve_ollama_models_dir())
    env["OLLAMA_HOST"] = COREX_OLLAMA_HOST
    env["OLLAMA_KEEP_ALIVE"] = MODEL_KEEP_ALIVE
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    from core.gpu_preference import apply_gpu_env

    return apply_gpu_env(env)


def begin_ollama_generation() -> None:
    global _generation_active
    _generation_active += 1
    note_ollama_activity()


def end_ollama_generation() -> None:
    global _generation_active
    _generation_active = max(0, _generation_active - 1)
    note_ollama_activity()


def is_generation_active() -> bool:
    return _generation_active > 0


def note_ollama_activity() -> None:
    global _last_activity
    _last_activity = time.monotonic()


def is_any_pull_active() -> bool:
    from core.ollama_pull_progress import _RUNNING

    for job_id, task in list(_RUNNING.items()):
        if is_pull_running(job_id) or (task and not task.done()):
            return True
    return False


def should_sleep_ollama(*, now: float | None = None) -> bool:
    current = now if now is not None else time.monotonic()
    if _last_activity <= 0:
        return False
    if is_any_pull_active():
        return False
    if is_generation_active():
        return False
    return (current - _last_activity) >= IDLE_SLEEP_SEC


def seconds_until_idle_sleep(*, now: float | None = None) -> int:
    current = now if now is not None else time.monotonic()
    if _last_activity <= 0:
        return IDLE_SLEEP_SEC
    remaining = IDLE_SLEEP_SEC - (current - _last_activity)
    return max(0, int(remaining))


def get_ollama_state() -> str:
    if is_any_pull_active() or is_generation_active():
        return "busy"
    if _using_desktop:
        return "running"
    if _serve_process is not None and _serve_process.poll() is None:
        return "running"
    return "sleeping"


def detect_installed_models_from_disk(
    *,
    models_root: Path | None = None,
) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    seen: set[str] = set()
    root = models_root if models_root is not None else resolve_ollama_models_dir()
    manifests = root / "manifests"
    if not manifests.is_dir():
        return models

    library = manifests / "registry.ollama.ai" / "library"
    if library.is_dir():
        for name_dir in sorted(library.iterdir()):
            if not name_dir.is_dir():
                continue
            for tag_path in sorted(name_dir.iterdir()):
                if not tag_path.is_file():
                    continue
                model_name = f"{name_dir.name}:{tag_path.name}"
                if model_name not in seen:
                    seen.add(model_name)
                    models.append({"name": model_name})
    return models


async def _is_server_running(base_url: str | None = None) -> bool:
    root = (base_url or resolve_ollama_base_url()).rstrip("/")
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{root}/api/tags") as response:
                return response.status < 500
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return False


async def _is_desktop_ollama_running() -> bool:
    return await _is_server_running(DESKTOP_OLLAMA_BASE_URL)


async def attach_if_already_running() -> bool:
    """Подключиться к уже живой Ollama, не поднимая второй сервер."""
    if should_skip_desktop_ollama():
        if await _is_server_running(COREX_OLLAMA_BASE_URL):
            _attach_endpoint(COREX_OLLAMA_BASE_URL, desktop=False)
            note_ollama_activity()
            return True
        return False
    if await _is_desktop_ollama_running():
        _attach_endpoint(DESKTOP_OLLAMA_BASE_URL, desktop=True)
        note_ollama_activity()
        return True
    if await _is_server_running(COREX_OLLAMA_BASE_URL):
        _attach_endpoint(COREX_OLLAMA_BASE_URL, desktop=False)
        note_ollama_activity()
        return True
    return False


def _find_listener_pid(port: int) -> int | None:
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        for line in completed.stdout.splitlines():
            match = _NETSTAT_PID_RE.match(line)
            if not match:
                continue
            if int(match.group(1)) == port:
                return int(match.group(2))
        return None

    try:
        completed = subprocess.run(
            ["ss", "-ltnp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    token = f":{port}"
    for line in completed.stdout.splitlines():
        if token not in line or "pid=" not in line:
            continue
        pid_match = re.search(r"pid=(\d+)", line)
        if pid_match:
            return int(pid_match.group(1))
    return None


def _terminate_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return completed.returncode in (0, 128)
    try:
        os.kill(pid, 15)
        return True
    except OSError:
        return False


def collect_descendant_pids(root_pid: int, rows: list[dict[str, int | str]]) -> set[int]:
    descendants: set[int] = set()
    if root_pid <= 0:
        return descendants
    stack = [root_pid]
    while stack:
        current = stack.pop()
        for row in rows:
            parent_pid = int(row.get("parent_pid") or 0)
            pid = int(row.get("pid") or 0)
            if parent_pid == current and pid > 0 and pid not in descendants:
                descendants.add(pid)
                stack.append(pid)
    return descendants


def _list_process_rows() -> list[dict[str, int | str]]:
    if sys.platform != "win32":
        return []
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object Name,ParentProcessId,ProcessId | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _list_process_rows_wmic()
    if completed.returncode != 0 or not completed.stdout.strip():
        return _list_process_rows_wmic()
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return _list_process_rows_wmic()
    if isinstance(payload, dict):
        payload = [payload]
    rows: list[dict[str, int | str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").strip()
        parent_pid = int(item.get("ParentProcessId") or 0)
        pid = int(item.get("ProcessId") or 0)
        if not name or pid <= 0:
            continue
        rows.append({"name": name, "parent_pid": parent_pid, "pid": pid})
    return rows


def _list_process_rows_wmic() -> list[dict[str, int | str]]:
    try:
        completed = subprocess.run(
            ["wmic", "process", "get", "Name,ParentProcessId,ProcessId", "/FORMAT:CSV"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    rows: list[dict[str, int | str]] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("node,"):
            continue
        parts = line.split(",")
        if len(parts) < 4:
            continue
        name = str(parts[1] or "").strip()
        parent_pid = int(parts[2] or 0)
        pid = int(parts[3] or 0)
        if not name or pid <= 0:
            continue
        rows.append({"name": name, "parent_pid": parent_pid, "pid": pid})
    return rows


async def _evict_desktop_ollama() -> None:
    """Закрыть приложение Ollama в трее: оно поднимает Vulkan на Intel и не даёт слушать 11435."""
    await _unload_desktop_loaded_models()
    corex_pid = _find_listener_pid(COREX_OLLAMA_PORT)
    desktop_pid = _find_listener_pid(DESKTOP_OLLAMA_PORT)
    rows = _list_process_rows()
    protected: set[int] = set()
    if corex_pid:
        protected.add(corex_pid)
        protected.update(collect_descendant_pids(corex_pid, rows))

    kill_app: list[int] = []
    kill_rest: list[int] = []
    for row in rows:
        name = str(row.get("name") or "").lower()
        pid = int(row.get("pid") or 0)
        if pid <= 0 or pid in protected:
            continue
        if "ollama app" in name:
            kill_app.append(pid)
        elif name == "ollama.exe" and desktop_pid and pid == desktop_pid:
            kill_rest.append(pid)
        elif name == "llama-server.exe":
            kill_rest.append(pid)
    for pid in kill_app + kill_rest:
        _terminate_pid(pid)
    if kill_app or kill_rest:
        await asyncio.sleep(0.4)


async def cleanup_zombie_llama_workers() -> bool:
    if await _is_server_running():
        return False

    rows = _list_process_rows()
    if not rows:
        return False

    protected: set[int] = set()
    desktop_pid = _find_listener_pid(DESKTOP_OLLAMA_PORT)
    if desktop_pid:
        protected.add(desktop_pid)
        protected.update(collect_descendant_pids(desktop_pid, rows))

    killed = False
    for row in rows:
        name = str(row.get("name") or "").lower()
        pid = int(row.get("pid") or 0)
        if name != "llama-server.exe" or pid <= 0 or pid in protected:
            continue
        killed = _terminate_pid(pid) or killed
    return killed


def _ensure_watchdog_started() -> None:
    global _watchdog_task
    if _watchdog_task is not None and not _watchdog_task.done():
        return

    async def _loop() -> None:
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL_SEC)
            await maybe_sleep_ollama()

    _watchdog_task = asyncio.create_task(_loop())


async def maybe_sleep_ollama() -> bool:
    if _using_desktop:
        return False
    if not should_sleep_ollama():
        return False
    if await _is_server_running(COREX_OLLAMA_BASE_URL):
        return await stop_ollama_serve(reason="idle")
    return False


async def stop_ollama_serve(*, reason: str = "manual") -> bool:
    global _serve_process, _we_started_process
    if _using_desktop:
        return False

    stopped = False

    if _serve_process is not None and _serve_process.poll() is None:
        with contextlib.suppress(OSError):
            _serve_process.terminate()
        stopped = True

    force_port_kill = reason in {"shutdown", "manual"}

    if await _is_server_running(COREX_OLLAMA_BASE_URL):
        pid = _find_listener_pid(COREX_OLLAMA_PORT)
        if pid and (_we_started_process or force_port_kill):
            stopped = _terminate_pid(pid) or stopped

    _serve_process = None
    _we_started_process = False
    from core.ollama_model_session import clear_active_ollama_model

    clear_active_ollama_model()
    if reason in {"idle", "shutdown", "manual"}:
        await cleanup_zombie_llama_workers()
    return stopped


async def restart_managed_ollama_serve() -> bool:
    """Перезапуск 11435, чтобы подхватить CUDA/Vulkan после смены GPU."""
    global _using_desktop

    _using_desktop = False
    await stop_ollama_serve(reason="manual")
    return await ensure_ollama_serve_running()


async def _attach_desktop_ollama() -> None:
    global _serve_process, _we_started_process
    corex_pid = _find_listener_pid(COREX_OLLAMA_PORT)
    if corex_pid:
        _terminate_pid(corex_pid)
    _serve_process = None
    _we_started_process = False
    _attach_endpoint(DESKTOP_OLLAMA_BASE_URL, desktop=True)
    note_ollama_activity()


async def _unload_desktop_loaded_models() -> None:
    """Снять модель с Intel-Vulkan в приложении Ollama, чтобы не держать второй llama-server."""
    if not await _is_desktop_ollama_running():
        return
    root = DESKTOP_OLLAMA_BASE_URL.rstrip("/")
    timeout = aiohttp.ClientTimeout(total=8)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{root}/api/ps") as response:
                if response.status != 200:
                    return
                data = await response.json()
            for item in data.get("models") or []:
                name = str(item.get("name") or item.get("model") or "").strip()
                if not name:
                    continue
                with contextlib.suppress(aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    async with session.post(
                        f"{root}/api/generate",
                        json={"model": name, "keep_alive": 0},
                    ) as unload:
                        await unload.read()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, json.JSONDecodeError):
        return


async def ensure_ollama_serve_running() -> bool:
    global _serve_process, _we_started_process, _last_start_error

    skip_desktop = should_skip_desktop_ollama()
    if skip_desktop:
        await _evict_desktop_ollama()
    elif await _is_desktop_ollama_running():
        await _attach_desktop_ollama()
        return True

    _attach_endpoint(COREX_OLLAMA_BASE_URL, desktop=False)
    if await _is_server_running(COREX_OLLAMA_BASE_URL):
        note_ollama_activity()
        _ensure_watchdog_started()
        return True

    async with _start_lock:
        if not skip_desktop and await _is_desktop_ollama_running():
            await _attach_desktop_ollama()
            return True
        if await _is_server_running(COREX_OLLAMA_BASE_URL):
            note_ollama_activity()
            _ensure_watchdog_started()
            return True

        await cleanup_zombie_llama_workers()

        ollama_bin = resolve_ollama_executable()
        env = merge_ollama_runtime_env()
        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "env": env,
        }
        log_handle = None
        if skip_desktop:
            log_path = Path(COREX_ROOT) / "chat" / "ollama-serve.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("ab")
            popen_kwargs["stdout"] = log_handle
            popen_kwargs["stderr"] = log_handle
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        for launch_attempt in range(STARTUP_MAX_RESTARTS + 1):
            try:
                _serve_process = subprocess.Popen([ollama_bin, "serve"], **popen_kwargs)
                _we_started_process = True
                _last_start_error = ""
            except FileNotFoundError:
                _serve_process = None
                _we_started_process = False
                if log_handle is not None:
                    log_handle.close()
                _last_start_error = (
                    f"Команда Ollama не найдена ({ollama_bin}). "
                    "Установите Ollama с https://ollama.com/download"
                )
                return False
            except OSError as exc:
                _serve_process = None
                _we_started_process = False
                if log_handle is not None:
                    log_handle.close()
                _last_start_error = f"Не удалось запустить Ollama: {exc}"
                return False

            for _ in range(STARTUP_WAIT_ROUNDS):
                await asyncio.sleep(STARTUP_WAIT_SEC)
                if await _is_server_running(COREX_OLLAMA_BASE_URL):
                    _attach_endpoint(COREX_OLLAMA_BASE_URL, desktop=False)
                    note_ollama_activity()
                    _ensure_watchdog_started()
                    return True
                if _serve_process is not None and _serve_process.poll() is not None:
                    break

            exit_code = None
            if _serve_process is not None:
                exit_code = _serve_process.poll()
            _serve_process = None
            _we_started_process = False

            if launch_attempt < STARTUP_MAX_RESTARTS:
                await cleanup_zombie_llama_workers()
                await asyncio.sleep(0.8)
                continue

            if exit_code is not None:
                _last_start_error = (
                    f"Ollama завершилась сразу после запуска (код {exit_code}). "
                    "Проверьте локальную установку Ollama и доступ к папке ollama_models."
                )
            elif skip_desktop:
                _last_start_error = (
                    f"Ollama не ответила на {COREX_OLLAMA_HOST}. "
                    "Закройте приложение Ollama в трее (Quit) и перезапустите CoreX — "
                    "иначе модель садится на Intel UHD, а не на NVIDIA."
                )
            else:
                _last_start_error = (
                    f"Ollama не ответила на {COREX_OLLAMA_HOST} после запуска. "
                    "Если открыто приложение Ollama — оставьте его, CoreX подключится к порту 11434. "
                    "Иначе проверьте VPN или брандмауэр."
                )
            if log_handle is not None:
                log_handle.close()
            return False
