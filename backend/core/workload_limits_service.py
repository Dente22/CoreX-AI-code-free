"""Настраиваемые лимиты нагрузки для локального AI (ползунок в настройках)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from core.core_x_library import COREX_ROOT
from core.device_profile import Tier

LIMITS_FILENAME = "ai_workload_limits.json"
DEFAULT_TEAM_PIPELINE = "design-delivery-local"

# Абсолютный минимум: самый слабый ПК, на котором ещё реально тянуть локальную LLM.
GLOBAL_WORKLOAD_MIN: dict[str, int] = {
    "max_total_turns": 20,
    "max_turns_per_step": 10,
    "max_file_writes": 12,
    "delay_between_turns_ms": 800,
    "delay_between_steps_ms": 2500,
}

# Абсолютный максимум: топовое железо (RTX 5090, i9, 64+ ГБ RAM) — ползунок 100%.
GLOBAL_WORKLOAD_MAX: dict[str, int] = {
    "max_total_turns": 96,
    "max_turns_per_step": 32,
    "max_file_writes": 50,
    "delay_between_turns_ms": 200,
    "delay_between_steps_ms": 800,
}

TurnsLimitMode = Literal["team", "per_agent"]

# Рекомендуемая позиция ползунка под обнаруженное железо (не ограничивает максимум).
_TIER_DEFAULT_SLIDER: dict[Tier, int] = {
    "low": 35,
    "medium": 52,
    "high": 72,
}

_LIMIT_KEYS = tuple(GLOBAL_WORKLOAD_MIN.keys())

UNLIMITED_WORKLOAD: dict[str, int] = {
    "max_total_turns": 9999,
    "max_turns_per_step": 9999,
    "max_file_writes": 9999,
    "delay_between_turns_ms": 0,
    "delay_between_steps_ms": 0,
}

DEFAULT_DESIGN_FOLDER = "design-system"


@dataclass(frozen=True)
class CustomTurnLimits:
    enabled: bool
    mode: TurnsLimitMode
    team_max_total_turns: int
    team_max_turns_per_step: int
    per_agent_turns: dict[str, int]


def _chat_dir(app_root: Path) -> Path:
    return app_root / "chat"


def _limits_path(app_root: Path) -> Path:
    return _chat_dir(app_root) / LIMITS_FILENAME


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_slider_for_tier(tier: Tier) -> int:
    return int(_TIER_DEFAULT_SLIDER.get(tier, _TIER_DEFAULT_SLIDER["medium"]))


def interpolate_workload_limits(slider: int, tier: Tier | None = None) -> dict[str, int]:
    del tier  # шкала единая для всех; tier влияет только на рекомендацию по умолчанию
    pct = max(0, min(100, int(slider))) / 100.0
    return {
        key: int(
            round(
                GLOBAL_WORKLOAD_MIN[key]
                + (GLOBAL_WORKLOAD_MAX[key] - GLOBAL_WORKLOAD_MIN[key]) * pct
            )
        )
        for key in _LIMIT_KEYS
    }


def load_default_team_steps() -> list[dict[str, Any]]:
    path = COREX_ROOT / "core_x_agents" / "teams" / f"{DEFAULT_TEAM_PIPELINE}.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    steps = data.get("steps") or []
    rows: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        agent_id = str(step.get("agent_id") or "").strip()
        if not agent_id:
            continue
        rows.append(
            {
                "agent_id": agent_id,
                "role": step.get("role") or agent_id,
                "default_max_turns": int(step.get("max_turns") or 10),
            }
        )
    return rows


def _parse_custom_turn_limits(raw: dict[str, Any]) -> CustomTurnLimits:
    per_agent_raw = raw.get("per_agent_turns") or {}
    per_agent: dict[str, int] = {}
    if isinstance(per_agent_raw, dict):
        for key, value in per_agent_raw.items():
            agent = str(key or "").replace("agent:", "").strip()
            turns = int(value or 0)
            if agent and turns > 0:
                per_agent[agent] = turns
    mode = str(raw.get("turns_limit_mode") or "team").strip().lower()
    if mode not in {"team", "per_agent"}:
        mode = "team"
    return CustomTurnLimits(
        enabled=bool(raw.get("turns_limit_enabled")),
        mode=mode,  # type: ignore[arg-type]
        team_max_total_turns=max(0, int(raw.get("team_max_total_turns") or 0)),
        team_max_turns_per_step=max(0, int(raw.get("team_max_turns_per_step") or 0)),
        per_agent_turns=per_agent,
    )


def get_custom_turn_limits(app_root: Path | None) -> CustomTurnLimits:
    root = app_root or COREX_ROOT
    raw = _load_json(_limits_path(root))
    return _parse_custom_turn_limits(raw)


def get_saved_slider(app_root: Path | None, *, tier: Tier) -> int:
    root = app_root or COREX_ROOT
    raw = _load_json(_limits_path(root))
    if "slider" in raw:
        return max(0, min(100, int(raw.get("slider") or 0)))
    return default_slider_for_tier(tier)


def set_workload_slider(app_root: Path, slider: int) -> dict[str, Any]:
    value = max(0, min(100, int(slider)))
    path = _limits_path(app_root)
    raw = _load_json(path)
    raw["slider"] = value
    _save_json(path, raw)
    return {"success": True, "slider": value}


def save_workload_settings(app_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _limits_path(app_root)
    raw = _load_json(path)
    if "slider" in payload:
        raw["slider"] = max(0, min(100, int(payload.get("slider") or 0)))
    if "turns_limit_enabled" in payload:
        raw["turns_limit_enabled"] = bool(payload.get("turns_limit_enabled"))
    if "turns_limit_mode" in payload:
        mode = str(payload.get("turns_limit_mode") or "team").strip().lower()
        raw["turns_limit_mode"] = mode if mode in {"team", "per_agent"} else "team"
    if "team_max_total_turns" in payload:
        raw["team_max_total_turns"] = max(0, int(payload.get("team_max_total_turns") or 0))
    if "team_max_turns_per_step" in payload:
        raw["team_max_turns_per_step"] = max(0, int(payload.get("team_max_turns_per_step") or 0))
    if "per_agent_turns" in payload and isinstance(payload.get("per_agent_turns"), dict):
        cleaned: dict[str, int] = {}
        for key, value in payload["per_agent_turns"].items():
            agent = str(key or "").replace("agent:", "").strip()
            turns = int(value or 0)
            if agent and turns > 0:
                cleaned[agent] = turns
        raw["per_agent_turns"] = cleaned
    if "unlimited_limits" in payload:
        raw["unlimited_limits"] = bool(payload.get("unlimited_limits"))
    if "step_by_step_enabled" in payload:
        raw["step_by_step_enabled"] = bool(payload.get("step_by_step_enabled"))
    if "design_folder_path" in payload:
        raw["design_folder_path"] = str(payload.get("design_folder_path") or "").strip()
    _save_json(path, raw)
    return {"success": True}


def _load_workflow_raw(app_root: Path | None) -> dict[str, Any]:
    root = app_root or COREX_ROOT
    return _load_json(_limits_path(root))


def is_unlimited_limits(app_root: Path | None) -> bool:
    return bool(_load_workflow_raw(app_root).get("unlimited_limits"))


def is_step_by_step_enabled(app_root: Path | None) -> bool:
    raw = _load_workflow_raw(app_root)
    if "step_by_step_enabled" in raw:
        return bool(raw.get("step_by_step_enabled"))
    return True


def get_design_folder_path(app_root: Path | None) -> str:
    raw = _load_workflow_raw(app_root)
    value = str(raw.get("design_folder_path") or "").strip()
    return value or DEFAULT_DESIGN_FOLDER


def get_workload_settings(app_root: Path | None, *, tier: Tier) -> dict[str, Any]:
    root = app_root or COREX_ROOT
    raw = _load_json(_limits_path(root))
    slider = get_saved_slider(root, tier=tier)
    unlimited = bool(raw.get("unlimited_limits"))
    current = dict(UNLIMITED_WORKLOAD) if unlimited else interpolate_workload_limits(slider, tier)
    custom = _parse_custom_turn_limits(raw)
    team_steps = load_default_team_steps()
    per_agent_turns = dict(custom.per_agent_turns)
    for step in team_steps:
        agent_id = step["agent_id"]
        per_agent_turns.setdefault(agent_id, int(step.get("default_max_turns") or 10))
    return {
        "slider": slider,
        "default_slider": default_slider_for_tier(tier),
        "tier": tier,
        "limits": current,
        "min_limits": dict(GLOBAL_WORKLOAD_MIN),
        "max_limits": dict(GLOBAL_WORKLOAD_MAX),
        "absolute_max_limits": dict(GLOBAL_WORKLOAD_MAX),
        "turns_limit_enabled": custom.enabled,
        "turns_limit_mode": custom.mode,
        "team_max_total_turns": custom.team_max_total_turns or (
            current["max_total_turns"] if not unlimited else UNLIMITED_WORKLOAD["max_total_turns"]
        ),
        "team_max_turns_per_step": custom.team_max_turns_per_step or (
            current["max_turns_per_step"] if not unlimited else UNLIMITED_WORKLOAD["max_turns_per_step"]
        ),
        "per_agent_turns": per_agent_turns,
        "team_steps": team_steps,
        "team_pipeline_id": DEFAULT_TEAM_PIPELINE,
        "unlimited_limits": unlimited,
        "step_by_step_enabled": is_step_by_step_enabled(root),
        "design_folder_path": get_design_folder_path(root),
    }


def resolve_step_max_turns(
    app_root: Path | None,
    *,
    agent_id: str,
    step_default: int,
    slider_limit: int,
) -> int:
    if is_unlimited_limits(app_root):
        return UNLIMITED_WORKLOAD["max_turns_per_step"]
    custom = get_custom_turn_limits(app_root)
    if not custom.enabled:
        return min(step_default, slider_limit)
    if custom.mode == "per_agent":
        key = (agent_id or "").replace("agent:", "").strip()
        configured = int(custom.per_agent_turns.get(key) or 0)
        if configured > 0:
            return min(configured, GLOBAL_WORKLOAD_MAX["max_turns_per_step"])
    if custom.mode == "team" and custom.team_max_turns_per_step > 0:
        return min(custom.team_max_turns_per_step, GLOBAL_WORKLOAD_MAX["max_turns_per_step"])
    return min(step_default, slider_limit)


def resolve_workload_limits(
    app_root: Path | None,
    *,
    tier: Tier,
    pipeline_limits: dict | None = None,
) -> dict[str, int]:
    if is_unlimited_limits(app_root):
        return dict(UNLIMITED_WORKLOAD)
    slider = get_saved_slider(app_root, tier=tier)
    limits = interpolate_workload_limits(slider, tier)
    custom = get_custom_turn_limits(app_root)
    custom_pipeline = dict(pipeline_limits or {})

    if custom.enabled:
        if custom.team_max_total_turns > 0:
            limits["max_total_turns"] = min(
                custom.team_max_total_turns,
                GLOBAL_WORKLOAD_MAX["max_total_turns"],
            )
        if custom.mode == "team" and custom.team_max_turns_per_step > 0:
            limits["max_turns_per_step"] = min(
                custom.team_max_turns_per_step,
                GLOBAL_WORKLOAD_MAX["max_turns_per_step"],
            )
    else:
        for key in ("max_total_turns", "max_turns_per_step", "max_file_writes"):
            custom_val = int(custom_pipeline.get(key) or 0)
            if custom_val <= 0:
                continue
            limits[key] = min(limits[key], custom_val)

    for key in ("delay_between_turns_ms", "delay_between_steps_ms"):
        custom_val = int(custom_pipeline.get(key) or 0)
        if custom_val <= 0:
            continue
        limits[key] = max(limits[key], custom_val)

    return limits


def workload_limits_summary_ru(settings: dict[str, Any]) -> str:
    if settings.get("unlimited_limits"):
        return "Лимиты отключены (экспериментальный режим)"
    limits = settings.get("limits") or {}
    base = (
        f"Лимиты (ползунок {settings.get('slider', 0)}%): "
        f"ходы {limits.get('max_total_turns', 0)}, "
        f"на этап {limits.get('max_turns_per_step', 0)}, "
        f"записи {limits.get('max_file_writes', 0)}"
    )
    if settings.get("turns_limit_enabled"):
        mode = settings.get("turns_limit_mode")
        if mode == "per_agent":
            return base + " · ручной лимит ходов на каждого агента"
        return base + " · ручной лимит ходов на команду"
    return base
