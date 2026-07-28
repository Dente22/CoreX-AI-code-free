# Cursor AI Pack — экспорт из CoreX

Портативный набор агентов, скилов, команд и правил, собранный из проекта CoreX для переноса в другой проект.

## Содержимое

Пакет объединяет **три слоя**: Cursor IDE, ECC (внешний набор) и **собственные артефакты CoreX**.

### Слой CoreX (то, что мы делали для самого CoreX)

| Папка / файл | Описание |
|---|---|
| **`corex/agents/`** | Агенты CoreX: Старший разработчик, QA, Ревьюер, Security, DevOps |
| **`corex/teams/`** | Команды агентов CoreX (`agent_id`: dev-team, quick-fix, secure-feature) |
| **`corex/personas/`** | Шаблоны скилов для чата CoreX (developer, tester, reviewer, architect…) |
| **`corex/pipelines/`** | Шаблоны команд для чата CoreX (`persona_id`: dev-team, quick-fix) |
| **`corex/data/`** | Каталоги скилов (`skills_catalog.json`, `core_x_skill_catalog.json`) |
| **`corex/docs/SKILLS.md`** | Документация по скиллам и командам CoreX |
| `core_x_skills/` | Расширенный каталог скилов CoreX (75+ скилов по категориям) |
| `knowledge/` | База правил CoreX по языкам и контекстам |

### Слой Cursor IDE

| Папка / файл | Описание |
|---|---|
| `.cursor/commands/` | Команды Cursor (`/tdd`, `/e2e`, `/security-review`) |
| `.cursor/rules/` | Правила Cursor (`.mdc`) — TDD, E2E, security-review, coding-style |
| `.cursor/skills/` | Скилы в формате Cursor (`SKILL.md`) |
| `.cursor/hooks/` | Хуки автоматизации (форматирование, линт, субагенты) |

### Слой ECC (внешний набор best-practice)

| Папка / файл | Описание |
|---|---|
| `agents/` | ECC-агенты (planner, tdd-guide, e2e-runner, code-reviewer и др.) + агенты CoreX |
| `commands/` | Исходники команд ECC (43 команды) |
| `skills/` | Скилы ECC (tdd-workflow, e2e-testing, security-review и др.) |
| `teams/` | Копия команд CoreX (дублирует `corex/teams/`) |
| `AGENTS.md` | Общие инструкции для агентов ECC |

## Быстрая установка в новый проект

### Минимум (только Cursor)

Скопируйте папку `.cursor` в корень нового проекта:

```powershell
Copy-Item -Path ".\cursor-ai-pack\.cursor" -Destination "C:\path\to\new-project\.cursor" -Recurse -Force
```

После этого в Cursor будут доступны команды `/tdd`, `/e2e`, `/security-review` и связанные правила.

### Полная установка

```powershell
$dest = "C:\path\to\new-project"

# Cursor config
Copy-Item -Path ".\cursor-ai-pack\.cursor" -Destination "$dest\.cursor" -Recurse -Force

# Агенты (для справки и ручной настройки)
Copy-Item -Path ".\cursor-ai-pack\agents" -Destination "$dest\agents" -Recurse -Force

# Скилы ECC
Copy-Item -Path ".\cursor-ai-pack\skills" -Destination "$dest\skills" -Recurse -Force

# Команды ECC (дополнительные)
Copy-Item -Path ".\cursor-ai-pack\commands" -Destination "$dest\commands" -Recurse -Force

# Команды агентов (teams)
Copy-Item -Path ".\cursor-ai-pack\teams" -Destination "$dest\teams" -Recurse -Force

# База знаний
Copy-Item -Path ".\cursor-ai-pack\knowledge" -Destination "$dest\knowledge" -Recurse -Force

# AGENTS.md в корень
Copy-Item -Path ".\cursor-ai-pack\AGENTS.md" -Destination "$dest\AGENTS.md" -Force
```

### Установка для CoreX (другой инстанс CoreX)

```powershell
$dest = "C:\path\to\new-project"

# Агенты и команды CoreX
Copy-Item -Path ".\cursor-ai-pack\corex\agents" -Destination "$dest\core_x_agents" -Recurse -Force
Copy-Item -Path ".\cursor-ai-pack\corex\teams" -Destination "$dest\core_x_agents\teams" -Recurse -Force

# Скилы и база знаний
Copy-Item -Path ".\cursor-ai-pack\core_x_skills" -Destination "$dest\core_x_skills" -Recurse -Force
Copy-Item -Path ".\cursor-ai-pack\knowledge" -Destination "$dest\core_x_knowledge" -Recurse -Force

# Шаблоны для UI чата (опционально)
Copy-Item -Path ".\cursor-ai-pack\corex\personas" -Destination "$dest\backend\templates\personas" -Recurse -Force
Copy-Item -Path ".\cursor-ai-pack\corex\pipelines" -Destination "$dest\backend\templates\pipelines" -Recurse -Force
Copy-Item -Path ".\cursor-ai-pack\corex\data" -Destination "$dest\backend\data" -Recurse -Force
```

### Расширенный каталог скилов (опционально)

Если нужен полный каталог CoreX:

```powershell
Copy-Item -Path ".\cursor-ai-pack\core_x_skills" -Destination "$dest\core_x_skills" -Recurse -Force
```

## Основные команды

| Команда | Назначение |
|---|---|
| `/tdd` | Test-driven development (тесты → код → рефакторинг, 80%+ coverage) |
| `/e2e` | E2E-тесты Playwright |
| `/security-review` | Проверка безопасности незакоммиченных изменений |
| `/plan` | Планирование реализации |
| `/code-review` | Code review |
| `/build-fix` | Исправление ошибок сборки |
| `/refactor-clean` | Рефакторинг и удаление мёртвого кода |

## Агенты CoreX (`corex/agents/`)

| Агент | Файл | Роль |
|---|---|---|
| Старший разработчик | `lead-developer.md` | Production-ready код, Python, API |
| QA-инженер | `qa-engineer.md` | Тесты, запуск main.py, баги |
| Ревьюер кода | `code-reviewer.md` | Code review, безопасность, стиль |
| Security-аудитор | `security-auditor.md` | Уязвимости, секреты, auth |
| DevOps-инженер | `devops-engineer.md` | Docker, CI/CD, деплой |

## Готовые команды CoreX (`corex/teams/`)

| Файл | Этапы |
|---|---|
| `dev-team.json` | Старший разработчик → QA → Ревьюер |
| `quick-fix.json` | Старший разработчик → Ревьюер |
| `secure-feature.json` | Разработчик → Security → QA |

## Примечания

- Хуки в `.cursor/hooks/` могут требовать адаптации под стек нового проекта (npm/pnpm, eslint, prettier и т.д.).
- Правила в `knowledge/rules/` — справочные; для Cursor используйте `.cursor/rules/`.
- Файлы `core_x_skills/` — большой каталог; копируйте только нужные скилы, если не нужен весь набор.
