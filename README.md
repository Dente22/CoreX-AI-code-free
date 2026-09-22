<p align="center">
  <img src="frontend/public/corex-logo.svg" alt="CoreX" width="120" />
</p>

<h1 align="center">CoreX</h1>

<p align="center">
  <strong>Local-first AI IDE</strong> — write, plan, and ship code with agents that live on <em>your</em> machine.<br/>
  Free online models when you want them. Full privacy when you don’t.
</p>

<p align="center">
  <a href="README.ru.md"><strong>Русский</strong></a> ·
  <a href="#corex"><strong>English</strong></a> ·
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

## Why CoreX?

Most AI coding tools send your project to the cloud by default.  
**CoreX flips that:** a real desktop IDE with an AI agent that can read files, write code, run commands, and orchestrate multi-step teams — starting from **local models** (Ollama) and optional **free online** providers (OpenRouter).

| You get | What it means |
|--------|----------------|
| 🖥️ **Desktop app** | Electron + React UI — editor, chat, terminal, file tree |
| 🧠 **Agent that acts** | Not just chat — creates/edits files, runs tools, verifies results |
| 🔒 **Keys stay local** | API keys live in your machine profile, not in the project folder |
| 🆓 **Free online path** | OpenRouter Free (`openrouter/free`) with auto-fallback if a model disappears |
| 🧩 **Teams & skills** | Designer → developer → QA pipelines, plus a large skill library |
| 📦 **Showcase** | Drop finished demos into `showcase/` for the public repo |

---

## What it does

```text
  You: "Create a landing page for a cafe"
           │
           ▼
  ┌──────────────────── CoreX ────────────────────┐
  │  Plan  →  Agent tools  →  Write files  →  Done │
  │                                                │
  │  Local: Ollama          Online: OpenRouter     │
  │  (phi / qwen / …)       (free router / :free)  │
  └────────────────────────────────────────────────┘
           │
           ▼
  Real files in your project folder
```

**In practice CoreX can:**
- Scaffold websites and small apps from a natural-language request  
- Edit existing code with `view_file` / `write_file` / `patch_file`  
- Run multi-agent pipelines (design → code → QA)  
- Work **offline** with Ollama or **online** with your API key  
- Keep token usage lean on free online models (compact prompts, short history, auto model switch)

---

## Quick start

### Requirements
- **Windows** (primary)
- **Python** 3.10+
- **Node.js** 18+
- Optional: [Ollama](https://ollama.com) for fully local AI

### Run from source

```powershell
git clone https://github.com/Dente22/CoreX-AI-code-free.git
cd CoreX-AI-code-free

# Backend deps
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt

# Frontend deps
cd frontend
npm install
cd ..

# Launch (splash → backend → UI)
.\start-corex.bat
```

### Scripts

| File | Purpose |
|------|---------|
| `start-corex.bat` | Start the app |
| `start-corex-dev.bat` | UI hot-reload for development |
| `build-corex-installer.bat` | Build Windows NSIS installer |
| `stop-corex-runtime.bat` | Stop CoreX / related runtime |

> **Installer release:** coming as a GitHub Release (`CoreX-Setup-*.exe`). Until then, run from source.

---

## Online Free setup (2 minutes)

1. Create a key at [openrouter.ai/keys](https://openrouter.ai/keys) (no card required for free models)  
2. In CoreX → **Online** → add **OpenRouter (Free)**  
3. Default model: `openrouter/free` (auto-picks an available free model)  
4. Your key is stored under `%LOCALAPPDATA%\CoreX\secrets\` — **not** committed with the project  

If a free model is retired, CoreX **auto-switches** to another free option and keeps going.

---

## Project layout

```text
CoreX-AI-code-free/
├── backend/           # Python API, orchestrator, tools
├── frontend/          # Electron + React IDE
├── core_x_skills/     # Skill library
├── core_x_agents/     # Agents & team pipelines
├── core_x_knowledge/  # Coding rules for the agent
├── chat/              # Default configs (no secrets)
├── showcase/          # Finished demo projects for the repo
├── docs/              # Extra documentation
└── start-corex.bat    # One-click launch
```

Finished projects → put them in [`showcase/`](showcase/README.md).

---

## Architecture (short)

| Layer | Stack |
|-------|--------|
| UI | React, Vite, Electron |
| Backend | Python, WebSocket/HTTP API |
| Local AI | Ollama |
| Online AI | OpenAI-compatible APIs + Gemini + OpenRouter |
| Agent loop | Plan → tool calls → verify → done |

---

## Roadmap

- [x] Local agent IDE (editor + chat + tools)  
- [x] OpenRouter Free + local secrets  
- [x] Auto free-model fallback & lean online prompts  
- [x] Public clean repo + `showcase/`  
- [ ] Official Windows installer on GitHub Releases  
- [ ] Screenshots / short demo video in this README  
- [ ] Broader platform support  

---

## Contributing

Issues and PRs are welcome.  
For publishable demos, open a PR that adds a folder under `showcase/<project-name>/` with a short README.

---

## Disclaimer

CoreX is **early access**. Expect rough edges. Always review AI-generated code before shipping to production.

---

<p align="center">
  Made for builders who want AI <strong>without giving up control</strong>.<br/>
  <a href="https://github.com/Dente22/CoreX-AI-code-free">⭐ Star the repo</a> if CoreX helps you ship.
</p>
