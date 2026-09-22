"""Запуск Aider как слоя правок кода для CoreX (без автокоммита)."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.llm_runtime import ActiveLlm

LineCallback = Callable[[str], Awaitable[None] | None]

_EDITED_RE = re.compile(
    r"(?:Applied edit to|Wrote|Created|Updated)\s+[`'\"]?([^\s`'\"]+)",
    re.I,
)


@dataclass
class AiderLaunch:
    argv: list[str]
    env: dict[str, str]
    cwd: Path
    model: str


@dataclass
class AiderRunResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    model: str = ""
    edited_files: list[str] = field(default_factory=list)
    error: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_aider_command() -> list[str] | None:
    """CLI Aider: sidecar .venv-aider (Py 3.11/3.12), PATH, или py -3.11 -m aider."""
    sidecar = _repo_root() / ".venv-aider" / "Scripts" / "aider.exe"
    if not sidecar.is_file():
        sidecar = _repo_root() / ".venv-aider" / "bin" / "aider"
    if sidecar.is_file():
        return [str(sidecar)]

    exe = shutil.which("aider")
    if exe:
        return [exe]

    for ver in ("3.12", "3.11", "3.10"):
        try:
            probe = subprocess.run(
                ["py", f"-{ver}", "-c", "import aider"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return ["py", f"-{ver}", "-m", "aider"]
    return None


def aider_missing_message() -> str:
    return (
        "Aider не найден. На Python 3.14 пакет aider-chat не ставится — "
        "нужен sidecar 3.11/3.12. Запусти scripts\\ensure_aider_venv.bat "
        "или: py -3.11 -m venv .venv-aider && .venv-aider\\Scripts\\pip install -r "
        "backend\\requirements-aider.txt"
    )


def resolve_aider_model_env(active: ActiveLlm) -> tuple[str, dict[str, str]]:
    """Модель + env для Aider/litellm из ActiveLlm CoreX."""
    env = os.environ.copy()
    model_name = (active.model_name or "").strip()
    if not model_name:
        raise ValueError("Не выбрана модель для Aider")

    if active.mode == "local" or active.api_type == "ollama":
        base = str(getattr(active.client, "root_url", "") or "").rstrip("/")
        if not base:
            from core.ollama_lifecycle import resolve_ollama_base_url

            base = resolve_ollama_base_url().rstrip("/")
        env["OLLAMA_API_BASE"] = base
        return f"ollama_chat/{model_name}", env

    api_key = str(getattr(active.client, "api_key", "") or "").strip()
    base_url = str(getattr(active.client, "base_url", "") or "").rstrip("/")
    if not api_key:
        raise ValueError("Для онлайн-модели нужен API-ключ")

    if active.api_type == "gemini":
        env["GEMINI_API_KEY"] = api_key
        env["GOOGLE_API_KEY"] = api_key
        slug = model_name
        if slug.startswith("models/"):
            slug = slug.split("/", 1)[-1]
        return f"gemini/{slug}", env

    env["OPENAI_API_KEY"] = api_key
    if base_url:
        env["OPENAI_API_BASE"] = base_url

    if "openrouter.ai" in base_url.lower():
        env["OPENROUTER_API_KEY"] = api_key
        if model_name.startswith("openrouter/"):
            return model_name, env
        return f"openrouter/{model_name}", env

    if "/" in model_name and not model_name.startswith("openai/"):
        return model_name, env
    return f"openai/{model_name}", env


def build_aider_message(
    *,
    task: str,
    persona_label: str = "",
    persona_body: str = "",
    knowledge_text: str = "",
    language_hint: str = "",
    write_dest: str = "",
    attached_files: list[str] | None = None,
    plan_text: str = "",
) -> str:
    """Промпт для Aider: скилы/персона/язык без JSON-протокола CoreX."""
    parts: list[str] = [
        "Ты работаешь внутри CoreX через Aider.",
        "Прави правила в файлах проекта. Не вызывай JSON-инструменты CoreX.",
        "Не делай git commit — коммиты только по явной просьбе пользователя.",
        "Отвечай кратко по-русски после правок.",
    ]
    if language_hint:
        parts.append(f"Язык/стек: {language_hint}")
    if persona_label or persona_body:
        label = persona_label or "persona"
        parts.append(f"=== PERSONA: {label} ===\n{(persona_body or '').strip()}\n=== END PERSONA ===")
    if knowledge_text.strip():
        parts.append(
            "=== COREX KNOWLEDGE / SKILLS ===\n"
            f"{knowledge_text.strip()}\n"
            "=== END KNOWLEDGE ==="
        )
    if plan_text.strip():
        parts.append(plan_text.strip())
    if write_dest:
        parts.append(f"Целевой путь/подсказка: {write_dest}")
    files = [f for f in (attached_files or []) if f]
    if files:
        parts.append("Упомянутые файлы: " + ", ".join(files))
    parts.append("=== TASK ===\n" + (task or "").strip())
    return "\n\n".join(parts)


_VALID_CHAT_MODES = frozenset({
    "architect",
    "ask",
    "context",
    "diff",
    "diff-fenced",
    "editor-diff",
    "editor-diff-fenced",
    "editor-whole",
    "help",
    "patch",
    "udiff",
    "udiff-simple",
    "whole",
})


def normalize_aider_chat_mode(chat_mode: str | None, *, for_question: bool = False) -> str | None:
    """Aider 0.86+ не знает mode 'code'. Для правок — default (None), для вопросов — ask."""
    raw = (chat_mode or "").strip().lower()
    if for_question or raw == "ask":
        return "ask"
    if raw in {"code", "default", ""}:
        return None
    if raw in _VALID_CHAT_MODES:
        return raw
    return None


def ensure_project_git(project_root: Path) -> None:
    """Локальный .git в проекте, чтобы Aider не ушёл в родительский репозиторий CoreX."""
    root = project_root.resolve()
    if (root / ".git").exists():
        return
    try:
        subprocess.run(
            ["git", "init"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def build_aider_launch(
    *,
    project_root: Path,
    active: ActiveLlm,
    message: str,
    chat_mode: str | None = None,
    read_files: list[str] | None = None,
    for_question: bool = False,
) -> AiderLaunch:
    cmd = find_aider_command()
    if not cmd:
        raise RuntimeError(aider_missing_message())
    model, env = resolve_aider_model_env(active)
    root = project_root.resolve()
    ensure_project_git(root)
    mode = normalize_aider_chat_mode(chat_mode, for_question=for_question)

    msg_path = root / "chat" / "_aider_message.txt"
    try:
        msg_path.parent.mkdir(parents=True, exist_ok=True)
        msg_path.write_text(message or "", encoding="utf-8")
        use_file = True
    except OSError:
        use_file = False

    argv = [
        *cmd,
        "--model",
        model,
        "--yes-always",
        "--no-auto-commits",
        "--no-pretty",
        "--no-stream",
        "--subtree-only",
        "--exit",
    ]
    if mode:
        argv.extend(["--chat-mode", mode])
    if use_file:
        argv.extend(["--message-file", str(msg_path)])
    else:
        argv.extend(["--message", message])
    for rel in read_files or []:
        clean = str(rel or "").replace("\\", "/").strip()
        if clean:
            argv.extend(["--read", clean])
    env = {
        **env,
        "GIT_EDITOR": "true",
        "EDITOR": "true",
        "VISUAL": "true",
        "AIDER_NO_BROWSER": "1",
    }
    return AiderLaunch(argv=argv, env=env, cwd=root, model=model)



def parse_edited_files(output: str) -> list[str]:
    found: list[str] = []
    for match in _EDITED_RE.finditer(output or ""):
        path = match.group(1).strip().rstrip(".,;")
        if path and path not in found:
            found.append(path)
    return found


async def run_aider(
    launch: AiderLaunch,
    *,
    on_line: LineCallback | None = None,
    timeout_sec: float = 900.0,
    process_holder: dict[str, Any] | None = None,
) -> AiderRunResult:
    """Запуск Aider через subprocess.Popen (Windows SelectorEventLoop не умеет asyncio subprocess)."""
    import sys

    loop = asyncio.get_running_loop()
    event_q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    chunks: list[str] = []

    def _worker() -> None:
        popen_kwargs: dict[str, Any] = {
            "cwd": str(launch.cwd),
            "env": launch.env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(launch.argv, **popen_kwargs)
        except FileNotFoundError as exc:
            loop.call_soon_threadsafe(event_q.put_nowait, ("fail", ("missing", exc)))
            return
        except OSError as exc:
            loop.call_soon_threadsafe(event_q.put_nowait, ("fail", ("os", exc)))
            return

        if process_holder is not None:
            process_holder["process"] = proc
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                text = raw.rstrip("\r\n")
                chunks.append(text)
                loop.call_soon_threadsafe(event_q.put_nowait, ("line", text))
            code = proc.wait(timeout=max(1.0, float(timeout_sec)))
            loop.call_soon_threadsafe(event_q.put_nowait, ("done", int(code)))
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
            loop.call_soon_threadsafe(event_q.put_nowait, ("timeout", None))
        except Exception as exc:
            try:
                proc.kill()
            except Exception:
                pass
            loop.call_soon_threadsafe(event_q.put_nowait, ("fail", ("run", exc)))
        finally:
            if process_holder is not None:
                process_holder.pop("process", None)

    worker_fut = loop.run_in_executor(None, _worker)
    code = 1
    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(event_q.get(), timeout=timeout_sec + 5.0)
            except asyncio.TimeoutError:
                proc = (process_holder or {}).get("process")
                if proc is not None and getattr(proc, "poll", lambda: 0)() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                blob = "\n".join(chunks)
                return AiderRunResult(
                    ok=False,
                    exit_code=-1,
                    stdout=blob,
                    stderr="",
                    model=launch.model,
                    edited_files=parse_edited_files(blob),
                    error="Aider превысил лимит времени",
                )
            if kind == "line":
                text = str(payload or "")
                if on_line and text.strip():
                    maybe = on_line(text)
                    if asyncio.iscoroutine(maybe):
                        await maybe
            elif kind == "done":
                code = int(payload)
                break
            elif kind == "timeout":
                blob = "\n".join(chunks)
                return AiderRunResult(
                    ok=False,
                    exit_code=-1,
                    stdout=blob,
                    stderr="",
                    model=launch.model,
                    edited_files=parse_edited_files(blob),
                    error="Aider превысил лимит времени",
                )
            elif kind == "fail":
                tag, exc = payload
                if tag == "missing":
                    return AiderRunResult(
                        ok=False,
                        exit_code=127,
                        stdout="",
                        stderr="",
                        model=launch.model,
                        error=aider_missing_message(),
                    )
                return AiderRunResult(
                    ok=False,
                    exit_code=1,
                    stdout="\n".join(chunks),
                    stderr="",
                    model=launch.model,
                    error=f"Не удалось запустить Aider: {type(exc).__name__}: {exc}".strip(": "),
                )
    finally:
        try:
            await asyncio.wait_for(asyncio.shield(worker_fut), timeout=15.0)
        except Exception:
            pass

    blob = "\n".join(chunks)
    edited = parse_edited_files(blob)
    ok = code == 0
    error = None if ok else (blob[-1500:] if blob else f"Aider exit {code}")
    if not ok and "No module named aider" in blob:
        error = aider_missing_message()
    if not ok and "invalid choice" in (error or "").lower() and "chat-mode" in (error or "").lower():
        error = (
            "Aider: неверный --chat-mode. "
            "Обнови CoreX — для правок mode 'code' больше не используется."
        )
    return AiderRunResult(
        ok=ok,
        exit_code=int(code),
        stdout=blob,
        stderr="",
        model=launch.model,
        edited_files=edited,
        error=error,
    )


def aider_install_hint() -> str:
    return "scripts\\ensure_aider_venv.bat"
