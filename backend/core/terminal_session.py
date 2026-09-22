"""Интерактивный процесс консоли: stdin открыт, чтобы работал input()."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from core.terminal_output import sanitize_terminal_output
from core.terminal_service import (
    _append_python_hints,
    _build_file_command,
    _env_with_venv,
    _resolve_corex_library_paths,
    _resolve_in_project,
    resolve_project_python,
    rewrite_shell_command_for_project_python,
)

_INTERACTIVE_SUFFIXES = {
    ".py",
    ".pyw",
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".tsx",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
}


def is_interactive_path(rel_path: str) -> bool:
    lower = (rel_path or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    dot = lower.rfind(".")
    if dot < 0:
        return False
    return lower[dot:] in _INTERACTIVE_SUFFIXES


class InteractiveTerminal:
    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._chunks: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self.command = ""
        self.cwd = ""

    def running(self) -> bool:
        proc = self._proc
        return proc is not None and proc.poll() is None

    def start(
        self,
        *,
        cwd: Path,
        env: dict[str, str],
        argv: list[str] | None = None,
        command: str | None = None,
        display: str = "",
    ) -> dict:
        self.kill()
        run_env = dict(env)
        run_env["PYTHONUNBUFFERED"] = "1"
        run_env["PYTHONIOENCODING"] = "utf-8"
        kwargs: dict = {
            "cwd": str(cwd),
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "bufsize": 0,
            "env": run_env,
        }
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            if command is not None:
                proc = subprocess.Popen(command, shell=True, **kwargs)
            elif argv:
                proc = subprocess.Popen(argv, shell=False, **kwargs)
            else:
                return {"success": False, "running": False, "error": "Нет команды"}
        except FileNotFoundError as exc:
            missing = exc.filename or (argv[0] if argv else command or "?")
            return {"success": False, "running": False, "error": f"Команда не найдена: {missing}"}
        except OSError as exc:
            return {"success": False, "running": False, "error": str(exc)}

        self._proc = proc
        self.command = display or command or " ".join(argv or [])
        self.cwd = str(cwd)
        self._reader = threading.Thread(target=self._read_stdout, args=(proc,), daemon=True)
        self._reader.start()
        return {
            "success": True,
            "running": True,
            "command": self.command,
            "cwd": self.cwd,
            "output": "",
            "error": "",
        }

    def write_stdin(self, text: str) -> dict:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            return {"success": False, "error": "Процесс не запущен"}
        payload = text if text.endswith("\n") else f"{text}\n"
        try:
            proc.stdin.write(payload.encode("utf-8"))
            proc.stdin.flush()
        except OSError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True}

    def snapshot(self) -> dict:
        output = self._drain()
        proc = self._proc
        if proc is None:
            return {
                "success": True,
                "running": False,
                "output": output,
                "exit_code": None,
                "command": self.command,
                "cwd": self.cwd,
            }
        code = proc.poll()
        if code is None:
            return {
                "success": True,
                "running": True,
                "output": output,
                "exit_code": None,
                "command": self.command,
                "cwd": self.cwd,
            }
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(timeout=0.4)
            output += self._drain()
        return {
            "success": code == 0,
            "running": False,
            "output": output,
            "exit_code": code,
            "command": self.command,
            "cwd": self.cwd,
            "error": "" if code == 0 else f"Код выхода: {code}",
        }

    def kill(self) -> dict:
        proc = self._proc
        if proc is None:
            return {"success": True, "running": False}
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except OSError:
            pass
        leftover = self._drain()
        self._proc = None
        return {"success": True, "running": False, "output": leftover, "exit_code": proc.returncode}

    def _drain(self) -> str:
        parts: list[str] = []
        while True:
            try:
                parts.append(self._chunks.get_nowait())
            except queue.Empty:
                break
        return sanitize_terminal_output("".join(parts))

    def _read_stdout(self, proc: subprocess.Popen[bytes]) -> None:
        stream = proc.stdout
        if stream is None:
            return
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                self._chunks.put(chunk.decode("utf-8", errors="replace"))
        except OSError:
            return


def start_file(session: InteractiveTerminal, project_root: Path, rel_path: str) -> dict:
    target = _resolve_in_project(project_root, rel_path)
    if not target:
        return {"success": False, "running": False, "error": "Путь вне проекта"}
    if not target.is_file():
        return {"success": False, "running": False, "error": f"Файл не найден: {rel_path}"}

    python_exe, venv_label = resolve_project_python(project_root, target.parent)
    built = _build_file_command(target, python_exe=python_exe)
    if isinstance(built, dict):
        return {"success": False, "running": False, **built}

    argv, display = built
    env = _env_with_venv(python_exe, venv_label)
    install_note = ""
    if target.suffix.lower() in {".py", ".pyw"}:
        from core.python_deps import ensure_source_imports

        try:
            source = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            source = ""
        if source:
            install_note = ensure_source_imports(
                project_root, source, python_exe=python_exe
            )
    result = session.start(argv=argv, cwd=target.parent, env=env, display=display)
    if install_note:
        result["output"] = install_note + (result.get("output") or "")
    result["file"] = rel_path.replace("\\", "/")
    if venv_label:
        result["python"] = python_exe
        result["venv"] = venv_label
    return result


def start_command(
    session: InteractiveTerminal,
    project_root: Path,
    command: str,
    cwd: str | None = None,
) -> dict:
    command = _resolve_corex_library_paths((command or "").strip())
    if not command:
        return {"success": False, "running": False, "error": "Пустая команда"}

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
    result = session.start(command=command, cwd=work_dir, env=env, display=command)
    if venv_label:
        result["venv"] = venv_label
    return result


def annotate_python_hints(result: dict, project_root: Path, rel_path: str | None) -> dict:
    if not rel_path:
        return result
    target = _resolve_in_project(project_root, rel_path)
    if not target or target.suffix.lower() not in {".py", ".pyw"}:
        return result
    python_exe, venv_label = resolve_project_python(project_root, target.parent)
    return _append_python_hints(result, python_exe=python_exe, venv_label=venv_label)
