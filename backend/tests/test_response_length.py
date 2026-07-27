"""TDD: длина ответа для conversational."""

from core.task_routing import is_conversational_message, response_length_instruction


def test_greeting_gets_natural_length_hint():
    hint = response_length_instruction("привет", conversational=True)
    assert "1–2" in hint or "1-2" in hint or "приветств" in hint.lower()


def test_exact_sentence_count():
    hint = response_length_instruction("ответь в 3 предложениях", conversational=True)
    assert "3" in hint


def test_brief_request():
    hint = response_length_instruction("кратко объясни", conversational=True)
    assert "1" in hint or "кратк" in hint.lower()
