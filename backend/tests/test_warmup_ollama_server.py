"""TDD: CLI warmup Ollama при запуске CoreX."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.warmup_ollama_server import warmup_ollama_server


@pytest.mark.asyncio
async def test_warmup_ollama_server_starts_in_local_mode(monkeypatch):
    preset = MagicMock()
    preset.model_name = "qwen2.5-coder:7b"
    runtime = MagicMock()
    runtime.get_mode.return_value = "local"
    runtime.local_service.get_selected_preset.return_value = preset

    ensure = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ai_runtime_service.default_runtime_service", lambda **_: runtime)
    monkeypatch.setattr("core.ollama_lifecycle.ensure_ollama_serve_running", ensure)

    code = await warmup_ollama_server()
    assert code == 0
    ensure.assert_awaited_once()


@pytest.mark.asyncio
async def test_warmup_ollama_server_skips_online_mode(monkeypatch):
    runtime = MagicMock()
    runtime.get_mode.return_value = "online"
    monkeypatch.setattr("core.ai_runtime_service.default_runtime_service", lambda **_: runtime)
    ensure = AsyncMock()
    monkeypatch.setattr("core.ollama_lifecycle.ensure_ollama_serve_running", ensure)

    code = await warmup_ollama_server()
    assert code == 0
    ensure.assert_not_called()
