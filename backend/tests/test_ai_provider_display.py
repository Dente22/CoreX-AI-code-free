"""Unit tests for AI provider display helpers used in chat UI."""

import pytest

from core.ai_provider_catalog import get_preset, list_presets


@pytest.mark.unit
class TestAiProviderCatalogDisplay:
    def test_all_presets_have_short_friendly_names(self):
        names = {preset.id: preset.name for preset in list_presets()}
        assert "Qwen" in names["ollama-qwen"]
        assert "Qwen" in names["ollama-qwen-7b"]
        assert "Qwen" in names["ollama-qwen-14b"]
        assert "Llama" in names["ollama-claude"] or "Claude" in names["ollama-claude"]
        assert "Phi" in names["ollama-lite"]

    def test_tiers_cover_all_performance_levels(self):
        tiers = {preset.tier for preset in list_presets()}
        assert tiers == {"low", "medium", "high"}

    def test_lite_is_lightest_requirement(self):
        lite = get_preset("ollama-lite")
        others = [get_preset("ollama-qwen"), get_preset("ollama-claude")]
        assert all(lite.min_ram_gb <= preset.min_ram_gb for preset in others)
