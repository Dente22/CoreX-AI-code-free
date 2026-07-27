"""Команды: библиотека core_x_agents/teams + chat/pipelines/ проекта."""

from __future__ import annotations

import json
import re
from pathlib import Path

from core.persona_service import list_project_personas

PIPELINES_REL_DIR = Path("chat") / "pipelines"
_SLUG_RE = re.compile(r"[^a-z0-9_]+")

DEFAULT_LIMITS = {
    "max_total_turns": 22,
    "max_turns_per_step": 7,
    "max_file_writes": 10,
    "delay_between_turns_ms": 600,
    "delay_between_steps_ms": 2500,
}


def pipelines_dir(project_root: Path) -> Path:
    return project_root / PIPELINES_REL_DIR


def ensure_pipelines_dir(project_root: Path) -> Path:
    target = pipelines_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _slugify(name: str) -> str:
    base = name.strip().lower()
    base = _SLUG_RE.sub("_", base.replace(" ", "_").replace("-", "_"))
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "pipeline"


def _unique_pipeline_path(directory: Path, pipeline_id: str) -> Path:
    candidate = directory / f"{pipeline_id}.json"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = directory / f"{pipeline_id}_{index}.json"
        if not candidate.exists():
            return candidate
        index += 1


def _all_skill_ids(project_root: Path) -> set[str]:
    from core.core_x_library import list_library_skills

    return {p["id"] for p in list_library_skills()} | {
        p["id"] for p in list_project_personas(project_root)
    }


def _step_actor_id(step: dict) -> str:
    return (step.get("agent_id") or step.get("persona_id") or "").strip()


def _known_agent_stems() -> set[str]:
    from core.core_x_library import AGENTS_ROOT

    if not AGENTS_ROOT.is_dir():
        return set()
    return {p.stem for p in AGENTS_ROOT.glob("*.md")}


def missing_step_actors(project_root: Path, steps: list) -> list[str]:
    known_skills = _all_skill_ids(project_root)
    known_agents = _known_agent_stems()
    missing: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("agent_id"):
            stem = str(step["agent_id"]).replace("agent:", "")
            if stem not in known_agents:
                missing.append(stem)
            continue
        actor = (step.get("persona_id") or "").strip()
        if not actor:
            missing.append("(пустой этап)")
        elif actor not in known_skills:
            missing.append(actor)
    return missing


def _step_labels(project_root: Path, steps: list) -> list[str]:
    from core.core_x_library import AGENT_NAME_RU, resolve_persona_prompt

    labels: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        actor = _step_actor_id(step)
        role = step.get("role") or actor
        if actor.startswith("agent:"):
            key = actor[6:]
            labels.append(AGENT_NAME_RU.get(key, role))
            continue
        name, _ = resolve_persona_prompt(project_root, actor or None)
        labels.append(name or role)
    return labels


def list_project_pipelines(project_root: Path) -> list[dict]:
    directory = ensure_pipelines_dir(project_root)
    items: list[dict] = []

    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue

        if not data.get("user_created"):
            continue

        steps = data.get("steps") or []
        if not steps or missing_step_actors(project_root, steps):
            continue

        pid = data.get("id") or path.stem
        items.append({
            "id": pid,
            "name": data.get("name") or path.stem,
            "description": data.get("description", ""),
            "steps_count": len(steps),
            "step_labels": _step_labels(project_root, steps),
            "limits": data.get("limits") or {},
            "filename": path.name,
            "source": "project",
            "category_ru": "Мои команды",
        })

    return items


def list_pipelines(project_root: Path) -> list[dict]:
    from core.core_x_library import list_library_teams

    return list_library_teams() + list_project_pipelines(project_root)


def load_pipeline(project_root: Path, pipeline_id: str) -> dict | None:
    if pipeline_id.startswith("lib-team:"):
        from core.core_x_library import load_library_team
        return load_library_team(pipeline_id)

    directory = ensure_pipelines_dir(project_root)
    for path in directory.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = data.get("id") or path.stem
        if pid == pipeline_id or path.stem == pipeline_id:
            if not data.get("user_created"):
                return None
            steps = data.get("steps") or []
            if missing_step_actors(project_root, steps):
                return None
            data["id"] = pid
            return data
    return None


def create_pipeline(
    project_root: Path,
    name: str,
    description: str,
    steps: list[dict],
    limits: dict | None = None,
) -> dict:
    name = name.strip()
    description = description.strip()

    if not name:
        return {"error": "Название команды обязательно"}
    if not steps:
        return {"error": "Добавьте хотя бы один этап (скил)"}

    directory = ensure_pipelines_dir(project_root)
    known = _all_skill_ids(project_root)
    normalized_steps: list[dict] = []

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            return {"error": f"Этап {index}: неверный формат"}
        persona_id = (step.get("persona_id") or "").strip()
        if not persona_id:
            return {"error": f"Этап {index}: укажите скил"}
        if persona_id not in known:
            return {"error": f"Скил не найден: {persona_id}"}

        normalized_steps.append({
            "persona_id": persona_id,
            "role": (step.get("role") or "").strip() or persona_id,
            "goal": (step.get("goal") or "").strip(),
            "max_turns": int(step.get("max_turns") or DEFAULT_LIMITS["max_turns_per_step"]),
            "allow_writes": step.get("allow_writes", True),
        })

    pipeline_id = _slugify(name)
    file_path = _unique_pipeline_path(directory, pipeline_id)
    pipeline_id = file_path.stem

    payload = {
        "id": pipeline_id,
        "name": name,
        "description": description or f"Команда: {name}",
        "user_created": True,
        "limits": {**DEFAULT_LIMITS, **(limits or {})},
        "steps": normalized_steps,
    }

    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "success": True,
        "pipeline": {
            "id": pipeline_id,
            "name": name,
            "description": payload["description"],
            "steps_count": len(normalized_steps),
            "step_labels": [s["role"] for s in normalized_steps],
            "limits": payload["limits"],
            "filename": file_path.name,
            "source": "project",
            "category_ru": "Мои команды",
        },
    }


def delete_pipeline(project_root: Path, pipeline_id: str) -> dict:
    if pipeline_id.startswith("lib-team:"):
        return {"error": "Нельзя удалить команду из библиотеки CoreX"}

    directory = pipelines_dir(project_root)
    if not directory.is_dir():
        return {"error": "Команда не найдена"}

    for path in directory.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = data.get("id") or path.stem
        if pid == pipeline_id or path.stem == pipeline_id:
            path.unlink()
            return {"success": True, "id": pipeline_id}

    return {"error": "Команда не найдена"}
