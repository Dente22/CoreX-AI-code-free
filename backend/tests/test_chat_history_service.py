"""TDD: история чата UI."""

from core.chat_history_service import (
    archive_current_chat,
    clear_ui_messages,
    list_chat_sessions,
    load_ui_messages,
    save_ui_messages,
)


def test_save_and_load_ui_messages(tmp_path):
    messages = [
        {"id": "u1", "role": "user", "content": "создай сайт", "timestamp": "10:00"},
        {"id": "a1", "role": "assistant", "content": "Готово", "timestamp": "10:01"},
    ]
    save_ui_messages(tmp_path, messages)
    loaded = load_ui_messages(tmp_path)
    assert len(loaded) == 2
    assert loaded[0]["content"] == "создай сайт"


def test_empty_ui_messages_does_not_fallback_to_conversation(tmp_path):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True)
    chat_dir.joinpath("conversation.json").write_text(
        '{"messages": [{"role": "user", "content": "legacy"}]}\n',
        encoding="utf-8",
    )
    save_ui_messages(tmp_path, [])
    loaded = load_ui_messages(tmp_path)
    assert loaded == []


def test_archive_creates_session(tmp_path):
    messages = [{"role": "user", "content": "тест архива", "timestamp": ""}]
    result = archive_current_chat(tmp_path, messages)
    assert result.get("success")
    sessions = list_chat_sessions(tmp_path)
    assert len(sessions) == 1
    assert "тест" in sessions[0]["title"]


def test_archive_skips_duplicate_session(tmp_path):
    messages = [{"role": "user", "content": "один и тот же чат", "timestamp": ""}]
    first = archive_current_chat(tmp_path, messages)
    second = archive_current_chat(tmp_path, messages)
    assert first.get("success")
    assert second.get("success")
    assert second.get("duplicate")
    assert len(list_chat_sessions(tmp_path)) == 1


def test_dedupe_consecutive_messages(tmp_path):
    messages = [
        {"role": "user", "content": "привет"},
        {"role": "user", "content": "привет"},
        {"role": "assistant", "content": "ок"},
    ]
    save_ui_messages(tmp_path, messages)
    loaded = load_ui_messages(tmp_path)
    assert len(loaded) == 2
    assert loaded[0]["role"] == "user"
    assert loaded[1]["role"] == "assistant"


def test_clear_ui_messages_keeps_empty_file(tmp_path):
    save_ui_messages(tmp_path, [{"role": "user", "content": "x"}])
    clear_ui_messages(tmp_path)
    assert load_ui_messages(tmp_path) == []
    assert (tmp_path / "chat" / "ui_messages.json").is_file()


def test_fallback_from_conversation_json(tmp_path):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True)
    chat_dir.joinpath("conversation.json").write_text(
        '{"messages": [{"role": "user", "content": "legacy"}]}\n',
        encoding="utf-8",
    )
    loaded = load_ui_messages(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["content"] == "legacy"
