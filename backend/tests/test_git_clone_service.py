from pathlib import Path
from unittest.mock import patch

from core.git_clone_service import clone_repository, folder_name_from_remote, is_allowed_git_remote


def test_https_github_url_is_allowed():
    assert is_allowed_git_remote("https://github.com/Dente22/CoreX-AI-code-free.git")
    assert is_allowed_git_remote("https://gitlab.com/group/project")


def test_ssh_urls_are_allowed():
    assert is_allowed_git_remote("git@github.com:Dente22/CoreX-AI-code-free.git")
    assert is_allowed_git_remote("ssh://git@github.com/Dente22/CoreX-AI-code-free.git")


def test_unsafe_remotes_are_rejected():
    assert not is_allowed_git_remote("http://github.com/user/repo")
    assert not is_allowed_git_remote("file:///C:/secret")
    assert not is_allowed_git_remote("javascript:alert(1)")
    assert not is_allowed_git_remote("https://user:pass@github.com/user/repo")
    assert not is_allowed_git_remote("git clone https://github.com/x/y")


def test_folder_name_from_https_and_ssh():
    assert folder_name_from_remote("https://github.com/Dente22/CoreX-AI-code-free.git") == "CoreX-AI-code-free"
    assert folder_name_from_remote("git@github.com:Dente22/demo.git") == "demo"


def test_clone_rejects_missing_parent(tmp_path):
    result = clone_repository("https://github.com/a/b.git", tmp_path / "missing")
    assert result.get("error")


def test_clone_runs_git_with_safe_argv(tmp_path):
    parent = tmp_path / "ws"
    parent.mkdir()

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    with patch("core.git_clone_service.subprocess.run", return_value=Result()) as run:
        result = clone_repository("https://github.com/acme/demo.git", parent)
    assert result.get("success") is True
    assert result["root"] == str(parent / "demo")
    argv = run.call_args.args[0]
    assert argv[:3] == ["git", "clone", "--"]
    assert argv[3] == "https://github.com/acme/demo.git"
    assert argv[4] == str(parent / "demo")


def test_clone_blocks_existing_folder(tmp_path):
    parent = tmp_path / "ws"
    dest = parent / "demo"
    dest.mkdir(parents=True)
    (dest / "readme.md").write_text("x", encoding="utf-8")
    result = clone_repository("https://github.com/acme/demo.git", parent)
    assert "уже существует" in (result.get("error") or "")
