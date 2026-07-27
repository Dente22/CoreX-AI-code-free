"""TDD: лимиты токенов для онлайн API."""

from core.token_usage_service import (
    TokenUsage,
    check_budget,
    get_limits,
    get_usage_summary,
    record_usage,
    reset_session_usage,
    set_limits,
)


def test_record_usage_increments_session_and_daily(tmp_path):
    limits_path = tmp_path / "chat" / "ai_usage_limits.json"
    limits_path.parent.mkdir(parents=True, exist_ok=True)
    limits_path.write_text('{"enabled": true, "session_limit": 1000, "daily_limit": 2000}\n', encoding="utf-8")
    reset_session_usage(tmp_path)

    record_usage(tmp_path, TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150), mode="online")
    summary = get_usage_summary(tmp_path)
    assert summary["session"]["total_tokens"] == 150
    assert summary["daily"]["total_tokens"] == 150
    assert summary["remaining_session"] == 850


def test_check_budget_blocks_when_session_exceeded(tmp_path):
    reset_session_usage(tmp_path)
    set_limits(tmp_path, {"enabled": True, "session_limit": 1000, "daily_limit": 5000})
    record_usage(tmp_path, TokenUsage(total_tokens=1500, prompt_tokens=1500), mode="online")
    ok, message = check_budget(tmp_path, mode="online")
    assert not ok
    assert "сессию" in message.lower()


def test_session_resets_on_reset_and_not_persisted(tmp_path):
    reset_session_usage(tmp_path)
    record_usage(tmp_path, TokenUsage(total_tokens=500), mode="online")
    usage_path = tmp_path / "chat" / "token_usage.json"
    saved = usage_path.read_text(encoding="utf-8")
    assert "session" not in saved

    reset_session_usage(tmp_path)
    summary = get_usage_summary(tmp_path)
    assert summary["session"]["total_tokens"] == 0
    assert summary["daily"]["total_tokens"] == 500


def test_local_mode_skips_budget(tmp_path):
    set_limits(tmp_path, {"enabled": True, "session_limit": 10, "daily_limit": 10})
    ok, message = check_budget(tmp_path, mode="local")
    assert ok
    assert message == ""


def test_record_usage_ignored_for_local_mode(tmp_path):
    reset_session_usage(tmp_path)
    record_usage(tmp_path, TokenUsage(total_tokens=9999), mode="local")
    summary = get_usage_summary(tmp_path)
    assert summary["session"]["total_tokens"] == 0
