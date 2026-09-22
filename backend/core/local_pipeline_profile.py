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
    if any(token in model for token in ("phi3", "phi-3", "mini", ":1b", ":2b", ":3b")):
        return "low"
    if any(token in model for token in (":7b", ":8b")):
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
            knowledge_chars=800,
            num_predict_agent=512,
            num_predict_tool=384,
            relax_verification=True,
            hint_ru=(
                "Малая локальная модель (4096 токенов): один файл за ход, "
                "только write_file / view_file / patch_file, без run_command."
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
                "Локальный режим: один полный файл за ход (```python). "
                "Сайт: HTML/CSS/JS по одному файлу за ход."
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


def _local_code_mode_body(head: str, lang_block: str) -> str:
    return (
        f"{head}\n\n"
        f"{lang_block}"
        "ЛОКАЛЬНЫЙ РЕЖИМ CoreX:\n"
        "- list_directory, write_file, append_file, patch_file, run_file.\n"
        "- Новый файл: ПОЛНАЯ программа в ```python. JSON не обязателен.\n"
        "- Один файл целиком за ход. Не каркас из двух print. Не inspect пустой папки.\n"
        "- Не повторяй import. Не копируй инструкции System в файл.\n"
        "- Не читай design-system/ и не пиши HTML, если задача не про сайт.\n"
    )


def compact_persona_for_local(
    persona_body: str,
    persona_id: str | None,
    *,
    coding_language: str = "auto",
    user_task: str = "",
) -> str:
    """Урезать персону для локальных моделей — убрать run_command/search.py."""
    from core.coding_language import language_forces_code, language_prompt_ru
    from core.web_delivery_layers import is_web_site_task

    agent = (persona_id or "").replace("agent:", "").lower()
    head = "\n".join((persona_body or "").strip().splitlines()[:8])[:480]
    lang_block = language_prompt_ru(coding_language)
    web_task = is_web_site_task(user_task, coding_language=coding_language)
    if language_forces_code(coding_language):
        return _local_code_mode_body(head, lang_block)
    if "designer" in agent or "ui-ux" in agent:
        if not web_task:
            return _local_code_mode_body(head, lang_block)
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
        if not web_task:
            return _local_code_mode_body(head, lang_block)
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
    extra = f"\n{lang_block}" if lang_block else ""
    return (head[:700] + extra).strip()


def pipeline_step_json_hint(
    agent_id: str | None,
    *,
    user_task: str = "",
    coding_language: str = "auto",
) -> str:
    from core.coding_language import language_forces_code, resolve_effective_language

    agent = (agent_id or "").replace("agent:", "").lower()
    effective = resolve_effective_language(coding_language, user_task)
    code_hint = (
        "TURN 1 — полный файл. JSON не обязателен:\n"
        "```python\n"
        "# весь рабочий файл — имя подбери сам, не main.py по привычке\n"
        "```\n"
        "Или JSON write_file + тот же блок ``` после него.\n"
        "Не каркас. Не list_directory. Один файл за ход.\n"
        "Do not view_file design-system/."
    )
    if language_forces_code(effective):
        return code_hint
    from core.web_delivery_layers import is_web_site_task

    web_task = is_web_site_task(user_task, coding_language=coding_language)
    if "designer" in agent or "ui-ux" in agent:
        if not web_task:
            return code_hint
        return (
            "TURN 1 — write_file design-system/MASTER.md (full spec):\n"
            '{"status":"act","server":"filesystem","tool":"write_file",'
            '"arguments":{"path":"design-system/MASTER.md","content":"# Design Spec\\n..."}}\n'
            "TURN 2 — write_file design-system/pages/index.md:\n"
            '{"status":"act","server":"filesystem","tool":"write_file",'
            '"arguments":{"path":"design-system/pages/index.md","content":"# Page index\\n..."}}'
        )
    if "developer" in agent or "lead" in agent:
        if not web_task:
            return code_hint
        return (
            "LAYER 1 — view_file design-system/MASTER.md\n"
            '{"status":"act","server":"filesystem","tool":"view_file",'
            '"arguments":{"path":"design-system/MASTER.md"}}\n'
            "LAYER 2 — view_file design-system/pages/index.md\n"
            "LAYER 3 — write_file index.html + style.css по spec\n"
        )
    return ""


COMPACT_AGENT_SYSTEM_PROMPT = (
    "You are CoreX. For a new program, output the COMPLETE file. JSON is optional.\n"
    "Preferred: ```python\\n<full working program>\\n``` — CoreX saves it under a fitting name "
    "(snake.py, calculator.py, or folder/<name>.py if the user said /folder). Do not default to main.py.\n"
    "Optional header then fence: "
    '{"status":"act","server":"filesystem","tool":"write_file","arguments":{"path":"app.py"}}\n'
    "One complete file per turn. Not a 2-line stub. Do not inspect an empty folder first.\n"
    "Edits: view_file then patch_file. Missing pip packages are not syntax errors. "
    "CoreX installs pip into the same Python as Run. "
            "Window/GUI: follow the current plan step only (short tkinter Canvas + mainloop). "
            "Do not raycast. Do not swap in a different app. "
            "Empty pygame window is forbidden. Need mainloop or a real UI loop, not pass. "
    "If pygame is needed, CoreX installs pygame-ce (Python 3.14 has no classic pygame wheels). "
    "Do not replace a working program with an empty pygame window. "
    "CoreX fixes indent/truncation, not program logic.\n"
    'Finish: {"status":"done","message":"кратко по-русски"}.\n'
)
