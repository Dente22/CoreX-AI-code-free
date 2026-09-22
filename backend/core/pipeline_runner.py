"""Конвейер: несколько персон/скиллов подряд с лимитами нагрузки."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from core.conversation_memory import save_history, trim_history_for_llm
from core.core_x_library import resolve_persona_prompt
from core.local_pipeline_profile import (
    adapt_pipeline_for_local,
    build_local_pipeline_profile,
    local_team_suggestion_ru,
    pipeline_step_json_hint,
)
from core.orchestrator import _FIX_TASK_PATTERNS
from core.pipeline_service import load_pipeline
from core.device_profile import detect_device_profile
from core.knowledge_service import build_knowledge_bundle
from core.resource_limits import ResourceBudget
from core.workload_limits_service import get_design_folder_path, resolve_step_max_turns
from core.design_handoff import (
    collect_design_bundle,
    designer_handoff_prompt_ru,
    developer_handoff_prompt_ru,
    ensure_design_scaffold,
    format_design_bundle_for_prompt,
    validate_design_handoff,
)
from core.web_delivery_layers import (
    developer_layers_prompt_ru,
    is_web_site_task,
    qa_web_polish_prompt_ru,
)

if TYPE_CHECKING:
    from core.orchestrator import CoreXOrchestrator

MEMORY_REL_PATH = "chat/project_memory.md"


def _pipeline_json_target(raw_actor: str, *, files_written: set[str] | None = None) -> str | None:
    agent = (raw_actor or "").replace("agent:", "").lower()
    written = {p.replace("\\", "/").lower() for p in (files_written or set())}
    if "designer" in agent or "ui-ux" in agent:
        return "design-system/MASTER.md"
    if "developer" in agent or "lead" in agent:
        if "index.html" not in written:
            return "index.html"
        if "style.css" not in written and "styles.css" not in written:
            return "style.css"
        return "script.js"
    return None


def _is_designer_actor(raw_actor: str) -> bool:
    agent = (raw_actor or "").replace("agent:", "").lower()
    return "designer" in agent or "ui-ux" in agent


def _is_developer_actor(raw_actor: str) -> bool:
    agent = (raw_actor or "").replace("agent:", "").lower()
    return "developer" in agent or "lead" in agent


async def run_team_pipeline(
    orchestrator: CoreXOrchestrator,
    *,
    user_task: str,
    pipeline_id: str,
    active_root: Path,
    conversation: list[dict],
    plan_text: str,
    project_snapshot: str,
    requires_writes: bool,
    conversational: bool,
    is_question: bool,
    llm_history: list[dict],
) -> None:
    pipeline = load_pipeline(active_root, pipeline_id)
    if not pipeline:
        orchestrator._broadcast("chat", "CoreX Error", f"Конвейер не найден: {pipeline_id}")
        return

    active = orchestrator._resolve_llm()
    local_profile = build_local_pipeline_profile(active)
    if local_profile:
        pipeline = adapt_pipeline_for_local(pipeline, local_profile)
        orchestrator._broadcast_thinking(local_profile.hint_ru)
        suggestion = local_team_suggestion_ru(active, pipeline_id)
        if suggestion:
            orchestrator._broadcast("chat", "CoreX", suggestion)

    steps = pipeline.get("steps") or []
    if not steps:
        orchestrator._broadcast("chat", "CoreX Error", "Конвейер пуст — добавьте этапы в настройках команды.")
        return

    # In online mode we should NOT rely on device-based limits for stopping.
    # Otherwise Gemini/OpenAI quota issues look like "offline" budget stops.
    device = detect_device_profile()
    online_mode = getattr(active, "mode", "") == "online"

    from core.workload_limits_service import (
        UNLIMITED_WORKLOAD,
        get_design_folder_path,
        is_step_by_step_enabled,
        is_unlimited_limits,
    )

    app_root = orchestrator._app_root()
    unlimited = is_unlimited_limits(app_root)
    step_by_step = is_step_by_step_enabled(app_root)

    if unlimited:
        budget = ResourceBudget.from_dict(UNLIMITED_WORKLOAD, app_root=app_root)
        orchestrator._budget = budget
    elif online_mode:
        budget = ResourceBudget.for_online(pipeline.get("limits"))
        orchestrator._budget = budget

        # Show token-budget context instead of device-based "turn/write" caps.
        try:
            usage = orchestrator.get_token_usage()
            session = usage.get("session") or {}
            daily = usage.get("daily") or {}
            limits = usage.get("limits") or {}
            orchestrator._broadcast_thinking(
                f"Токены API (online): сессия {session.get('total_tokens', 0):,}/"
                f"{limits.get('session_limit', 0):,}, день {daily.get('total_tokens', 0):,}/"
                f"{limits.get('daily_limit', 0):,}"
            )
        except Exception:
            # Fallback: still proceed; budget/status line will be correct.
            pass
    else:
        budget = ResourceBudget.for_device(pipeline.get("limits"), app_root=app_root)
        orchestrator._budget = budget
    step_summaries: list[str] = []

    if unlimited:
        orchestrator._broadcast_thinking("Лимиты отключены (экспериментальный режим)")
    elif not online_mode:
        orchestrator._broadcast_thinking(device.summary_ru())
        orchestrator._broadcast_thinking(
            f"Лимиты конвейера: ходы {budget.max_total_turns}, "
            f"на этап ≤{budget.max_turns_per_step}, записи {budget.max_file_writes}"
        )
    knowledge = build_knowledge_bundle(active_root, user_task)
    if unlimited:
        orchestrator._broadcast("chat", "CoreX", "Лимиты отключены (эксперимент).")
    elif not online_mode:
        orchestrator._broadcast(
            "chat",
            "CoreX",
            (
                f"{device.summary_ru()}. "
                f"Лимиты конвейера: ходы {budget.max_total_turns}, "
                f"на этап ≤{budget.max_turns_per_step}, записи {budget.max_file_writes}"
            ),
        )
    if knowledge.text:
        orchestrator._broadcast_thinking(knowledge.summary_ru())
        orchestrator._broadcast("chat", "CoreX", knowledge.summary_ru())
    orchestrator._broadcast_thinking(
        f"Конвейер «{pipeline.get('name', pipeline_id)}»: {len(steps)} этапов. {budget.status_line()}"
    )

    try:
        for index, step in enumerate(steps, start=1):
            await budget.pause_step()
            role = step.get("role") or f"Этап {index}"
            raw_actor = step.get("agent_id") or step.get("persona_id") or ""
            if step.get("agent_id") and not str(raw_actor).startswith("agent:"):
                persona_id = f"agent:{raw_actor}"
            else:
                persona_id = raw_actor
            goal = step.get("goal", "")
            allow_writes = step.get("allow_writes", True)
            configured_turns = int(step.get("max_turns") or budget.max_turns_per_step)
            step_max_turns = resolve_step_max_turns(
                app_root,
                agent_id=raw_actor,
                step_default=configured_turns,
                slider_limit=budget.max_turns_per_step,
            )
            if unlimited:
                step_max_turns = UNLIMITED_WORKLOAD["max_turns_per_step"]
            budget.begin_step(step_max_turns)

            if not budget.can_turn():
                orchestrator._broadcast("chat", "CoreX", budget.stop_reason() or "Лимит нагрузки.")
                break

            persona_name, _ = resolve_persona_prompt(active_root, persona_id or None)
            label = persona_name or role
            limit_label = "без лимита" if unlimited else f"лимит {step_max_turns} ходов"
            orchestrator._broadcast_thinking(
                f"── Этап {index}/{len(steps)}: {label} ({limit_label}) ──"
            )
            orchestrator._broadcast("chat", "CoreX", f"Этап {index}: {label}")
            orchestrator._broadcast_trace(
                "pipeline",
                "step_start",
                f"Этап {index}/{len(steps)}: {label}",
                node="llm",
                status="active",
                meta={"step": index, "total": len(steps), "role": role},
            )

            prior = "\n".join(f"- {s}" for s in step_summaries)
            design_folder = get_design_folder_path(app_root)
            coding_language = getattr(orchestrator, "_coding_language", "auto")
            web_task_step = is_web_site_task(
                user_task,
                goal,
                coding_language=coding_language,
            )
            fix_context = bool(_FIX_TASK_PATTERNS.search(user_task)) or bool(
                _FIX_TASK_PATTERNS.search(goal)
            )
            is_review_step = index > 1

            # Короткий промпт: детали шагов выдаёт orchestrator по одному кусочку.
            if step_by_step:
                step_prompt = (
                    f"=== TEAM PIPELINE STEP {index}/{len(steps)} ===\n"
                    f"Role: {role}\n"
                    f"User task: {user_task}\n"
                    f"Project: {active_root}\n"
                    f"{project_snapshot}"
                )
                web_block = getattr(orchestrator, "_web_search_block", "") or ""
                if web_block:
                    step_prompt += f"{web_block}\n"
                if prior:
                    step_prompt += f"Previous: {prior}\n"
                if _is_designer_actor(raw_actor):
                    step_prompt += (
                        f"Сохраняй design в {design_folder}/. Relative paths only. "
                        "Один write_file за ход. Не done раньше времени.\n"
                    )
                elif _is_developer_actor(raw_actor):
                    if web_task_step:
                        step_prompt += (
                            f"Сначала читай {design_folder}/ через view_file, потом HTML/CSS. "
                            "Один tool за ход. Не done раньше времени.\n"
                        )
                    else:
                        step_prompt += (
                            "Пиши код по выбранному языку. list_directory / write_file. "
                            "Не читай design-system/, если задача не про сайт.\n"
                        )
                    if web_task_step and not collect_design_bundle(active_root, app_root=app_root):
                        ensure_design_scaffold(
                            active_root,
                            user_task=user_task,
                            app_root=app_root,
                        )
                elif "qa" in (raw_actor or "").replace("agent:", "").lower():
                    step_prompt += "Проверь index.html/style.css vs design. patch при необходимости.\n"
                step_prompt += 'Finish: {"status":"done","message":"what changed — 1-2 sentences, no template phrases"}\n'
            else:
                step_prompt = (
                    f"{plan_text}"
                    f"=== TEAM PIPELINE STEP {index}/{len(steps)} ===\n"
                    f"Role: {role}\n"
                    f"Goal: {goal}\n"
                    f"Original user task: {user_task}\n"
                    f"Active project root: {active_root}\n"
                    f"{project_snapshot}"
                )
                web_block = getattr(orchestrator, "_web_search_block", "") or ""
                if web_block:
                    step_prompt += f"{web_block}\n"
                if prior:
                    step_prompt += f"Previous steps summary:\n{prior}\n"

                if web_task_step and _is_developer_actor(raw_actor):
                    bundle = collect_design_bundle(active_root, app_root=app_root)
                    if not bundle:
                        ensure_design_scaffold(
                            active_root,
                            user_task=user_task,
                            app_root=app_root,
                        )
                        bundle = collect_design_bundle(active_root, app_root=app_root)
                    step_prompt += (
                        f"\n=== DESIGN HANDOFF ({design_folder}) ===\n"
                        f"{format_design_bundle_for_prompt(bundle)}\n"
                    )
                    step_prompt += developer_handoff_prompt_ru(
                        user_task=user_task,
                        design_folder=design_folder,
                    )

                if not allow_writes:
                    step_prompt += "This step: READ and REVIEW only. No write_file unless critical fix.\n"
                else:
                    step_prompt += (
                        "Follow plan. One tool per turn.\n"
                        "To edit an existing file: view_file(path) → patch_file (one line per turn).\n"
                        "If you find a bug (crash, NameError, missing code), you MUST fix it with write_file "
                        "before done — do not only describe the fix in the message.\n"
                    )
                    if fix_context or is_review_step:
                        step_prompt += (
                            "This step requires real changes on disk when issues are found. "
                            "Reporting fixes without write_file is forbidden.\n"
                        )
                    if is_review_step:
                        step_prompt += (
                            "MANDATORY: run run_file on main.py (or project entry) BEFORE done. "
                            "If run fails — fix with write_file and run again. No done without a successful run.\n"
                        )
                json_hint = pipeline_step_json_hint(
                    raw_actor,
                    user_task=user_task,
                    coding_language=coding_language,
                )
                if json_hint:
                    step_prompt += f"\n=== REQUIRED JSON FORMAT ===\n{json_hint}\n"
                if _is_designer_actor(raw_actor):
                    step_prompt += (
                        "\n=== DESIGNER STEP (strict) ===\n"
                        "- Skip browsing folders. Do NOT view_file on directory names.\n"
                        "- Сохрани spec в design-system/ — разработчик читает только эти файлы.\n"
                        "- Relative paths only. No C:/ absolute paths.\n"
                        "- Colors: #9A5EFF, #00D2FF. Не done без write_file в design-system/.\n"
                    )
                if web_task_step:
                    if _is_designer_actor(raw_actor):
                        step_prompt += designer_handoff_prompt_ru(
                            user_task=user_task,
                            design_folder=design_folder,
                        )
                    elif _is_developer_actor(raw_actor):
                        step_prompt += developer_layers_prompt_ru(user_task=user_task)
                    elif "qa" in (raw_actor or "").replace("agent:", "").lower():
                        step_prompt += qa_web_polish_prompt_ru()
                step_prompt += f"Resource budget: {budget.status_line()}\n"
                step_prompt += 'Finish this step: {"status":"done","message":"what changed — 1-2 sentences, no template phrases"}\n'

            step_prompt = orchestrator._inject_project_memory(
                step_prompt,
                active_root,
                max_chars=800 if (local_profile and local_profile.model_tier == "low") else (1200 if online_mode else None),
            )
            orchestrator.system_prompt = orchestrator._build_system_prompt(
                active_root,
                persona_id or None,
                user_task=user_task,
                step_role=role,
                compact=bool((local_profile and local_profile.compact_prompt) or online_mode),
                knowledge_char_cap=(
                    local_profile.knowledge_chars
                    if local_profile
                    else (2500 if online_mode else None)
                ),
            )

            if online_mode:
                step_history = trim_history_for_llm(llm_history, max_turns=4, max_chars=2000)
            else:
                step_history = [] if local_profile and local_profile.reset_history_each_step else llm_history

            first_step_chat = conversational and index == 1
            first_step_question = is_question and index == 1
            step_requires = (
                allow_writes
                and not first_step_chat
                and not first_step_question
                and (requires_writes or fix_context)
            )
            enforce_writes = allow_writes and not first_step_chat and fix_context
            if web_task_step and _is_designer_actor(raw_actor):
                step_requires = True
                enforce_writes = True
            if web_task_step and _is_developer_actor(raw_actor):
                step_requires = True
                enforce_writes = True
            require_verification = (
                allow_writes and not first_step_chat and (is_review_step or fix_context or step_requires)
            )
            if local_profile and local_profile.relax_verification:
                require_verification = False

            reply = await orchestrator._run_agent_loop(
                current_prompt=step_prompt,
                llm_history=step_history,
                active_root=active_root,
                conversational=first_step_chat,
                is_question=first_step_question,
                requires_writes=step_requires,
                enforce_writes=enforce_writes,
                require_verification=require_verification,
                persona_id=persona_id or None,
                local_num_predict=local_profile.num_predict_agent if local_profile else None,
                json_target_path=_pipeline_json_target(raw_actor),
                local_compact=bool(local_profile),
                user_task=user_task,
            )

            if reply:
                step_summaries.append(f"{label}: {reply}")
            else:
                step_summaries.append(f"{label}: этап завершён (лимит или без отчёта)")

            if web_task_step and _is_designer_actor(raw_actor):
                validation = validate_design_handoff(active_root, app_root=app_root)
                if not validation.ok:
                    created = ensure_design_scaffold(
                        active_root,
                        user_task=user_task,
                        app_root=app_root,
                    )
                    if created:
                        orchestrator._broadcast(
                            "chat",
                            "CoreX",
                            f"Design fallback: созданы файлы — {', '.join(created)}",
                        )
                    validation = validate_design_handoff(active_root, app_root=app_root)
                if validation.ok:
                    step_summaries[-1] = (
                        f"{label}: Design сохранён на диск ({validation.summary})"
                    )
                    orchestrator._broadcast_thinking(
                        f"Design handoff OK: {validation.summary}"
                    )
                else:
                    step_summaries[-1] = (
                        f"{label}: ⚠ Design неполный — {validation.error}"
                    )

            # Online provider quota failures (429) return critical error from the model.
            # In that case continuing the pipeline only produces misleading "stage finished" records.
            if online_mode and reply is None:
                break

            if budget.stop_reason() and budget.turns_used >= budget.max_total_turns:
                break

        final = "Конвейер завершён.\n" + "\n".join(step_summaries)
        final += f"\n\n{budget.status_line()}"
        orchestrator._broadcast("chat", "CoreX Status", final)
        conversation.append({"role": "assistant", "content": final})
        save_history(active_root, conversation)

    finally:
        orchestrator._budget = None
