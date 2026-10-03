"""Потоковый запуск внешних CLI (Aider, Claude Code) с построчной отдачей stdout."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

LineCallback = Callable[[str], Awaitable[None] | None]
SpawnErrorKind = Literal["missing", "os", "run"]


@dataclass
class CliRunOutcome:
    exit_code: int
    lines: list[str] = field(default_factory=list)
    timed_out: bool = False
    spawn_error: tuple[SpawnErrorKind, Exception] | None = None

    @property
    def output(self) -> str:
        return "\n".join(self.lines)


async def run_streaming_cli(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    on_line: LineCallback | None = None,
    timeout_sec: float = 900.0,
    process_holder: dict[str, Any] | None = None,
    stdin_text: str | None = None,
) -> CliRunOutcome:
    """Popen в потоке: Windows SelectorEventLoop не умеет asyncio subprocess."""
    loop = asyncio.get_running_loop()
    event_q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    lines: list[str] = []

    def _emit(kind: str, payload: Any) -> None:
        loop.call_soon_threadsafe(event_q.put_nowait, (kind, payload))

    def _worker() -> None:
        popen_kwargs: dict[str, Any] = {
            "cwd": str(cwd),
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(argv, **popen_kwargs)
        except FileNotFoundError as exc:
            _emit("fail", ("missing", exc))
            return
        except OSError as exc:
            _emit("fail", ("os", exc))
            return

        if process_holder is not None:
            process_holder["process"] = proc
        try:
            if stdin_text is not None and proc.stdin is not None:
                try:
                    proc.stdin.write(stdin_text)
                finally:
                    proc.stdin.close()
            assert proc.stdout is not None
            for raw in proc.stdout:
                text = raw.rstrip("\r\n")
                lines.append(text)
                _emit("line", text)
            _emit("done", int(proc.wait(timeout=max(1.0, float(timeout_sec)))))
        except subprocess.TimeoutExpired:
            _kill_quietly(proc)
            _emit("timeout", None)
        except Exception as exc:
            _kill_quietly(proc)
            _emit("fail", ("run", exc))
        finally:
            if process_holder is not None:
                process_holder.pop("process", None)

    worker_fut = loop.run_in_executor(None, _worker)
    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(event_q.get(), timeout=timeout_sec + 5.0)
            except asyncio.TimeoutError:
                proc = (process_holder or {}).get("process")
                if proc is not None and getattr(proc, "poll", lambda: 0)() is None:
                    _kill_quietly(proc)
                return CliRunOutcome(exit_code=-1, lines=lines, timed_out=True)
            if kind == "line":
                text = str(payload or "")
                if on_line and text.strip():
                    maybe = on_line(text)
                    if asyncio.iscoroutine(maybe):
                        await maybe
            elif kind == "done":
                return CliRunOutcome(exit_code=int(payload), lines=lines)
            elif kind == "timeout":
                return CliRunOutcome(exit_code=-1, lines=lines, timed_out=True)
            elif kind == "fail":
                tag, exc = payload
                return CliRunOutcome(exit_code=127 if tag == "missing" else 1, lines=lines, spawn_error=(tag, exc))
    finally:
        try:
            await asyncio.wait_for(asyncio.shield(worker_fut), timeout=15.0)
        except Exception:
            pass


def _kill_quietly(proc: Any) -> None:
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass
