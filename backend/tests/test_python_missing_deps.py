import pytest

from core.code_verify import verify_python_file
from core.error_remediation import parse_error_hints, remediate_python_error
from core.local_pipeline_profile import COMPACT_AGENT_SYSTEM_PROMPT
from core.orchestrator import CoreXOrchestrator
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_verify_missing_module_is_dependency_phase(tmp_path):
    (tmp_path / "main.py").write_text(
        "import corex_no_such_pkg_xyz\n",
        encoding="utf-8",
    )
    result = await verify_python_file(tmp_path, "main.py")
    assert result["ok"] is False
    assert result["phase"] == "dependency"
    assert result["missing_module"] == "corex_no_such_pkg_xyz"


def test_remediate_does_not_write_to_project_root(tmp_path):
    (tmp_path / "main.py").write_text("import pygame\n", encoding="utf-8")
    result = remediate_python_error(
        tmp_path,
        ".",
        "Error: No module named 'pygame'\n",
    )
    assert result.get("ok") is False
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == "import pygame\n"


def test_remediate_adds_requirements_without_touching_source(tmp_path):
    (tmp_path / "main.py").write_text("import pygame\npygame.init()\n", encoding="utf-8")
    result = remediate_python_error(
        tmp_path,
        "main.py",
        "ModuleNotFoundError: No module named 'pygame'",
    )
    assert result.get("ok") is True
    assert "pygame" in (tmp_path / "requirements.txt").read_text(encoding="utf-8")
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == (
        "import pygame\npygame.init()\n"
    )


def test_parse_short_no_module_named():
    hints = parse_error_hints("Error: No module named 'pygame'\nКод выхода: 1")
    assert "pygame" in hints["missing_modules"]


def test_compact_prompt_patch_example_is_not_stub():
    assert "# fix" not in COMPACT_AGENT_SYSTEM_PROMPT
    assert '"content":"fix"' not in COMPACT_AGENT_SYSTEM_PROMPT
    assert "skeleton" not in COMPACT_AGENT_SYSTEM_PROMPT
    assert "JSON is optional" in COMPACT_AGENT_SYSTEM_PROMPT
    assert "```python" in COMPACT_AGENT_SYSTEM_PROMPT


def test_system_prompt_does_not_teach_hash_fix_stub(tmp_path):
    orchestrator = CoreXOrchestrator(
        ollama_client=MagicMock(),
        mcp_manager=MagicMock(),
        gui=MagicMock(),
    )
    text = orchestrator._build_system_prompt(
        tmp_path,
        "developer",
        user_task="создай змейку",
        include_knowledge=False,
        compact=False,
    )
    assert "# fix" not in text
    compact = orchestrator._build_system_prompt(
        tmp_path,
        "developer",
        user_task="создай змейку",
        include_knowledge=False,
        compact=True,
    )
    assert "# fix" not in compact
    assert '"content":"fix"' not in compact
    assert "400" not in compact
    assert "template" not in compact.lower()
    assert "```python" in compact or "fence" in compact.lower()
