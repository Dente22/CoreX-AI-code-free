"""Создание нового проекта на диске (папка + scaffold)."""

from __future__ import annotations

import re
from pathlib import Path

from core.agent_service import ensure_agents_dir
from core.persona_service import ensure_personas_dir
from core.pipeline_service import ensure_pipelines_dir

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_\-\u0400-\u04FF]+")


def _slugify(name: str) -> str:
    base = name.strip()
    base = _SLUG_RE.sub("-", base.replace(" ", "-"))
    base = re.sub(r"-+", "-", base).strip("-")
    return base or "project"


def build_project_scaffold_task(name: str, description: str, project_root: Path) -> str:
    folder = str(project_root.resolve())
    desc = description.strip() or f"Проект {name}"
    return (
        f"Создай полноценный рабочий проект «{name}» по описанию:\n{desc}\n\n"
        f"Рабочая папка уже открыта в CoreX:\n{folder}\n\n"
        "Требования:\n"
        "- Создай ВСЕ нужные файлы в корне этой папки (main.py / app entry, README.md, requirements или package.json).\n"
        "- Не создавай вложенную подпапку с именем проекта.\n"
        "- Код должен запускаться: после записи проверь через run_file или run_command.\n"
        "- Добавь минимальные тесты, если уместно.\n"
        "- Обнови chat/project_memory.md после основных файлов.\n"
        "- Используй режим production-ready: без заглушек и пустых pass."
    )


def create_project(
    parent_path: Path,
    name: str,
    description: str = "",
    stack: str = "python",
) -> dict:
    name = name.strip()
    description = description.strip()
    stack = (stack or "python").strip().lower()

    if not name:
        return {"error": "Название проекта обязательно"}

    parent = Path(parent_path).expanduser().resolve()
    if not parent.is_dir():
        return {"error": f"Родительская папка не найдена: {parent}"}

    slug = _slugify(name)
    project_path = parent / slug
    if project_path.exists():
        try:
            if any(project_path.iterdir()):
                return {"error": f"Папка уже существует и не пуста: {project_path}"}
        except OSError:
            return {"error": f"Не удалось проверить папку: {project_path}"}
    else:
        project_path.mkdir(parents=True, exist_ok=True)

    ensure_personas_dir(project_path)
    ensure_agents_dir(project_path)
    ensure_pipelines_dir(project_path)

    readme_lines = [
        f"# {name}",
        "",
        description or f"Проект {name}, создан в CoreX.",
        "",
        "## Стек",
        f"- {stack}",
        "",
        "## Запуск",
        "Следуйте инструкциям в файлах проекта после генерации AI.",
        "",
    ]
    readme_path = project_path / "README.md"
    if not readme_path.is_file():
        readme_path.write_text("\n".join(readme_lines), encoding="utf-8")

    memory_dir = project_path / "chat"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = memory_dir / "project_memory.md"
    if not memory_path.is_file():
        memory_path.write_text(
            f"# Память проекта: {name}\n\n{description}\n",
            encoding="utf-8",
        )

    return {
        "success": True,
        "root": str(project_path),
        "name": name,
        "slug": slug,
        "stack": stack,
        "task": build_project_scaffold_task(name, description, project_path),
    }
