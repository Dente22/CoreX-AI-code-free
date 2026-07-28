"""Категории скиллов и примеры состава команд (справочник, не автозаполнение)."""

from __future__ import annotations

# Категории для поля category в chat/personas/*.md
SKILL_CATEGORIES: list[dict[str, str]] = [
    {"id": "development", "name": "Разработка", "hint": "Написание и изменение кода, паттерны, рефакторинг"},
    {"id": "testing", "name": "Тестирование", "hint": "Unit/e2e тесты, граничные случаи, проверка регрессий"},
    {"id": "review", "name": "Ревью", "hint": "Code review, стиль, дублирование, читаемость"},
    {"id": "security", "name": "Безопасность", "hint": "Уязвимости, секреты, валидация ввода"},
    {"id": "architecture", "name": "Архитектура", "hint": "Структура проекта, модули, API-дизайн"},
    {"id": "devops", "name": "DevOps", "hint": "Docker, CI/CD, деплой, миграции БД"},
    {"id": "planning", "name": "Планирование", "hint": "Разбор задачи, план шагов до кода"},
    {"id": "other", "name": "Другое", "hint": "Специализированные или нишевые роли"},
]

# Примеры команд — только подсказки в UI/доках; создаются вручную из ваших скилов
TEAM_PRESETS: list[dict] = [
    {
        "id": "dev-team",
        "name": "Команда разработки",
        "description": "Код → тесты → ревью",
        "categories": ["development", "testing", "review"],
        "example_steps": [
            {"role": "Разработчик", "category": "development"},
            {"role": "Тестировщик", "category": "testing"},
            {"role": "Ревьюер", "category": "review"},
        ],
    },
    {
        "id": "quick-fix",
        "name": "Быстрое исправление",
        "description": "Разработчик → ревьюер (без отдельного тест-этапа)",
        "categories": ["development", "review"],
        "example_steps": [
            {"role": "Разработчик", "category": "development"},
            {"role": "Ревьюер", "category": "review"},
        ],
    },
    {
        "id": "secure-feature",
        "name": "Безопасная фича",
        "description": "Разработка → security review → тесты",
        "categories": ["development", "security", "testing"],
        "example_steps": [
            {"role": "Разработчик", "category": "development"},
            {"role": "Security", "category": "security"},
            {"role": "Тестировщик", "category": "testing"},
        ],
    },
]
