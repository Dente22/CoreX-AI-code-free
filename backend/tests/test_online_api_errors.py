"""TDD: понятные ошибки онлайн API (429 quota и др.)."""

from core.online_api_errors import (
    extract_api_error_message,
    format_online_api_error,
    is_online_api_failure,
    is_quota_or_rate_limit,
)


GEMINI_429_BODY = """{
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details."
  }
}"""


def test_extract_api_error_message_from_gemini_json():
    msg = extract_api_error_message(GEMINI_429_BODY)
    assert "quota" in msg.lower()


def test_is_quota_or_rate_limit_for_429():
    assert is_quota_or_rate_limit(429, GEMINI_429_BODY)


def test_format_online_api_error_429_gemini_is_user_friendly():
    text = format_online_api_error(
        429,
        GEMINI_429_BODY,
        api_type="gemini",
        model_name="gemini-2.5-flash",
    )
    assert "[CoreX Critical Error]" not in text
    assert "Квота Gemini" in text
    assert "aistudio.google.com" in text
    assert "Ollama" in text
    assert "flash-lite" in text


def test_is_online_api_failure_detects_quota_message():
    text = format_online_api_error(429, GEMINI_429_BODY, api_type="gemini")
    assert is_online_api_failure(text)


def test_is_online_api_failure_detects_critical_error():
    assert is_online_api_failure("[CoreX Critical Error]: something")


def test_is_model_unavailable_for_404():
    from core.online_api_errors import is_model_unavailable_error

    body = (
        '{"error":{"message":"This model is unavailable for free. '
        'The paid version is available now - use this slug instead: '
        'meta-llama/llama-3.3-70b-instruct"}}'
    )
    assert is_model_unavailable_error(404, body)
    assert not is_model_unavailable_error(401, body)


def test_format_history_trim_clips_long_messages():
    from core.conversation_memory import trim_history_for_llm

    history = [
        {"role": "user", "content": "a" * 5000},
        {"role": "assistant", "content": "ok"},
    ]
    trimmed = trim_history_for_llm(history, max_turns=2, max_chars=100)
    assert len(trimmed) == 2
    assert "…" in trimmed[0]["content"]
    assert len(trimmed[0]["content"]) <= 110