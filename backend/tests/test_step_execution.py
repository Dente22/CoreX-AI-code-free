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
from core.orchestrator import IDLE_NO_CODE_TURNS


def test_create_python_plan_is_one_complete_file():
    steps = pick_execution_plan(
        user_task="напиши скрипт сортировки списка",
        coding_language="python",
    )
    ids = [step.id for step in steps]
    assert ids == ["write_complete", "verify"]
    assert "inspect" not in ids
    assert "skeleton" not in ids
    assert "Не каркас" in steps[0].instruction or "ПОЛНЫЙ" in steps[0].instruction


def test_snake_plan_is_single_complete_write():
    steps = pick_execution_plan(
        user_task="создай змейку на питоне",
        coding_language="python",
    )
    ids = [step.id for step in steps]
    assert ids == ["write_complete", "verify"]
    assert "inspect" not in ids
    assert "write_game" not in ids


def test_fix_python_plan_starts_with_inspect():
    steps = pick_execution_plan(
        user_task="исправь SyntaxError в main.py",
        coding_language="python",
    )
    ids = [step.id for step in steps]
    assert ids[0] == "inspect"
    assert "write_complete" not in ids


def test_mark_python_write_completes_create_plan():
    steps = pick_execution_plan(user_task="скрипт сортировки", coding_language="python")
    after_write = mark_step_completed(
        steps, set(), tool="write_file", path="main.py", success=True
    )
    assert "write_complete" in after_write
    steps = web_developer_plan(design_folder="design-system")
    ids = [step.id for step in steps]
    assert "read_design" in ids
    assert "html_structure" in ids
    assert "css_layout" in ids


def test_python_create_plan_does_not_block_done_like_gui():
    from core.step_execution import should_block_done_for_plan

    steps = pick_execution_plan(user_task="скрипт сортировки", coding_language="python")
    assert should_block_done_for_plan(steps, set(), is_web=False) is False
    web = web_developer_plan()
    assert should_block_done_for_plan(web, set(), is_web=True) is True
    assert should_block_done_for_plan(web, set(), is_web=False) is False


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


def test_idle_no_code_turns_is_short():
    assert IDLE_NO_CODE_TURNS == 8
