"""Разбор и восстановление JSON-ответов агента."""

from __future__ import annotations

import json
import re
from typing import Any

def _find_balanced_json(text: str, opener: str, closer: str) -> list[str]:
    candidates: list[str] = []
    for idx, ch in enumerate(text):
        if ch != opener:
            continue
        depth = 0
        in_string = False
        escape = False
        for j in range(idx, len(text)):
            c = text[j]
            if escape:
                escape = False
                continue
            if c == "\\" and in_string:
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    candidates.append(text[idx : j + 1])
                    break
    return candidates


_STATUS_RE = re.compile(r'"status"\s*:\s*"(act|done)"', re.IGNORECASE)
_TOOL_RE = re.compile(r'"tool"\s*:\s*"([a-z_.]+)"', re.IGNORECASE)
_SERVER_RE = re.compile(r'"server"\s*:\s*"([a-z_]+)"', re.IGNORECASE)
_PATH_RE = re.compile(r'"path"\s*:\s*"([^"]+)"')
_COMMAND_RE = re.compile(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_OP_RE = re.compile(r'"op"\s*:\s*"([a-z_]+)"', re.IGNORECASE)
_LINE_RE = re.compile(r'"line"\s*:\s*(\d+)')
_CONTENT_RE = re.compile(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_MESSAGE_RE = re.compile(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _repair_json_text(text: str) -> str:
    repaired = text.strip()
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = repaired.replace("\r\n", "\n")
    return repaired


def _try_load(text: str) -> Any | None:
    if not text:
        return None
    for candidate in (text, _repair_json_text(text)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _coerce_action_shape(data: dict) -> dict:
    """Малые модели часто кладут path/content на верхний уровень без arguments."""
    if not isinstance(data, dict):
        return data
    if data.get("arguments"):
        return data
    args: dict[str, Any] = {}
    for key in ("path", "content", "command", "op", "line", "cwd", "operations", "script", "file", "args"):
        if key in data:
            args[key] = data[key]
    if not args:
        return data
    coerced = {k: v for k, v in data.items() if k not in args}
    coerced["arguments"] = args
    tool = str(coerced.get("tool") or "").lower()
    if tool in {"write_file", "view_file", "patch_file"}:
        coerced.setdefault("server", "filesystem")
    elif tool in {"run_file", "run_command"}:
        coerced.setdefault("server", "terminal")
    return coerced


def _extract_json_object(text: str) -> str | None:
    """Вырезать первый JSON-объект из текста с пояснениями модели."""
    cleaned = _strip_fences(text)
    start = cleaned.find("{")
    if start < 0:
        return None
    for fragment in _find_balanced_json(cleaned[start:], "{", "}"):
        return fragment
    return None


def _extract_quoted_field(text: str, field: str) -> str | None:
    pattern = re.compile(
        rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return _unescape_json_string(match.group(1))


def _minimal_file_stub(path: str) -> str:
    """Короткая заглушка, если модель оборвала content в write_file."""
    try:
        from core.web_delivery_layers import maybe_autofill_salvaged_web

        filled = maybe_autofill_salvaged_web(path, "", user_task="")
        if filled:
            return filled
    except ImportError:
        pass
    name = (path or "").replace("\\", "/").lower()
    if name.endswith(".css"):
        return (
            ":root{--brand:#9A5EFF;--accent:#00D2FF}"
            "body{margin:0;font-family:Inter,sans-serif;background:#0f1720;color:#e5e9f0}"
        )
    if name.endswith(".js"):
        return "document.addEventListener('DOMContentLoaded',()=>{});"
    if name.endswith(".html"):
        return (
            '<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">'
            '<title>CoreX</title></head><body></body></html>'
        )
    if name.endswith(".md"):
        return "# CoreX\n\nDraft — expand in next turn."
    if name.endswith(".py"):
        return 'print("CoreX stub")'
    return "CoreX draft"


def _salvage_truncated_write_file(text: str) -> dict | None:
    """write_file оборван на \"content\" без значения — path есть, content пустой."""
    if not re.search(r'"tool"\s*:\s*"write_file"', text, re.IGNORECASE):
        return None
    path = _extract_quoted_field(text, "path")
    if not path:
        path_match = re.search(
            r'"path"\s*:\s*"([^"]+\.(?:css|html|js|py|md))"',
            text,
            re.IGNORECASE,
        )
        path = path_match.group(1) if path_match else None
    if not path:
        return None
    if _extract_quoted_field(text, "content") is not None:
        return None
    if not re.search(r'"content"\s*', text, re.IGNORECASE):
        return None
    content = _minimal_file_stub(path)
    return {
        "status": "act",
        "server": "filesystem",
        "tool": "write_file",
        "arguments": {"path": path.replace("\\", "/"), "content": content},
        "_salvaged_truncated": True,
    }


def _salvage_write_file(text: str) -> dict | None:
    path = _extract_quoted_field(text, "path")
    if not path:
        path_match = re.search(
            r'(?:path|file)["\']?\s*:\s*["\']([^"\']+\.(?:md|html|css|js|py|tsx?|jsx?))["\']',
            text,
            re.IGNORECASE,
        )
        path = path_match.group(1) if path_match else None
    content = _extract_quoted_field(text, "content")
    if not path:
        return None
    if content is None:
        # Markdown/HTML block after path mention
        block = re.search(
            r"(?:content|markdown|html)\s*[:=]\s*```(?:html|markdown|md)?\s*([\s\S]+?)```",
            text,
            re.IGNORECASE,
        )
        if block:
            content = block.group(1).strip()
    if content is None:
        salvaged = _salvage_truncated_write_file(text)
        if salvaged:
            return salvaged
        return None
    return {
        "status": "act",
        "server": "filesystem",
        "tool": "write_file",
        "arguments": {"path": path.replace("\\", "/"), "content": content},
    }


def _salvage_done(text: str) -> dict | None:
    if not re.search(r'"status"\s*:\s*"done"', text, re.IGNORECASE):
        if not re.search(r"\bstatus\b.*\bdone\b", text, re.IGNORECASE):
            return None
    message = _extract_quoted_field(text, "message") or "Готово"
    return {"status": "done", "message": message}


def _regex_fallback_action(text: str) -> dict | None:
    salvaged = _salvage_truncated_write_file(text)
    if salvaged:
        return salvaged
    salvaged = _salvage_write_file(text)
    if salvaged:
        return salvaged
    salvaged_done = _salvage_done(text)
    if salvaged_done:
        return salvaged_done

    status_match = _STATUS_RE.search(text)
    if not status_match:
        return None
    status = status_match.group(1).lower()

    if status == "done":
        message_match = _MESSAGE_RE.search(text)
        message = message_match.group(1).replace('\\"', '"') if message_match else "Готово"
        return {"status": "done", "message": message}

    tool_match = _TOOL_RE.search(text)
    tool = tool_match.group(1).lower() if tool_match else None
    path_match = _PATH_RE.search(text)
    path = path_match.group(1) if path_match else None

    if tool == "view_file" and path:
        return {
            "status": "act",
            "server": "filesystem",
            "tool": "view_file",
            "arguments": {"path": path},
        }

    if tool in {"patch_file", "write_file"} or (path and _OP_RE.search(text)):
        tool = tool or "patch_file"
        args: dict[str, Any] = {}
        if path:
            args["path"] = path
        op_match = _OP_RE.search(text)
        if op_match:
            args["op"] = op_match.group(1).lower()
        line_match = _LINE_RE.search(text)
        if line_match:
            args["line"] = int(line_match.group(1))
        content_match = _CONTENT_RE.search(text)
        if content_match:
            args["content"] = content_match.group(1).replace('\\"', '"').replace("\\n", "\n")
        if tool == "write_file" and "content" in args:
            return {
                "status": "act",
                "server": "filesystem",
                "tool": "write_file",
                "arguments": {"path": path, "content": args["content"]},
            }
        if args.get("path") and (args.get("op") or args.get("content") is not None):
            return {
                "status": "act",
                "server": "filesystem",
                "tool": "patch_file",
                "arguments": args,
            }

    if tool == "run_file" and path:
        return {
            "status": "act",
            "server": "terminal",
            "tool": "run_file",
            "arguments": {"path": path},
        }

    command_match = _COMMAND_RE.search(text)
    if tool == "run_command" or command_match:
        command = _unescape_json_string(command_match.group(1)) if command_match else ""
        if not command and path and path.endswith(".py"):
            command = f"python {path}"
        if command:
            return {
                "status": "act",
                "server": "terminal",
                "tool": "run_command",
                "arguments": {"command": command},
            }

    return None


def _unescape_json_string(value: str) -> str:
    return value.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").strip()


def _split_server_tool(server: str | None, tool: str | None) -> tuple[str | None, str | None]:
    if tool and "." in tool:
        prefix, _, suffix = tool.partition(".")
        if prefix in {"filesystem", "terminal"} and suffix:
            return prefix, suffix
    if server and "." in server:
        prefix, _, suffix = server.partition(".")
        if prefix in {"filesystem", "terminal"} and suffix and not tool:
            return prefix, suffix
    return server, tool


def infer_run_command(args: dict, action: dict | None = None, raw_text: str = "") -> str:
    """Восстановить command для run_command — малые модели часто его пропускают."""
    action = action or {}
    direct = str(args.get("command") or action.get("command") or "").strip()
    if direct:
        return direct

    if raw_text:
        cmd_match = _COMMAND_RE.search(raw_text)
        if cmd_match:
            return _unescape_json_string(cmd_match.group(1))

        py_match = re.search(
            r"(?:python|py)\s+([^\s\"']+\.py)(?:\s+(--[\w-]+(?:\s+[\w.-]+)?))*",
            raw_text,
            re.IGNORECASE,
        )
        if py_match:
            cmd = f"python {py_match.group(1)}"
            if py_match.group(2):
                cmd += f" {py_match.group(2).strip()}"
            return cmd.strip()

    for key in ("script", "file", "path"):
        val = str(args.get(key) or action.get(key) or "").strip().replace("\\", "/")
        if not val:
            continue
        if val.endswith(".py"):
            extra = str(args.get("args") or action.get("args") or "").strip()
            return f"python {val}{f' {extra}' if extra else ''}".strip()
        if val.endswith((".sh", ".bash")):
            return f"bash {val}"
        if val.endswith(".js"):
            return f"node {val}"

    return ""


def normalize_agent_action(action: dict, *, raw_text: str = "") -> dict:
    if not isinstance(action, dict):
        return action

    status = action.get("status")
    server = action.get("server") or "filesystem"
    tool = action.get("tool")
    args = dict(action.get("arguments") or {})

    for key in ("path", "op", "line", "content", "command", "cwd", "operations", "script", "file", "args"):
        if key in action and key not in args:
            args[key] = action[key]

    server, tool = _split_server_tool(str(server) if server else None, str(tool) if tool else None)

    if not tool and args.get("op") and args.get("path"):
        tool = "patch_file"
        server = "filesystem"

    if tool in {"run_file", "run_command"}:
        server = "terminal"

    if tool == "run_command":
        inferred = infer_run_command(args, action, raw_text=raw_text)
        if inferred:
            args["command"] = inferred

    if tool:
        return {
            "status": status,
            "server": server,
            "tool": tool,
            "arguments": args,
        }
    return action


def parse_agent_json(text: str) -> dict | None:
    cleaned = _strip_fences(text)
    if not cleaned:
        return None

    parsed = _try_load(cleaned)
    if parsed is None:
        parsed = _try_load(text.strip())

    if parsed is None:
        for opener, closer in (("{", "}"), ("[", "]")):
            for fragment in _find_balanced_json(cleaned, opener, closer):
                parsed = _try_load(fragment)
                if parsed is not None:
                    break
            if parsed is not None:
                break

    if parsed is None:
        extracted = _extract_json_object(text)
        if extracted:
            parsed = _try_load(extracted)

    if parsed is None:
        parsed = _regex_fallback_action(cleaned) or _regex_fallback_action(text)

    if parsed is None:
        return None

    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else None
    if not isinstance(parsed, dict):
        return None

    parsed = _coerce_action_shape(parsed)

    if "status" not in parsed:
        return None

    return normalize_agent_action(parsed, raw_text=text)


def compact_tool_result_for_prompt(tool: str, result: dict, *, focus_line: int | None = None) -> dict:
    """Укоротить результат view_file — меньше шансов сломать JSON на следующем ходе."""
    if not isinstance(result, dict):
        return result
    if tool != "view_file" or result.get("status") != "Success":
        compact = dict(result)
        compact.pop("result", None)
        if "output" in compact and len(str(compact.get("output", ""))) > 2000:
            compact["output"] = str(compact["output"])[:2000] + "..."
        return compact

    payload = dict(result.get("result") or {})
    numbered = payload.get("numbered_content") or ""
    lines = numbered.splitlines()
    line_count = int(payload.get("line_count") or len(lines))

    if focus_line and lines:
        window = 12
        start = max(0, focus_line - window - 1)
        end = min(len(lines), focus_line + window)
        snippet = "\n".join(lines[start:end])
        return {
            "status": "Success",
            "tool": "view_file",
            "path": result.get("path"),
            "line_count": line_count,
            "numbered_snippet": snippet,
            "focus_line": focus_line,
            "hint": "Edit with patch_file: one op per turn. Escape quotes in content.",
        }

    max_lines = 36
    if len(lines) > max_lines:
        head = lines[:18]
        tail = lines[-12:]
        numbered = "\n".join(
            head + [f"   ... ({line_count - 30} lines hidden) ..."] + tail
        )

    return {
        "status": "Success",
        "tool": "view_file",
        "path": result.get("path"),
        "line_count": line_count,
        "numbered_content": numbered,
        "hint": "Edit with patch_file using line numbers. ONE short JSON object per turn.",
    }


JSON_RETRY_TEMPLATES = (
    'view: {"status":"act","server":"filesystem","tool":"view_file","arguments":{"path":"main.py"}}',
    'write: {"status":"act","server":"filesystem","tool":"write_file","arguments":{"path":"main.py","content":"print(1)"}}',
    'run: {"status":"act","server":"terminal","tool":"run_command","arguments":{"command":"python main.py","cwd":"."}}',
    'patch: {"status":"act","server":"filesystem","tool":"patch_file","arguments":{"path":"main.py","op":"replace","line":60,"content":"    pygame.quit()"}}',
    'done: {"status":"done","message":"Готово"}',
)


def json_retry_hint(attempt: int, snippet: str, *, target_path: str | None = None) -> str:
    templates = "\n".join(f"  {item}" for item in JSON_RETRY_TEMPLATES)
    path_hint = ""
    if not target_path:
        path_match = _PATH_RE.search(snippet)
        if path_match:
            target_path = path_match.group(1)
    if target_path:
        ext = target_path.rsplit(".", 1)[-1].lower() if "." in target_path else ""
        if ext == "css":
            example_content = (
                ":root{--brand:#9A5EFF;--accent:#00D2FF}"
                "body{margin:0;font-family:Inter,sans-serif;background:#0f1720;color:#e5e9f0}"
            )
        elif ext == "html":
            example_content = "<!DOCTYPE html><html><head><meta charset=\\\"UTF-8\\\"></head><body></body></html>"
        else:
            example_content = "# Spec\\n..."
        path_hint = (
            f"\nFor THIS step respond ONLY with write_file to \"{target_path}\". "
            f"Keep content under 500 chars on ONE line. Escape quotes as \\\". Example:\n"
            f'{{"status":"act","server":"filesystem","tool":"write_file",'
            f'"arguments":{{"path":"{target_path}","content":"{example_content}"}}}}\n'
        )
    return (
        f"\nAssistant output was invalid.\n"
        "System Error: Return EXACTLY ONE raw JSON object. No markdown. No text outside JSON.\n"
        "Escape double quotes inside content as \\\". Keep content on one line when possible.\n"
        f"{path_hint}"
        f"Valid templates:\n{templates}\n"
        f"Attempt {attempt}. Broken output started with: {snippet[:300]}\n"
    )
