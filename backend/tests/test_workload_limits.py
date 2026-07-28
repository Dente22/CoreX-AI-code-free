"""TDD: настраиваемые лимиты нагрузки для локального AI."""

from __future__ import annotations

from core.workload_limits_service import (
    GLOBAL_WORKLOAD_MAX,
    GLOBAL_WORKLOAD_MIN,
    default_slider_for_tier,
    get_workload_settings,
    interpolate_workload_limits,
    resolve_step_max_turns,
    resolve_workload_limits,
    save_workload_settings,
    set_workload_slider,
)


def test_global_min_not_above_global_max():
    for key in ("max_total_turns", "max_turns_per_step", "max_file_writes"):
        assert GLOBAL_WORKLOAD_MIN[key] <= GLOBAL_WORKLOAD_MAX[key]
    assert GLOBAL_WORKLOAD_MIN["delay_between_turns_ms"] >= GLOBAL_WORKLOAD_MAX["delay_between_turns_ms"]
    assert GLOBAL_WORKLOAD_MIN["delay_between_steps_ms"] >= GLOBAL_WORKLOAD_MAX["delay_between_steps_ms"]


def test_slider_zero_uses_global_min_for_any_tier():
    assert interpolate_workload_limits(0, "low") == GLOBAL_WORKLOAD_MIN
    assert interpolate_workload_limits(0, "medium") == GLOBAL_WORKLOAD_MIN
    assert interpolate_workload_limits(0, "high") == GLOBAL_WORKLOAD_MIN


def test_slider_hundred_is_global_max_for_any_tier():
    assert interpolate_workload_limits(100, "low") == GLOBAL_WORKLOAD_MAX
    assert interpolate_workload_limits(100, "medium") == GLOBAL_WORKLOAD_MAX
    assert interpolate_workload_limits(100, "high") == GLOBAL_WORKLOAD_MAX


def test_slider_midpoint_uses_global_range():
    limits = interpolate_workload_limits(50, "medium")
    assert limits["max_total_turns"] > GLOBAL_WORKLOAD_MIN["max_total_turns"]
    assert limits["max_total_turns"] < GLOBAL_WORKLOAD_MAX["max_total_turns"]


def test_default_slider_is_tier_specific_recommendation_only():
    assert default_slider_for_tier("low") < default_slider_for_tier("medium")
    assert default_slider_for_tier("medium") < default_slider_for_tier("high")
    assert default_slider_for_tier("high") < 100


def test_settings_expose_global_max_not_tier_cap(tmp_path):
    settings = get_workload_settings(tmp_path, tier="medium")
    assert settings["max_limits"] == GLOBAL_WORKLOAD_MAX
    assert settings["absolute_max_limits"] == GLOBAL_WORKLOAD_MAX


def test_persist_workload_slider(tmp_path):
    set_workload_slider(tmp_path, 72)
    settings = get_workload_settings(tmp_path, tier="medium")
    assert settings["slider"] == 72
    assert settings["limits"]["max_total_turns"] >= GLOBAL_WORKLOAD_MIN["max_total_turns"]


def test_resolve_workload_limits_caps_by_pipeline_for_medium(tmp_path):
    set_workload_slider(tmp_path, 60)
    merged = resolve_workload_limits(
        tmp_path,
        tier="medium",
        pipeline_limits={"max_total_turns": 28, "max_turns_per_step": 8, "max_file_writes": 14},
    )
    assert merged["max_total_turns"] == 28
    assert merged["max_turns_per_step"] == 8
    assert merged["max_file_writes"] == 14


def test_resolve_workload_limits_without_pipeline_uses_slider(tmp_path):
    set_workload_slider(tmp_path, 60)
    merged = resolve_workload_limits(tmp_path, tier="medium")
    assert merged["max_total_turns"] > GLOBAL_WORKLOAD_MIN["max_total_turns"]


def test_medium_tier_can_reach_near_global_max_with_slider(tmp_path):
    set_workload_slider(tmp_path, 95)
    merged = resolve_workload_limits(tmp_path, tier="medium")
    assert merged["max_total_turns"] >= 90


def test_custom_turn_limits_per_agent(tmp_path):
    save_workload_settings(
        tmp_path,
        {
            "turns_limit_enabled": True,
            "turns_limit_mode": "per_agent",
            "team_max_total_turns": 50,
            "per_agent_turns": {"lead-developer": 20},
        },
    )
    turns = resolve_step_max_turns(
        tmp_path,
        agent_id="lead-developer",
        step_default=10,
        slider_limit=12,
    )
    assert turns == 20


def test_custom_turn_limits_team_mode(tmp_path):
    save_workload_settings(
        tmp_path,
        {
            "turns_limit_enabled": True,
            "turns_limit_mode": "team",
            "team_max_total_turns": 55,
            "team_max_turns_per_step": 18,
        },
    )
    merged = resolve_workload_limits(tmp_path, tier="medium")
    assert merged["max_total_turns"] == 55
    assert merged["max_turns_per_step"] == 18


def test_begin_step_resets_step_turns_for_next_agent():
    """После исчерпания лимита этапа следующий агент получает свой счётчик с нуля."""
    from core.resource_limits import ResourceBudget

    budget = ResourceBudget(max_total_turns=50, max_turns_per_step=10)
    budget.begin_step(5)
    for _ in range(5):
        budget.record_step_turn()
        budget.record_llm_call()
    assert budget.step_turns == 5
    assert not budget.can_turn()

    budget.begin_step(12)
    assert budget.step_turns == 0
    assert budget.can_turn()
    assert budget._current_step_limit == 12
