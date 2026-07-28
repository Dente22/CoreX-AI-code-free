"""TDD: устойчивость OllamaClient к обрыву соединения."""

from __future__ import annotations

from core.ollama_client import format_ollama_connection_error
from core.ollama_lifecycle import (
    begin_ollama_generation,
    end_ollama_generation,
    is_generation_active,
    reset_ollama_lifecycle_state,
)


def test_format_ollama_connection_error_for_winerror_10054():
    msg = format_ollama_connection_error(OSError("[WinError 10054] reset"), model_name="llama3.1:8b")
    assert "оборвала соединение" in msg.lower()


def test_generation_guard_blocks_idle_while_active():
    reset_ollama_lifecycle_state()
    begin_ollama_generation()
    assert is_generation_active() is True
    end_ollama_generation()
    assert is_generation_active() is False
