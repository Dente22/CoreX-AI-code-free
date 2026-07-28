"""TDD: прямая загрузка GGUF в папку CoreX."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.model_direct_download import (
    DIRECT_MODEL_SOURCES,
    cleanup_direct_download,
    direct_download_curl_command,
    has_direct_source,
    resolve_gguf_path,
    resolve_models_storage_dir,
)
from core.ollama_pull_progress import apply_http_download_progress, init_pull_progress


def test_resolve_models_storage_dir_under_corex(tmp_path, monkeypatch):
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)
    path = resolve_models_storage_dir()
    assert path == tmp_path / "models"
    assert path.is_dir()


def test_all_catalog_providers_have_direct_source():
    for provider_id in ("ollama-lite", "ollama-qwen", "ollama-claude"):
        assert has_direct_source(provider_id)
        cmd = direct_download_curl_command(provider_id)
        assert cmd.startswith("curl -L")
        assert "-sS" in cmd
        assert DIRECT_MODEL_SOURCES[provider_id].url in cmd


def test_build_curl_download_argv_uses_silent_flags(tmp_path):
    from core.model_direct_download import build_curl_download_argv

    argv = build_curl_download_argv("curl", tmp_path / "m.gguf.part", "https://example.com/m.gguf")
    assert "-sS" in argv
    assert "-f" in argv
    assert "-C" in argv


def test_cleanup_direct_download(tmp_path, monkeypatch):
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)
    target = resolve_models_storage_dir() / "ollama-lite"
    target.mkdir(parents=True)
    (target / "phi3-mini-q4.gguf").write_bytes(b"gguf")
    result = cleanup_direct_download("ollama-lite")
    assert result["removed"] is True
    assert not target.exists()


def test_apply_http_download_progress_sets_percent():
    state = init_pull_progress("job", "phi3:mini", "ollama-lite")
    apply_http_download_progress(state, 500_000_000, 1_000_000_000)
    assert state["status"] == "downloading"
    assert state["percent"] == 50.0
    assert state["indeterminate"] is False
    assert "Hugging Face" in state["message"]


@pytest.mark.asyncio
async def test_start_pull_provider_model_uses_direct_download(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_model_service.ensure_corex_ollama_running",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "core.ollama_model_service.start_direct_provider_pull",
        AsyncMock(return_value={"success": True, "started": True, "download_method": "direct"}),
    )

    from core.ollama_model_service import start_pull_provider_model

    result = await start_pull_provider_model("ollama-lite")
    assert result["success"] is True
    assert result.get("download_method") == "direct"


@pytest.mark.asyncio
async def test_download_and_import_direct_success(tmp_path, monkeypatch):
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)
    monkeypatch.setattr(
        "core.ollama_model_service.COREX_ROOT",
        tmp_path,
    )

    async def fake_http_download(url, dest, *, job_id, size_hint):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"gguf-data" * 1000)

    monkeypatch.setattr(
        "core.model_direct_download.download_model_file",
        fake_http_download,
    )
    monkeypatch.setattr(
        "core.model_direct_download.ensure_ollama_serve_running",
        AsyncMock(return_value=True),
    )

    async def fake_prepare(provider_id, model_name):
        return {"success": True}

    async def fake_import(model_name, gguf_path, *, job_id):
        return {"success": True, "output": "created"}

    monkeypatch.setattr(
        "core.model_direct_download.import_gguf_with_retry",
        fake_import,
    )

    from core.model_direct_download import download_and_import_direct
    from core.ollama_pull_progress import init_pull_progress

    job_id = "ollama-lite"
    init_pull_progress(job_id, "phi3:mini", job_id)

    result = await download_and_import_direct(
        "ollama-lite",
        job_id,
        prepare_pull=fake_prepare,
    )
    assert result["success"] is True
    assert resolve_gguf_path("ollama-lite").is_file()


@pytest.mark.asyncio
async def test_file_ready_skips_download_and_sets_import_progress(tmp_path, monkeypatch):
    monkeypatch.setattr("core.model_direct_download.COREX_ROOT", tmp_path)

    dest = resolve_gguf_path("ollama-lite")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"g" * 4096)

    async def fake_prepare(provider_id, model_name):
        return {"success": True, "file_ready": True, "partial_bytes": 4096}

    import_called = {"value": False}
    captured: dict = {}

    async def fake_import(model_name, gguf_path, *, job_id):
        import_called["value"] = True
        from core.ollama_pull_progress import get_pull_progress_state

        state = get_pull_progress_state(job_id)
        if state is not None:
            captured["progress"] = dict(state)
        return {"success": True, "output": "created"}

    monkeypatch.setattr(
        "core.model_direct_download.download_model_file",
        AsyncMock(side_effect=AssertionError("download should be skipped")),
    )
    monkeypatch.setattr(
        "core.model_direct_download.import_gguf_with_retry",
        fake_import,
    )

    from core.model_direct_download import download_and_import_direct
    from core.ollama_pull_progress import init_pull_progress

    job_id = "file-ready-job"
    init_pull_progress(job_id, "phi3:mini", "ollama-lite", download_method="direct")

    result = await download_and_import_direct(
        "ollama-lite",
        job_id,
        prepare_pull=fake_prepare,
    )
    progress = captured.get("progress") or {}

    assert result["success"] is True
    assert import_called["value"] is True
    assert progress.get("status") == "importing"
    assert progress.get("percent") == 0.0
    assert progress.get("percent_label") == "0%"
    assert progress.get("completed_bytes") == 0
    assert progress.get("total_bytes") == 4096
