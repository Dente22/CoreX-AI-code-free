"""Понятные сообщения об ошибках онлайн API (Gemini, OpenAI-compatible)."""

from __future__ import annotations

import json
import re

_QUOTA_PATTERNS = re.compile(
    r"quota|rate.?limit|resource.?exhausted|too many requests",
    re.IGNORECASE,
)

_MODEL_UNAVAILABLE_PATTERNS = re.compile(
    r"unavailable for free|no endpoints? found|model .* not found|"
    r"is not a valid model|does not exist|paid version is available|"
    r"not available|unknown model",
    re.IGNORECASE,
)


def extract_api_error_message(body: str) -> str:
    """Извлечь текст ошибки из JSON-ответа провайдера."""
    text = (body or "").strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]

    if not isinstance(data, dict):
        return text[:300]

    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message).strip()
    if isinstance(error, str):
        return error.strip()

    message = data.get("message")
    if message:
        return str(message).strip()

    return text[:300]


def is_quota_or_rate_limit(status: int, body: str) -> bool:
    if status == 429:
        return True
    message = extract_api_error_message(body)
    return bool(_QUOTA_PATTERNS.search(message))


def is_model_unavailable_error(status: int, body: str) -> bool:
    """True when provider rejected the model slug (404 / retired :free / no endpoints)."""
    if status in {401, 403, 429}:
        return False
    message = extract_api_error_message(body)
    if status == 404:
        return True
    return bool(_MODEL_UNAVAILABLE_PATTERNS.search(message))


def format_online_api_error(
    status: int,
    body: str,
    *,
    api_type: str = "openai",
    model_name: str = "",
) -> str:
    """Сформировать понятное сообщение для пользователя."""
    provider = "Gemini" if api_type == "gemini" else "онлайн API"
    detail = extract_api_error_message(body)

    if is_quota_or_rate_limit(status, body):
        model_hint = ""
        if api_type == "gemini" and model_name and "lite" not in model_name.lower():
            model_hint = (
                "\n• Попробуйте модель gemini-2.5-flash-lite — у неё обычно выше бесплатный лимит."
            )
        return (
            f"[CoreX] Квота {provider} исчерпана (HTTP {status}).\n\n"
            "Это ограничение Google/провайдера, не лимиты CoreX и не «защита ПК».\n\n"
            "Что сделать:\n"
            "• Проверьте ключ и квоту: https://aistudio.google.com/apikey\n"
            "• Подключите биллинг в Google Cloud или дождитесь сброса дневного лимита\n"
            "• Создайте новый API-ключ в AI Studio\n"
            "• Переключитесь на локальную модель (Ollama) в селекторе моделей"
            f"{model_hint}"
            + (f"\n\nДетали: {detail}" if detail else "")
        )

    if status in (401, 403):
        return (
            f"[CoreX] Доступ к {provider} запрещён (HTTP {status}).\n"
            "Проверьте API-ключ в настройках онлайн-провайдера."
            + (f"\n\nДетали: {detail}" if detail else "")
        )

    if status == 404:
        return (
            f"[CoreX] Модель или endpoint не найден (HTTP {status}).\n"
            f"Проверьте имя модели ({model_name or 'не указана'}) и base URL провайдера."
            + (f"\n\nДетали: {detail}" if detail else "")
        )

    return (
        f"[CoreX Critical Error]: {provider} вернул статус {status}."
        + (f" {detail}" if detail else "")
    )


def is_online_api_failure(text: str) -> bool:
    """Ответ модели — ошибка API (нужно остановить цикл, не парсить как JSON)."""
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    if stripped.startswith("[CoreX Critical Error]"):
        return True
    if stripped.startswith("[CoreX]"):
        return True
    return False
