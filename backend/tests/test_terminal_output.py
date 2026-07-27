"""TDD: очистка вывода терминала (ANSI, ollama pull)."""

from core.terminal_output import (
    append_ollama_pull_hints,
    command_timeout_sec,
    sanitize_terminal_output,
    strip_ansi_escapes,
)

OLLAMA_GARBAGE = (
    "\x1b[?2026h\x1b[?25l\x1b[1Gpulling manifest \u2838 \x1b[K"
    "\x1b[?25h\x1b[?2026l\nError: connection reset"
)


def test_strip_ansi_escapes_removes_spinner_codes():
    cleaned = strip_ansi_escapes(OLLAMA_GARBAGE)
    assert "\x1b[" not in cleaned
    assert "pulling manifest" in cleaned


def test_sanitize_terminal_output_collapses_manifest_spinner():
    raw = OLLAMA_GARBAGE + "\n" + OLLAMA_GARBAGE + "\nError: pull model manifest failed"
    cleaned = sanitize_terminal_output(raw)
    assert cleaned.count("pulling manifest") == 1
    assert "Error:" in cleaned
    assert "\x1b[" not in cleaned


def test_append_ollama_pull_hints_for_network_error():
    result = append_ollama_pull_hints(
        {
            "command": "ollama pull llama3.1:8b",
            "output": "Error: read tcp wsarecv: forcibly closed",
            "error": "Код выхода: 1",
        }
    )
    assert "Подсказка CoreX" in result["output"]
    assert "registry.ollama.ai" in result["output"]


def test_command_timeout_longer_for_ollama_pull():
    assert command_timeout_sec("ollama pull llama3.1:8b", 120) == 3600
    assert command_timeout_sec("python main.py", 120) == 120
