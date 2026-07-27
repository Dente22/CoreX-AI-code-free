"""TDD: терминал должен уметь запускать HTML/CSS и TS (tsx/ts-node) локально."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.terminal_service import _build_file_command


def _dummy_python_exe() -> str:
    return sys.executable


def test_build_html_opens_in_browser(tmp_path: Path):
    html = tmp_path / "index.html"
    html.write_text("<html></html>", encoding="utf-8")

    built = _build_file_command(html, python_exe=_dummy_python_exe())
    assert isinstance(built, tuple)
    argv, display = built
    assert argv, "runner argv must be non-empty"
    assert any("cmd" in part.lower() for part in argv) if sys.platform == "win32" else True


def test_build_css_opens_in_browser(tmp_path: Path):
    css = tmp_path / "style.css"
    css.write_text("body{}", encoding="utf-8")

    built = _build_file_command(css, python_exe=_dummy_python_exe())
    assert isinstance(built, tuple)
    argv, _display = built
    assert argv


def test_build_ts_uses_local_tsx_when_present(tmp_path: Path):
    node_bin = tmp_path / "node_modules" / ".bin"
    node_bin.mkdir(parents=True, exist_ok=True)

    # Windows: npm/.bin executables are .cmd
    tsx_name = "tsx.cmd" if sys.platform == "win32" else "tsx"
    (node_bin / tsx_name).write_text("", encoding="utf-8")

    ts = tmp_path / "app.ts"
    ts.write_text("console.log('x')", encoding="utf-8")

    built = _build_file_command(ts, python_exe=_dummy_python_exe())
    assert isinstance(built, tuple)
    argv, _display = built
    assert Path(argv[0]).name.lower().startswith("tsx")


def test_build_ts_returns_help_when_ts_runner_missing(tmp_path: Path):
    ts = tmp_path / "app.ts"
    ts.write_text("console.log('x')", encoding="utf-8")

    built = _build_file_command(ts, python_exe=_dummy_python_exe())
    assert isinstance(built, dict)
    assert "tsx" in built.get("error", "").lower()
    assert "ts-node" in built.get("error", "").lower()

