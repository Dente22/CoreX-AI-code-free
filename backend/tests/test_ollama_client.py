"""TDD: оптимизация OllamaClient под профиль устройства."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.device_profile import DeviceProfile
from core.ollama_client import OllamaClient


@pytest.mark.parametrize(
    ("tier", "expected_ctx"),
    [("low", 4096), ("medium", 6144), ("high", 8192)],
)
def test_device_profile_ollama_num_ctx(tier, expected_ctx):
    profile = DeviceProfile(
        tier=tier,
        cpu_cores=8,
        ram_gb=16.0,
        ram_available_gb=8.0,
        platform="Windows",
        machine="AMD64",
        recommended_limits={},
    )
    assert profile.ollama_num_ctx() == expected_ctx


@pytest.mark.asyncio
async def test_ollama_client_uses_lifecycle_not_local_popen(monkeypatch):
    ensure = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_client.ensure_ollama_serve_running", ensure)

    client = OllamaClient()
    ok = await client.ensure_ready()
    assert ok is True
    ensure.assert_awaited_once()


def test_ollama_client_runtime_options_respects_tier(monkeypatch):
    profile = DeviceProfile(
        tier="low",
        cpu_cores=4,
        ram_gb=8.0,
        ram_available_gb=3.0,
        platform="Windows",
        machine="AMD64",
        recommended_limits={},
    )
    monkeypatch.setattr("core.ollama_client.detect_device_profile", lambda: profile)
    client = OllamaClient()
    options = client._runtime_options(temperature=0.2)
    assert options["num_ctx"] == 4096
    assert options["num_batch"] == 128


def test_context_overflow_detector():
    body = '{"error":{"type":"exceed_context_size_error","message":"request exceeds the available context size"}}'
    assert OllamaClient._is_context_overflow_error(body) is True


def test_compact_messages_keeps_tail_and_trims():
    client = OllamaClient()
    messages = [
        {"role": "system", "content": "S" * 6000},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "U" * 7000},
    ]
    compact = client._compact_messages(messages, aggressive=False)
    assert compact[0]["role"] == "system"
    assert len(compact[0]["content"]) < 3000
    assert compact[-1]["role"] == "user"
    assert len(compact[-1]["content"]) < 4200
    assert len(compact) <= 6
