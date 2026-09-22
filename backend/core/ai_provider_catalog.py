"""Каталог локальных AI-провайдеров CoreX (без автозагрузки моделей)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ProviderType = Literal["ollama"]
Tier = Literal["low", "medium", "high"]

DEFAULT_PROVIDER_ID = "ollama-qwen"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11435"

CODING_PROVIDER_BY_TIER: dict[Tier, str] = {
    "low": "ollama-qwen",
    "medium": "ollama-qwen-7b",
    "high": "ollama-qwen-14b",
}


@dataclass(frozen=True)
class AiProviderPreset:
    id: str
    name: str
    description: str
    provider_type: ProviderType
    model_name: str
    base_url: str
    min_ram_gb: float
    min_vram_gb: float
    size_gb: float
    tier: Tier
    pull_command: str
    is_default: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


_PRESETS: tuple[AiProviderPreset, ...] = (
    AiProviderPreset(
        id="ollama-qwen",
        name="Ollama — Qwen Coder 3B",
        description="Код на слабом GPU: целиком в 4 ГБ VRAM, контекст 4096.",
        provider_type="ollama",
        model_name="qwen2.5-coder:3b",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=4.0,
        min_vram_gb=4.0,
        size_gb=1.9,
        tier="low",
        pull_command="ollama pull qwen2.5-coder:3b",
        is_default=True,
    ),
    AiProviderPreset(
        id="ollama-lite",
        name="Ollama Lite — Phi-3 Mini",
        description="Лёгкий чат для слабых ПК. В коде слабее Qwen 3B.",
        provider_type="ollama",
        model_name="phi3:mini",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=4.0,
        min_vram_gb=4.0,
        size_gb=2.2,
        tier="low",
        pull_command="ollama pull phi3:mini",
    ),
    AiProviderPreset(
        id="ollama-qwen-7b",
        name="Ollama — Qwen Coder 7B",
        description="Лучший локальный код на 8 ГБ VRAM (RTX 3050 и аналоги).",
        provider_type="ollama",
        model_name="qwen2.5-coder:7b",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=8.0,
        min_vram_gb=6.0,
        size_gb=4.7,
        tier="medium",
        pull_command="ollama pull qwen2.5-coder:7b",
    ),
    AiProviderPreset(
        id="ollama-claude",
        name="Ollama — Llama 3.1 8B",
        description="Чат и ревью на среднем ПК. Для кода слабее Qwen 7B.",
        provider_type="ollama",
        model_name="llama3.1:8b",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=10.0,
        min_vram_gb=6.0,
        size_gb=4.9,
        tier="medium",
        pull_command="ollama pull llama3.1:8b",
    ),
    AiProviderPreset(
        id="ollama-qwen-14b",
        name="Ollama — Qwen Coder 14B",
        description="Максимум качества: часть слоёв может уйти в RAM на 8 ГБ VRAM.",
        provider_type="ollama",
        model_name="qwen2.5-coder:14b",
        base_url=DEFAULT_OLLAMA_URL,
        min_ram_gb=16.0,
        min_vram_gb=8.0,
        size_gb=9.0,
        tier="high",
        pull_command="ollama pull qwen2.5-coder:14b",
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def recommend_model_tier(
    vram_gb: float | None = None,
    ram_gb: float | None = None,
) -> Tier:
    """Вкладка каталога по железу. VRAM важнее RAM.

    Без VRAM не предлагаем 14B: 16 ГБ как на рабочем ПК остаются на 3B,
    32 ГБ без GPU — на 7B.
    """
    if vram_gb is not None and vram_gb > 0:
        if vram_gb <= 4.5:
            return "low"
        if vram_gb <= 10.0:
            return "medium"
        return "high"
    ram = ram_gb or 0.0
    if ram >= 24:
        return "medium"
    return "low"


def recommended_provider_id(
    vram_gb: float | None = None,
    ram_gb: float | None = None,
) -> str:
    return CODING_PROVIDER_BY_TIER[recommend_model_tier(vram_gb, ram_gb)]


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
