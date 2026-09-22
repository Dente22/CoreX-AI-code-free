from core.staged_write import is_protocol_leak, merge_append, sanitize_code_chunk


def test_sanitize_drops_next_chunk_instruction():
    raw = (
        "import pygame\n"
        "fence with the NEXT chunk only.\n"
        "pygame.init()\n"
    )
    cleaned = sanitize_code_chunk(raw)
    assert "import pygame" in cleaned
    assert "pygame.init" in cleaned
    assert "NEXT chunk" not in cleaned


def test_protocol_leak_without_code():
    assert is_protocol_leak("fence with the NEXT chunk only.")
    assert is_protocol_leak("(Blocked done attempt 2/3)\n")
    assert not is_protocol_leak("import pygame\npygame.init()\n")


def test_sanitize_drops_blocked_done_and_json_fence():
    raw = (
        "import tkinter as tk\n"
        "root = tk.Tk()\n"
        "root.mainloop()\n"
        "(Blocked done attempt 2/3)\n"
        "```json\n"
        '{"status":"done","unchanged": false}\n'
    )
    cleaned = sanitize_code_chunk(raw)
    assert "import tkinter" in cleaned
    assert "mainloop" in cleaned
    assert "Blocked done" not in cleaned
    assert "```" not in cleaned
    assert "unchanged" not in cleaned


def test_merge_append_skips_duplicate_imports():
    existing = "import pygame\nimport sys\n\n"
    merged = merge_append(existing, "import pygame\nimport random\n\ndef loop():\n    pass\n")
    assert merged.count("import pygame") == 1
    assert "import random" in merged
    assert "def loop" in merged


def test_merge_append_ignores_leaked_hint():
    existing = "import pygame\n"
    merged = merge_append(existing, "fence with the NEXT chunk only.\n")
    assert merged == existing
