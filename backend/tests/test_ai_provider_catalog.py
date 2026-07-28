"""Unit tests for AI provider catalog — curated local model presets."""

import pytest

from core.ai_provider_catalog import (
    DEFAULT_PROVIDER_ID,
    get_preset,
    list_presets,
    list_preset_dicts,
    validate_provider_id,
)


@pytest.mark.unit
class TestAiProviderCatalog:
    def test_has_three_presets(self):
        presets = list_presets()
        assert len(presets) == 3

    def test_default_is_ollama_qwen(self):
        assert DEFAULT_PROVIDER_ID == "ollama-qwen"
        preset = get_preset(DEFAULT_PROVIDER_ID)
        assert preset.is_default is True
        assert preset.provider_type == "ollama"

    def test_all_presets_have_required_fields(self):
        for preset in list_presets():
            assert preset.id
            assert preset.name
            assert preset.description
            assert preset.model_name
            assert preset.base_url.startswith("http")
            assert preset.pull_command.startswith("ollama pull")
            assert preset.min_ram_gb > 0

    def test_ollama_claude_preset_exists(self):
        preset = get_preset("ollama-claude")
        assert "claude" in preset.id.lower() or "llama" in preset.model_name.lower()

    def test_lite_preset_for_weak_pcs(self):
        preset = get_preset("ollama-lite")
        assert preset.tier == "low"
        assert preset.min_ram_gb <= 8

    def test_validate_known_id(self):
        assert validate_provider_id("ollama-qwen") is True
        assert validate_provider_id("ollama-lite") is True
        assert validate_provider_id("ollama-claude") is True

    def test_validate_unknown_id(self):
        assert validate_provider_id("unknown-provider") is False

    def test_list_preset_dicts_serializable(self):
        items = list_preset_dicts()
        assert len(items) == 3
        for item in items:
            assert "id" in item
            assert "name" in item
            assert "is_default" in item
            assert item["id"] != ""

    def test_get_unknown_preset_raises(self):
        with pytest.raises(KeyError):
            get_preset("does-not-exist")
