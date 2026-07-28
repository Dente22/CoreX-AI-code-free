"""TDD: прямая загрузка не должна зависать на ollama pull/manifest."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.ollama_model_service import prepare_direct_provider_download, prepare_pull


@pytest.mark.asyncio
async def test_prepare_direct_skips_ollama_rm_and_prune(monkeypatch, tmp_path):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.ollama_model_service._is_server_running", AsyncMock(return_value=False))

    run_sync = MagicMock()
    monkeypatch.setattr("core.ollama_model_service._run_ollama_sync", run_sync)

    result = await prepare_direct_provider_download("ollama-qwen", "qwen2.5-coder:7b")

    assert result.get("success") is True
    run_sync.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_direct_detects_existing_gguf(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)

    gguf = tmp_path / "models" / "ollama-qwen" / "qwen2.5-coder-7b-q4_k_m.gguf"
    gguf.parent.mkdir(parents=True)
    gguf.write_bytes(b"x" * 12_000_000)

    result = await prepare_direct_provider_download("ollama-qwen", "qwen2.5-coder:7b")

    assert result.get("file_ready") is True


@pytest.mark.asyncio
async def test_prepare_direct_detects_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)

    part = tmp_path / "models" / "ollama-qwen" / "qwen2.5-coder-7b-q4_k_m.gguf.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"x" * 5_000_000)

    result = await prepare_direct_provider_download("ollama-qwen", "qwen2.5-coder:7b")

    assert result.get("partial_bytes") == 5_000_000


@pytest.mark.asyncio
async def test_prepare_pull_still_uses_ollama_cleanup(monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.cleanup_partial_downloads", lambda: {"count": 0})
    monkeypatch.setattr("core.ollama_model_service.ensure_corex_ollama_running", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "core.ollama_model_service.list_installed_models",
        AsyncMock(return_value={"models": []}),
    )
    run_sync = MagicMock(return_value={"success": True})
    monkeypatch.setattr("core.ollama_model_service._run_ollama_sync", run_sync)

    await prepare_pull("phi3:mini")

    assert run_sync.call_count >= 2
