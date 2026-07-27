"""TDD: core_x_skills пути в run_command резолвятся из установки CoreX."""

from __future__ import annotations

from core.core_x_library import COREX_ROOT
from core.terminal_service import _resolve_corex_library_paths


def test_resolve_corex_skills_script_path():
    rel = "core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py"
    command = f'python {rel} "fintech" --design-system -p "Test"'
    resolved = _resolve_corex_library_paths(command)
    expected = COREX_ROOT / rel
    assert expected.is_file(), "fixture search.py must exist in CoreX install"
    assert str(expected) in resolved
    assert "Documents\\test" not in resolved
    assert "Documents/test" not in resolved


def test_resolve_leaves_project_paths_unchanged():
    command = "python main.py"
    assert _resolve_corex_library_paths(command) == command


def test_resolve_corex_agents_path():
    rel = "core_x_agents/ui-ux-designer.md"
    command = f"type {rel}"
    resolved = _resolve_corex_library_paths(command)
    expected = COREX_ROOT / rel
    if expected.is_file():
        assert str(expected) in resolved
