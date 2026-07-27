"""CLI: запустить сервер Ollama CoreX до старта UI."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

COREX_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = COREX_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


async def warmup_ollama_server() -> int:
    from core.ai_runtime_service import default_runtime_service
    from core.ollama_lifecycle import ensure_ollama_serve_running

    runtime = default_runtime_service(project_root=COREX_ROOT)
    if runtime.get_mode() != "local":
        print("[CoreX] Online mode — Ollama warmup skipped")
        return 0

    preset = runtime.local_service.get_selected_preset()
    ok = await ensure_ollama_serve_running()
    if ok:
        print("[CoreX] Ollama server ready on 127.0.0.1:11435")
        print(f"[CoreX] Selected model: {preset.model_name} (loads on first chat)")
        return 0

    print("[CoreX] Ollama not available — install from https://ollama.com/download")
    return 1


def main() -> int:
    from bootstrap import configure_event_loop_policy, configure_stdio_utf8

    configure_stdio_utf8()
    configure_event_loop_policy()
    return asyncio.run(warmup_ollama_server())


if __name__ == "__main__":
    raise SystemExit(main())
