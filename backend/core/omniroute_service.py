"""OmniRoute — локальный AI-шлюз: проверка подключения, автозапуск и инструкция."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

OMNIROUTE_DEFAULT_PORT = 20128
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_START_WAIT_SEC = 25.0
_PROBE_TIMEOUT_SEC = 2.0

_start_lock: asyncio.Lock | None = None


@dataclass(frozen=True)
class OmniRouteStatus:
    ok: bool
    started: bool = False
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def is_omniroute_url(base_url: str, provider_name: str = "") -> bool:
    parsed = urlparse(base_url or "")
    return (
        parsed.port == OMNIROUTE_DEFAULT_PORT
        or "omniroute" in (parsed.hostname or "").lower()
        or "omniroute" in (provider_name or "").lower()
    )


def omniroute_root(base_url: str) -> str:
    parsed = urlparse(base_url or "")
    if not parsed.scheme or not parsed.netloc:
        return f"http://127.0.0.1:{OMNIROUTE_DEFAULT_PORT}"
    return f"{parsed.scheme}://{parsed.netloc}"


def _port_of(base_url: str) -> int:
    return urlparse(base_url or "").port or OMNIROUTE_DEFAULT_PORT


def omniroute_setup_guide(base_url: str = "", reason: str = "") -> str:
    root = omniroute_root(base_url)
    port = _port_of(base_url)
    lines = [reason or f"OmniRoute не отвечает на {root}."]
    lines += [
        "",
        "Как подключить:",
        "1. Установите один раз (нужен Node.js 20+): npm install -g omniroute",
        f"2. Запустите шлюз: omniroute serve --daemon --no-open --port {port}",
        f"3. Откройте дашборд {root} → API Keys → скопируйте ключ sk-...",
        f"4. В CoreX: Модели → Онлайн → OmniRoute: Base URL {root}/v1, ключ и модель "
        "вида ollama-local/qwen3:4b или claude-free.",
        "",
        "Если omniroute установлен не в PATH, укажите путь к omniroute.cmd "
        "в переменной окружения COREX_OMNIROUTE_PATH.",
    ]
    return "\n".join(lines)


def find_omniroute_command() -> list[str] | None:
    override = (os.environ.get("COREX_OMNIROUTE_PATH") or "").strip()
    if override and Path(override).is_file():
        return [override]
    exe = shutil.which("omniroute")
    if exe:
        return [exe]
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        candidate = Path(appdata) / "npm" / "omniroute.cmd"
        if candidate.is_file():
            return [str(candidate)]
    return None


async def probe_omniroute(base_url: str, timeout_sec: float = _PROBE_TIMEOUT_SEC) -> bool:
    """Любой HTTP-ответ шлюза = запущен; ошибка соединения = нет."""
    import aiohttp

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{omniroute_root(base_url)}/api/health") as response:
                return response.status < 500
    except Exception:
        return False


def start_omniroute(command: list[str], port: int) -> None:
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [*command, "serve", "--daemon", "--no-open", "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


async def ensure_omniroute(
    base_url: str,
    *,
    autostart: bool = True,
    wait_sec: float = _START_WAIT_SEC,
) -> OmniRouteStatus:
    if await probe_omniroute(base_url):
        return OmniRouteStatus(ok=True)

    host = (urlparse(base_url or "").hostname or "127.0.0.1").lower()
    if not autostart or host not in _LOCAL_HOSTS:
        return OmniRouteStatus(ok=False, message=omniroute_setup_guide(base_url))

    global _start_lock
    if _start_lock is None:
        _start_lock = asyncio.Lock()
    async with _start_lock:
        # Пока ждали замок, шлюз мог поднять параллельный запрос.
        if await probe_omniroute(base_url):
            return OmniRouteStatus(ok=True, started=True)

        command = find_omniroute_command()
        if not command:
            return OmniRouteStatus(
                ok=False,
                message=omniroute_setup_guide(base_url, "Команда omniroute не найдена на этом ПК."),
            )
        try:
            start_omniroute(command, _port_of(base_url))
        except OSError as exc:
            return OmniRouteStatus(
                ok=False,
                message=omniroute_setup_guide(base_url, f"Не удалось запустить OmniRoute: {exc}"),
            )

        deadline = time.monotonic() + wait_sec
        while time.monotonic() < deadline:
            await asyncio.sleep(1.0)
            if await probe_omniroute(base_url):
                return OmniRouteStatus(
                    ok=True,
                    started=True,
                    message=f"OmniRoute запущен автоматически ({omniroute_root(base_url)}).",
                )
        return OmniRouteStatus(
            ok=False,
            message=omniroute_setup_guide(
                base_url,
                f"Запустил omniroute, но шлюз не ответил за {int(wait_sec)} с.",
            ),
        )
