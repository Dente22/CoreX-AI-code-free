"""Unit tests for project_paths — path normalization and skip rules."""

import pytest

from core.project_paths import (
    collect_mentionable_files,
    ensure_chat_gitignored,
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

    def test_nested_chat_folder_is_not_internal(self):
        assert not is_corex_internal_path("src/chat/notes.md")

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

    def test_skips_root_chat_folder(self):
        assert should_skip_for_analysis("chat", "chat")
        assert should_skip_for_analysis("project_memory.md", "chat/project_memory.md")

    def test_keeps_user_chat_folder_inside_src(self):
        assert not should_skip_for_analysis("chat", "src/chat")


def test_collect_mentionable_files_skips_chat(tmp_path):
    (tmp_path / "chat").mkdir()
    (tmp_path / "chat" / "project_memory.md").write_text("secret", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "src" / "chat").mkdir()
    (tmp_path / "src" / "chat" / "notes.md").write_text("ok", encoding="utf-8")
    files = collect_mentionable_files(tmp_path)
    assert "src/app.py" in files
    assert "src/chat/notes.md" in files
    assert "src" in files
    assert all(not path.startswith("chat/") and path != "chat" for path in files)


def test_collect_mentionable_includes_empty_folder(tmp_path):
    (tmp_path / "test").mkdir()
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    files = collect_mentionable_files(tmp_path)
    assert "test" in files
    assert "main.py" in files


def test_ensure_chat_gitignored(tmp_path):
    ensure_chat_gitignored(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "/chat/" in text
    ensure_chat_gitignored(tmp_path)
    again = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert again.count("/chat/") == 1
