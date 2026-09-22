"""TDD: локальный профиль конвейера."""

from core.local_pipeline_profile import (
    adapt_pipeline_for_local,
    build_local_pipeline_profile,
    compact_persona_for_local,
    pipeline_step_json_hint,
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


def test_resolve_model_tier_qwen_coder_3b():
    active = ActiveLlm(
        client=_FakeClient(),
        mode="local",
        provider_id="ollama-qwen",
        provider_name="Qwen",
        model_name="qwen2.5-coder:3b",
        api_type="ollama",
    )
    assert resolve_model_tier(active) == "low"
    profile = build_local_pipeline_profile(active)
    assert profile is not None
    assert profile.compact_prompt is True
    assert profile.knowledge_chars <= 800
    assert profile.num_predict_agent <= 512


def test_resolve_model_tier_does_not_treat_13b_as_low():
    active = ActiveLlm(
        client=_FakeClient(),
        mode="local",
        provider_id="",
        provider_name="Qwen",
        model_name="qwen2.5-coder:13b",
        api_type="ollama",
    )
    assert resolve_model_tier(active) != "low"


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
    assert profile.knowledge_chars <= 800


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


def test_compact_persona_python_skips_design_system():
    text = compact_persona_for_local(
        "Lead developer persona",
        "lead-developer",
        coding_language="python",
        user_task="сделай змейку",
    )
    assert "pages/index.md" not in text
    assert "design-system" in text
    assert "Не читай design-system" in text


def test_compact_persona_html_keeps_web_layers():
    text = compact_persona_for_local(
        "Lead developer persona",
        "lead-developer",
        coding_language="html",
        user_task="сделай лендинг",
    )
    assert "pages/index.md" in text


def test_pipeline_hint_python_skips_design_system():
    hint = pipeline_step_json_hint(
        "lead-developer",
        user_task="змейка",
        coding_language="python",
    )
    assert "pages/index.md" not in hint
    assert "```python" in hint
