"""TDD: импорт моделей из системной Ollama в CoreX."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from core.desktop_ollama_bridge import (
    collect_manifest_digests,
    import_model_from_desktop,
    parse_model_ref,
)
from core.ollama_model_service import catalog_install_status


def test_parse_model_ref():
    assert parse_model_ref("qwen2.5-coder:7b") == ("qwen2.5-coder", "7b")
    assert parse_model_ref("phi3:mini") == ("phi3", "mini")


def test_collect_manifest_digests_reads_layers():
    manifest = {
        "config": {"digest": "sha256:abc"},
        "layers": [{"digest": "sha256:def"}],
    }
    digests = collect_manifest_digests(json.dumps(manifest))
    assert digests == {"sha256:abc", "sha256:def"}


def test_catalog_install_status_marks_desktop_only_as_needs_import():
    rows = catalog_install_status([], desktop_installed=[{"name": "qwen2.5-coder:7b"}])
    by_id = {row["id"]: row for row in rows}
    assert by_id["ollama-qwen"]["installed"] is True
    assert by_id["ollama-qwen"]["installed_in_desktop"] is True
    assert by_id["ollama-qwen"]["installed_in_corex"] is False
    assert by_id["ollama-qwen"]["needs_import"] is True


def test_import_model_from_desktop_copies_manifest_and_blob(tmp_path, monkeypatch):
    desktop_root = tmp_path / "desktop"
    corex_root = tmp_path / "corex"
    manifest_dir = (
        desktop_root
        / "manifests"
        / "registry.ollama.ai"
        / "library"
        / "qwen2.5-coder"
    )
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / "7b"
    manifest_path.write_text(
        json.dumps(
            {
                "config": {"digest": "sha256:cfg"},
                "layers": [{"digest": "sha256:layer"}],
            }
        ),
        encoding="utf-8",
    )
    desktop_blobs = desktop_root / "blobs"
    desktop_blobs.mkdir()
    (desktop_blobs / "sha256-cfg").write_bytes(b"cfg")
    (desktop_blobs / "sha256-layer").write_bytes(b"layer-data")

    monkeypatch.setattr(
        "core.desktop_ollama_bridge.resolve_desktop_ollama_models_dir",
        lambda: desktop_root,
    )
    monkeypatch.setattr(
        "core.desktop_ollama_bridge.resolve_ollama_models_dir",
        lambda: corex_root,
    )

    result = import_model_from_desktop("qwen2.5-coder:7b")
    assert result["success"] is True
    assert (corex_root / "blobs" / "sha256-layer").read_bytes() == b"layer-data"
    assert (
        corex_root
        / "manifests"
        / "registry.ollama.ai"
        / "library"
        / "qwen2.5-coder"
        / "7b"
    ).is_file()


@pytest.mark.asyncio
async def test_get_models_snapshot_includes_desktop_models(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_model_service.list_installed_models",
        AsyncMock(return_value={"success": True, "models": []}),
    )
    monkeypatch.setattr(
        "core.ollama_model_service.list_desktop_ollama_models",
        AsyncMock(return_value={"success": True, "models": [{"name": "qwen2.5-coder:7b"}]}),
    )

    from core.ollama_model_service import get_models_snapshot

    snapshot = await get_models_snapshot()
    qwen = next(row for row in snapshot["catalog"] if row["id"] == "ollama-qwen")
    assert qwen["needs_import"] is True
    assert snapshot["desktop_models"] == [{"name": "qwen2.5-coder:7b"}]
