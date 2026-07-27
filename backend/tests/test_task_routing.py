"""TDD: маршрутизация чата — не гонять планирование на small talk."""

from core.task_routing import (
    infer_task_route,
    is_conversational_message,
    should_include_knowledge_in_prompt,
    should_run_planning_phase,
)


def test_greeting_skips_planning():
    assert is_conversational_message("привет")
    assert not should_run_planning_phase("привет")
    assert not should_include_knowledge_in_prompt("привет")


def test_thanks_skips_planning():
    assert is_conversational_message("спасибо!")
    assert not should_run_planning_phase("спасибо!")


def test_english_hi_skips_planning():
    assert is_conversational_message("hello")
    assert not should_run_planning_phase("hello")


def test_code_task_still_plans():
    assert not is_conversational_message("создай змейку на pygame")
    assert should_run_planning_phase("создай змейку на pygame")
    assert should_include_knowledge_in_prompt("создай змейку на pygame")


def test_pure_question_skips_heavy_planning():
    assert not is_conversational_message("что такое Flask?")
    assert not should_run_planning_phase("что такое Flask?")


def test_follow_up_in_coding_thread_still_plans():
    history = [
        {"role": "user", "content": "создай main.py с hello world"},
        {"role": "assistant", "content": "Готово"},
    ]
    assert should_run_planning_phase("добавь тесты", history)


def test_casual_ack_skips_planning():
    assert not should_run_planning_phase("ок")
    assert not should_run_planning_phase("понятно")


def test_implicit_game_request_still_plans():
    assert should_run_planning_phase("змейка на pygame")


def test_tell_fact_in_coding_project_skips_planning():
    history = [
        {"role": "user", "content": "создай main.py"},
        {"role": "assistant", "content": "Готово, main.py создан"},
    ]
    assert infer_task_route("расскажи интересный факт", history) == "question"
    assert not should_run_planning_phase("расскажи интересный факт", history)
