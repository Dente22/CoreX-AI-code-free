"""Tests for coding engine preference (Aider vs CoreX agent)."""

from pathlib import Path

from core.coding_engine import (
    DEFAULT_CODING_ENGINE,
    coding_engine_snapshot,
    get_coding_engine,
    set_coding_engine,
    validate_coding_engine,
)


def test_default_engine_is_aider(tmp_path: Path):
    assert get_coding_engine(tmp_path) == "aider"
    assert DEFAULT_CODING_ENGINE == "aider"
    assert validate_coding_engine("nope") == "aider"
    assert validate_coding_engine("corex") == "corex"


def test_persist_coding_engine(tmp_path: Path):
    assert set_coding_engine(tmp_path, "corex") == "corex"
    assert get_coding_engine(tmp_path) == "corex"
    snap = coding_engine_snapshot(tmp_path)
    assert snap["engine"] == "corex"
    assert any(item["id"] == "aider" for item in snap["engines"])
