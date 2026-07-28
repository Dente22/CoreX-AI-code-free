"""Профиль конвейера для локальных моделей (Ollama / phi3 / qwen)."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.ai_provider_catalog import get_preset
from core.device_profile import detect_device_profile

if TYPE_CHECKING:
    from core.llm_runtime import ActiveLlm

ModelTier = Literal["low", "medium", "high"]

_SEARCH_PY_GOAL = re.compile(
    r"search\.py|ui-ux-pro-max\s+search|--design-system|--persist",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LocalPipelineProfile:
    model_tier: ModelTier
    compact_prompt: bool
    reset_history_each_step: bool
    knowledge_chars: int
    num_predict_agent: int
    num_predict_tool: int
    relax_verification: bool
    hint_ru: str


def resolve_model_tier(active: ActiveLlm) -> ModelTier:
    preset = get_preset(active.provider_id) if active.provider_id else None
    if preset:
        return preset.tier  # type: ignore[return-value]
    model = (active.model_name or "").lower()
    if any(token in model for token in ("phi3", "phi-3", "mini", "1b", "2b", "3b")):
        return "low"
    if any(token in model for token in ("7b", "8b", "coder")):
        return "medium"
    return "high"


def build_local_pipeline_profile(active: ActiveLlm) -> LocalPipelineProfile | None:
    if active.mode != "local":
        return None

    model_tier = resolve_model_tier(active)
    device = detect_device_profile()

    if model_tier == "low":
        return LocalPipelineProfile(
            model_tier="low",
            compact_prompt=True,
            reset_history_each_step=True,
            knowledge_chars=2_500,
            num_predict_agent=1_024,
            num_predict_tool=640,
            relax_verification=True,
            hint_ru=(
                "Локальный режим (малый контекст): один файл за ход, пиши развёрнутый content, "
                "без run_command на скриптах — только write_file / view_file."
            ),
        )

    if model_tier == "medium" or device.tier != "high":
        return LocalPipelineProfile(
            model_tier="medium",
            compact_prompt=True,
            reset_history_each_step=True,
            knowledge_chars=5_000,
            num_predict_agent=2_560,
            num_predict_tool=1_024,
            relax_verification=False,
            hint_ru=(
                "Локальный режим: один файл за ход, но content должен быть длинным "
                "(HTML ≥1200, CSS ≥1400, JS ≥500 символов)."
            ),
        )

    return LocalPipelineProfile(
        model_tier="high",
        compact_prompt=False,
        reset_history_each_step=False,
        knowledge_chars=8_000,
        num_predict_agent=3_072,
        num_predict_tool=1_536,
        relax_verification=False,
        hint_ru="Локальный режим (сильная модель): полный промпт, длинные файлы за ход.",
    )


def adapt_pipeline_for_local(pipeline: dict, profile: LocalPipelineProfile) -> dict:
    """Упростить цели этапов, которые требуют тяжёлых CLI-скриптов."""
    adapted = copy.deepcopy(pipeline)
    steps = adapted.get("steps") or []
    new_steps: list[dict] = []

    for step in steps:
        if not isinstance(step, dict):
            continue
        step_copy = dict(step)
        goal = str(step_copy.get("goal") or "")

        if profile.model_tier in ("low", "medium") and _SEARCH_PY_GOAL.search(goal):
            step_copy["goal"] = (
                "Создай краткий Design Spec в design-system/MASTER.md через write_file: "
                "палитра (#9A5EFF, #00D2FF), шрифты, 3–5 компонентов, 2 anti-patterns. "
                "Не вызывай run_command и внешние CLI-скрипты — только write_file."
            )
            step_copy["max_turns"] = min(int(step_copy.get("max_turns") or 8), 10)

        if profile.model_tier == "low" and step_copy.get("agent_id") == "security-auditor":
            continue

        new_steps.append(step_copy)

    if profile.model_tier == "low" and len(new_steps) > 3:
        new_steps = new_steps[:3]

    adapted["steps"] = new_steps
    limits = dict(adapted.get("limits") or {})
    if profile.model_tier == "low":
        limits.setdefault("max_total_turns", 36)
        limits.setdefault("max_turns_per_step", 12)
        limits.setdefault("max_file_writes", 12)
    adapted["limits"] = limits
    return adapted


def recommended_local_team_id(model_tier: ModelTier) -> str:
    if model_tier == "low":
        return "lib-team:design-delivery-local"
    return "lib-team:design-delivery"


def local_team_suggestion_ru(active: ActiveLlm, pipeline_id: str) -> str | None:
    if active.mode != "local":
        return None
    if pipeline_id in {"lib-team:design-delivery", "design-delivery"}:
        return (
            "Для локальных моделей рекомендуем команду "
            "«Дизайн и разработка (локально)» — дизайнер, разработчик и QA без CLI-скриптов."
        )
    return None


def compact_persona_for_local(persona_body: str, persona_id: str | None) -> str:
    """Урезать персону для локальных моделей — убрать run_command/search.py."""
    agent = (persona_id or "").replace("agent:", "").lower()
    head = "\n".join((persona_body or "").strip().splitlines()[:8])[:480]
    if "designer" in agent or "ui-ux" in agent:
        return (
            f"{head}\n\n"
            "ЛОКАЛЬНЫЙ РЕЖИМ CoreX (дизайнер):\n"
            "- Сохрани spec в design-system/ (MASTER.md, pages/index.md, blocks/*.md).\n"
            "- ПЕРВЫЙ ход: write_file design-system/MASTER.md\n"
            "- Затем pages/index.md и blocks/hero.md, blocks/navigation.md, blocks/sections.md\n"
            "- НЕ view_file для папок. Только относительные пути.\n"
            "- run_command ЗАПРЕЩЁН. done только после write_file в design-system/.\n"
        )
    if "developer" in agent or "lead" in agent:
        return (
            f"{head}\n\n"
            "ЛОКАЛЬНЫЙ РЕЖИМ CoreX (разработчик, веб-слои):\n"
            "1) view_file design-system/MASTER.md и pages/index.md\n"
            "2) write_file index.html (+ style.css link + script.js)\n"
            "3) write_file style.css — тёмный gradient, cards, @media\n"
            "4) write_file script.js — nav toggle + smooth scroll + CTA\n"
            "5) без run_command. Не done без script.js.\n"
        )
    if "qa" in agent:
        return (
            f"{head}\n\n"
            "ЛОКАЛЬНЫЙ РЕЖИМ CoreX:\n"
            "- view_file, patch_file, run_file. Один JSON за ход.\n"
        )
    return head[:700]


def pipeline_step_json_hint(agent_id: str | None, *, user_task: str = "") -> str:
    agent = (agent_id or "").replace("agent:", "").lower()
    if "designer" in agent or "ui-ux" in agent:
        return (
            "TURN 1 — write_file design-system/MASTER.md (full spec):\n"
            '{"status":"act","server":"filesystem","tool":"write_file",'
            '"arguments":{"path":"design-system/MASTER.md","content":"# Design Spec\\n..."}}\n'
            "TURN 2 — write_file design-system/pages/index.md:\n"
            '{"status":"act","server":"filesystem","tool":"write_file",'
            '"arguments":{"path":"design-system/pages/index.md","content":"# Page index\\n..."}}'
        )
    if "developer" in agent or "lead" in agent:
        return (
            "LAYER 1 — view_file design-system/MASTER.md\n"
            '{"status":"act","server":"filesystem","tool":"view_file",'
            '"arguments":{"path":"design-system/MASTER.md"}}\n'
            "LAYER 2 — view_file design-system/pages/index.md\n"
            "LAYER 3 — write_file index.html + style.css по spec\n"
        )
    return ""


COMPACT_AGENT_SYSTEM_PROMPT = (
    "You are CoreX agent. Reply with ONE raw JSON object per turn.\n"
    "Tools:\n"
    '- view_file: {"status":"act","server":"filesystem","tool":"view_file","arguments":{"path":"main.py"}}\n'
    '- write_file: {"status":"act","server":"filesystem","tool":"write_file","arguments":{"path":"index.html","content":"..."}}\n'
    '- patch_file: {"status":"act","server":"filesystem","tool":"patch_file","arguments":{"path":"main.py","op":"replace","line":1,"content":"fix"}}\n'
    '- run_file: {"status":"act","server":"terminal","tool":"run_file","arguments":{"path":"main.py"}}\n'
    "Rules: new files → write_file (one file per turn). Edit → view_file then patch_file. "
    "Avoid run_command on local PC. Finish: {\"status\":\"done\",\"message\":\"кратко по-русски\"}.\n"
    "Escape quotes in content. No markdown outside JSON.\n"
)
