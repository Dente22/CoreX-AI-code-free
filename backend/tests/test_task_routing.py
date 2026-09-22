"""TDD: маршрутизация чата — не гонять планирование на small talk."""

from core.task_routing import (
    infer_task_route,
    is_conversational_message,
    looks_like_economy_model,
    looks_like_fix_request,
    should_include_knowledge_in_prompt,
    should_run_planning_phase,
    resolve_online_model_for_route,
    resolve_local_model_for_route,
    OPENROUTER_CHAT_ECONOMY_MODEL,
    GEMINI_CHAT_ECONOMY_MODEL,
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


def test_chat_uses_openrouter_free_pool():
    selected = "google/gemma-4-31b-it:free"
    assert (
        resolve_online_model_for_route(
            "conversational",
            selected,
            api_type="openai",
            is_openrouter=True,
        )
        == OPENROUTER_CHAT_ECONOMY_MODEL
    )
    assert (
        resolve_online_model_for_route(
            "question",
            selected,
            api_type="openai",
            is_openrouter=True,
        )
        == OPENROUTER_CHAT_ECONOMY_MODEL
    )
    assert OPENROUTER_CHAT_ECONOMY_MODEL == "openrouter/free"


def test_code_keeps_selected_model():
    selected = "google/gemma-4-31b-it:free"
    assert (
        resolve_online_model_for_route(
            "code",
            selected,
            api_type="openai",
            is_openrouter=True,
        )
        == selected
    )


def test_local_pair_chat_uses_phi3():
    installed = ["phi3:mini", "qwen2.5-coder:3b"]
    assert resolve_local_model_for_route("conversational", "qwen2.5-coder:3b", installed) == "phi3:mini"
    assert resolve_local_model_for_route("question", "qwen2.5-coder:3b", installed) == "phi3:mini"


def test_local_pair_code_uses_qwen_3b():
    installed = ["phi3:mini", "qwen2.5-coder:3b"]
    assert resolve_local_model_for_route("code", "phi3:mini", installed) == "qwen2.5-coder:3b"


def test_local_pair_skips_when_only_one_installed():
    assert (
        resolve_local_model_for_route("conversational", "qwen2.5-coder:3b", ["qwen2.5-coder:3b"])
        == "qwen2.5-coder:3b"
    )


def test_local_pair_does_not_override_7b():
    installed = ["phi3:mini", "qwen2.5-coder:3b", "qwen2.5-coder:7b"]
    assert (
        resolve_local_model_for_route("conversational", "qwen2.5-coder:7b", installed)
        == "qwen2.5-coder:7b"
    )


def test_large_free_model_is_not_treated_as_economy():
    assert not looks_like_economy_model("google/gemma-4-31b-it:free")
    assert not looks_like_economy_model("gemini-2.5-pro")
    assert looks_like_economy_model("openai/gpt-oss-20b:free")
    assert looks_like_economy_model("qwen2.5-coder:7b")
    selected = "openai/gpt-oss-20b:free"
    assert (
        resolve_online_model_for_route(
            "conversational",
            selected,
            api_type="openai",
            is_openrouter=True,
        )
        == OPENROUTER_CHAT_ECONOMY_MODEL
    )
    assert (
        resolve_online_model_for_route(
            "conversational",
            "openrouter/free",
            api_type="openai",
            is_openrouter=True,
        )
        == "openrouter/free"
    )


def test_gemini_chat_uses_flash_lite():
    assert (
        resolve_online_model_for_route(
            "question",
            "gemini-2.5-pro",
            api_type="gemini",
        )
        == GEMINI_CHAT_ECONOMY_MODEL
    )


def test_non_openrouter_openai_keeps_selected():
    selected = "my-lab/big-model"
    assert (
        resolve_online_model_for_route(
            "conversational",
            selected,
            api_type="openai",
            is_openrouter=False,
        )
        == selected
    )


def test_fix_request_is_not_a_new_app():
    assert looks_like_fix_request("исправь SyntaxError в main.py")
    assert looks_like_fix_request("fix NameError on line 12")
    assert not looks_like_fix_request("создай змейку на питоне")
    assert not looks_like_fix_request("напиши скрипт сортировки")
