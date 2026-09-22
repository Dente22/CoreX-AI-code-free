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
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        cleaned = re.sub(
            r"^(json|python|py|javascript|js|typescript|ts|tsx|jsx|html|css|markdown|md)\b[ \t]*\r?\n?",
            "",
            cleaned,
            count=1,
            flags=re.I,
        )
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


_AGENT_TOOLS = {
    "write_file",
    "append_file",
    "view_file",
    "patch_file",
    "run_file",
    "run_command",
    "list_directory",
}


def _tool_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def _is_agent_payload(data: Any) -> bool:
    if isinstance(data, list) and data:
        return _is_agent_payload(data[0])
    if not isinstance(data, dict):
        return False
    status = str(data.get("status") or "").strip().lower()
    if status in {"act", "done"}:
        return True
    return _tool_name(data.get("tool")) in _AGENT_TOOLS


def _close_truncated_json(text: str) -> str | None:
    """Закрыть оборванный JSON (незакрытая строка / скобки) — типичный write_file."""
    start = text.find("{")
    if start < 0:
        return None
    body = text[start:].rstrip()
    in_string = False
    escape = False
    braces = 0
    brackets = 0
    for ch in body:
        if escape:
            escape = False
            continue
        if in_string:
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            braces += 1
        elif ch == "}":
            braces = max(0, braces - 1)
        elif ch == "[":
            brackets += 1
        elif ch == "]":
            brackets = max(0, brackets - 1)
    if not in_string and braces == 0 and brackets == 0 and not escape:
        return None
    closed = body
    if escape and closed.endswith("\\"):
        closed = closed[:-1]
    if in_string:
        closed += '"'
    if brackets:
        closed += "]" * brackets
    if braces:
        closed += "}" * braces
    return closed


def _content_string_closed(text: str) -> bool:
    marker = re.search(r'"content"\s*:\s*"', text, re.IGNORECASE)
    if not marker:
        return False
    rest = text[marker.end() :]
    escape = False
    for idx, ch in enumerate(rest):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            after = rest[idx + 1 :].lstrip()
            if after == "" or after[:1] in {"}", ",", "]"}:
                return True
    return False


def _extract_write_file_content(text: str) -> str | None:
    """Достать content write_file даже если строка оборвана или кавычки не экранированы."""
    marker = re.search(r'"content"\s*:\s*"', text, re.IGNORECASE)
    if not marker:
        return None
    rest = text[marker.end() :]
    out: list[str] = []
    escape = False
    for idx, ch in enumerate(rest):
        if escape:
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
            out.append(mapping.get(ch, ch))
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            after = rest[idx + 1 :].lstrip()
            if after == "" or after[:1] in {"}", ",", "]"}:
                return "".join(out)
            out.append(ch)
            continue
        out.append(ch)
    blob = "".join(out)
    if escape and blob.endswith("\\"):
        blob = blob[:-1]
    blob = re.sub(r"[\s}\]]+$", "", blob)
    return blob


_FENCE_RE = re.compile(
    r"```([a-zA-Z0-9_+-]*)[ \t]*\r?\n?([\s\S]*?)```",
)
_OPEN_FENCE_RE = re.compile(
    r"```([a-zA-Z0-9_+-]*)[ \t]*\r?\n?([\s\S]*)$",
)


def extract_fenced_code(text: str) -> str | None:
    """Код в ``` после JSON — без экранирования кавычек внутри файла."""
    if not text:
        return None

    def _usable(lang: str, body: str) -> bool:
        head = body.lstrip()[:200]
        if lang.lower() == "json" and '"status"' in head and '"tool"' in head:
            return False
        if head.startswith("{") and '"status"' in head and '"tool"' in head:
            return False
        return bool(body.strip())

    last_end = 0
    best: str | None = None
    for match in _FENCE_RE.finditer(text):
        last_end = match.end()
        body = match.group(2).replace("\r\n", "\n")
        if _usable(match.group(1) or "", body):
            best = body if body.endswith("\n") else body + "\n"
    if best:
        return best
    rest = text[last_end:]
    open_match = _OPEN_FENCE_RE.search(rest)
    if open_match:
        body = open_match.group(2).replace("\r\n", "\n")
        if _usable(open_match.group(1) or "", body):
            return body
    return None


def _merge_fenced_content(action: dict, raw_text: str) -> dict:
    tool = _tool_name(action.get("tool"))
    if tool not in {"write_file", "append_file"}:
        return action
    fenced = extract_fenced_code(raw_text)
    if not fenced or not fenced.strip():
        return action
    args = dict(action.get("arguments") or {})
    existing = str(args.get("content") or "")
    if existing.strip() and len(fenced.strip()) < len(existing.strip()) + 8:
        return action
    args["content"] = fenced
    merged = {**action, "arguments": args}
    if existing.strip():
        merged["_from_fence"] = True
    return merged


