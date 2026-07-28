"""TDD: создание нового проекта на диске."""

from core.project_bootstrap_service import build_project_scaffold_task, create_project


def test_create_project_makes_folder_and_readme(tmp_path):
    parent = tmp_path / "workspace"
    parent.mkdir()
    result = create_project(parent, "My App", "Тестовый проект", stack="python")
    assert result.get("success") is True
    root = parent / "My-App"
    assert root.is_dir()
    assert (root / "README.md").is_file()
    assert (root / "chat" / "project_memory.md").is_file()
    assert (root / "chat" / "personas").is_dir()
    assert "My App" in result["task"]


def test_create_project_rejects_nonempty_folder(tmp_path):
    parent = tmp_path / "workspace"
    project = parent / "exists"
    project.mkdir(parents=True)
    (project / "old.txt").write_text("x", encoding="utf-8")
    result = create_project(parent, "exists", "desc")
    assert result.get("error")


def test_build_project_scaffold_task_mentions_root(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    task = build_project_scaffold_task("Demo", "Описание", project)
    assert str(project.resolve()) in task
    assert "полноценный" in task.lower() or "полноценный" in task
