"""Tests for Aider launch mapping (no live Aider process)."""

from pathlib import Path
from types import SimpleNamespace

from core.aider_service import (
    build_aider_launch,
    build_aider_message,
    parse_edited_files,
    resolve_aider_model_env,
)
from core.llm_runtime import ActiveLlm


def test_ollama_model_env():
    client = SimpleNamespace(root_url="http://127.0.0.1:11435", api_key="", base_url="")
    active = ActiveLlm(
        client=client,
        mode="local",
        provider_id="ollama-qwen",
        provider_name="Qwen",
        model_name="qwen2.5-coder:3b",
        api_type="ollama",
    )
    model, env = resolve_aider_model_env(active)
    assert model == "ollama_chat/qwen2.5-coder:3b"
    assert env["OLLAMA_API_BASE"] == "http://127.0.0.1:11435"


def test_openrouter_model_env():
    client = SimpleNamespace(
        root_url="",
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
    )
    active = ActiveLlm(
        client=client,
        mode="online",
        provider_id="or",
        provider_name="OpenRouter",
        model_name="openrouter/free",
        api_type="openai",
    )
    model, env = resolve_aider_model_env(active)
    assert model == "openrouter/free"
    assert env["OPENROUTER_API_KEY"] == "sk-test"
    assert env["OPENAI_API_BASE"] == "https://openrouter.ai/api/v1"


def test_build_message_includes_persona_and_no_json_protocol():
    text = build_aider_message(
        task="сделай калькулятор",
        persona_label="developer",
        persona_body="Пиши чистый код",
        knowledge_text="skill tip",
        language_hint="Python",
        write_dest="calculator.py",
    )
    assert "калькулятор" in text
    assert "developer" in text
    assert "skill tip" in text
    assert "не делай git commit" in text.lower() or "Не делай git commit" in text
    assert "write_file" not in text


def test_build_launch_disables_autocommit(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "core.aider_service.find_aider_command",
        lambda: ["aider"],
    )
    client = SimpleNamespace(root_url="http://127.0.0.1:11435", api_key="", base_url="")
    active = ActiveLlm(
        client=client,
        mode="local",
        provider_id="ollama-qwen",
        provider_name="Qwen",
        model_name="qwen2.5-coder:3b",
        api_type="ollama",
    )
    launch = build_aider_launch(
        project_root=tmp_path,
        active=active,
        message="fix bug",
        chat_mode="code",
    )
    assert launch.argv[0] == "aider"
    assert "--no-auto-commits" in launch.argv
    assert "--yes-always" in launch.argv
    assert "--exit" in launch.argv
    assert "--subtree-only" in launch.argv
    assert "--chat-mode" not in launch.argv
    assert "--message-file" in launch.argv
    assert launch.model.startswith("ollama_chat/")


def test_normalize_chat_mode_rejects_code():
    from core.aider_service import normalize_aider_chat_mode

    assert normalize_aider_chat_mode("code") is None
    assert normalize_aider_chat_mode("ask") == "ask"
    assert normalize_aider_chat_mode(None, for_question=True) == "ask"


def test_run_aider_works_on_selector_loop(tmp_path: Path, monkeypatch):
    """Windows SelectorEventLoop не поддерживает asyncio subprocess — нужен Popen."""
    import asyncio
    import sys

    from core.aider_service import AiderLaunch, run_aider

    launch = AiderLaunch(
        argv=[sys.executable, "-c", "print('aider-ok')"],
        env={**dict(**{k: v for k, v in __import__('os').environ.items()})},
        cwd=tmp_path,
        model="test",
    )

    async def _run():
        return await run_aider(launch, timeout_sec=30.0)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    result = asyncio.run(_run())
    assert result.ok is True
    assert "aider-ok" in result.stdout
