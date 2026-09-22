"""TDD: разбор JSON-ответов агента и восстановление run_command."""

import json

from core.agent_json import infer_run_command, normalize_agent_action, parse_agent_json


def test_run_command_from_path_argument():
    action = {
        "status": "act",
        "tool": "run_command",
        "arguments": {"path": "core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py"},
    }
    normalized = normalize_agent_action(action)
    assert normalized["server"] == "terminal"
    assert normalized["arguments"]["command"].startswith("python ")
    assert "search.py" in normalized["arguments"]["command"]


def test_run_command_from_dotted_tool_name():
    action = {
        "status": "act",
        "tool": "terminal.run_command",
        "arguments": {"command": "python main.py"},
    }
    normalized = normalize_agent_action(action)
    assert normalized["server"] == "terminal"
    assert normalized["tool"] == "run_command"


def test_parse_run_command_from_broken_json():
    text = (
        '{"status":"act","tool":"run_command","arguments":{"path":'
        '"core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py"}}'
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["tool"] == "run_command"
    assert "python" in parsed["arguments"]["command"]


def test_infer_command_from_raw_text():
    raw = (
        'Some text {"status":"act","tool":"run_command","arguments":{}} '
        'python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py --design-system'
    )
    cmd = infer_run_command({}, raw_text=raw)
    assert "search.py" in cmd
    assert cmd.startswith("python ")


def test_view_file_split_server_tool():
    action = {"status": "act", "tool": "filesystem.view_file", "arguments": {"path": "main.py"}}
    normalized = normalize_agent_action(action)
    assert normalized["server"] == "filesystem"
    assert normalized["tool"] == "view_file"


def test_parse_flat_write_file_shape():
    action = {
        "status": "act",
        "tool": "write_file",
        "path": "design-system/MASTER.md",
        "content": "# Design Spec",
    }
    parsed = parse_agent_json(json.dumps(action))
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "design-system/MASTER.md"


def test_salvage_write_file_from_broken_json():
    text = (
        'Some text {"status":"act","tool":"write_file","path":"index.html",'
        '"content":"<!DOCTYPE html><html></html>"} trailing'
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["arguments"]["path"] == "index.html"


def test_salvage_truncated_write_file_css():
    text = (
        '{"status":"act","server":"filesystem","tool":"write_file",'
        '"arguments":{"path":"style.css","content"}}'
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "style.css"
    assert "brand" in parsed["arguments"]["content"] or len(parsed["arguments"]["content"]) > 0


def test_parse_truncated_snake_write_file_keeps_python():
    """Модель обрывает JSON на середине pygame-змейки — не ретраить, сохранить код."""
    text = (
        '{ "status": "act", "server": "filesystem", "tool": "write_file", '
        '"arguments": { "path": "main.py", "content": '
        '"#!/usr/bin/env python3\\n\\nimport pygame\\nimport time\\nimport random\\n\\n'
        'class SnakeGame:\\n def __init__(self, w'
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    content = parsed["arguments"]["content"]
    assert "pygame" in content
    assert "SnakeGame" in content
    assert 'print("CoreX stub")' not in content
    assert parsed.get("_salvaged_truncated") is True


def test_empty_python_write_does_not_become_corex_stub():
    text = (
        '{"status":"act","server":"filesystem","tool":"write_file",'
        '"arguments":{"path":"main.py","content":'
    )
    parsed = parse_agent_json(text)
    if parsed is not None:
        content = str((parsed.get("arguments") or {}).get("content") or "")
        assert 'print("CoreX stub")' not in content


def test_parse_write_file_ignores_inner_python_dict():
    """Неэкранированные кавычки в Python не должны отдавать {\"x\": 10} вместо write_file."""
    text = (
        '{"status":"act","server":"filesystem","tool":"write_file",'
        '"arguments":{"path":"main.py","content":"'
        'FOOD = {"x": 10, "y": 20}\\n'
        'pygame.display.set_caption("Snake")\\n'
        "print(FOOD)"
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["status"] == "act"
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    content = parsed["arguments"]["content"]
    assert "FOOD" in content
    assert "10" in content


def test_json_retry_hint_python_allows_complete_fence():
    from core.agent_json import json_retry_hint

    hint = json_retry_hint(1, '{"path":"main.py"', target_path="main.py")
    assert "# Spec" not in hint
    assert "```python" in hint
    assert "не обязателен" in hint.lower() or "json не обязателен" in hint.lower()
    assert "main.py" in hint


def test_parse_write_file_with_fenced_code_after_json():
    text = (
        '{"status":"act","server":"filesystem","tool":"write_file",'
        '"arguments":{"path":"main.py"}}\n'
        "```python\n"
        "import pygame\n"
        "pygame.init()\n"
        'print("snake")\n'
        "```\n"
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    assert "import pygame" in parsed["arguments"]["content"]
    assert 'print("snake")' in parsed["arguments"]["content"]


def test_parse_append_file_with_unclosed_fence():
    text = (
        '{"status":"act","server":"filesystem","tool":"append_file",'
        '"arguments":{"path":"main.py"}}\n'
        "```python\n"
        "def game_loop():\n"
        "    running = True\n"
    )
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["tool"] == "append_file"
    assert parsed["server"] == "filesystem"
    assert "def game_loop" in parsed["arguments"]["content"]
    assert "running = True" in parsed["arguments"]["content"]


def test_fence_wins_over_tiny_json_content():
    text = (
        '{"status":"act","tool":"write_file","arguments":{"path":"main.py","content":"x"}}\n'
        "```python\n"
        "import pygame\nclass Snake:\n    pass\n"
        "```\n"
    )
    parsed = parse_agent_json(text)
    assert "import pygame" in parsed["arguments"]["content"]


def test_parse_bare_python_dump_without_json():
    """Модель вывела код змейки без JSON — сохранить как write_file main.py."""
    text = (
        "python import pygame import time import random # Initialize the game "
        "pygame.init() # Define colors white = (255, 255, 255) yellow = (255, 255, 102) "
        "black = (0, 0, 0) red = (213, 50, 80) green = (0, 255, 0) blue = (50, 153, 213) # Define"
    )
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    assert "pygame.init" in parsed["arguments"]["content"]
    assert "import pygame" in parsed["arguments"]["content"]


def test_parse_fenced_python_without_json_header():
    text = "```python\nimport pygame\npygame.init()\nprint(1)\n```"
    parsed = parse_agent_json(text)
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    assert "pygame.init" in parsed["arguments"]["content"]
    assert not parsed["arguments"]["content"].lstrip().startswith("python")
    assert not parsed.get("_salvaged_truncated")


def test_bare_python_honors_folder_default_path():
    text = "```python\nimport tkinter as tk\nroot = tk.Tk()\nroot.mainloop()\n```"
    parsed = parse_agent_json(text, default_path="test1/main.py")
    assert parsed is not None
    assert parsed["arguments"]["path"] == "test1/main.py"


def test_compact_view_includes_line_map_and_delete_hint():
    from core.agent_json import compact_tool_result_for_prompt

    source = (
        "import pygame\n\n"
        "def gameLoop():\n"
        "    pass\n\n"
        "gameLoop()\n"
    )
    compact = compact_tool_result_for_prompt(
        "view_file",
        {
            "status": "Success",
            "path": "main.py",
            "result": {
                "content": source,
                "numbered_content": "   1| import pygame",
                "line_count": 6,
            },
        },
    )
    assert "line_map" in compact
    assert "gameLoop" in compact["line_map"]
    assert "delete" in compact["hint"].lower() or "Удалить" in compact["hint"] or "delete" in compact["line_map"]
    assert "numbered_content" in compact
    assert "3|" in compact["numbered_content"] or "   3|" in compact["numbered_content"]


def test_prose_then_python_fence_writes_main():
    text = "Вот программа:\n```python\nimport pygame\npygame.init()\nprint(1)\n```"
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["tool"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    assert "pygame.init" in parsed["arguments"]["content"]


def test_parse_bare_assignment_is_append_not_json_retry():
    text = "new_head = (head[0] - 1, head[1])"
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["status"] == "act"
    assert parsed["tool"] == "append_file"
    assert parsed["arguments"]["path"] == "main.py"
    assert "new_head" in parsed["arguments"]["content"]


def test_parse_bare_elif_fragment_is_append():
    text = "elif direction == 'left':\n    new_head = (head[0] - 1, head[1])"
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["tool"] == "append_file"
    assert "elif direction" in parsed["arguments"]["content"]


def test_parse_numbered_viewfile_dump_is_append_without_line_prefixes():
    text = (
        "54| if event.keysym == 'Left' and self.direction != 'right': "
        "55| self.direction = 'left' "
        "56| elif event.keysym == 'Right' and self.direction != 'left': "
        "57| self.direction = 'right'"
    )
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["status"] == "act"
    assert parsed["tool"] == "append_file"
    content = parsed["arguments"]["content"]
    assert "54|" not in content
    assert "self.direction = 'left'" in content
    assert "elif event.keysym" in content


def test_parse_self_method_call_is_append_not_json_retry():
    text = "self.snake.append([self.width // 2, self.height // 2])"
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["tool"] == "append_file"
    assert "self.snake.append" in parsed["arguments"]["content"]


def test_parse_canvas_bind_is_append():
    text = "self.canvas.bind('<KeyPress>', self.on_key_press)"
    parsed = parse_agent_json(text, default_path="main.py")
    assert parsed is not None
    assert parsed["tool"] == "append_file"
    assert "canvas.bind" in parsed["arguments"]["content"]
