"""Tests for OpenRouter free-model auto-fallback."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.online_api_client import OPENROUTER_FREE_FALLBACK_MODELS, OnlineApiClient


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_complete_switches_to_openrouter_free_on_404():
    client = OnlineApiClient(
        model_name="meta-llama/llama-3.3-70b-instruct:free",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-test",
        api_type="openai",
    )
    switched: list[tuple[str, str]] = []
    client.on_model_switched = lambda old, new: switched.append((old, new))

    unavailable_body = json.dumps(
        {
            "error": {
                "message": (
                    "This model is unavailable for free. The paid version is available now "
                    "- use this slug instead: meta-llama/llama-3.3-70b-instruct"
                )
            }
        }
    )
    success_payload = {
        "choices": [{"message": {"content": '{"status":"done","message":"ok"}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    response_404 = MagicMock()
    response_404.status = 404
    response_404.text = AsyncMock(return_value=unavailable_body)
    response_404.__aenter__ = AsyncMock(return_value=response_404)
    response_404.__aexit__ = AsyncMock(return_value=None)

    response_ok = MagicMock()
    response_ok.status = 200
    response_ok.json = AsyncMock(return_value=success_payload)
    response_ok.__aenter__ = AsyncMock(return_value=response_ok)
    response_ok.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.post = MagicMock(side_effect=[response_404, response_ok])
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with patch("core.online_api_client.aiohttp.ClientSession", return_value=session):
        result = await client.chat_complete("sys", "user task")

    assert "done" in result
    assert client.model_name == "openrouter/free"
    assert switched == [("meta-llama/llama-3.3-70b-instruct:free", "openrouter/free")]
    notices = client.consume_model_switch_notices()
    assert notices and "openrouter/free" in notices[0]
    assert OPENROUTER_FREE_FALLBACK_MODELS[0] == "openrouter/free"


@pytest.mark.unit
def test_trim_history_used_in_build_messages():
    client = OnlineApiClient(
        model_name="openrouter/free",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk",
    )
    history = [{"role": "user", "content": "x" * 8000}] + [
        {"role": "assistant", "content": f"a{i}"} for i in range(20)
    ]
    messages = client._build_messages("sys", "ask", history)
    # system + trimmed history + user
    assert len(messages) <= 1 + 8 + 1
    assert all(len(m["content"]) <= 2600 for m in messages if m["role"] != "system")


def test_temporary_model_restores_selected():
    client = OnlineApiClient(
        model_name="google/gemma-4-31b-it:free",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk",
    )
    with client.temporary_model("openai/gpt-oss-20b:free"):
        assert client.model_name == "openai/gpt-oss-20b:free"
    assert client.model_name == "google/gemma-4-31b-it:free"