_LEADING_LANG_RE = re.compile(
    r"^(?:json|python|py|javascript|js|typescript|ts|tsx|jsx|html|css)\b[ \t]*",
    re.I,
)


def _strip_leading_lang_tag(text: str) -> str:
    blob = (text or "").strip()
    if re.match(
        r"^(?:python|py)\b[ \t]+(?:import |from |def |class |pygame)",
        blob,
        re.I,
    ):
        return _LEADING_LANG_RE.sub("", blob, count=1).strip()
    if re.match(r"^(?:python|py)\b\s*\n", blob, re.I):
        return blob.split("\n", 1)[-1].lstrip()
    return blob


_INLINE_LINE_NO_RE = re.compile(r"\s+(\d+)\|\s?")
_PREFIX_LINE_NO_RE = re.compile(r"^\s*\d+\|\s?(.*)$")


def strip_viewfile_line_numbers(text: str) -> str:
    """Снять префиксы «54| » из ответа модели (карта view_file, иногда в одну строку)."""
    blob = (text or "").strip()
    if not blob or "|" not in blob:
        return blob
    if not re.search(r"(?:^|\s)\d+\|", blob):
        return blob
    blob = _INLINE_LINE_NO_RE.sub(r"\n\1| ", blob)
    lines: list[str] = []
    for line in blob.splitlines():
        match = _PREFIX_LINE_NO_RE.match(line)
        lines.append(match.group(1) if match else line)
    return "\n".join(lines).strip()


def _looks_like_source(text: str) -> bool:
    blob = strip_viewfile_line_numbers(_strip_leading_lang_tag(text))
    if not blob or blob[0] in "{[":
        return False
    head = blob[:400]
    if '"status"' in head and '"tool"' in head:
        return False
    lowered = blob.lower()
    if any(
        token in lowered
        for token in (
            "pygame.init",
            "import pygame",
            "import tkinter",
            "class snake",
            "class snakegame",
        )
    ):
        return True
    if re.search(r"(?:^|\n)\s*(import |from \w+ import |def |class )", blob):
        return True
    return False


def _infer_write_path(source: str, default_path: str | None) -> str:
    cleaned_default = (default_path or "").replace("\\", "/").strip()
    if cleaned_default and cleaned_default not in {".", "/"}:
        return cleaned_default
    blob = source.lower()
    if "<html" in blob or "<!doctype" in blob:
        return "index.html"
    return "main.py"


def _looks_like_python_fragment(text: str) -> bool:
    """Одна строка/кусок кода без JSON — типичный срыв qwen после патча."""
    blob = strip_viewfile_line_numbers(_strip_leading_lang_tag(text)).strip()
    if not blob or blob[0] in "{[":
        return False
    head = blob[:200]
    if '"status"' in head and '"tool"' in head:
        return False
    if len(blob) > 8000:
        return False
    lowered = blob.lower()
    if any(
        token in lowered
        for token in ("tkinter", "canvas.", "pygame.", "keysym", "snake", "bind(")
    ):
        return True
    return bool(
        re.search(
            r"^\s*(?:def |class |import |from |if |elif |else:|for |while |"
            r"return |print\(|pass\b|self\.|"
            r"[A-Za-z_]\w*\s*=|"
            r"[A-Za-z_]\w*\.[A-Za-z_]\w*\s*\()",
            blob,
            re.M,
        )
    )


def _prefer_append_salvage(blob: str) -> bool:
    stripped = blob.strip()
    has_import = bool(re.search(r"(?:^|\n)\s*(import |from \w+ import )", stripped))
    if has_import and (
        "def " in stripped
        or "pygame" in stripped.lower()
        or "class " in stripped
        or len(stripped) > 80
    ):
        return False
    return True


def _salvage_bare_source(text: str, default_path: str | None = None) -> dict | None:
    """Модель вывела код без JSON — всё равно записать файл."""
    fenced = extract_fenced_code(text)
    blob = fenced.strip() if fenced and fenced.strip() else _strip_leading_lang_tag(_strip_fences(text))
    blob = strip_viewfile_line_numbers(blob)
    looks_full = _looks_like_source(blob)
    looks_frag = _looks_like_python_fragment(blob)
    if not looks_full and not looks_frag:
        return None
    path = _infer_write_path(blob, default_path)
    content = blob if blob.endswith("\n") else blob + "\n"
    tool = (
        "write_file"
        if looks_full and not _prefer_append_salvage(blob)
        else "append_file"
    )
    from core.file_outline import looks_like_truncated_source

    truncated = tool == "write_file" and looks_like_truncated_source(content)
    return {
        "status": "act",
        "server": "filesystem",
        "tool": tool,
        "arguments": {"path": path, "content": content},
        "_salvaged_truncated": truncated,
    }


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
    if tool in {"write_file", "view_file", "patch_file", "append_file"}:
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
    return ""


