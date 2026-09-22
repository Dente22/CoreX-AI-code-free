"""Проверка Python-кода после записи агентом."""

from __future__ import annotations

import asyncio
import py_compile
import re
from pathlib import Path

from core.python_deps import extract_missing_module
from core.terminal_service import run_file

ENTRY_POINT_NAMES = frozenset(
    {"main.py", "app.py", "run.py", "__main__.py", "game.py", "start.py"}
)

_RUNTIME_ERROR_MARKERS = re.compile(
    r"Traceback \(most recent call last\)|"
    r"SyntaxError:|IndentationError:|NameError:|TypeError:|"
    r"ModuleNotFoundError:|AttributeError:|ImportError:|"
    r"UnboundLocalError:|ZeroDivisionError:|FileNotFoundError:",
    re.IGNORECASE,
)


def _resolve(project_root: Path, rel_path: str) -> Path | None:
    root = project_root.resolve()
    normalized = rel_path.replace("\\", "/").lstrip("/")
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def is_python_entry_point(rel_path: str) -> bool:
    return Path(rel_path).name.lower() in ENTRY_POINT_NAMES


_INTERACTIVE_HINTS = (
    "pygame",
    "import turtle",
    "turtle.",
    "tkinter",
    "curses",
    "msvcrt",
    "pynput",
    "keyboard",
    "input(",
)


def looks_like_interactive_python(source: str) -> bool:
    """Игры, GUI и while True нельзя гонять как smoke-тест — падают на вводе или висят."""
    blob = source or ""
    if not blob.strip():
        return False
    lowered = blob.lower()
    if any(token in lowered for token in _INTERACTIVE_HINTS):
        return True
    if re.search(r"(?m)^\s*while\s+True\s*:", blob):
        return True
    if re.search(
        r"\b(snake|змейк|draw_field|game_loop|tetris|minesweeper|сап[её]р|sapper)\b",
        lowered,
    ):
        return True
    return False


def compact_runtime_detail(detail: str, limit: int = 900) -> str:
    text = detail or ""
    tb = text.rfind("Traceback")
    if tb >= 0 and text.count(". . .") >= 6:
        return text[tb:][:limit]
    return text[:limit]


def _output_has_runtime_error(output: str) -> bool:
    return bool(_RUNTIME_ERROR_MARKERS.search(output or ""))


def verify_python_syntax(project_root: Path, rel_path: str) -> dict:
    target = _resolve(project_root, rel_path)
    if not target or not target.is_file():
        return {
            "ok": False,
            "phase": "syntax",
            "path": rel_path,
            "detail": f"Файл не найден: {rel_path}",
        }
    try:
        py_compile.compile(str(target), doraise=True)
    except py_compile.PyCompileError as exc:
        return {
            "ok": False,
            "phase": "syntax",
            "path": rel_path,
            "detail": str(exc),
        }
    except OSError as exc:
        return {
            "ok": False,
            "phase": "syntax",
            "path": rel_path,
            "detail": str(exc),
        }
    return {"ok": True, "phase": "syntax", "path": rel_path, "detail": "Синтаксис OK"}


async def smoke_run_python(
    project_root: Path,
    rel_path: str,
    *,
    timeout: int = 8,
) -> dict:
    result = await run_file(
        project_root, rel_path, timeout=timeout, stdin_devnull=True
    )
    output = (result.get("output") or "").strip()
    error_text = (result.get("error") or "").strip()
    combined = f"{output}\n{error_text}".strip()

    if re.search(r"EOF when reading a line", combined, re.IGNORECASE):
        return {
            "ok": True,
            "phase": "smoke_run",
            "path": rel_path,
            "detail": "Скрипт ждёт ввод в консоли — это не ошибка кода",
            "exit_code": result.get("exit_code"),
            "command": result.get("command"),
        }

    if _output_has_runtime_error(combined):
        module = extract_missing_module(combined)
        if module:
            return {
                "ok": False,
                "phase": "dependency",
                "missing_module": module,
                "path": rel_path,
                "detail": combined[:4000] or f"Нет пакета {module}",
                "exit_code": result.get("exit_code"),
                "command": result.get("command"),
            }
        return {
            "ok": False,
            "phase": "smoke_run",
            "path": rel_path,
            "detail": combined[:4000] or "Ошибка при запуске",
            "exit_code": result.get("exit_code"),
            "command": result.get("command"),
        }

    if result.get("success"):
        return {
            "ok": True,
            "phase": "smoke_run",
            "path": rel_path,
            "detail": "Запуск завершился без ошибок",
            "exit_code": result.get("exit_code"),
            "command": result.get("command"),
        }

    timed_out = "Превышен лимит" in error_text or "timeout" in error_text.lower()
    if timed_out and not _output_has_runtime_error(output):
        return {
            "ok": True,
            "phase": "smoke_run",
            "path": rel_path,
            "detail": "Запуск без падения (прерван по таймауту — нормально для игр/GUI)",
            "exit_code": result.get("exit_code"),
            "command": result.get("command"),
        }

    module = extract_missing_module(combined) or extract_missing_module(error_text)
    if module:
        return {
            "ok": False,
            "phase": "dependency",
            "missing_module": module,
            "path": rel_path,
            "detail": combined[:4000] or error_text or f"Нет пакета {module}",
            "exit_code": result.get("exit_code"),
            "command": result.get("command"),
        }
    return {
        "ok": False,
        "phase": "smoke_run",
        "path": rel_path,
        "detail": combined[:4000] or error_text or "Неизвестная ошибка запуска",
        "exit_code": result.get("exit_code"),
        "command": result.get("command"),
    }


async def verify_python_file(project_root: Path, rel_path: str) -> dict:
    syntax = await asyncio.to_thread(verify_python_syntax, project_root, rel_path)
    if not syntax.get("ok"):
        return syntax
    if not is_python_entry_point(rel_path):
        return syntax
    target = _resolve(project_root, rel_path)
    source = ""
    if target and target.is_file():
        source = target.read_text(encoding="utf-8", errors="replace")
    from core.python_deps import probe_missing_modules
    from core.terminal_service import resolve_project_python

    python_exe, _venv = resolve_project_python(project_root, target.parent if target else project_root)
    missing = await asyncio.to_thread(
        probe_missing_modules, source, python_exe, project_root
    )
    if missing:
        module = missing[0]
        return {
            "ok": False,
            "phase": "dependency",
            "missing_module": module,
            "path": rel_path,
            "detail": f"No module named '{module}'",
        }
    if looks_like_interactive_python(source):
        return {
            "ok": True,
            "phase": "syntax",
            "path": rel_path,
            "detail": "Синтаксис OK (игру/цикл не запускаем автоматически)",
        }
    return await smoke_run_python(project_root, rel_path)
