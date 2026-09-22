"""TDD: execute_task не вызывает планирование на приветствие."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_runtime import ActiveLlm
from core.orchestrator import CoreXOrchestrator


class _FakeLlmClient:
    model_name = "qwen2.5-coder:3b"


@pytest.fixture
def orchestrator() -> CoreXOrchestrator:
    return CoreXOrchestrator(
        ollama_client=MagicMock(),
        mcp_manager=MagicMock(),
        gui=MagicMock(),
    )


@pytest.mark.asyncio
async def test_planning_phase_guard_returns_none_for_greeting(
    orchestrator: CoreXOrchestrator,
    tmp_path,
):
    project = tmp_path / "proj"
    project.mkdir()
    result = await orchestrator._run_planning_phase(
        "привет",
        project,
        [],
        "",
    )
    assert result is None


@pytest.mark.asyncio
async def test_execute_task_skips_planning_for_greeting(
    orchestrator: CoreXOrchestrator,
    tmp_path,
):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "chat").mkdir()

    planning = AsyncMock(return_value=None)
    agent_loop = AsyncMock(return_value='{"status":"done","message":"Привет!"}')
    thinking: list[str] = []

    orchestrator._run_planning_phase = planning
    orchestrator._run_agent_loop = agent_loop
    orchestrator._broadcast_thinking = lambda msg: thinking.append(msg)

    ready = ActiveLlm(
        client=_FakeLlmClient(),
        mode="local",
        provider_id="ollama-qwen",
        provider_name="Qwen",
        model_name="qwen2.5-coder:3b",
        api_type="ollama",
    )

    with patch("core.orchestrator.ensure_llm_ready", new=AsyncMock(return_value=True)):
        with patch.object(orchestrator, "_resolve_llm", return_value=ready):
            with patch.object(
                orchestrator,
                "_resolve_ready_llm",
                new=AsyncMock(return_value=ready),
            ):
                await orchestrator.execute_task(
                    "привет",
                    project_root=str(project),
                    history=[],
                )

    planning.assert_not_called()
    assert any("без планирования" in msg.lower() for msg in thinking)
