"""Tests for the Claude Code engine mapping (no live Claude Code process)."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import claude_code_service as ccs
from core.claude_code_service import (
    OMNIROUTE_HINT,
    ClaudeBrain,
    ClaudeStreamParser,
    build_claude_code_launch,
    build_claude_env,
    build_claude_system_prompt,
    build_claude_task_message,
    public_claude_reply,
    resolve_claude_brain,
    run_claude_code,
)
from core.llm_runtime import ActiveLlm


def _active(mode, api_type, model, *, base_url="", api_key="", root_url="", provider_name="P"):
    client = SimpleNamespace(root_url=root_url, api_key=api_key, base_url=base_url)
    return ActiveLlm(
        client=client,
        mode=mode,
        provider_id="p",
        provider_name=provider_name,
        model_name=model,
        api_type=api_type,
    )


def test_local_ollama_brain_uses_native_anthropic_endpoint():
    brain = resolve_claude_brain(
        _active("local", "ollama", "qwen3:4b", root_url="http://127.0.0.1:11435/")
    )
    assert brain == ClaudeBrain("http://127.0.0.1:11435", "ollama", "qwen3:4b", True)


def test_omniroute_brain_strips_v1_and_keeps_bare():
    brain = resolve_claude_brain(
        _active(
            "online",
            "openai",
            "auto/coding",
            base_url="http://127.0.0.1:20128/v1",
            api_key="sk-omni",
        )
    )
    assert brain.base_url == "http://127.0.0.1:20128"
    assert brain.bare is True
    assert brain.model == "auto/coding"


def test_openrouter_brain_uses_bearer_mode():
    brain = resolve_claude_brain(
        _active(
            "online",
            "openai",
            "openrouter/free",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or",
        )
    )
    assert brain.base_url == "https://openrouter.ai/api"
    assert brain.bare is False


@pytest.mark.parametrize(
    ("api_type", "base_url"),
    [("gemini", "https://generativelanguage.googleapis.com"), ("openai", "https://api.groq.com/openai/v1")],
)
def test_openai_only_providers_point_to_omniroute(api_type, base_url):
    with pytest.raises(ValueError) as err:
        resolve_claude_brain(_active("online", api_type, "m", base_url=base_url, api_key="k"))
    assert str(err.value) == OMNIROUTE_HINT


def test_online_without_key_is_rejected():
    with pytest.raises(ValueError):
        resolve_claude_brain(_active("online", "openai", "m", base_url="http://127.0.0.1:20128/v1"))


def test_env_replaces_inherited_anthropic_vars(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "leaked")
    monkeypatch.setenv("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku")
    env = build_claude_env(ClaudeBrain("http://127.0.0.1:11435", "ollama", "qwen3:4b", True))
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:11435"
    assert env["ANTHROPIC_API_KEY"] == "ollama"
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "ANTHROPIC_SMALL_FAST_MODEL" not in env
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "qwen3:4b"
    assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "qwen3:4b"


def test_env_bearer_mode_blanks_api_key():
    env = build_claude_env(ClaudeBrain("https://openrouter.ai/api", "sk-or", "m", False))
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-or"
    assert env["ANTHROPIC_API_KEY"] == ""


def test_launch_argv_edit_and_read_only(monkeypatch, tmp_path):
    monkeypatch.setattr(ccs, "find_claude_command", lambda: ["claude"])
    active = _active("local", "ollama", "qwen3:4b", root_url="http://127.0.0.1:11435")

    launch = build_claude_code_launch(
        project_root=tmp_path,
        active=active,
        task_message="сделай hello.py",
        system_prompt="rules",
    )
    try:
        argv = launch.argv
        assert argv[:2] == ["claude", "-p"]
        assert "--bare" in argv
        assert argv[argv.index("--tools") + 1] == "Bash,Edit,Write,Read,Glob,Grep"
        assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
        assert argv[argv.index("--model") + 1] == "qwen3:4b"
        prompt_file = Path(argv[argv.index("--append-system-prompt-file") + 1])
        assert prompt_file.read_text(encoding="utf-8") == "rules"
        assert launch.stdin_text == "сделай hello.py"
        assert launch.cwd == tmp_path.resolve()
    finally:
        for path in launch.temp_files:
            path.unlink(missing_ok=True)

    read_only = build_claude_code_launch(
        project_root=tmp_path, active=active, task_message="что тут?", read_only=True
    )
    assert read_only.argv[read_only.argv.index("--tools") + 1] == "Read,Glob,Grep"
    assert "--append-system-prompt-file" not in read_only.argv


def test_launch_without_cli_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(ccs, "find_claude_command", lambda: None)
    with pytest.raises(RuntimeError):
        build_claude_code_launch(
            project_root=tmp_path,
            active=_active("local", "ollama", "m", root_url="http://x"),
            task_message="t",
        )


def test_prompts_carry_rules_persona_and_task():
    system = build_claude_system_prompt(
        persona_label="Dev", persona_body="be brief", knowledge_text="skill", language_hint="Python"
    )
    assert "git push" in system
    assert "=== PERSONA: Dev ===" in system
    assert "skill" in system
    task = build_claude_task_message(task="fix bug", plan_text="план", write_dest="app.py")
    assert task.endswith("=== TASK ===\nfix bug")
    assert "app.py" in task


def _assistant(*blocks):
    return json.dumps({"type": "assistant", "message": {"content": list(blocks)}})


def test_stream_parser_events_paths_and_usage(tmp_path):
    parser = ClaudeStreamParser(cwd=tmp_path)
    win_path = "/" + str(tmp_path / "src" / "app.py").replace("\\", "/")

    assert parser.feed('{"type":"system","subtype":"init"}')[0].kind == "noise"
    events = parser.feed(
        _assistant(
            {"type": "text", "text": "Создаю файл"},
            {"type": "tool_use", "name": "Write", "input": {"file_path": win_path, "content": "x"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "python src/app.py"}},
        )
    )
    assert [e.kind for e in events] == ["reply", "file", "command"]
    expected = "src/app.py" if sys.platform == "win32" else events[1].path
    assert events[1].path == expected
    assert parser.commands == ["python src/app.py"]

    parser.feed(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "result": "Готово, файл создан.",
                "usage": {"input_tokens": 100, "cache_read_input_tokens": 50, "output_tokens": 20},
            }
        )
    )
    assert parser.reply_text == "Готово, файл создан."
    usage = parser.usage
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (150, 20, 170)


def test_stream_parser_counts_text_tool_calls():
    parser = ClaudeStreamParser()
    events = parser.feed(
        _assistant({"type": "text", "text": '{"name": "Write", "arguments": {"file_path": "a.py"}}'})
    )
    assert events[0].kind == "noise"
    assert parser.text_tool_calls == 1
    assert parser.reply_text == ""


def test_public_reply_hides_code_and_falls_back_to_files():
    assert public_claude_reply("Сделано.", ["a.py"]) == "Сделано."
    assert public_claude_reply("```py\nx\n```", ["a.py"]) == "Готово: a.py."
    assert public_claude_reply("", []) == "Шаг завершён."
    assert len(public_claude_reply("x" * 5000)) == 1200


def _fake_cli_launch(tmp_path, lines, exit_code=0, extra_code=""):
    script = tmp_path.parent / f"fake_claude_{tmp_path.name}.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.read()\n"
        f"{extra_code}\n"
        f"for line in {lines!r}:\n"
        "    print(line, flush=True)\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    prompt = tmp_path.parent / f"prompt_{tmp_path.name}.md"
    prompt.write_text("rules", encoding="utf-8")
    return ccs.ClaudeCodeLaunch(
        argv=[sys.executable, str(script)],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=tmp_path,
        model="qwen3:4b",
        stdin_text="task",
        temp_files=[prompt],
    )


async def test_run_claude_code_success_streams_events(tmp_path):
    lines = [
        _assistant({"type": "tool_use", "name": "Edit", "input": {"file_path": "main.py"}}),
        json.dumps({"type": "result", "subtype": "success", "result": "ok", "usage": {"output_tokens": 3}}),
    ]
    launch = _fake_cli_launch(tmp_path, lines)
    seen = []
    result = await run_claude_code(launch, on_event=lambda e: seen.append(e.kind))
    assert result.ok, result.error
    assert result.edited_files == ["main.py"]
    assert result.reply == "ok"
    assert seen == ["file", "result"]
    assert not launch.temp_files[0].exists()


async def test_run_claude_code_detects_files_written_by_bash(tmp_path):
    (tmp_path / "keep.txt").write_text("old", encoding="utf-8")
    lines = [
        _assistant({"type": "tool_use", "name": "Bash", "input": {"command": "echo x > hello.py"}}),
        json.dumps({"type": "result", "subtype": "success", "result": "ok"}),
    ]
    extra = "open('hello.py', 'w').write('print(1)')"
    result = await run_claude_code(_fake_cli_launch(tmp_path, lines, extra_code=extra))
    assert result.ok, result.error
    assert result.edited_files == ["hello.py"]
    assert result.commands == ["echo x > hello.py"]


async def test_run_claude_code_reports_max_turns(tmp_path):
    lines = [json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True})]
    result = await run_claude_code(_fake_cli_launch(tmp_path, lines, exit_code=1))
    assert not result.ok
    assert "лимит шагов" in result.error


async def test_run_claude_code_without_result_event_fails(tmp_path):
    result = await run_claude_code(_fake_cli_launch(tmp_path, ["plain text"]))
    assert not result.ok
    assert "result" in result.error
