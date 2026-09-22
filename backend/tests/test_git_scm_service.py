import shutil

import pytest

from core.git_scm_service import (
    commit_staged,
    discard_paths,
    get_status,
    init_repository,
    parse_porcelain,
    safe_rel_path,
    stage_paths,
    unstage_paths,
)


def test_safe_rel_path_rejects_traversal():
    assert safe_rel_path("src/app.ts") == "src/app.ts"
    assert safe_rel_path("../secret") is None
    assert safe_rel_path("C:/Windows/system.ini") is None
    assert safe_rel_path("-hooks") is None
    assert safe_rel_path("/etc/passwd") is None


def test_parse_porcelain_status_codes():
    files = parse_porcelain(" M src/a.ts\nM  src/b.ts\n?? new.md\n")
    by_path = {item["path"]: item for item in files}
    assert by_path["src/a.ts"]["unstaged"] is True
    assert by_path["src/a.ts"]["staged"] is False
    assert by_path["src/b.ts"]["staged"] is True
    assert by_path["new.md"]["untracked"] is True


def test_parse_porcelain_hides_chat_folder():
    files = parse_porcelain(" M src/a.ts\n?? chat/project_memory.md\n?? chat/visio/a.mmd\n")
    assert [item["path"] for item in files] == ["src/a.ts"]


@pytest.mark.skipif(not shutil.which("git"), reason="git is not on PATH")
def test_init_stage_commit_discard(tmp_path):
    status = init_repository(tmp_path)
    assert status.get("is_repo") is True

    tracked = tmp_path / "readme.md"
    tracked.write_text("hello\n", encoding="utf-8")
    subprocess_env_commit_identity(tmp_path)

    staged = stage_paths(tmp_path, ["readme.md"])
    assert any(item["path"] == "readme.md" and item["staged"] for item in staged["files"])

    committed = commit_staged(tmp_path, "add readme")
    assert committed.get("committed") is True
    leftover = {item["path"] for item in committed.get("files") or []}
    assert "readme.md" not in leftover
    assert not any(path == "chat" or path.startswith("chat/") for path in leftover)

    tracked.write_text("hello world\n", encoding="utf-8")
    dirty = get_status(tmp_path)
    assert any(item["path"] == "readme.md" and item["unstaged"] for item in dirty["files"])

    extra = tmp_path / "scratch.txt"
    extra.write_text("tmp\n", encoding="utf-8")
    discarded = discard_paths(tmp_path, ["readme.md", "scratch.txt"])
    names = {item["path"] for item in discarded["files"]}
    assert "readme.md" not in names
    assert "scratch.txt" not in names
    assert not any(path == "chat" or path.startswith("chat/") for path in names)
    assert tracked.read_text(encoding="utf-8") == "hello\n"


def subprocess_env_commit_identity(root):
    from core.git_scm_service import _run_git

    _run_git(root, ["config", "user.email", "corex@test.local"])
    _run_git(root, ["config", "user.name", "CoreX Test"])


@pytest.mark.skipif(not shutil.which("git"), reason="git is not on PATH")
def test_unstage_keeps_working_tree(tmp_path):
    init_repository(tmp_path)
    subprocess_env_commit_identity(tmp_path)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    stage_paths(tmp_path, ["a.txt"])
    commit_staged(tmp_path, "base")
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    stage_paths(tmp_path, ["a.txt"])
    result = unstage_paths(tmp_path, ["a.txt"])
    item = next(file for file in result["files"] if file["path"] == "a.txt")
    assert item["staged"] is False
    assert item["unstaged"] is True
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "two\n"


@pytest.mark.skipif(not shutil.which("git"), reason="git is not on PATH")
def test_status_hides_chat_and_rejects_stage(tmp_path):
    init_repository(tmp_path)
    subprocess_env_commit_identity(tmp_path)
    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "/chat/" in ignore

    (tmp_path / "chat").mkdir()
    (tmp_path / "chat" / "project_memory.md").write_text("secret\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")

    status = get_status(tmp_path)
    paths = {item["path"] for item in status.get("files") or []}
    assert "app.py" in paths
    assert not any(path == "chat" or path.startswith("chat/") for path in paths)

    blocked = stage_paths(tmp_path, ["chat/project_memory.md"])
    assert blocked.get("error")
