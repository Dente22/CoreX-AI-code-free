"""Пользовательские агенты в chat/agents/ активного проекта."""

from __future__ import annotations

import re
from pathlib import Path

AGENTS_REL_DIR = Path("chat") / "agents"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def agents_dir(project_root: Path) -> Path:
    return project_root / AGENTS_REL_DIR


def ensure_agents_dir(project_root: Path) -> Path:
    target = agents_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _slugify(name: str) -> str:
    base = name.strip().lower()
    base = _SLUG_RE.sub("_", base.replace(" ", "_").replace("-", "_"))
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "agent"


def _unique_agent_path(directory: Path, agent_id: str) -> Path:
    candidate = directory / f"{agent_id}.md"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = directory / f"{agent_id}_{index}.md"
        if not candidate.exists():
            return candidate
        index += 1


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text.strip())
    if not match:
        return {}, text.strip()

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, match.group(2).strip()


def _format_agent_file(
    agent_id: str,
    name: str,
    prompt: str,
    description: str = "",
    category_ru: str = "",
) -> str:
    desc = description or f"Агент: {name}"
    category = category_ru.strip() or "Мои агенты"
    lines = [
        "---",
        f"id: {agent_id}",
        f"name: {name}",
        f"name_ru: {name}",
        f"description: {desc}",
        f"category_ru: {category}",
        "user_created: true",
        "---",
        "",
        prompt.strip(),
        "",
    ]
    return "\n".join(lines)


def list_project_agents(project_root: Path) -> list[dict[str, str]]:
    directory = ensure_agents_dir(project_root)
    items: list[dict[str, str]] = []

    for path in sorted(directory.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = _parse_frontmatter(raw)
        if meta.get("user_created") != "true":
            continue
        agent_id = meta.get("id") or path.stem
        name = meta.get("name_ru") or meta.get("name") or agent_id
        items.append({
            "id": f"agent:{agent_id}",
            "name": name,
            "description": meta.get("description", ""),
            "category": agent_id,
            "category_ru": meta.get("category_ru") or "Мои агенты",
            "filename": path.name,
            "source": "project",
        })

    return items


def list_agents(project_root: Path) -> list[dict[str, str]]:
    from core.core_x_library import list_library_agents

    return list_library_agents() + list_project_agents(project_root)


def load_project_agent(
    project_root: Path,
    agent_id: str,
    *,
    expand_skills: bool = True,
) -> tuple[str, str]:
    stem = agent_id[6:] if agent_id.startswith("agent:") else agent_id
    directory = agents_dir(project_root)
    if not directory.is_dir():
        return "", ""

    for path in directory.glob("*.md"):
        if path.name.upper() == "README.MD":
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _parse_frontmatter(raw)
        file_id = meta.get("id") or path.stem
        if file_id == stem or path.stem == stem:
            name = meta.get("name_ru") or meta.get("name") or file_id
            if expand_skills:
                from core.core_x_library import _expand_skill_refs

                body = _expand_skill_refs(body)
            return name, body

    return "", ""


def delete_agent(project_root: Path, agent_id: str) -> dict:
    stem = agent_id[6:] if agent_id.startswith("agent:") else agent_id
    directory = agents_dir(project_root)
    if not directory.is_dir():
        return {"error": "Агент не найден"}

    for path in directory.glob("*.md"):
        if path.name.upper() == "README.MD":
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = _parse_frontmatter(raw)
        if meta.get("user_created") != "true":
            continue
        file_id = meta.get("id") or path.stem
        if file_id == stem or path.stem == stem:
            path.unlink()
            return {"success": True, "id": f"agent:{file_id}"}

    return {"error": "Нельзя удалить агента из библиотеки CoreX"}


def create_agent(
    project_root: Path,
    name: str,
    prompt: str,
    category_ru: str = "",
) -> dict:
    name = name.strip()
    prompt = prompt.strip()
    category_ru = category_ru.strip()

    if not name:
        return {"error": "Название агента обязательно"}
    if not prompt:
        return {"error": "Текст промпта обязателен"}

    directory = ensure_agents_dir(project_root)
    agent_id = _slugify(name)
    file_path = _unique_agent_path(directory, agent_id)
    agent_id = file_path.stem

    content = _format_agent_file(agent_id, name, prompt, category_ru=category_ru)
    file_path.write_text(content, encoding="utf-8")

    category = category_ru or "Мои агенты"
    return {
        "success": True,
        "agent": {
            "id": f"agent:{agent_id}",
            "name": name,
            "description": f"Агент: {name}",
            "category": agent_id,
            "category_ru": category,
            "filename": file_path.name,
            "source": "project",
        },
    }
