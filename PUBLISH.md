# CoreX — пакет для Git

Это отдельная очищенная копия рабочей папки `D:\Project\CoreX` для публикации.

Рабочая копия (с venv, node_modules, локальными ключами) остаётся в `CoreX`.  
Сюда кладём только то, что должно уехать в репозиторий.

## Структура

| Путь | Назначение |
|------|------------|
| `backend/` | Python API, оркестратор |
| `frontend/` | Electron + React (без node_modules) |
| `core_x_skills/` | Скиллы |
| `core_x_agents/` | Агенты |
| `core_x_knowledge/` | Знания для AI |
| `chat/` | Дефолтные конфиги **без секретов** |
| `docs/` | Документация |
| `showcase/` | **Готовые проекты** для показа в репо |
| `showcase/_inbox/` | Временный сброс (игнорируется git) |

## Секреты

API-ключи хранятся на машине пользователя (`%LOCALAPPDATA%\CoreX\secrets\`), не в этой папке.  
Шаблон: `chat/ai_online_providers.example.json`.

## Как обновить пакет из рабочей копии

Из PowerShell (когда снова нужно синхронизировать исходники):

```powershell
# вручную: скопировать изменённые файлы из D:\Project\CoreX
# или попросить агента «обновить CoreX-repo»
```

## Первый push

```powershell
cd D:\Project\CoreX-repo
git status
git add .
git commit -m "Initial CoreX clean package"
# затем remote + push
```
