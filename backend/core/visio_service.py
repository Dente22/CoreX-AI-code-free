"""Диаграммы Visio (Mermaid): логика открытого проекта и системные схемы CoreX."""

from __future__ import annotations

import re
from pathlib import Path

from core.pipeline_service import list_project_pipelines
from core.project_paths import COREX_INTERNAL_DIRS

VISIO_REL_DIR = Path("chat") / "visio"

_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    ".venv-1",
    "__pycache__",
    "dist",
    ".cursor",
    ".idea",
}


def visio_dir(project_root: Path) -> Path:
    return project_root / VISIO_REL_DIR


def ensure_visio_dir(project_root: Path) -> Path:
    target = visio_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _read_mermaid(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _mermaid_label(text: str) -> str:
    return re.sub(r'["\[\]{}]', "", text)[:72] or "item"


def _mermaid_id(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", text)
    return slug[:40] or "node"


def _label_for_mmd(stem: str) -> str:
    labels = {
        "workflow": "Логика проекта",
        "architecture": "Архитектура проекта",
    }
    return labels.get(stem, stem.replace("_", " ").replace("-", " ").title())


def _overview_diagram() -> str:
    return """flowchart TB
    subgraph user [Пользователь]
        A[Открыть проект]
        B[Редактор кода]
        C[Запуск F5]
        D[Чат CoreX AI]
    end
    subgraph corex [CoreX]
        E[Планирование задачи]
        F[Скил / Агент / Команда]
        G[Чтение и запись файлов]
        H[Консоль]
    end
    A --> B
    B --> C
    C --> H
    B --> D
    D --> E
    E --> F
    F --> G
    G --> B
    style user fill:#1e3a5f,stroke:#2563eb,color:#e5e9f0
    style corex fill:#2e1065,stroke:#7c3aed,color:#e5e9f0"""


def _default_system_architecture() -> str:
    return """flowchart TB
    subgraph frontend [Frontend Electron + React]
        UI[Редактор и Visio]
        Chat[Чат AI]
    end
    subgraph backend [Backend Python]
        API[HTTP + WebSocket]
        Orch[Оркестратор]
        Ollama[Ollama LLM]
    end
    subgraph data [Данные проекта]
        Files[Файлы кода]
        Skills[core_x_skills]
        Agents[core_x_agents]
    end
    UI --> API
    Chat --> API
    API --> Orch
    Orch --> Ollama
    Orch --> Files
    Orch --> Skills
    Orch --> Agents"""


def _structure_diagram(project_root: Path) -> str:
    name = _mermaid_label(project_root.name or "project")
    lines = ["flowchart TB", f'    root["{name}"]']

    try:
        entries = sorted(project_root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        entries = []

    count = 0
    for entry in entries:
        if count >= 14:
            lines.append('    root --> more["…"]')
            break
        if entry.name in _SKIP_DIRS or entry.name.startswith(".") or entry.name in COREX_INTERNAL_DIRS:
            continue
        node_id = f"n{count}"
        label = _mermaid_label(entry.name)
        if entry.is_dir():
            lines.append(f'    root --> {node_id}["📁 {label}"]')
            child_count = 0
            try:
                for child in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
                    if child_count >= 4:
                        break
                    if child.name in _SKIP_DIRS or child.name.startswith(".") or child.name in COREX_INTERNAL_DIRS:
                        continue
                    child_id = f"{node_id}_{child_count}"
                    child_label = _mermaid_label(child.name)
                    prefix = "📁 " if child.is_dir() else "📄 "
                    lines.append(f'    {node_id} --> {child_id}["{prefix}{child_label}"]')
                    child_count += 1
            except OSError:
                pass
        else:
            lines.append(f'    root --> {node_id}["📄 {label}"]')
        count += 1

    if count == 0:
        lines.append('    root --> empty["Пустой проект"]')

    lines.append("    style root fill:#0f766e,stroke:#14b8a6,color:#fff")
    return "\n".join(lines)


def _pipelines_diagram(project_root: Path) -> str:
    pipelines = list_project_pipelines(project_root)
    if not pipelines:
        return ""

    lines = ["flowchart LR", "    user[Задача] --> hub[Команды проекта]"]
    for index, pipeline in enumerate(pipelines[:6]):
        pid = _mermaid_id(pipeline.get("id") or f"pipe{index}")
        name = _mermaid_label(pipeline.get("name") or pid)
        lines.append(f'    hub --> {pid}["{name}"]')
        labels = pipeline.get("step_labels") or []
        prev = pid
        for step_index, label in enumerate(labels[:5]):
            step_id = f"{pid}_s{step_index}"
            lines.append(f'    {prev} --> {step_id}["{_mermaid_label(label)}"]')
            prev = step_id

    return "\n".join(lines)


def _collect_project_diagrams(project_root: Path) -> list[dict]:
    root = project_root.resolve()
    ensure_visio_dir(root)
    diagrams: list[dict] = []
    seen_ids: set[str] = set()

    for path in sorted(visio_dir(root).glob("*.mmd")):
        if path.name.endswith(".example"):
            continue
        source = _read_mermaid(path)
        if not source:
            continue
        diagram_id = path.stem
        if diagram_id in seen_ids:
            diagram_id = f"{diagram_id}_{len(seen_ids)}"
        seen_ids.add(diagram_id)
        diagrams.append({
            "id": diagram_id,
            "label": _label_for_mmd(path.stem),
            "path": "",
            "source": source,
            "origin": "file",
            "kind": "diagram",
        })

    structure = _structure_diagram(root)
    diagrams.append({
        "id": "structure",
        "label": "Структура проекта",
        "path": "",
        "source": structure,
        "origin": "generated",
        "kind": "structure",
    })

    pipelines = _pipelines_diagram(root)
    if pipelines:
        diagrams.append({
            "id": "pipelines",
            "label": "Команды проекта",
            "path": "",
            "source": pipelines,
            "origin": "generated",
            "kind": "pipelines",
        })

    memory_path = root / "chat" / "project_memory.md"
    if memory_path.is_file():
        diagrams.append({
            "id": "memory",
            "label": "Память проекта",
            "path": "",
            "source": _memory_diagram(memory_path),
            "origin": "generated",
            "kind": "memory",
        })

    return diagrams


def _memory_diagram(memory_path: Path) -> str:
    try:
        text = memory_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    lines = ["flowchart TB", '    mem["Память проекта"]']
    headings = re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)
    for index, heading in enumerate(headings[:8]):
        node_id = f"h{index}"
        lines.append(f'    mem --> {node_id}["{_mermaid_label(heading)}"]')
    if len(headings) == 0:
        lines.append('    mem --> note["Контекст для AI"]')
    return "\n".join(lines)


def get_visio_payload(project_root: Path) -> dict:
    root = project_root.resolve()
    diagrams = _collect_project_diagrams(root)

    return {
        "success": True,
        "project_name": root.name or "project",
        "diagrams": diagrams,
        "system": {
            "overview": _overview_diagram(),
            "architecture": _default_system_architecture(),
        },
        "paths": {
            "workflow": "",
            "architecture": "",
            "directory": "",
        },
    }
