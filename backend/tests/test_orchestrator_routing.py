"""TDD: оркестратор не гоняет планирование на small talk и теорию."""

from unittest.mock import MagicMock

import pytest

from core.orchestrator import CoreXOrchestrator


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
