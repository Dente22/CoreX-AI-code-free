"""Unit tests for file_patch — critical for AI-driven code edits."""

import pytest

from core.file_patch import apply_file_patch, number_file_content


@pytest.mark.unit
class TestNumberFileContent:
    def test_empty_content(self):
        assert number_file_content("") == "    1| "

    def test_single_line(self):
        result = number_file_content("hello")
        assert result == "   1| hello"


@pytest.mark.unit
class TestApplyFilePatch:
    def test_replace_line(self):
        content = "line1\nline2\nline3\n"
        ops = [{"op": "replace", "line": 2, "content": "replaced"}]
        new_content, highlights, errors = apply_file_patch(content, ops)
        assert "replaced" in new_content
        assert not errors
        assert len(highlights) == 1
        assert highlights[0]["type"] == "modify"

    def test_delete_line(self):
        content = "a\nb\nc\n"
        ops = [{"op": "delete", "line": 2}]
        new_content, highlights, errors = apply_file_patch(content, ops)
        assert "b" not in new_content
        assert not errors

    def test_empty_operations_returns_error(self):
        _, _, errors = apply_file_patch("text\n", [])
        assert any("Нет операций" in e for e in errors)

    def test_invalid_line_number(self):
        content = "only\n"
        ops = [{"op": "replace", "line": 99, "content": "x"}]
        _, highlights, errors = apply_file_patch(content, ops)
        assert errors
        assert not highlights
