"""Интерактивный stdin консоли: input() не должен получать EOF."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from core.terminal_session import InteractiveTerminal, is_interactive_path, start_file


def _wait_for(session: InteractiveTerminal, needle: str, timeout: float = 6.0) -> str:
    buf = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        buf += session.snapshot()["output"]
        if needle in buf:
            return buf
        time.sleep(0.05)
    return buf


def test_is_interactive_path():
    assert is_interactive_path("main.py") is True
    assert is_interactive_path("src/app.ts") is True
    assert is_interactive_path("index.html") is False
    assert is_interactive_path("style.css") is False


def test_python_input_roundtrip(tmp_path: Path):
    script = tmp_path / "ask.py"
    script.write_text(
        "print('READY', flush=True)\n"
        "value = input('name:')\n"
        "print('GOT=' + value, flush=True)\n",
        encoding="utf-8",
    )
    session = InteractiveTerminal()
    started = session.start(
        argv=[sys.executable, "-u", str(script)],
        cwd=tmp_path,
        env=__import__("os").environ.copy(),
        display="python ask.py",
    )
    assert started["success"] is True
    try:
        buf = _wait_for(session, "READY")
        assert "READY" in buf
        written = session.write_stdin("corex")
        assert written["success"] is True
        buf += _wait_for(session, "GOT=corex")
        assert "GOT=corex" in buf
        done = _wait_for(session, "GOT=corex")
        snap = session.snapshot()
        deadline = time.time() + 4
        while snap.get("running") and time.time() < deadline:
            time.sleep(0.05)
            snap = session.snapshot()
        assert snap.get("running") is False
        assert snap.get("exit_code") == 0
    finally:
        session.kill()


def test_start_file_keeps_stdin_open(tmp_path: Path):
    script = tmp_path / "main.py"
    script.write_text(
        "print('PROMPT', flush=True)\n"
        "print('GOT=' + input(), flush=True)\n",
        encoding="utf-8",
    )
    session = InteractiveTerminal()
    started = start_file(session, tmp_path, "main.py")
    assert started["success"] is True
    try:
        buf = _wait_for(session, "PROMPT")
        assert "PROMPT" in buf
        assert "EOF" not in buf
        session.write_stdin("7")
        buf += _wait_for(session, "GOT=7")
        assert "GOT=7" in buf
    finally:
        session.kill()
