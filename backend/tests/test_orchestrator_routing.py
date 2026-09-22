"""TDD: оркестратор не гоняет планирование на small talk и теорию."""

from unittest.mock import MagicMock

import pytest

from core.orchestrator import CoreXOrchestrator, filesystem_tool_succeeded
from core.task_routing import looks_like_fix_request


@pytest.fixture
def orchestrator() -> CoreXOrchestrator:
    return CoreXOrchestrator(
        ollama_client=MagicMock(),
        mcp_manager=MagicMock(),
        gui=MagicMock(),
    )


def test_infer_task_mode_greeting(orchestrator: CoreXOrchestrator):
    conversational, is_question, requires_writes = orchestrator._infer_task_mode(
        "привет",
        [],
        None,
    )
    assert conversational is True
    assert is_question is False
    assert requires_writes is False


def test_infer_task_mode_pure_theory_question(orchestrator: CoreXOrchestrator):
    conversational, is_question, requires_writes = orchestrator._infer_task_mode(
        "что такое Flask?",
        [],
        None,
    )
    assert conversational is False
    assert is_question is True
    assert requires_writes is False


def test_infer_task_mode_tell_fact_in_coding_project(orchestrator: CoreXOrchestrator):
    history = [
        {"role": "user", "content": "создай main.py"},
        {"role": "assistant", "content": "Готово"},
    ]
    conversational, is_question, requires_writes = orchestrator._infer_task_mode(
        "расскажи интересный факт",
        history,
        None,
    )
    assert conversational is False
    assert is_question is True
    assert requires_writes is False


def test_normalize_plan_skips_fallback_for_greeting(orchestrator: CoreXOrchestrator):
    assert orchestrator._normalize_plan(None, "привет", []) is None


def test_normalize_plan_skips_fallback_for_theory(orchestrator: CoreXOrchestrator):
    assert orchestrator._normalize_plan(None, "что такое Flask?", []) is None


def test_normalize_plan_keeps_fallback_for_code_task(orchestrator: CoreXOrchestrator):
    plan = orchestrator._normalize_plan(None, "создай змейку на pygame", [])
    assert plan is not None
    assert plan.get("intent") == "code_task"


def test_success_write_message_is_not_a_failure():
    assert filesystem_tool_succeeded(
        {"status": "Success", "message": "File written to D:\\TEST\\TEST2\\main.py"}
    )
    assert filesystem_tool_succeeded({"status": "Error", "message": "stub"}) is False
    assert filesystem_tool_succeeded("File written to D:\\TEST\\TEST2\\main.py") is False


def test_create_snake_is_not_a_fix_request():
    assert looks_like_fix_request("создай змейку на питоне") is False


@pytest.mark.asyncio
async def test_broken_syntax_is_dropped_from_verified(orchestrator: CoreXOrchestrator, tmp_path):
    (tmp_path / "main.py").write_text(
        'x = int(input("Enter col\n',
        encoding="utf-8",
    )
    verified = await orchestrator._drop_broken_syntax_from_verified(
        tmp_path,
        {"main.py"},
        {"main.py"},
    )
    assert "main.py" not in verified
    assert looks_like_fix_request("исправь main.py") is True


def test_remember_code_lesson_once(orchestrator: CoreXOrchestrator, tmp_path, monkeypatch):
    store = tmp_path / "lessons.json"
    monkeypatch.setenv("COREX_LESSONS_PATH", str(store))
    orchestrator._lesson_recorded = False
    orchestrator._remember_code_lesson(
        "создай калькулятор с окном",
        ok=True,
        how="gui_template",
        files=["calculator.py"],
    )
    orchestrator._remember_code_lesson(
        "создай калькулятор с окном",
        ok=False,
        how="syntax_loop",
        files=["calculator.py"],
        error="Blocked done",
    )
    text = store.read_text(encoding="utf-8")
    assert text.count("gui_template") == 1
    assert "syntax_loop" not in text
