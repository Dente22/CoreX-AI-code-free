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
    assert "не вставляй полный HTML" in text


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
    assert "--skip-sanity-check-repo" in launch.argv
    assert "--no-check-update" in launch.argv
    assert "--chat-mode" not in launch.argv
    assert launch.env.get("TERM") == "dumb"
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


def test_aider_chat_filter_keeps_prose_and_hides_diff():
    from core.aider_service import AiderChatFilter

    filt = AiderChatFilter()
    kinds = []
    for line in [
        "Aider v0.86.1",
        "Main model: ollama_chat/qwen2.5-coder:7b with diff edit format",
        "Git repo: .git with 3 files",
        "> сделай калькулятор",
        "Соберу калькулятор на tkinter с кнопками.",
        "calculator.py",
        "<<<<<<< SEARCH",
        "=======",
        "import tkinter as tk",
        ">>>>>>> REPLACE",
        "Applied edit to calculator.py",
        "Tokens: 1.2k sent, 400 received.",
        "https://aider.chat/docs",
    ]:
        event = filt.feed(line)
        if event:
            kinds.append(event.kind)

    assert "reply" in kinds
    assert "file" in kinds
    assert filt.reply_text == "Соберу калькулятор на tkinter с кнопками."
    assert filt.files == ["calculator.py"]
    assert kinds.count("reply") == 1
    assert "import tkinter" not in filt.reply_text
    assert "Aider v" not in filt.reply_text
    assert "Tokens:" not in filt.reply_text


def test_aider_chat_filter_hides_html_dump_and_windows_noise():
    from core.aider_service import AiderChatFilter, public_aider_reply

    filt = AiderChatFilter()
    for line in [
        "Can't initialize prompt toolkit: No Windows console found. Are you running cmd.exe?",
        "Model: ollama_chat/qwen2.5-coder:7b with whole edit format",
        "D:\\Project\\Test11\\snake.py: file not found error",
        "Dropping snake.py from the chat.",
        "Сайт клуба будет тёмным лендингом.",
        "### index.html",
        "```html",
        "<!DOCTYPE html>",
        "<html lang=\"ru\">",
        "<body>",
        "```",
        "body {",
        "font-family: Arial, sans-serif;",
        "Summarization failed for model ollama_chat/qwen2.5-coder:7b",
        "Applied edit to index.html",
    ]:
        filt.feed(line)

    assert filt.reply_text == "Сайт клуба будет тёмным лендингом."
    assert filt.files == ["index.html"]
    assert "<!DOCTYPE" not in filt.reply_text
    assert "prompt toolkit" not in filt.reply_text
    assert public_aider_reply(filt.reply_text, filt.files) == "Сайт клуба будет тёмным лендингом."
    assert public_aider_reply("<!DOCTYPE html>\n<html>", ["index.html"]) == "Готово: index.html."
