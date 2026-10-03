"""Tests for coding engine preference (Claude Code / Aider / CoreX agent)."""

from pathlib import Path

from core.coding_engine import (
    DEFAULT_CODING_ENGINE,
    coding_engine_snapshot,
    get_coding_engine,
    set_coding_engine,
    validate_coding_engine,
)


def test_default_engine_is_claude_code(tmp_path: Path):
    assert get_coding_engine(tmp_path) == "claude_code"
    assert DEFAULT_CODING_ENGINE == "claude_code"
    assert validate_coding_engine("nope") == "claude_code"
    assert validate_coding_engine("corex") == "corex"
    assert validate_coding_engine("aider") == "aider"


def test_persist_coding_engine(tmp_path: Path):
    assert set_coding_engine(tmp_path, "corex") == "corex"
    assert get_coding_engine(tmp_path) == "corex"
    snap = coding_engine_snapshot(tmp_path)
    assert snap["engine"] == "corex"
    ids = [item["id"] for item in snap["engines"]]
    assert ids == ["claude_code", "aider", "corex"]
