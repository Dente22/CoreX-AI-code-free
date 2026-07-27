# CoreX

Локальный AI-редактор: Python backend + Electron/React UI.

## Быстрый запуск (рекомендуется)

**Двойной клик:**
- `start-corex.bat` — запуск приложения (splash → backend → UI)
- `start-corex-dev.bat` — разработка UI с hot-reload
- `build-corex-installer.bat` — установщик Windows
- `stop-corex-runtime.bat` — остановить CoreX и Ollama

**Из терминала (корень проекта):**
```powershell
cd D:\Project\CoreX
.\start-corex.bat
```

**Уже в `frontend`:**
```powershell
npm run start:dev
```

Полная пересборка UI и иконок (если меняли дизайн):
```powershell
cd frontend
npm run start
```

**Разработка UI (hot-reload):**
```bash
cd frontend
npm run dev:app
```

Electron сам запускает Python backend и закрывает его при выходе.

## Только backend (отладка)

```bash
pip install -r backend/requirements.txt
python main.py --mode server --port 8000
```

## Legacy GUI (без Electron)

```bash
python backend/main.py --mode gui
```

## Структура

| Папка | Назначение |
|-------|------------|
| `backend/` | WebSocket API, Ollama, файловые операции |
| `frontend/` | React UI + Electron |
| `chat/` | Память агента (`project_memory.md`) |
| `legacy/` | Устаревший код |

## Требования

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) с моделью `qwen2.5-coder:7b`

```bash
ollama pull qwen2.5-coder:7b
```

## Персоны и команды AI

| Папка | Назначение |
|-------|------------|
| `chat/personas/` | Один скил (промпт роли) |
| `chat/pipelines/` | Конвейеры команд (dev-team, quick-fix) |

**Режимы в чате:**
- **Один скил** — одна персона на задачу
- **Команда** — цепочка ролей (разработчик → тестировщик → ревьюер) с паузами и лимитами для ПК

Справочник 91 скилла из ECC + Best Practice: [docs/SKILLS.md](docs/SKILLS.md) · API: `/api/skills/catalog`

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `COREX_PYTHON` | Путь к Python (если не в PATH) |
| `COREX_BACKEND_PORT` | Порт backend (обычно выбирается автоматически) |
