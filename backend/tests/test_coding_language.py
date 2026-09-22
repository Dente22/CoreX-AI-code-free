from pathlib import Path

from core.coding_language import (
    get_coding_language,
    infer_coding_language,
    language_forces_code,
    language_forces_web,
    resolve_effective_language,
    set_coding_language,
    validate_language_id,
)
from core.step_execution import pick_execution_plan


def test_infer_snake_is_python():
    assert infer_coding_language("сделай на питоне змейку") == "python"


def test_infer_site_is_html():
    assert infer_coding_language("сделай сайт компьютерного клуба") == "html"


def test_pinned_python_wins_over_web_words():
    assert resolve_effective_language("python", "сделай сайт") == "python"
    assert language_forces_code("python") is True
    assert language_forces_web("python") is False


def test_validate_unknown_falls_back_to_auto():
    assert validate_language_id("cobol") == "auto"


def test_persist_coding_language(tmp_path: Path):
    assert get_coding_language(tmp_path) == "auto"
    result = set_coding_language(tmp_path, "python")
    assert result["language"] == "python"
    assert get_coding_language(tmp_path) == "python"


def test_python_task_does_not_use_design_system_plan():
    steps = pick_execution_plan(
        user_task="сделай на питоне змейку",
        agent_id="lead-developer",
        has_design_folder=True,
        coding_language="python",
    )
    joined = " ".join(step.instruction for step in steps)
    assert "pages/index.md" not in joined
    assert "index.html" not in joined


def test_auto_snake_does_not_use_web_plan():
    steps = pick_execution_plan(
        user_task="сделай на питоне змейку",
        agent_id="lead-developer",
        has_design_folder=True,
        coding_language="auto",
    )
    joined = " ".join(step.instruction for step in steps)
    assert "pages/index.md" not in joined


def test_html_language_keeps_web_plan():
    steps = pick_execution_plan(
        user_task="сделай лендинг",
        agent_id="lead-developer",
        has_design_folder=True,
        coding_language="html",
    )
    joined = " ".join(step.instruction for step in steps)
    assert "index.html" in joined
