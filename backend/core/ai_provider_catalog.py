"""Каталог локальных AI-провайдеров CoreX (без автозагрузки моделей)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ProviderType = Literal["ollama"]
Tier = Literal["low", "medium", "high"]

DEFAULT_PROVIDER_ID = "ollama-qwen"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11435"


@dataclass(frozen=True)
class AiProviderPreset:
    id: str
    name: str
    description: str
    provider_type: ProviderType
    model_name: str
    base_url: str
    min_ram_gb: float
    tier: Tier
    pull_command: str
    is_default: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


_PRESETS: tuple[AiProviderPreset, ...] = (
    AiProviderPreset(
        id="ollama-qwen",
        name="Ollama — Qwen Coder",
        description=(
            "Рекомендуемый вариант для разработки: баланс качества кода и требований к железу."
        ),
        provider_type="ollama",
        model_name="qwen2.5-coder:7b",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=8.0,
        tier="medium",
        pull_command="ollama pull qwen2.5-coder:7b",
        is_default=True,
    ),
    AiProviderPreset(
        id="ollama-claude",
        name="Ollama — Claude-style (Llama 3.1)",
        description=(
            "Универсальный ассистент с сильным рассуждением. Подходит для сложных задач и ревью."
        ),
        provider_type="ollama",
        model_name="llama3.1:8b",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=10.0,
        tier="high",
        pull_command="ollama pull llama3.1:8b",
    ),
    AiProviderPreset(
        id="ollama-lite",
        name="Ollama Lite — Phi-3 Mini",
        description=(
            "Облегчённая модель для слабых ПК и ноутбуков. Меньше RAM, быстрее отклик."
        ),
        provider_type="ollama",
        model_name="phi3:mini",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=4.0,
        tier="low",
        pull_command="ollama pull phi3:mini",
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def list_presets() -> list[AiProviderPreset]:
    return list(_PRESETS)


def list_preset_dicts() -> list[dict]:
    return [preset.to_dict() for preset in _PRESETS]


def get_preset(provider_id: str) -> AiProviderPreset:
    preset = _PRESET_BY_ID.get(provider_id)
    if preset is None:
        raise KeyError(f"Unknown AI provider: {provider_id}")
    return preset


def validate_provider_id(provider_id: str) -> bool:
    return provider_id in _PRESET_BY_ID


def get_default_preset() -> AiProviderPreset:
    return get_preset(DEFAULT_PROVIDER_ID)
