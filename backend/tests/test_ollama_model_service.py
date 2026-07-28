"""TDD: управление моделями Ollama в папке CoreX."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ollama_model_service import (
    COREX_OLLAMA_BASE_URL,
    catalog_install_status,
    cleanup_partial_downloads,
    merge_ollama_env,
    model_name_matches,
    resolve_ollama_models_dir,
    scrub_orphan_blobs,
)


def test_resolve_ollama_models_dir_under_corex(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    path = resolve_ollama_models_dir()
    assert path == tmp_path / "ollama_models"
    assert path.is_dir()


def test_cleanup_partial_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    blobs = resolve_ollama_models_dir() / "blobs"
    blobs.mkdir(parents=True)
    partial = blobs / "sha256-deadbeef-partial-0"
    partial.write_bytes(b"partial")
    result = cleanup_partial_downloads()
    assert result["count"] == 1
    assert not partial.exists()


def test_scrub_orphan_blobs(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    blobs = resolve_ollama_models_dir() / "blobs"
    blobs.mkdir(parents=True)
    orphan = blobs / "sha256-abc"
    orphan.write_bytes(b"data")
    result = scrub_orphan_blobs()
    assert result["count"] == 1
    assert not orphan.exists()


def test_merge_ollama_env_sets_models_and_host(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", tmp_path)
    env = merge_ollama_env({"PATH": "/bin"})
    assert env["PATH"] == "/bin"
    assert env["OLLAMA_MODELS"] == str(tmp_path / "ollama_models")
    assert "11435" in env["OLLAMA_HOST"]
    assert env["OLLAMA_KEEP_ALIVE"] == "10m"


@pytest.mark.parametrize(
    ("installed", "target", "expected"),
    [
        ("phi3:mini", "phi3:mini", True),
        ("llama3.1:8b", "llama3.1:8b", True),
        ("qwen2.5-coder:7b", "qwen2.5-coder:7b", True),
        ("phi3:mini", "llama3.1:8b", False),
    ],
)
def test_model_name_matches(installed, target, expected):
    assert model_name_matches(installed, target) is expected


def test_catalog_install_status_marks_installed_models():
    installed = [{"name": "phi3:mini"}]
    rows = catalog_install_status(installed)
    by_id = {row["id"]: row["installed_in_corex"] for row in rows}
    assert by_id["ollama-lite"] is True
    assert by_id["ollama-qwen"] is False


@pytest.mark.asyncio
async def test_get_models_snapshot_uses_tags_api(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_model_service._is_server_running",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "core.ollama_model_service.list_desktop_ollama_models",
        AsyncMock(return_value={"success": True, "models": []}),
    )

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self):
            return {"models": [{"name": "phi3:mini"}]}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url):
            assert url.endswith("/api/tags")
            return FakeResponse()

    monkeypatch.setattr("core.ollama_model_service.aiohttp.ClientSession", FakeSession)

    from core.ollama_model_service import get_models_snapshot

    snapshot = await get_models_snapshot()
    assert snapshot["success"] is True
    assert snapshot["models"] == [{"name": "phi3:mini"}]
    assert snapshot["base_url"] == COREX_OLLAMA_BASE_URL
    assert any(row["id"] == "ollama-lite" and row["installed_in_corex"] for row in snapshot["catalog"])


@pytest.mark.asyncio
async def test_pull_provider_model_unknown_id():
    from core.ollama_model_service import pull_provider_model

    result = await pull_provider_model("missing")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_pull_model_runs_ollama_api(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_model_service.ensure_corex_ollama_running",
        AsyncMock(return_value=True),
    )

    async def fake_pull(model_name: str, job_id: str):
        return {
            "success": True,
            "model_name": model_name,
            "job_id": job_id,
            "progress": {"done": True, "success": True, "percent": 100},
        }

    monkeypatch.setattr("core.ollama_model_service._pull_model_via_api", fake_pull)

    from core.ollama_model_service import pull_model

    result = await pull_model("phi3:mini")
    assert result["success"] is True
