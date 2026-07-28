"""Актуальные имена моделей Google Gemini для Generative Language API."""

from __future__ import annotations

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Устаревшие ID из UI/документации -> рабочие модели API (июль 2026).
_GEMINI_MODEL_ALIASES: dict[str, str] = {
    "gemini-1.5-flash": DEFAULT_GEMINI_MODEL,
    "gemini-1.5-flash-latest": DEFAULT_GEMINI_MODEL,
    "gemini-1.5-flash-8b": DEFAULT_GEMINI_MODEL,
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-1.5-pro-latest": "gemini-2.5-pro",
    "gemini-2.0-flash": DEFAULT_GEMINI_MODEL,
    "gemini-2.0-flash-001": DEFAULT_GEMINI_MODEL,
    "gemini-2.0-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite-001": "gemini-2.5-flash-lite",
}


def normalize_gemini_model_name(model_name: str) -> str:
    cleaned = (model_name or "").strip()
    if not cleaned:
        return DEFAULT_GEMINI_MODEL
    return _GEMINI_MODEL_ALIASES.get(cleaned, cleaned)
