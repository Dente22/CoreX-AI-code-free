"""TDD: бюджет лимитов нагрузки для online API."""

from core.resource_limits import ResourceBudget


def test_for_online_uses_high_caps_and_does_not_use_device_profile(monkeypatch):
    import core.resource_limits as rl

    def _boom():
        raise AssertionError("detect_device_profile must not be called in for_online")

    monkeypatch.setattr(rl, "detect_device_profile", _boom)

    budget = ResourceBudget.for_online({"max_total_turns": 5, "max_turns_per_step": 2, "max_file_writes": 1})

    # Online mode should not be constrained by device-based "offline" caps.
    assert budget.max_total_turns >= 200
    assert budget.max_turns_per_step >= 60
    assert budget.max_file_writes >= 50
    assert budget.delay_between_turns_ms == 0
    assert budget.delay_between_steps_ms == 0


def test_for_online_respects_higher_pipeline_limits():
    budget = ResourceBudget.for_online(
        {"max_total_turns": 999, "max_turns_per_step": 333, "max_file_writes": 200}
    )

    assert budget.max_total_turns == 999
    assert budget.max_turns_per_step == 333
    assert budget.max_file_writes == 200

