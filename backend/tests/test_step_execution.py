"""TDD: поэтапный режим и unlimited limits."""

from __future__ import annotations

from core.step_execution import (
    format_plan_for_prompt,
    mark_step_completed,
    pick_execution_plan,
    web_developer_plan,
)
from core.workload_limits_service import (
    UNLIMITED_WORKLOAD,
    get_workload_settings,
    is_unlimited_limits,
    resolve_workload_limits,
    save_workload_settings,
    workload_limits_summary_ru,
)


def test_web_developer_plan_has_read_and_write_steps():
    steps = web_developer_plan(design_folder="design-system")
    ids = [step.id for step in steps]
    assert "read_design" in ids
    assert "html_structure" in ids
    assert "css_layout" in ids


def test_format_plan_for_prompt_lists_steps():
    steps = web_developer_plan()
    text = format_plan_for_prompt(steps)
    assert "План (" in text
    assert "СЕЙЧАС ШАГ 1/" in text
    assert "Шаг 2/" not in text  # не скармливаем весь план сразу


def test_format_current_bite_advances():
    from core.step_execution import format_current_bite

    steps = web_developer_plan()
    first = format_current_bite(steps, set())
    assert "read_design" in first
    second = format_current_bite(steps, {"read_design"})
    assert "read_page" in second


def test_unlimited_uses_app_root_not_project(tmp_path):
    """Лимиты хранятся в app_root (CoreX), а не в папке пользовательского проекта."""
    from core.workload_limits_service import is_unlimited_limits, save_workload_settings

    app = tmp_path / "corex"
    project = tmp_path / "project"
    app.mkdir()
    project.mkdir()
    save_workload_settings(app, {"unlimited_limits": True})
    assert is_unlimited_limits(app) is True
    assert is_unlimited_limits(project) is False


def test_mark_step_completed_tracks_html_and_css():
    steps = web_developer_plan()
    done = mark_step_completed(steps, set(), tool="write_file", path="index.html", success=True)
    assert "html_structure" in done
    done = mark_step_completed(steps, done, tool="write_file", path="style.css", success=True)
    assert "css_layout" in done


def test_unlimited_limits_bypasses_caps(tmp_path):
    save_workload_settings(tmp_path, {"unlimited_limits": True})
    assert is_unlimited_limits(tmp_path) is True
    merged = resolve_workload_limits(tmp_path, tier="medium")
    assert merged["max_total_turns"] == UNLIMITED_WORKLOAD["max_total_turns"]
    settings = get_workload_settings(tmp_path, tier="medium")
    assert settings["unlimited_limits"] is True
    assert settings["limits"]["max_total_turns"] == UNLIMITED_WORKLOAD["max_total_turns"]
    assert "без лимитов" in workload_limits_summary_ru(settings).lower() or settings["unlimited_limits"]


def test_pick_execution_plan_for_developer_with_design_folder():
    steps = pick_execution_plan(
        user_task="сделай сайт клуба",
        agent_id="lead-developer",
        design_folder="my-design",
        has_design_folder=True,
    )
    assert any("my-design" in step.instruction for step in steps)
