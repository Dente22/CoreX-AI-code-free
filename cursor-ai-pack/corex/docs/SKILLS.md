# Скилы и команды в CoreX

В интерфейсе отображаются **только реальные файлы** открытого проекта:

| Что | Папка | Как появляется в UI |
|-----|-------|---------------------|
| **Скил** (роль AI) | `chat/personas/*.md` | Кнопка **«Добавить»** в режиме «Один скил» |
| **Команда** (цепочка скилов) | `chat/pipelines/*.json` | Кнопка **«Создать»** в режиме «Команда» |

Шаблоны в `backend/templates/` — справочные примеры. CoreX **не копирует** их в проект автоматически.

---

## Категории скилов

При создании скила можно указать категорию — она сохраняется в frontmatter файла.

| Категория | Когда использовать | Примеры ролей |
|-----------|-------------------|---------------|
| **development** | Написание и изменение кода | Разработчик, Python-эксперт, Frontend |
| **testing** | Тесты, граничные случаи | Тестировщик, QA, E2E |
| **review** | Code review, стиль | Ревьюер, Линтер-наставник |
| **security** | Уязвимости, секреты | Security engineer |
| **architecture** | Структура, API, модули | Архитектор, API designer |
| **devops** | Docker, CI/CD, деплой | DevOps, SRE |
| **planning** | План до кода | Аналитик, Планировщик |
| **other** | Нишевые задачи | Документация, контент |

### Куда отнести скиллы из внешних наборов (ECC / best-practice)

| Тип из каталога | Категория в CoreX |
|-----------------|-------------------|
| `*-patterns`, `coding-standards`, `backend-patterns` | development |
| `*-testing`, `tdd-workflow`, `e2e-testing` | testing |
| `verification-loop`, `code-quality` | review |
| `security-review`, `*-security` | security |
| `api-design`, `docker-patterns` | architecture / devops |
| `deployment-patterns`, `database-migrations` | devops |
| `strategic-compact`, `search-first` | planning |
| Контент, логистика, демо-скиллы | other |

Статический справочник 91 внешнего скила: `backend/data/skills_catalog.json` (для ручного копирования промптов, **не показывается в чате**).

---

## Готовые составы команд

Команда = несколько **ваших** скилов подряд с лимитами нагрузки на ПК.

| Команда | Этапы (категории) | Когда применять |
|---------|-------------------|-----------------|
| **Команда разработки** | development → testing → review | Новая фича, рефакторинг |
| **Быстрое исправление** | development → review | Мелкий баг, hotfix |
| **Безопасная фича** | development → security → testing | Auth, платежи, PII |
| **Только план** | planning → development | Сложная задача, много файлов |
| **DevOps-релиз** | development → devops → review | Деплой, Docker, CI |

Примеры шаблонов JSON: `backend/templates/pipelines/dev-team.json`, `quick-fix.json`.

---

## Инструкция: добавить скил (появится в проекте)

### Через UI (рекомендуется)

1. Откройте папку проекта в CoreX (**Файл → Открыть папку**).
2. В чате выберите режим **«Один скил»**.
3. Нажмите **«Добавить»**.
4. Заполните:
   - **Название** — как в списке (например, «Разработчик»).
   - **Категория** — по таблице выше.
   - **Промпт** — роль и правила для AI.
5. **Сохранить** → файл `chat/personas/<id>.md` создаётся сразу, скил виден в выпадающем списке.

### Вручную (файл)

Создайте `chat/personas/developer.md`:

```markdown
---
id: developer
name: Разработчик
description: Senior-разработчик
category: development
---

Ты опытный разработчик. Пиши чистый код...
```

`id` в frontmatter должен совпадать с тем, на что ссылаются команды (`persona_id`).

Примеры промптов: `backend/templates/personas/*.md`.

---

## Инструкция: создать команду

### Через UI

1. Создайте нужные скилы (минимум один).
2. Режим **«Команда»** → **«Создать»**.
3. Название, описание, добавьте этапы в нужном порядке (можно указать цель этапа).
4. **Сохранить** → `chat/pipelines/<id>.json`.

Команда **не отобразится**, если в JSON указан `persona_id`, которого нет в `chat/personas/`.

### Вручную (JSON)

`chat/pipelines/dev-team.json`:

```json
{
  "id": "dev-team",
  "name": "Команда разработки",
  "description": "Код → тесты → ревью",
  "limits": {
    "max_total_turns": 22,
    "max_turns_per_step": 7,
    "max_file_writes": 10,
    "delay_between_turns_ms": 600,
    "delay_between_steps_ms": 2500
  },
  "steps": [
    {
      "persona_id": "developer",
      "role": "Разработчик",
      "goal": "Реализуй задачу. Один файл за ход.",
      "max_turns": 7,
      "allow_writes": true
    },
    {
      "persona_id": "tester",
      "role": "Тестировщик",
      "goal": "Добавь тесты и проверь граничные случаи.",
      "max_turns": 6,
      "allow_writes": true
    },
    {
      "persona_id": "reviewer",
      "role": "Ревьюер",
      "goal": "Code review. Только критичные правки.",
      "max_turns": 5,
      "allow_writes": true
    }
  ]
}
```

Перед использованием создайте скилы с `id`: `developer`, `tester`, `reviewer`.

---

## Лимиты (защита локального ПК)

| Параметр | Один скил | Команда (по умолчанию) |
|----------|-----------|------------------------|
| Макс. ходов LLM | 24 | 22 |
| Ходов на этап | 8 | 7 |
| Записей файлов | 10 | 10 |
| Пауза между ходами | 500 мс | 600 мс |
| Пауза между этапами | — | 2500 мс |

Настраиваются в `limits` внутри JSON команды.

---

## API (для интеграций)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/personas` | Список скилов проекта |
| POST | `/api/personas` | `{ name, prompt, category? }` |
| GET | `/api/pipelines` | Валидные команды (все persona_id существуют) |
| POST | `/api/pipelines` | `{ name, description, steps[] }` |
| GET | `/api/skills/meta` | Категории и примеры составов (не создаёт файлы) |
