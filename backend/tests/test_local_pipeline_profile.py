"""TDD: локальный профиль конвейера."""

from core.local_pipeline_profile import (
    adapt_pipeline_for_local,
    build_local_pipeline_profile,
    resolve_model_tier,
)
from core.llm_runtime import ActiveLlm


class _FakeClient:
    model_name = "phi3:mini"


def test_resolve_model_tier_phi3():
    active = ActiveLlm(
        client=_FakeClient(),
        mode="local",
        provider_id="ollama-lite",
        provider_name="Phi-3",
        model_name="phi3:mini",
        api_type="ollama",
    )
    assert resolve_model_tier(active) == "low"


def test_low_profile_compact_and_reset_history():
    active = ActiveLlm(
        client=_FakeClient(),
        mode="local",
        provider_id="ollama-lite",
        provider_name="Phi-3",
        model_name="phi3:mini",
        api_type="ollama",
        model_tier="low",
    )
    profile = build_local_pipeline_profile(active)
    assert profile is not None
    assert profile.compact_prompt is True
    assert profile.reset_history_each_step is True
    assert profile.knowledge_chars <= 3000


def test_adapt_pipeline_replaces_search_py_goal():
    active = ActiveLlm(
        client=_FakeClient(),
        mode="local",
        provider_id="ollama-lite",
        provider_name="Phi-3",
        model_name="phi3:mini",
        api_type="ollama",
        model_tier="low",
    )
    profile = build_local_pipeline_profile(active)
    pipeline = {
        "steps": [
            {
                "agent_id": "ui-ux-designer",
                "goal": "Run search.py --design-system and persist",
                "max_turns": 7,
            },
            {"agent_id": "security-auditor", "goal": "audit", "max_turns": 5},
            {"agent_id": "lead-developer", "goal": "build", "max_turns": 8},
        ]
    }
    adapted = adapt_pipeline_for_local(pipeline, profile)
    assert len(adapted["steps"]) <= 3
    assert "--design-system" not in adapted["steps"][0]["goal"].lower()
    assert all(s.get("agent_id") != "security-auditor" for s in adapted["steps"])
