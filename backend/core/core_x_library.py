"""Библиотека core_x_skills и core_x_agents (установка CoreX, не папка пользователя)."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_SKILL_REF_RE = re.compile(r"`(core_x_skills/[^`]+\.md)`")


def resolve_corex_root() -> Path:
    """Корень CoreX: репозиторий в dev, resources/ в установленном приложении."""
    env_root = (os.environ.get("COREX_ROOT") or "").strip()
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "core_x_agents").is_dir():
            return candidate

    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent,
        here.parent.parent.parent.parent,
    ]
    for root in candidates:
        if (root / "core_x_agents").is_dir():
            return root
    return here.parent.parent.parent


COREX_ROOT = resolve_corex_root()
SKILLS_ROOT = COREX_ROOT / "core_x_skills"
AGENTS_ROOT = COREX_ROOT / "core_x_agents"
TEAMS_ROOT = AGENTS_ROOT / "teams"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "core_x_skill_catalog.json"

CATEGORY_RU: dict[str, str] = {
    "engineering/core_standards": "Основы разработки",
    "engineering/backend": "Backend",
    "engineering/frontend_ui": "Frontend и UI",
    "design/ui_ux": "Дизайн и UI/UX",
    "engineering/qa_testing": "Тестирование и качество",
    "engineering/security": "Безопасность",
    "engineering/devops_infra": "DevOps и инфраструктура",
    "engineering/languages/python": "Python",
    "engineering/languages/java": "Java / Spring",
    "engineering/languages/golang": "Go",
    "engineering/languages/cpp": "C++",
    "engineering/languages/swift": "Swift / iOS",
    "engineering/languages/kotlin": "Kotlin",
    "engineering/languages/android": "Android",
    "ai_agents/core_ops": "AI-агенты: основы",
    "ai_agents/enterprise": "AI-агенты: enterprise",
    "ai_agents/tools": "AI-агенты: инструменты",
    "ai_agents/loops_learning": "AI-агенты: обучение",
    "business_and_content/marketing_pr": "Маркетинг и контент",
    "business_and_content/investments": "Инвестиции",
    "business_and_content/supply_chain": "Логистика и цепочки",
    "finance_legal_admin/documents": "Документы",
    "finance_legal_admin/legal_compliance": "Право и комплаенс",
    "loops_learning": "Циклы и автономия",
}

AGENT_NAME_RU: dict[str, str] = {
    "lead-developer": "Старший разработчик",
    "qa-engineer": "QA-инженер",
    "code-reviewer": "Ревьюер кода",
    "security-auditor": "Аудитор безопасности",
    "devops-engineer": "DevOps-инженер",
    "architect": "Архитектор",
    "ui-ux-designer": "UI/UX-дизайнер",
}

AGENT_CATEGORY_RU: dict[str, str] = {
    "lead-developer": "Разработка",
    "qa-engineer": "Тестирование",
    "code-reviewer": "Ревью",
    "security-auditor": "Безопасность",
    "devops-engineer": "DevOps",
    "architect": "Архитектура",
    "ui-ux-designer": "Дизайн",
}

TEAM_NAME_RU: dict[str, str] = {
    "dev-team": "Команда разработки",
    "quick-fix": "Быстрое исправление",
    "secure-feature": "Безопасная фича",
    "design-delivery": "Дизайн и разработка",
    "design-delivery-local": "Дизайн и разработка (локально)",
}

NAME_RU: dict[str, str] = {
    "api-design": "API-дизайн",
    "backend-patterns": "Паттерны бэкенда",
    "postgres-patterns": "PostgreSQL",
    "clickhouse-io": "ClickHouse",
    "coding-standards": "Стандарты кода",
    "search-first": "Сначала поиск",
    "strategic-compact": "Стратегическое сжатие контекста",
    "iterative-retrieval": "Итеративный поиск",
    "project-guidelines-example": "Гайдлайны проекта (пример)",
    "frontend-patterns": "Паттерны фронтенда",
    "frontend-slides": "Слайды и презентации UI",
    "liquid-glass-design": "Liquid Glass дизайн",
    "ui-ux-pro-max": "UI/UX Pro Max",
    "ui-ux-design-system": "Генератор design system",
    "ui-ux-style-colors": "Стили, цвета и типографика",
    "ui-ux-ux-review": "UX-ревью и чеклисты",
    "ui-ux-stack-patterns": "UI-паттерны по стеку",
    "tdd-workflow": "TDD-воркфлоу",
    "e2e-testing": "E2E-тестирование",
    "verification-loop": "Цикл верификации",
    "eval-harness": "Eval-harness",
    "plankton-code-quality": "Качество кода (Plankton)",
    "security-review": "Security review",
    "security-scan": "Сканирование безопасности",
    "docker-patterns": "Docker",
    "deployment-patterns": "Деплой",
    "database-migrations": "Миграции БД",
    "python-patterns": "Паттерны Python",
    "python-testing": "Тестирование Python",
    "django-patterns": "Django-паттерны",
    "django-tdd": "Django TDD",
    "django-security": "Безопасность Django",
    "django-verification": "Верификация Django",
    "java-coding-standards": "Стандарты Java",
    "springboot-patterns": "Spring Boot паттерны",
    "springboot-tdd": "Spring Boot TDD",
    "springboot-security": "Spring Boot безопасность",
    "springboot-verification": "Spring Boot верификация",
    "jpa-patterns": "JPA-паттерны",
    "golang-patterns": "Паттерны Go",
    "golang-testing": "Тестирование Go",
    "cpp-coding-standards": "Стандарты C++",
    "cpp-testing": "Тестирование C++",
    "swiftui-patterns": "SwiftUI",
    "swift-concurrency-6-2": "Swift Concurrency",
    "swift-actor-persistence": "Swift Actor persistence",
    "swift-protocol-di-testing": "Swift Protocol DI тесты",
    "foundation-models-on-device": "On-device Foundation Models",
    "kotlin-coroutines-flows": "Kotlin Coroutines",
    "compose-multiplatform-patterns": "Compose Multiplatform",
    "android-clean-architecture": "Clean Architecture Android",
    "agent-harness-construction": "Сборка agent harness",
    "agentic-engineering": "Agentic engineering",
    "ai-first-engineering": "AI-first разработка",
    "configure-ecc": "Настройка ECC",
    "enterprise-agent-ops": "Enterprise agent ops",
    "cost-aware-llm-pipeline": "Cost-aware LLM pipeline",
    "content-hash-cache-pattern": "Content-hash кэш",
    "regex-vs-llm-structured-text": "Regex vs LLM для текста",
    "continuous-learning": "Непрерывное обучение",
    "continuous-learning-v2": "Непрерывное обучение v2",
    "continuous-agent-loop": "Непрерывный agent loop",
    "autonomous-loops": "Автономные циклы",
    "nanoclaw-repl": "NanoClaw REPL",
    "skill-stocktake": "Инвентаризация скилов",
    "ralphinho-rfc-pipeline": "RFC pipeline (Ralphinho)",
    "article-writing": "Написание статей",
    "content-engine": "Контент-движок",
    "market-research": "Исследование рынка",
    "investor-materials": "Материалы для инвесторов",
    "inventory-demand-planning": "Планирование запасов",
    "production-scheduling": "Производственное планирование",
    "quality-nonconformance": "Несоответствия качества",
    "energy-procurement": "Закупка энергии",
    "returns-reverse-logistics": "Обратная логистика",
    "blueprint": "Blueprint документы",
    "nutrient-document-processing": "Обработка документов Nutrient",
    "videodb": "VideoDB",
    "visa-doc-translate": "Перевод визовых документов",
    "customs-trade-compliance": "Таможня и торговый комплаенс",
}


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


def _category_key(rel_parent: str) -> str:
    parts = rel_parent.replace("\\", "/").split("/")
    for length in range(len(parts), 0, -1):
        key = "/".join(parts[:length])
        if key in CATEGORY_RU:
            return key
    return parts[0] if parts else "other"


def _skill_id_from_rel(rel_parent: str, slug: str) -> str:
    if rel_parent in (".", ""):
        return f"lib:{slug}"
    return f"lib:{rel_parent}/{slug}"


def _skill_path_from_id(skill_id: str) -> Path | None:
    if not skill_id.startswith("lib:"):
        return None
    rel = skill_id[4:]
    return SKILLS_ROOT / rel / "SKILL.md"


def invalidate_cache() -> None:
    list_library_skills.cache_clear()
    list_library_agents.cache_clear()
    list_library_teams.cache_clear()
    try:
        from core.knowledge_service import invalidate_knowledge_cache

        invalidate_knowledge_cache()
    except ImportError:
        pass


@lru_cache(maxsize=1)
def list_library_skills() -> list[dict]:
    if CATALOG_PATH.is_file():
        try:
            data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("skills"), list):
                return data["skills"]
        except (OSError, json.JSONDecodeError):
            pass

    if not SKILLS_ROOT.is_dir():
        return []

    items: list[dict] = []
    for path in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        rel = path.relative_to(SKILLS_ROOT)
        rel_parent = str(rel.parent).replace("\\", "/")
        if rel_parent == ".":
            rel_parent = ""
        slug = path.parent.name
        cat_key = _category_key(rel_parent)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = _parse_frontmatter(raw)
        skill_id = _skill_id_from_rel(rel_parent, slug)
        name_ru = NAME_RU.get(slug, meta.get("name", slug).replace("-", " ").title())
        items.append({
            "id": skill_id,
            "name": name_ru,
            "description": meta.get("description", ""),
            "category": cat_key,
            "category_ru": CATEGORY_RU.get(cat_key, cat_key),
            "source": "library",
        })

    items.sort(key=lambda x: (x["category_ru"], x["name"]))
    return items


def load_library_skill(skill_id: str) -> tuple[str, str]:
    path = _skill_path_from_id(skill_id)
    if not path or not path.is_file():
        return "", ""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return "", ""
    meta, body = _parse_frontmatter(raw)
    slug = path.parent.name
    name = NAME_RU.get(slug, meta.get("name", slug))
    return name, body


@lru_cache(maxsize=1)
def list_library_agents() -> list[dict]:
    if not AGENTS_ROOT.is_dir():
        return []
    items: list[dict] = []
    for path in sorted(AGENTS_ROOT.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = _parse_frontmatter(raw)
        agent_id = path.stem
        name = meta.get("name_ru") or AGENT_NAME_RU.get(agent_id) or meta.get("name", agent_id)
        category_ru = meta.get("category_ru") or AGENT_CATEGORY_RU.get(agent_id, "Разработка")
        items.append({
            "id": f"agent:{agent_id}",
            "name": name,
            "description": meta.get("description", ""),
            "category": agent_id,
            "category_ru": category_ru,
            "source": "library",
        })
    return items


def _expand_skill_refs(body: str) -> str:
    blocks: list[str] = [body]
    for match in _SKILL_REF_RE.finditer(body):
        rel = match.group(1)
        skill_path = COREX_ROOT / rel
        if not skill_path.is_file():
            continue
        try:
            raw = skill_path.read_text(encoding="utf-8")
        except OSError:
            continue
        _, skill_body = _parse_frontmatter(raw)
        slug = skill_path.parent.name
        title = NAME_RU.get(slug, slug)
        blocks.append(f"\n\n=== SKILL: {title} ===\n{skill_body}\n")
    return "\n".join(blocks)


def load_library_agent(agent_id: str, *, expand_skills: bool = True) -> tuple[str, str]:
    if agent_id.startswith("agent:"):
        agent_id = agent_id[6:]
    path = AGENTS_ROOT / f"{agent_id}.md"
    if not path.is_file():
        return "", ""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return "", ""
    meta, body = _parse_frontmatter(raw)
    name = meta.get("name_ru") or AGENT_NAME_RU.get(agent_id) or meta.get("name", agent_id)
    if expand_skills:
        body = _expand_skill_refs(body)
    return name, body


@lru_cache(maxsize=1)
def list_library_teams() -> list[dict]:
    if not TEAMS_ROOT.is_dir():
        return []
    items: list[dict] = []
    for path in sorted(TEAMS_ROOT.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        tid = data.get("id") or path.stem
        steps = data.get("steps") or []
        labels: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            aid = step.get("agent_id", "")
            agent_key = aid.replace("agent:", "") if aid.startswith("agent:") else aid
            labels.append(
                AGENT_NAME_RU.get(agent_key, step.get("role") or agent_key)
            )
        items.append({
            "id": f"lib-team:{tid}",
            "name": TEAM_NAME_RU.get(tid, data.get("name") or tid),
            "description": data.get("description", ""),
            "steps_count": len(steps),
            "step_labels": labels,
            "limits": data.get("limits") or {},
            "source": "library",
            "category_ru": "Команды CoreX",
            "filename": path.name,
        })
    return items


def load_library_team(team_id: str) -> dict | None:
    if team_id.startswith("lib-team:"):
        team_id = team_id[9:]
    if not TEAMS_ROOT.is_dir():
        return None
    for path in TEAMS_ROOT.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        tid = data.get("id") or path.stem
        if tid == team_id:
            data["id"] = f"lib-team:{tid}"
            return data
    return None


def resolve_persona_prompt(
    project_root: Path,
    persona_id: str | None,
    *,
    for_orchestrator: bool = False,
) -> tuple[str, str]:
    """Скил: библиотека (lib:) → проект (chat/personas/)."""
    if not persona_id:
        return "", ""

    if persona_id.startswith("lib:"):
        return load_library_skill(persona_id)

    if persona_id.startswith("agent:"):
        name, body = load_library_agent(persona_id, expand_skills=not for_orchestrator)
        if body:
            return name, body
        from core.agent_service import load_project_agent

        return load_project_agent(
            project_root,
            persona_id,
            expand_skills=not for_orchestrator,
        )

    from core.persona_service import load_persona_prompt
    return load_persona_prompt(project_root, persona_id)
