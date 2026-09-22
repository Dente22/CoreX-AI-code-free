"""Запуск файлов и команд в консоли проекта."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

from core.terminal_output import (
    append_ollama_pull_hints,
    command_timeout_sec,
    sanitize_terminal_output,
)
from core.ollama_model_service import merge_ollama_env

MAX_OUTPUT_CHARS = 200_000
DEFAULT_TIMEOUT_SEC = 120
_VENV_DIR_NAMES = (".venv", "venv", ".venv-1")
_COREX_LIBRARY_PATH_RE = re.compile(
    r"(core_x_(?:skills|agents|knowledge)/[\w./\\-]+)",
    re.IGNORECASE,
)

# расширение -> argv-префикс (файл добавляется в конец; для .py подставляется python проекта)
_FILE_RUNNERS: dict[str, list[str]] = {
    ".py": ["{python}", "-u"],
    ".pyw": ["{python}", "-u"],
    ".js": ["node"],
    ".mjs": ["node"],
    ".cjs": ["node"],
    ".jsx": ["node"],
    ".ps1": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"],
    ".bat": ["cmd", "/c"],
    ".cmd": ["cmd", "/c"],
    ".sh": ["bash"],
}


def _find_local_node_bin(start_dir: Path, stems: tuple[str, ...]) -> Path | None:
    """Ищет node_modules/.bin/<stem>(.cmd) в цепочке родителей."""
    current = start_dir.resolve()
    root = current.anchor
    while str(current) and str(current) != root:
        bin_dir = current / "node_modules" / ".bin"
        if bin_dir.is_dir():
            for stem in stems:
                if sys.platform == "win32":
                    for suffix in (".cmd", ".exe", ""):
                        candidate = bin_dir / f"{stem}{suffix}"
                        if candidate.is_file():
                            return candidate
                else:
                    candidate = bin_dir / stem
                    if candidate.is_file():
                        return candidate
        if current.parent == current:
            break
        current = current.parent
    # One more level check at anchor's child (rare, but harmless)
    return None


def _open_file_command(full_path: Path) -> tuple[list[str], str]:
    """Команда открытия файла в системе (браузер для .html/.css)."""
    if sys.platform == "win32":
        # cmd /c start "" <file>
        argv = ["cmd", "/c", "start", "", str(full_path)]
        display = f'cmd /c start "" "{str(full_path)}"'
        return argv, display

    if sys.platform == "darwin":
        argv = ["open", str(full_path)]
        return argv, f'open \"{str(full_path)}\"'

    argv = ["xdg-open", str(full_path)]
    return argv, f'xdg-open \"{str(full_path)}\"'


def _resolve_in_project(project_root: Path, rel_path: str) -> Path | None:
    root = project_root.resolve()
    normalized = rel_path.replace("\\", "/").lstrip("/")
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... (обрезано, всего {len(text)} символов)"


def _venv_python_path(venv_dir: Path) -> Path | None:
    if sys.platform == "win32":
        candidate = venv_dir / "Scripts" / "python.exe"
    else:
        candidate = venv_dir / "bin" / "python"
    return candidate if candidate.is_file() else None


def _search_dirs_for_venv(project_root: Path, start_dir: Path) -> list[Path]:
    root = project_root.resolve()
    dirs: list[Path] = []
    current = start_dir.resolve()
    while True:
        dirs.append(current)
        if current == root:
            break
        if root not in current.parents:
            if root not in dirs:
                dirs.append(root)
            break
        current = current.parent
    return dirs


def resolve_project_python(project_root: Path, context_dir: Path) -> tuple[str, str | None]:
    """Python для запуска: venv проекта, иначе интерпретатор CoreX (часто тоже venv)."""
    for base in _search_dirs_for_venv(project_root, context_dir):
        for name in _VENV_DIR_NAMES:
            py = _venv_python_path(base / name)
            if py:
                return str(py), name
    python_exe = sys.executable
    scripts = _venv_scripts_dir(python_exe)
    if scripts:
        return python_exe, scripts.parent.name
    return python_exe, None


def _venv_scripts_dir(python_exe: str) -> Path | None:
    parent = Path(python_exe).resolve().parent
    if parent.name == "Scripts" or parent.name == "bin":
        return parent
    return None


def _env_with_venv(python_exe: str, venv_label: str | None) -> dict[str, str]:
    env = os.environ.copy()
    scripts = _venv_scripts_dir(python_exe)
    if scripts:
        env["VIRTUAL_ENV"] = str(scripts.parent)
        env["PATH"] = str(scripts) + os.pathsep + env.get("PATH", "")
    return merge_ollama_env(env)


_PIP_BARE_RE = re.compile(r"^(pip3?\.exe|pip3?)\s+(.*)$", re.IGNORECASE)
_PIP_MODULE_RE = re.compile(
    r"^(?:python(?:3(?:\.\d+)?)?|py(?:thon)?)(?:\.exe)?\s+-m\s+pip\s+(.*)$",
    re.IGNORECASE,
)
_PYTHON_BARE_RE = re.compile(
    r"^(?:python(?:3(?:\.\d+)?)?|py(?:thon)?)(?:\.exe)?\s+(.*)$",
    re.IGNORECASE,
)


def _quote_exe(path: str) -> str:
    if not path:
        return path
    if re.search(r"\s", path) and not path.startswith(('"', "'")):
        return f'"{path}"'
    return path


def rewrite_shell_command_for_project_python(command: str, python_exe: str) -> str:
    """pip/python в консоли → тот же интерпретатор, которым жмёт ▶."""
    text = (command or "").strip()
    py = (python_exe or "").strip()
    if not text or not py:
        return text
    quoted = _quote_exe(py)
    if text.startswith(quoted) or text.startswith(py):
        return text
    match = _PIP_BARE_RE.match(text)
    if match:
        return f"{quoted} -m pip {match.group(2)}"
    match = _PIP_MODULE_RE.match(text)
    if match:
        return f"{quoted} -m pip {match.group(1)}"
    match = _PYTHON_BARE_RE.match(text)
    if match:
        rest = match.group(1)
        if rest.startswith("-m pip"):
            return f"{quoted} {rest}"
        return f"{quoted} {rest}"
    return text


def _build_file_command(
    full_path: Path,
    *,
    python_exe: str,
) -> tuple[list[str], str] | dict:
    ext = full_path.suffix.lower()
    # Openable web assets: open via system (browser can display HTML/CSS directly).
    if ext in {".html", ".htm", ".css"}:
        return _open_file_command(full_path)

    # TS/TSX: prefer local node_modules/.bin/tsx or ts-node.
    if ext in {".ts", ".tsx"}:
        tsx_bin = _find_local_node_bin(full_path.parent, ("tsx",))
        if tsx_bin:
            cmd = [str(tsx_bin), str(full_path)]
            display = " ".join(f'"{part}"' if " " in part else part for part in cmd)
            return cmd, display

        ts_node_bin = _find_local_node_bin(full_path.parent, ("ts-node",))
        if ts_node_bin:
            cmd = [str(ts_node_bin), str(full_path)]
            display = " ".join(f'"{part}"' if " " in part else part for part in cmd)
            return cmd, display

        return {
            "error": (
                "Для .ts/.tsx нужен локальный запускатель. Установите в проект:\n"
                "  npm i -D tsx\n"
                "или\n"
                "  npm i -D ts-node\n"
                "После этого кнопка запуска будет работать."
            ),
        }

    template = _FILE_RUNNERS.get(ext)
    if not template:
        supported = ", ".join(sorted(_FILE_RUNNERS))
        return {"error": f"Тип {ext or '(без расширения)'} не поддерживается. Доступно: {supported}"}

    runner = [part.replace("{python}", python_exe) for part in template]
    cmd = runner + [str(full_path)]
    display = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    return cmd, display


def _append_python_hints(result: dict, *, python_exe: str, venv_label: str | None) -> dict:
    from core.python_deps import extract_missing_module, pip_package_name

    output = result.get("output") or ""
    module = extract_missing_module(output)
    if not module:
        return result

    package = pip_package_name(module)
    pip_cmd = f'{_quote_exe(python_exe)} -m pip install {package}'

    venv_note = f" (venv: {venv_label})" if venv_label else ""
    hint = (
        f"\n\n── Подсказка CoreX ──\n"
        f"Модуль «{module}» не установлен{venv_note}.\n"
        f"В консоли внизу достаточно:\n"
        f"  pip install {package}\n"
        f"CoreX поставит пакет в тот же Python, которым запускает ▶:\n"
        f"  {pip_cmd}\n"
    )

    result["output"] = output + hint
    result["hint"] = pip_cmd
    return result


def _run_process_sync(
    *,
    cwd: Path,
    argv: list[str] | None = None,
    command: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    env: dict[str, str] | None = None,
    stdin_devnull: bool = False,
) -> dict:
    """Синхронный запуск через subprocess.run (совместимо с Windows SelectorEventLoop)."""
    run_kwargs: dict = {
        "cwd": str(cwd),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "env": env or os.environ.copy(),
    }
    if stdin_devnull:
        run_kwargs["stdin"] = subprocess.DEVNULL
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        if command is not None:
            completed = subprocess.run(command, shell=True, **run_kwargs)
        elif argv:
            completed = subprocess.run(argv, shell=False, **run_kwargs)
        else:
            return {"success": False, "exit_code": -1, "output": "", "error": "Нет команды"}
    except FileNotFoundError as exc:
        missing = exc.filename or (argv[0] if argv else command or "?")
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": f"Команда не найдена: {missing}",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": f"Превышен лимит времени ({timeout} с)",
        }
    except OSError as exc:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": str(exc),
        }

    output = _truncate(sanitize_terminal_output((completed.stdout or "") + (completed.stderr or "")))
    code = completed.returncode if completed.returncode is not None else -1
    return {
        "success": code == 0,
        "exit_code": code,
        "output": output,
        "error": "" if code == 0 else f"Код выхода: {code}",
    }


async def _run_process(
    *,
    cwd: Path,
    argv: list[str] | None = None,
    command: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    env: dict[str, str] | None = None,
    stdin_devnull: bool = False,
) -> dict:
    return await asyncio.to_thread(
        _run_process_sync,
        cwd=cwd,
        argv=argv,
        command=command,
        timeout=timeout,
        env=env,
        stdin_devnull=stdin_devnull,
    )


async def run_file(
    project_root: Path,
    rel_path: str,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    *,
    stdin_devnull: bool = False,
) -> dict:
    target = _resolve_in_project(project_root, rel_path)
    if not target:
        return {"success": False, "error": "Путь вне проекта"}
    if not target.is_file():
        return {"success": False, "error": f"Файл не найден: {rel_path}"}

    python_exe, venv_label = resolve_project_python(project_root, target.parent)
    built = _build_file_command(target, python_exe=python_exe)
    if isinstance(built, dict):
        return {"success": False, **built}

    argv, display = built
    env = _env_with_venv(python_exe, venv_label)
    result = await _run_process(
        argv=argv,
        cwd=target.parent,
        timeout=timeout,
        env=env,
        stdin_devnull=stdin_devnull,
    )
    result["command"] = display
    result["file"] = rel_path.replace("\\", "/")
    result["cwd"] = str(target.parent)
    if venv_label:
        result["python"] = python_exe
        result["venv"] = venv_label

    if target.suffix.lower() in {".py", ".pyw"}:
        result = _append_python_hints(result, python_exe=python_exe, venv_label=venv_label)

    return result


def _resolve_corex_library_paths(command: str) -> str:
    """Пути core_x_skills/... живут в установке CoreX, не в папке проекта пользователя."""
    if not command or "core_x_" not in command.lower():
        return command

    from core.core_x_library import COREX_ROOT

    def repl(match: re.Match[str]) -> str:
        rel = match.group(1).replace("\\", "/")
        target = (COREX_ROOT / rel).resolve()
        if target.exists():
            text = str(target)
            return f'"{text}"' if " " in text else text
        return match.group(0)

    return _COREX_LIBRARY_PATH_RE.sub(repl, command)


async def run_command(
    project_root: Path,
    command: str,
    cwd: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> dict:
    command = (command or "").strip()
    if not command:
        return {"success": False, "error": "Пустая команда"}

    command = _resolve_corex_library_paths(command)

    root = project_root.resolve()
    work_dir = root
    if cwd:
        resolved = _resolve_in_project(root, cwd)
        if resolved and resolved.is_dir():
            work_dir = resolved
        elif resolved and resolved.is_file():
            work_dir = resolved.parent

    python_exe, venv_label = resolve_project_python(root, work_dir)
    command = rewrite_shell_command_for_project_python(command, python_exe)
    env = _env_with_venv(python_exe, venv_label)
    from core.core_x_library import COREX_ROOT

    env["COREX_ROOT"] = str(COREX_ROOT)
    result = await _run_process(command=command, cwd=work_dir, timeout=command_timeout_sec(command, timeout), env=env)
    result["command"] = command
    result["cwd"] = str(work_dir)
    if venv_label:
        result["venv"] = venv_label
    result = _append_python_hints(result, python_exe=python_exe, venv_label=venv_label)
    return append_ollama_pull_hints(result)