def _file_write_tool(text: str) -> str | None:
    match = re.search(
        r'"tool"\s*:\s*"(?:filesystem\.)?(write_file|append_file)"',
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).lower()
    return None


def _salvage_truncated_write_file(text: str) -> dict | None:
    """write_file/append_file оборван: сохранить уже сгенерированный код."""
    tool = _file_write_tool(text)
    if not tool:
        return None
    path = _extract_quoted_field(text, "path")
    if not path:
        path_match = re.search(
            r'"path"\s*:\s*"([^"]+\.(?:css|html|js|ts|tsx|jsx|py|md))"',
            text,
            re.IGNORECASE,
        )
        path = path_match.group(1) if path_match else None
    if not path:
        return None
    fenced = extract_fenced_code(text)
    if fenced and fenced.strip():
        return {
            "status": "act",
            "server": "filesystem",
            "tool": tool,
            "arguments": {"path": path.replace("\\", "/"), "content": fenced},
            "_salvaged_truncated": True,
        }
    if not re.search(r'"content"\s*', text, re.IGNORECASE):
        return None
    content = _extract_write_file_content(text)
    if _content_string_closed(text) and content is not None:
        return None
    if content is not None and content.strip():
        return {
            "status": "act",
            "server": "filesystem",
            "tool": tool,
            "arguments": {"path": path.replace("\\", "/"), "content": content},
            "_salvaged_truncated": True,
        }
    content = _minimal_file_stub(path)
    if not (content or "").strip():
        return None
    return {
        "status": "act",
        "server": "filesystem",
        "tool": tool,
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
    content = _extract_write_file_content(text) or _extract_quoted_field(text, "content")
    if content is None:
        fenced = extract_fenced_code(text)
        if fenced and fenced.strip():
            content = fenced
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
        "tool": _file_write_tool(text) or "write_file",
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

    if tool in {"patch_file", "write_file", "append_file"} or (path and _OP_RE.search(text)):
        tool = tool or "patch_file"
        args: dict[str, Any] = {}
        if path:
            args["path"] = path
        if tool == "append_file":
            fenced = extract_fenced_code(text)
            if fenced:
                args["content"] = fenced
            return {
                "status": "act",
                "server": "filesystem",
                "tool": "append_file",
                "arguments": args,
            }
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

    if tool in {"write_file", "append_file", "view_file", "patch_file"}:
        server = "filesystem"

    if tool in {"run_file", "run_command"}:
        server = "terminal"

    if tool == "run_command":
        inferred = infer_run_command(args, action, raw_text=raw_text)
        if inferred:
            args["command"] = inferred

    if tool:
        result = {
            "status": status,
            "server": server,
            "tool": tool,
            "arguments": args,
        }
        if action.get("_salvaged_truncated"):
            result["_salvaged_truncated"] = True
        return result
    return action


def _starts_with_json(text: str) -> bool:
    stripped = (text or "").lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return True
    return stripped[:12].lower().startswith("```json")


def parse_agent_json(text: str, *, default_path: str | None = None) -> dict | None:
    cleaned = _strip_fences(text)
    if not cleaned:
        return None

    if not _starts_with_json(text):
        salvaged = (
            _salvage_bare_source(text, default_path)
            or _salvage_bare_source(cleaned, default_path)
        )
        if salvaged:
            parsed = _coerce_action_shape(salvaged)
            result = normalize_agent_action(parsed, raw_text=text)
            if isinstance(result, dict):
                result = _merge_fenced_content(result, text)
                if salvaged.get("_salvaged_truncated"):
                    result["_salvaged_truncated"] = True
                return result

    parsed = _try_load(cleaned)
    if parsed is None:
        parsed = _try_load(text.strip())
    used_close = False

    if not _is_agent_payload(parsed):
        salvaged = _regex_fallback_action(cleaned) or _regex_fallback_action(text)
        if salvaged:
            parsed = salvaged

    if not _is_agent_payload(parsed):
        closed = _close_truncated_json(cleaned)
        if closed:
            loaded = _try_load(closed)
            if _is_agent_payload(loaded):
                parsed = loaded
                used_close = True

    if not _is_agent_payload(parsed):
        for opener, closer in (("{", "}"), ("[", "]")):
            for fragment in _find_balanced_json(cleaned, opener, closer):
                loaded = _try_load(fragment)
                if _is_agent_payload(loaded):
                    parsed = loaded
                    break
            if _is_agent_payload(parsed):
                break

    if not _is_agent_payload(parsed):
        extracted = _extract_json_object(text)
        if extracted:
            loaded = _try_load(extracted)
            if _is_agent_payload(loaded):
                parsed = loaded

    if not _is_agent_payload(parsed):
        parsed = (
            _salvage_bare_source(cleaned, default_path)
            or _salvage_bare_source(text, default_path)
        )

    if parsed is None:
        return None

    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else None
    if not isinstance(parsed, dict):
        return None

    salvaged_flag = bool(parsed.get("_salvaged_truncated")) or used_close
    parsed = _coerce_action_shape(parsed)

    if "status" not in parsed:
        fallback = _regex_fallback_action(cleaned) or _regex_fallback_action(text)
        if fallback:
            salvaged_flag = salvaged_flag or bool(fallback.get("_salvaged_truncated"))
            parsed = _coerce_action_shape(fallback)
        else:
            return None

    if "status" not in parsed:
        return None

    result = normalize_agent_action(parsed, raw_text=text)
    if isinstance(result, dict):
        result = _merge_fenced_content(result, text)
    if (
        salvaged_flag
        and isinstance(result, dict)
        and _tool_name(result.get("tool")) in {"write_file", "append_file"}
    ):
        result["_salvaged_truncated"] = True
    return result


def compact_tool_result_for_prompt(tool: str, result: dict, *, focus_line: int | None = None) -> dict:
    """Укоротить результат view_file — карта строк + номера для patch."""
    if not isinstance(result, dict):
        return result
    if tool != "view_file" or result.get("status") != "Success":
        compact = dict(result)
        compact.pop("result", None)
        if "output" in compact and len(str(compact.get("output", ""))) > 2000:
            compact["output"] = str(compact["output"])[:2000] + "..."
        return compact

    from core.file_outline import line_map_for_prompt, numbered_window

    payload = dict(result.get("result") or {})
    numbered = payload.get("numbered_content") or ""
    content = str(payload.get("content") or "")
    lines = numbered.splitlines()
    line_count = int(payload.get("line_count") or len(content.splitlines()) or len(lines))
    path = str(result.get("path") or payload.get("path") or "main.py")
    line_map = line_map_for_prompt(content, path=path) if content else ""
    hint = (
        "Номер слева = line для patch_file. "
        "Изменить: op=replace line=N content=эта_строка. "
        "Удалить: op=delete line=N. Не угадывай номер. "
        "Не append второй def с тем же именем."
    )

    if focus_line and content:
        return {
            "status": "Success",
            "tool": "view_file",
            "path": path,
            "line_count": line_count,
            "line_map": line_map,
            "numbered_snippet": numbered_window(content, int(focus_line), radius=12),
            "focus_line": focus_line,
            "hint": hint,
        }

    max_lines = 140
    rows = content.splitlines() if content else []
    if len(rows) > max_lines:
        head = "\n".join(f"{i + 1:4d}| {rows[i]}" for i in range(20))
        tail_start = max(20, len(rows) - 20)
        tail = "\n".join(f"{i + 1:4d}| {rows[i]}" for i in range(tail_start, len(rows)))
        numbered = f"{head}\n   ... середина скрыта, номера функций в line_map ...\n{tail}"
    elif content:
        from core.file_patch import number_file_content

        numbered = number_file_content(content)

    return {
        "status": "Success",
        "tool": "view_file",
        "path": path,
        "line_count": line_count,
        "line_map": line_map,
        "numbered_content": numbered,
        "hint": hint,
    }


JSON_RETRY_TEMPLATES = (
    'view: {"status":"act","server":"filesystem","tool":"view_file","arguments":{"path":"main.py"}}',
    'write: {"status":"act","server":"filesystem","tool":"write_file","arguments":{"path":"main.py"}}',
    'append: {"status":"act","server":"filesystem","tool":"append_file","arguments":{"path":"main.py"}}',
    'run: {"status":"act","server":"terminal","tool":"run_command","arguments":{"command":"python main.py","cwd":"."}}',
    'patch: {"status":"act","server":"filesystem","tool":"patch_file","arguments":{"path":"main.py","op":"replace","line":60,"content":"    pygame.quit()"}}',
    'done: {"status":"done","message":"Готово"}',
)


def json_retry_hint(attempt: int, snippet: str, *, target_path: str | None = None) -> str:
    path = target_path or ""
    if not path:
        path_match = _PATH_RE.search(snippet)
        if path_match:
            path = path_match.group(1)
    path = path or "main.py"
    return (
        "\nAssistant output was invalid.\n"
        "System: JSON не обязателен. Выведи ПОЛНЫЙ рабочий файл:\n"
        "```python\n"
        "# весь код программы, не заглушка\n"
        "```\n"
        f"CoreX сохранит это как {path}. Один файл целиком за ход.\n"
        "Если умеешь JSON — заголовок write_file, затем тот же блок ```.\n"
        f'{{"status":"act","server":"filesystem","tool":"write_file","arguments":{{"path":"{path}"}}}}\n'
        f"Attempt {attempt}. Broken output started with: {snippet[:300]}\n"
    )
