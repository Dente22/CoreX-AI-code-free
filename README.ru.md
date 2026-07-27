<p align="center">
  <img src="frontend/public/corex-logo.svg" alt="CoreX" width="120" />
</p>

<h1 align="center">CoreX</h1>

<p align="center">
  <strong>Локальный AI-IDE</strong> — пиши, планируй и собирай код с агентами на <em>своём</em> компьютере.<br/>
  Бесплатные онлайн-модели — когда нужно. Полная приватность — когда не нужно.
</p>

<p align="center">
  <a href="README.ru.md"><strong>Русский</strong></a> ·
  <a href="README.md"><strong>English</strong></a> ·
  <a href="https://github.com/Dente22/CoreX-AI-code-free"><strong>GitHub</strong></a>
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img alt="Electron" src="https://img.shields.io/badge/Electron-React-47848F?style=flat-square&logo=electron&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-see%20repo-lightgrey?style=flat-square" />
  <img alt="Status" src="https://img.shields.io/badge/status-early%20access-orange?style=flat-square" />
</p>

---

## Зачем CoreX?

Большинство AI-инструментов по умолчанию отправляют проект в облако.  
**CoreX делает наоборот:** настоящий десктопный IDE с агентом, который читает файлы, пишет код, запускает команды и ведёт многошаговые команды — начиная с **локальных моделей** (Ollama) и опционально **бесплатного онлайна** (OpenRouter).

| Что получаешь | Зачем это |
|---------------|-----------|
| 🖥️ **Десктоп-приложение** | Electron + React — редактор, чат, терминал, дерево файлов |
| 🧠 **Агент с действиями** | Не только болтовня — создаёт/правит файлы, вызывает инструменты, проверяет результат |
| 🔒 **Ключи только у тебя** | API-ключи на ПК пользователя, не в папке проекта |
| 🆓 **Бесплатный онлайн** | OpenRouter Free (`openrouter/free`) с автопереключением, если модель сняли |
| 🧩 **Команды и скиллы** | Конвейеры дизайнер → разработчик → QA и большая библиотека скиллов |
| 📦 **Showcase** | Готовые демо клади в `showcase/` — они едут в публичный репозиторий |

---

## Что умеет

```text
  Ты: «Сделай лендинг для кафе»
           │
           ▼
  ┌──────────────────── CoreX ────────────────────┐
  │  План → инструменты → запись файлов → готово  │
  │                                                │
  │  Локально: Ollama       Онлайн: OpenRouter     │
  │  (phi / qwen / …)       (free / :free)         │
  └────────────────────────────────────────────────┘
           │
           ▼
  Реальные файлы в папке твоего проекта
```

**На практике CoreX может:**
- собирать сайты и небольшие приложения по запросу на русском  
- править существующий код (`view_file` / `write_file` / `patch_file`)  
- гонять пайплайны из нескольких агентов (дизайн → код → QA)  
- работать **офлайн** (Ollama) или **онлайн** (твой API-ключ)  
- экономить токены на free-моделях (короткие промпты, урезанная история, автосмена модели)

---

## Быстрый старт

### Требования
- **Windows** (основная платформа)
- **Python** 3.10+
- **Node.js** 18+
- Опционально: [Ollama](https://ollama.com) для полностью локального AI

### Запуск из исходников

```powershell
git clone https://github.com/Dente22/CoreX-AI-code-free.git
cd CoreX-AI-code-free

# Зависимости backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt

# Зависимости frontend
cd frontend
npm install
cd ..

# Запуск (splash → backend → UI)
.\start-corex.bat
```

### Скрипты

| Файл | Назначение |
|------|------------|
| `start-corex.bat` | Запуск приложения |
| `start-corex-dev.bat` | Разработка UI с hot-reload |
| `build-corex-installer.bat` | Сборка установщика Windows |
| `stop-corex-runtime.bat` | Остановить CoreX / runtime |

> **Установщик:** появится в GitHub Releases (`CoreX-Setup-*.exe`). Пока — запуск из исходников.

---

## Онлайн Free за 2 минуты

1. Ключ на [openrouter.ai/keys](https://openrouter.ai/keys) (для free-моделей карта не обязательна)  
2. В CoreX → **Онлайн** → добавь **OpenRouter (бесплатно)**  
3. Модель по умолчанию: `openrouter/free`  
4. Ключ хранится в `%LOCALAPPDATA%\CoreX\secrets\` — **не** попадает в git  

Если free-модель сняли с каталога, CoreX **сам переключится** на другую и продолжит работу.

---

## Структура репозитория

```text
CoreX-AI-code-free/
├── backend/           # Python API, оркестратор, инструменты
├── frontend/          # Electron + React IDE
├── core_x_skills/     # Библиотека скиллов
├── core_x_agents/     # Агенты и командные пайплайны
├── core_x_knowledge/  # Правила для агента
├── chat/              # Дефолтные конфиги (без секретов)
├── showcase/          # Готовые демо-проекты для репо
├── docs/              # Документация
└── start-corex.bat    # Запуск в один клик
```

Готовые проекты → в [`showcase/`](showcase/README.md).

---

## Архитектура коротко

| Слой | Стек |
|------|------|
| UI | React, Vite, Electron |
| Backend | Python, WebSocket/HTTP API |
| Локальный AI | Ollama |
| Онлайн AI | OpenAI-compatible + Gemini + OpenRouter |
| Цикл агента | План → инструменты → проверка → done |

---

## Roadmap

- [x] Локальный AI-IDE (редактор + чат + инструменты)  
- [x] OpenRouter Free + локальные секреты  
- [x] Автофоллбек free-моделей и lean-промпты  
- [x] Публичный чистый репозиторий + `showcase/`  
- [ ] Официальный установщик Windows в Releases  
- [ ] Скриншоты / короткое демо-видео в README  
- [ ] Поддержка других платформ  

---

## Участие

Issues и Pull Request приветствуются.  
Демо для витрины — PR с папкой `showcase/<имя-проекта>/` и коротким README.

---

## Дисклеймер

CoreX — **ранний доступ**. Возможны шероховатости. Код от AI всегда проверяй перед продакшеном.

---

<p align="center">
  Для тех, кто хочет AI <strong>без потери контроля</strong>.<br/>
  <a href="https://github.com/Dente22/CoreX-AI-code-free">⭐ Поставь звезду</a>, если CoreX помогает тебе делать проекты.
</p>
