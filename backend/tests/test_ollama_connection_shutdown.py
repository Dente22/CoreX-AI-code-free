"""TDD: гонка watchdog / prepare и ошибки подключения к Ollama."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.ollama_client import OllamaClient, format_ollama_connection_error
from core.ollama_lifecycle import (
    begin_ollama_generation,
    is_generation_active,
    reset_ollama_lifecycle_state,
    should_sleep_ollama,
)
from core.ollama_model_session import warmup_ollama_model


def test_format_ollama_connection_error_for_connect_refused():
    exc = OSError("Cannot connect to host 127.0.0.1:11435 ssl:default [Connect call failed ('127.0.0.1', 11435)]")
    msg = format_ollama_connection_error(exc, model_name="llama3.1:8b")
    assert "ollama" in msg.lower()
    assert "Cannot connect to host" not in msg


@pytest.mark.asyncio
async def test_warmup_returns_friendly_connection_error(monkeypatch):
    class BoomSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            class Resp:
                async def __aenter__(self):
                    raise OSError(
                        "Cannot connect to host 127.0.0.1:11435 ssl:default "
                        "[Connect call failed ('127.0.0.1', 11435)]"
                    )

                async def __aexit__(self, *args):
                    return False

            return Resp()

    monkeypatch.setattr("core.ollama_model_session.aiohttp.ClientSession", lambda *args, **kwargs: BoomSession())

    result = await warmup_ollama_model("llama3.1:8b", "http://127.0.0.1:11435")

    assert result.get("success") is False
    assert "ollama" in str(result.get("error") or "").lower()
    assert "Cannot connect to host" not in str(result.get("error") or "")


@pytest.mark.asyncio
async def test_prepare_retries_after_connection_failure(monkeypatch):
    reset_ollama_lifecycle_state()
    attempts = {"count": 0}

    async def fake_ensure():
        attempts["count"] += 1
        return attempts["count"] >= 2

    recover = AsyncMock()
    monkeypatch.setattr("core.ollama_client.ensure_ollama_serve_running", fake_ensure)
    monkeypatch.setattr(
        "core.ollama_client.verify_model_installed",
        AsyncMock(return_value={"success": True, "installed": True}),
    )
    monkeypatch.setattr(
        "core.ollama_client.activate_ollama_model",
        AsyncMock(return_value={"success": True, "model_name": "phi3:mini"}),
    )
    monkeypatch.setattr(OllamaClient, "_recover_from_disconnect", recover)

    client = OllamaClient(model_name="phi3:mini")
    ok = await client.prepare_for_generation()

    assert ok is True
    assert attempts["count"] == 2
    recover.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_stream_holds_generation_guard_before_prepare(monkeypatch):
    reset_ollama_lifecycle_state()
    generation_during_prepare: list[bool] = []

    async def fake_prepare(self):
        generation_during_prepare.append(is_generation_active())
        return True

    async def fake_stream(self, payload):
        yield "ok"

    monkeypatch.setattr(OllamaClient, "prepare_for_generation", fake_prepare)
    monkeypatch.setattr(OllamaClient, "_stream_payload", fake_stream)

    client = OllamaClient()
    chunks = [chunk async for chunk in client.generate_stream("sys", "hi")]

    assert chunks == ["ok"]
    assert generation_during_prepare == [True]
    assert is_generation_active() is False


@pytest.mark.asyncio
async def test_watchdog_will_not_sleep_while_generation_guard_active(monkeypatch):
    reset_ollama_lifecycle_state()
    begin_ollama_generation()
    assert should_sleep_ollama(now=10_000.0) is False


@pytest.mark.asyncio
async def test_activate_already_loaded_requires_running_server(monkeypatch):
    from core.ollama_model_session import activate_ollama_model, get_active_ollama_model

    warmup = AsyncMock(return_value={"success": True})
    reachable = AsyncMock(return_value=False)
    monkeypatch.setattr("core.ollama_model_session.warmup_ollama_model", warmup)
    monkeypatch.setattr("core.ollama_model_session._is_ollama_reachable", reachable)

    await activate_ollama_model("phi3:mini", "http://127.0.0.1:11435", preload=True)
    result = await activate_ollama_model("phi3:mini", "http://127.0.0.1:11435", preload=True)

    assert result.get("success") is False
    assert "Ollama не отвечает" in str(result.get("error") or "")
    assert get_active_ollama_model() is None
