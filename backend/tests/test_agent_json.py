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
