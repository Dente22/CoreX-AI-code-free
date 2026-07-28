"""Unit tests for project_paths — path normalization and skip rules."""

import pytest

from core.project_paths import (
    is_allowed_internal_read,
    is_corex_internal_path,
    normalize_rel_path,
    should_skip_for_analysis,
)


@pytest.mark.unit
class TestNormalizeRelPath:
    def test_backslashes_to_forward(self):
        assert normalize_rel_path("src\\main.py") == "src/main.py"

    def test_strips_leading_slash(self):
        assert normalize_rel_path("/foo/bar") == "foo/bar"


@pytest.mark.unit
class TestCorexInternalPaths:
    def test_chat_is_internal(self):
        assert is_corex_internal_path("chat/project_memory.md")

    def test_src_is_not_internal(self):
        assert not is_corex_internal_path("src/app.py")

    def test_memory_read_allowed(self):
        assert is_allowed_internal_read("chat/project_memory.md")


@pytest.mark.unit
class TestShouldSkipForAnalysis:
    def test_skips_node_modules(self):
        assert should_skip_for_analysis("node_modules", "node_modules/pkg")

    def test_skips_dot_git(self):
        assert should_skip_for_analysis(".git", ".git/objects")

    def test_does_not_skip_normal_file(self):
        assert not should_skip_for_analysis("main.py", "src/main.py")
