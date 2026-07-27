"""Unit tests for Gemini model name normalization."""

import pytest

from core.gemini_models import DEFAULT_GEMINI_MODEL, normalize_gemini_model_name


@pytest.mark.unit
class TestGeminiModels:
    def test_default_when_empty(self):
        assert normalize_gemini_model_name("") == DEFAULT_GEMINI_MODEL

    def test_maps_deprecated_15_flash(self):
        assert normalize_gemini_model_name("gemini-1.5-flash") == "gemini-2.5-flash"

    def test_maps_shutdown_20_flash(self):
        assert normalize_gemini_model_name("gemini-2.0-flash") == "gemini-2.5-flash"

    def test_keeps_current_model(self):
        assert normalize_gemini_model_name("gemini-2.5-flash") == "gemini-2.5-flash"
        assert normalize_gemini_model_name("gemini-3.5-flash") == "gemini-3.5-flash"
