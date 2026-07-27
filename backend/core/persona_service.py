"""Промпты персон AI в папке chat/personas/ активного проекта."""

from __future__ import annotations

import re
from pathlib import Path

PERSONAS_REL_DIR = Path("chat") / "personas"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def personas_dir(project_root: Path) -> Path:
    return project_root / PERSONAS_REL_DIR


def ensure_personas_dir(project_root: Path) -> Path:
    """Создать пустую папку chat/personas/ без автозаполнения."""
    target = personas_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _slugify(name: str) -> str:
    base = name.strip().lower()
    base = _SLUG_RE.sub("_", base.replace(" ", "_").replace("-", "_"))
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "persona"


def _unique_persona_path(directory: Path, persona_id: str) -> Path:
    candidate = directory / f"{persona_id}.md"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = directory / f"{persona_id}_{index}.md"
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


def _format_persona_file(
    persona_id: str,
    name: str,
    prompt: str,
    description: str = "",
    category: str = "",
) -> str:
    desc = description or f"Скил: {name}"
    lines = [
        "---",
        f"id: {persona_id}",
        f"name: {name}",
        f"description: {desc}",
    ]
    if category.strip():
        lines.append(f"category: {category.strip()}")
    lines.append("user_created: true")
    lines.extend(["---", "", prompt.strip(), ""])
    return "\n".join(lines)


def list_project_personas(project_root: Path) -> list[dict[str, str]]:
    directory = ensure_personas_dir(project_root)
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
        persona_id = meta.get("id") or path.stem
        items.append({
            "id": persona_id,
            "name": meta.get("name") or persona_id,
            "description": meta.get("description", ""),
            "category": meta.get("category", ""),
            "category_ru": "Мои скилы",
            "filename": path.name,
            "source": "project",
        })

    return items


def list_personas(project_root: Path) -> list[dict[str, str]]:
    """Библиотека core_x_skills + скилы проекта chat/personas/."""
    from core.core_x_library import list_library_skills

    library = list_library_skills()
    project = list_project_personas(project_root)
    return library + project


def delete_persona(project_root: Path, persona_id: str) -> dict:
    if persona_id.startswith(("lib:", "agent:")):
        return {"error": "Нельзя удалить скил из библиотеки CoreX"}

    directory = personas_dir(project_root)
    if not directory.is_dir():
        return {"error": "Персона не найдена"}

    for path in directory.glob("*.md"):
        if path.name.upper() == "README.MD":
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = _parse_frontmatter(raw)
        file_id = meta.get("id") or path.stem
        if file_id == persona_id or path.stem == persona_id:
            path.unlink()
            return {"success": True, "id": persona_id}

    return {"error": "Персона не найдена"}


def load_persona_prompt(project_root: Path, persona_id: str | None) -> tuple[str, str]:
    if not persona_id:
        return "", ""

    directory = personas_dir(project_root)
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
        if file_id == persona_id or path.stem == persona_id:
            name = meta.get("name") or file_id
            return name, body

    return "", ""


def create_persona(
    project_root: Path,
    name: str,
    prompt: str,
    category: str = "",
) -> dict:
    name = name.strip()
    prompt = prompt.strip()
    category = category.strip()

    if not name:
        return {"error": "Название скила обязательно"}
    if not prompt:
        return {"error": "Текст промпта обязателен"}

    directory = ensure_personas_dir(project_root)
    persona_id = _slugify(name)
    file_path = _unique_persona_path(directory, persona_id)
    persona_id = file_path.stem

    content = _format_persona_file(persona_id, name, prompt, category=category)
    file_path.write_text(content, encoding="utf-8")

    return {
        "success": True,
        "persona": {
            "id": persona_id,
            "name": name,
            "description": f"Скил: {name}",
            "category": category,
            "filename": file_path.name,
        },
    }
