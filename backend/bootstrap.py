"""Shared startup helpers for CoreX backend."""

import asyncio
import os
import socket
import sys
import time
from pathlib import Path

from aiohttp import web

from core.file_service import FileService
from core.mcp_manager import MCPManager
from core.ollama_client import OllamaClient
from core.orchestrator import CoreXOrchestrator
from core.ai_provider_service import default_provider_service
from core.ai_runtime_service import default_runtime_service
from core.online_api_client import OnlineApiClient
from core.ws_server import WebSocketServer

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class HeadlessGUI:
    def __init__(self, project_dir: str):
        self.project_dir = project_dir

    def print_log(self, source: str, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{source}] {text}", flush=True)


def default_project_dir() -> str:
    return str(PROJECT_ROOT.resolve())


def find_free_port(start_port: int = 8000, host: str = "127.0.0.1", max_port: int = 8100) -> int:
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start_port}-{max_port - 1}")


def wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


async def _try_connect_mcp(mcp: MCPManager, project_dir: str) -> None:
    """Optional MCP filesystem — failures do not block the app."""
    try:
        await mcp.connect_server(
            server_name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", project_dir],
        )
    except Exception as exc:
        print(f"[MCP] filesystem unavailable, using local file IO: {exc}", flush=True)


async def run_backend_server(
    project_dir: str,
    port: int,
    host: str = "127.0.0.1",
    enable_mcp: bool = False,
) -> tuple[web.AppRunner, CoreXOrchestrator]:
    """Start WebSocket + HTTP API. Returns runner for cleanup."""
    gui = HeadlessGUI(project_dir=project_dir)

    ollama = OllamaClient()
    online = OnlineApiClient()
    provider_service = default_provider_service(project_root=PROJECT_ROOT)
    runtime_service = default_runtime_service(project_root=PROJECT_ROOT)
    runtime_service.normalize_startup_mode()
    runtime_service.apply_active_client(ollama, online)
    mcp = MCPManager()
    file_service = FileService(mcp, project_dir, use_mcp=enable_mcp)
    orchestrator = CoreXOrchestrator(ollama, mcp, gui, file_service, provider_service, runtime_service, online)
    # Активный проект задаётся из UI через /api/files/set_root или project_root в WebSocket.
    orchestrator.project_root = None

    ws_server = WebSocketServer(orchestrator, file_service)
    app = ws_server.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    gui.print_log("System", f"WebSocket: ws://{host}:{port}/ws")
    gui.print_log("System", f"File API: http://{host}:{port}/api/files")
    gui.print_log("System", f"Project root: {project_dir}")

    if enable_mcp:
        gui.print_log("System", "Connecting MCP filesystem (optional)...")
        asyncio.create_task(_try_connect_mcp(mcp, project_dir))
    else:
        gui.print_log("System", "Using local file IO (stable mode).")

    gui.print_log("System", "CoreX backend ready.")
    print(f"COREX_READY port={port}", flush=True)

    if runtime_service.get_mode() == "local":
        asyncio.create_task(_warmup_ollama_server(gui, runtime_service))

    return runner, orchestrator


async def _warmup_ollama_server(gui: HeadlessGUI, runtime_service) -> None:
    from core.ollama_lifecycle import ensure_ollama_serve_running

    preset = runtime_service.local_service.get_selected_preset()
    ok = await ensure_ollama_serve_running()
    if ok:
        gui.print_log(
            "System",
            f"Ollama: сервер запущен · выбрана {preset.model_name} (загрузится при генерации)",
        )
    else:
        gui.print_log("System", "Ollama: сервер не запущен — установите ollama.com")


def configure_stdio_utf8() -> None:
    """Windows: избежать UnicodeEncodeError (charmap) в логах и subprocess."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def configure_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
