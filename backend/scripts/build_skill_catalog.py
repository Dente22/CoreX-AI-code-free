"""Собрать backend/data/core_x_skill_catalog.json из core_x_skills (запускать при добавлении скилов)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_ROOT = ROOT / "core_x_skills"
OUT = ROOT / "backend" / "data" / "core_x_skill_catalog.json"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

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


def _parse_meta(text: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(text.strip())
    if not match:
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def _category_key(rel_parent: str) -> str:
    parts = rel_parent.replace("\\", "/").split("/")
    for length in range(len(parts), 0, -1):
        key = "/".join(parts[:length])
        if key in CATEGORY_RU:
            return key
    return parts[0] if parts else "other"


def main() -> None:
    items: list[dict] = []
    for path in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        rel = path.relative_to(SKILLS_ROOT)
        rel_parent = str(rel.parent).replace("\\", "/")
        slug = path.parent.name
        cat_key = _category_key(rel_parent)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = _parse_meta(raw)
        skill_id = f"lib:{rel_parent}/{slug}" if rel_parent != "." else f"lib:{slug}"
        name_ru = NAME_RU.get(slug, meta.get("name", slug).replace("-", " ").title())
        items.append({
            "id": skill_id,
            "slug": slug,
            "name": name_ru,
            "name_en": meta.get("name", slug),
            "description": meta.get("description", ""),
            "category": cat_key,
            "category_ru": CATEGORY_RU.get(cat_key, cat_key),
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "source": "library",
        })

    items.sort(key=lambda x: (x["category_ru"], x["name"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"skills": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} skills to {OUT}")


if __name__ == "__main__":
    main()
