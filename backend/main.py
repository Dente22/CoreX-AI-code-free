"""
CoreX backend entry point.

Modes:
  --server   API + WebSocket only (used by Electron launcher)
  --gui      Legacy Tkinter UI (fallback when frontend is unavailable)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bootstrap import (  # noqa: E402
    configure_event_loop_policy,
    configure_stdio_utf8,
    default_project_dir,
    find_free_port,
    run_backend_server,
)
from ui.gui_window import CoreXGUI  # noqa: E402

_loop: asyncio.AbstractEventLoop | None = None
_orchestrator = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CoreX backend")
    parser.add_argument(
        "--mode",
        choices=("server", "gui"),
        default="server",
        help="server = API only; gui = legacy Tkinter shell",
    )
    parser.add_argument("--port", type=int, default=0, help="HTTP port (0 = auto)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--project-dir", default=None, help="Default project folder")
    parser.add_argument(
        "--enable-mcp",
        action="store_true",
        help="Try MCP filesystem (optional; local IO is default)",
    )
    return parser.parse_args()


def _start_background_loop() -> threading.Thread:
    global _loop

    def _run() -> None:
        global _loop
        configure_event_loop_policy()
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    while _loop is None:
        time.sleep(0.01)
    return thread


async def _serve_forever(args: argparse.Namespace) -> None:
    project_dir = os.path.abspath(args.project_dir or default_project_dir())
    port = args.port if args.port > 0 else find_free_port(8000, host=args.host)

    runner, _orchestrator_ref = await run_backend_server(
        project_dir=project_dir,
        port=port,
        host=args.host,
        enable_mcp=args.enable_mcp,
    )

    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        await runner.cleanup()


def _run_server_mode(args: argparse.Namespace) -> None:
    configure_event_loop_policy()
    try:
        asyncio.run(_serve_forever(args))
    except KeyboardInterrupt:
        print("\n[CoreX] Backend stopped.")


def _run_gui_mode(args: argparse.Namespace) -> None:
    global _orchestrator

    project_dir = os.path.abspath(args.project_dir or default_project_dir())
    port = args.port if args.port > 0 else find_free_port(8000, host=args.host)

    _start_background_loop()

    ready = threading.Event()

    async def _init() -> None:
        global _orchestrator
        try:
            _, _orchestrator = await run_backend_server(
                project_dir=project_dir,
                port=port,
                host=args.host,
                enable_mcp=args.enable_mcp,
            )
        finally:
            ready.set()

    assert _loop is not None
    asyncio.run_coroutine_threadsafe(_init(), _loop)

    if not ready.wait(timeout=30):
        print("[CoreX] Backend init timed out.", file=sys.stderr)

    def on_submit(task_text: str) -> None:
        if _orchestrator and _loop:
            asyncio.run_coroutine_threadsafe(_orchestrator.execute_task(task_text), _loop)

    gui = CoreXGUI(project_dir=project_dir, on_submit_callback=on_submit)
    gui.mainloop()


def main() -> None:
    configure_stdio_utf8()
    args = _parse_args()
    if args.mode == "gui":
        _run_gui_mode(args)
    else:
        _run_server_mode(args)


if __name__ == "__main__":
    main()
