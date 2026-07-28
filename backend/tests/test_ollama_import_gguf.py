"""TDD: импорт GGUF в Ollama после прямой загрузки."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.model_direct_download import format_ollama_import_error, is_ollama_connection_error
from core.terminal_output import sanitize_terminal_output


def test_is_ollama_connection_error_detects_refused():
    raw = 'Error: Post "http://127.0.0.1:11435/api/blobs/sha256:abc": dial tcp 127.0.0.1:11435: connectex: actively refused'
    assert is_ollama_connection_error(raw) is True


def test_format_ollama_import_error_is_human_readable():
    raw = (
        "gathering model components ⠋ gathering model components ⠙ "
        'Error: Post "http://127.0.0.1:11435/api/blobs/sha256:abc": connectex: actively refused'
    )
    msg = format_ollama_import_error(raw)
    assert "11435" in msg
    assert "gathering model components" not in msg
    assert "файл уже на диске" in msg.lower()


def test_sanitize_terminal_output_collapses_gathering_spinner():
    raw = "gathering model components ⠋ gathering model components ⠙\nError: something failed"
    cleaned = sanitize_terminal_output(raw)
    assert "gathering model components" not in cleaned
    assert "Error: something failed" in cleaned


@pytest.mark.asyncio
async def test_import_retry_continues_when_ensure_transiently_fails(monkeypatch, tmp_path):
    gguf = tmp_path / "m.gguf"
    gguf.write_bytes(b"x")

    monkeypatch.setattr(
        "core.model_direct_download.ensure_ollama_serve_running",
        AsyncMock(side_effect=[False, True]),
    )
    monkeypatch.setattr("core.model_direct_download.stop_ollama_serve", AsyncMock(return_value=True))

    calls = {"count": 0}

    async def fake_import(_model_name: str, _gguf_path: Path, *, job_id: str):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "success": False,
                "error": 'Error: Post "http://127.0.0.1:11435/api/blobs/sha256:abc": dial tcp 127.0.0.1:11435: connectex: actively refused',
                "output": "",
            }
        return {"success": True, "output": "created", "error": ""}

    monkeypatch.setattr("core.model_direct_download.import_gguf_to_ollama", fake_import)

    from core.model_direct_download import import_gguf_with_retry
    from core.ollama_pull_progress import init_pull_progress

    init_pull_progress("job", "qwen2.5-coder:7b", "ollama-qwen", download_method="direct")
    result = await import_gguf_with_retry("qwen2.5-coder:7b", gguf, job_id="job")

    assert result["success"] is True
    assert calls["count"] == 2
