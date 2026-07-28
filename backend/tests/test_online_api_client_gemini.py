"""Unit tests for Gemini URL building with model normalization."""

import pytest

from core.online_api_client import OnlineApiClient


@pytest.mark.unit
class TestOnlineApiClientGemini:
    def test_gemini_url_uses_normalized_model_name(self):
        client = OnlineApiClient(
            model_name="gemini-1.5-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key="test-key",
            api_type="gemini",
        )
        url = client._gemini_generate_url(stream=False)
        assert "models/gemini-2.5-flash:generateContent" in url
        assert "gemini-1.5-flash" not in url
