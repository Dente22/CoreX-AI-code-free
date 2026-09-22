from pathlib import Path

from core.web_access import (
    get_web_access_mode,
    set_web_access_mode,
    should_search_web,
    user_asked_for_web,
)


def _patch_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.web_access.COREX_ROOT", tmp_path)


def test_default_mode_is_ask(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    assert get_web_access_mode() == "ask"
    assert should_search_web("сделай сапёр с окном") is False
    assert should_search_web("посмотри в интернете как сделать сапёр на tkinter") is True


def test_never_blocks_even_when_asked(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    set_web_access_mode("never")
    assert get_web_access_mode() == "never"
    assert should_search_web("погугли pygame") is False


def test_always_searches_code_tasks_not_chat(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    set_web_access_mode("always")
    assert should_search_web("сделай сапёр с окном tkinter") is True
    assert should_search_web("привет", conversational=True) is False
    assert should_search_web("что такое список?", is_question=True) is False
    assert should_search_web("hi") is False


def test_user_asked_for_web_phrases():
    assert user_asked_for_web("найди в гугле пример") is True
    assert user_asked_for_web("look up tkinter grid") is True
    assert user_asked_for_web("добавь кнопку") is False


def test_invalid_mode_falls_back_to_ask(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    snapshot = set_web_access_mode("nope")
    assert snapshot["mode"] == "ask"
    assert (tmp_path / "chat" / "web_access.json").is_file()
