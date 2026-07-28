"""TDD: устойчивая загрузка GGUF с докачкой."""

from __future__ import annotations

from pathlib import Path
import contextlib

import aiohttp
import pytest

from core.model_direct_download import (
    build_download_headers,
    friendly_download_error,
    is_retryable_download_error,
    resolve_resume_byte,
)
from core.ollama_pull_progress import friendly_pull_error, init_pull_progress


def test_resolve_resume_byte_from_partial_file(tmp_path):
    part = tmp_path / "model.gguf.part"
    part.write_bytes(b"x" * 28_131_838)
    assert resolve_resume_byte(part) == 28_131_838


def test_get_pull_progress_state_is_mutable():
    from core.ollama_pull_progress import get_pull_progress, get_pull_progress_state, init_pull_progress

    init_pull_progress("job-x", "phi3:mini", "ollama-lite", download_method="direct")
    state = get_pull_progress_state("job-x")
    assert state is not None
    state["total_bytes"] = 4_700_000_000
    state["status"] = "downloading"
    state["indeterminate"] = False

    snapshot = get_pull_progress("job-x")
    assert snapshot is not None
    assert snapshot["total_bytes"] == 4_700_000_000
    assert snapshot["status"] == "downloading"


def test_resolve_download_urls_adds_hf_mirror():
    from core.model_direct_download import resolve_download_urls

    urls = resolve_download_urls(
        "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/file.gguf"
    )
    assert len(urls) == 2
    assert "hf-mirror.com" in urls[1]


def test_resolve_resume_byte_zero_when_missing(tmp_path):
    assert resolve_resume_byte(tmp_path / "missing.gguf.part") == 0


def test_build_download_headers_adds_range_for_resume():
    headers = build_download_headers(1_000_000)
    assert headers["Range"] == "bytes=1000000-"
    assert "User-Agent" in headers


def test_build_download_headers_without_resume():
    headers = build_download_headers(0)
    assert "Range" not in headers


def test_friendly_pull_error_for_content_length():
    raw = (
        "Response payload is not completed: <ContentLengthError: 400, "
        "message='Not enough data to satisfy content length header "
        "(received 28131838 of 4683073536 bytes).'>"
    )
    msg = friendly_pull_error(raw)
    assert "снова" in msg.lower()


def test_friendly_download_error_wraps_content_length():
    exc = aiohttp.ClientPayloadError("Not enough data to satisfy content length header")
    msg = friendly_download_error(exc)
    assert "снова" in msg.lower()


def test_is_retryable_download_error_for_content_length():
    exc = aiohttp.ClientPayloadError("Not enough data to satisfy content length header")
    assert is_retryable_download_error(exc) is True


@pytest.mark.asyncio
async def test_http_download_retries_after_stream_error(tmp_path, monkeypatch):
    from core import model_direct_download as mdd

    monkeypatch.setattr(mdd, "MAX_DOWNLOAD_ATTEMPTS", 2)
    monkeypatch.setattr(mdd, "RETRY_DELAY_SEC", 0)

    dest = tmp_path / "models" / "ollama-lite" / "phi3-mini-q4.gguf"
    part = dest.with_suffix(dest.suffix + ".part")
    attempts = {"count": 0}

    class FakeContent:
        def __init__(self, body: bytes):
            self._body = body

        def iter_chunked(self, _size):
            return self._stream()

        async def _stream(self):
            attempts["count"] += 1
            if attempts["count"] == 1:
                yield b"x" * 1_024
                raise aiohttp.ClientPayloadError("Not enough data to satisfy content length header")
            yield self._body

    class FakeResponse:
        def __init__(self, status: int, body: bytes, *, total: int):
            self.status = status
            self.headers = {
                "Content-Length": str(len(body)),
                "Content-Range": f"bytes 0-{len(body) - 1}/{total}",
            }
            self.content = FakeContent(body)

        async def text(self):
            return ""

    get_calls = {"n": 0}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            get_calls["n"] += 1
            if get_calls["n"] > 1:
                with contextlib.suppress(OSError):
                    part.unlink(missing_ok=True)
            return FakeContext(FakeResponse(206, b"complete-data", total=13))

    class FakeContext:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mdd.aiohttp, "ClientSession", lambda *a, **k: FakeSession())
    init_pull_progress("test-job", "phi3:mini", "ollama-lite")

    await mdd._http_download_to_file(
        "https://example.com/model.gguf",
        dest,
        job_id="test-job",
        size_hint=13,
    )

    assert dest.is_file()
    assert dest.read_bytes() == b"complete-data"
    assert attempts["count"] == 2
    assert not part.exists()
