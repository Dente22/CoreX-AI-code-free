"""Claude Code CLI как движок правок CoreX: агент — Claude Code, «мозг» — модель из выбора CoreX.

Claude Code говорит только на протоколе Anthropic Messages. Его понимают:
Ollama (родной /v1/messages), OmniRoute (переводит на любой провайдер) и OpenRouter.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from core.cli_process import run_streaming_cli
from core.llm_runtime import ActiveLlm
from core.omniroute_service import is_omniroute_url
from core.token_usage_service import TokenUsage

CLAUDE_EDIT_TOOLS = ("Bash", "Edit", "Write", "Read", "Glob", "Grep")
CLAUDE_READ_TOOLS = ("Read", "Glob", "Grep")
DEFAULT_MAX_TURNS = 30

_FILE_TOOL_KEYS = {
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "Write": "file_path",
    "NotebookEdit": "notebook_path",
}
_REPLY_MAX_CHARS = 1200

OMNIROUTE_HINT = (
    "Claude Code понимает только протокол Anthropic. Groq, Gemini и другие "
    "OpenAI-совместимые API подключайте через OmniRoute: Модели → Онлайн → "
    "Добавить API → «OmniRoute (локальный шлюз)». Напрямую работают Ollama, "
    "OmniRoute и OpenRouter."
)

ClaudeEventKind = Literal["reply", "file", "command", "result", "noise"]


@dataclass(frozen=True)
class ClaudeBrain:
    base_url: str
    api_key: str
    model: str
    # --bare: минимальный системный промпт (~1k токенов вместо ~20k), но ключ только через x-api-key.
    bare: bool


@dataclass
class ClaudeCodeLaunch:
    argv: list[str]
    env: dict[str, str]
    cwd: Path
    model: str
    stdin_text: str
    temp_files: list[Path] = field(default_factory=list)


@dataclass
class ClaudeCodeEvent:
    kind: ClaudeEventKind
    text: str = ""
    path: str = ""
    payload: dict[str, Any] | None = None


@dataclass
class ClaudeCodeRunResult:
    ok: bool
    exit_code: int
    model: str = ""
    reply: str = ""
    edited_files: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    usage: TokenUsage | None = None
    text_tool_calls: int = 0
    error: str | None = None


def find_claude_command() -> list[str] | None:
    override = (os.environ.get("COREX_CLAUDE_CODE_PATH") or "").strip()
    if override and Path(override).is_file():
        return [override]
    home_bin = Path.home() / ".local" / "bin"
    for name in ("claude.exe", "claude"):
        candidate = home_bin / name
        if candidate.is_file():
            return [str(candidate)]
    exe = shutil.which("claude")
    if exe:
        return [exe]
    return None


def claude_code_missing_message() -> str:
    return (
        "Claude Code не найден. Установите его (https://docs.anthropic.com/claude-code) "
        "или укажите путь к claude.exe в переменной COREX_CLAUDE_CODE_PATH."
    )


def _strip_v1(base_url: str) -> str:
    clean = (base_url or "").rstrip("/")
    return clean[:-3] if clean.endswith("/v1") else clean


def resolve_claude_brain(active: ActiveLlm) -> ClaudeBrain:
    """Куда Claude Code шлёт запросы модели — по выбранному в CoreX провайдеру."""
    model = (active.model_name or "").strip()
    if not model:
        raise ValueError("Не выбрана модель для Claude Code")

    if active.mode == "local" or active.api_type == "ollama":
        base = str(getattr(active.client, "root_url", "") or "").rstrip("/")
        if not base:
            from core.ollama_lifecycle import resolve_ollama_base_url

            base = resolve_ollama_base_url().rstrip("/")
        return ClaudeBrain(base_url=base, api_key="ollama", model=model, bare=True)

    api_key = str(getattr(active.client, "api_key", "") or "").strip()
    base_url = str(getattr(active.client, "base_url", "") or "").rstrip("/")
    if not api_key:
        raise ValueError("Для онлайн-модели нужен API-ключ")
    if active.api_type == "gemini":
        raise ValueError(OMNIROUTE_HINT)

    host = (urlparse(base_url).hostname or "").lower()
    if host.endswith("openrouter.ai"):
        # OpenRouter документирует для Claude Code только Bearer (ANTHROPIC_AUTH_TOKEN).
        return ClaudeBrain(base_url="https://openrouter.ai/api", api_key=api_key, model=model, bare=False)
    if host.endswith("anthropic.com"):
        return ClaudeBrain(base_url="https://api.anthropic.com", api_key=api_key, model=model, bare=True)
    if is_omniroute_url(base_url, active.provider_name):
        return ClaudeBrain(base_url=_strip_v1(base_url), api_key=api_key, model=model, bare=True)
    raise ValueError(OMNIROUTE_HINT)


def build_claude_env(brain: ClaudeBrain) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("ANTHROPIC_") and key != "CLAUDE_CODE_SUBAGENT_MODEL"
    }
    env["ANTHROPIC_BASE_URL"] = brain.base_url
    if brain.bare:
        env["ANTHROPIC_API_KEY"] = brain.api_key
    else:
        env["ANTHROPIC_AUTH_TOKEN"] = brain.api_key
        env["ANTHROPIC_API_KEY"] = ""
    # Фоновые задачи Claude Code (заголовки, сабагенты) иначе просят claude-haiku/sonnet — у Ollama их нет.
    for key in (
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
    ):
        env[key] = brain.model
    env.update(
        {
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
            "NO_COLOR": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def build_claude_system_prompt(
    *,
    persona_label: str = "",
    persona_body: str = "",
    knowledge_text: str = "",
    language_hint: str = "",
) -> str:
    parts: list[str] = [
        "Ты работаешь внутри IDE CoreX как агент правок кода.",
        "Меняй файлы только внутри текущей папки проекта.",
        "Не делай git commit и git push — коммиты только по явной просьбе пользователя.",
        "Финальный ответ: 2–4 предложения по-русски, что сделано. Без полного кода, diff и markdown-фенсов.",
    ]
    if language_hint:
        parts.append(f"Язык/стек: {language_hint}")
    if persona_label or persona_body:
        label = persona_label or "persona"
        parts.append(f"=== PERSONA: {label} ===\n{(persona_body or '').strip()}\n=== END PERSONA ===")
    if knowledge_text.strip():
        parts.append(
            "=== COREX KNOWLEDGE / SKILLS ===\n"
            f"{knowledge_text.strip()}\n"
            "=== END KNOWLEDGE ==="
        )
    return "\n\n".join(parts)


def build_claude_task_message(
    *,
    task: str,
    plan_text: str = "",
    write_dest: str = "",
    attached_files: list[str] | None = None,
) -> str:
    parts: list[str] = []
    if plan_text.strip() and plan_text.strip() != (task or "").strip():
        parts.append(plan_text.strip())
    if write_dest:
        parts.append(f"Целевой путь/подсказка: {write_dest}")
    files = [item for item in (attached_files or []) if item]
    if files:
        parts.append("Упомянутые файлы: " + ", ".join(files))
    parts.append("=== TASK ===\n" + (task or "").strip())
    return "\n\n".join(parts)


def build_claude_code_launch(
    *,
    project_root: Path,
    active: ActiveLlm,
    task_message: str,
    system_prompt: str = "",
    read_only: bool = False,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> ClaudeCodeLaunch:
    cmd = find_claude_command()
    if not cmd:
        raise RuntimeError(claude_code_missing_message())
    brain = resolve_claude_brain(active)
    tools = ",".join(CLAUDE_READ_TOOLS if read_only else CLAUDE_EDIT_TOOLS)

    argv = [
        *cmd,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        *(["--bare"] if brain.bare else ["--setting-sources", "project,local"]),
        "--strict-mcp-config",
        "--tools",
        tools,
        "--allowedTools",
        tools,
        "--permission-mode",
        "acceptEdits",
        "--permission-prompts",
        "none",
        "--no-session-persistence",
        "--model",
        brain.model,
        "--max-turns",
        str(max(1, int(max_turns))),
    ]
    temp_files: list[Path] = []
    if system_prompt.strip():
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".md", prefix="corex_claude_", delete=False
        )
        with handle:
            handle.write(system_prompt)
        temp_files.append(Path(handle.name))
        argv.extend(["--append-system-prompt-file", handle.name])

    return ClaudeCodeLaunch(
        argv=argv,
        env=build_claude_env(brain),
        cwd=project_root.resolve(),
        model=brain.model,
        stdin_text=task_message,
        temp_files=temp_files,
    )


def _relative_path(raw: str, cwd: Path | None) -> str:
    clean = (raw or "").strip().replace("\\", "/")
    # Claude Code на Windows иногда отдаёт "/C:/..." — убираем ведущий слэш перед буквой диска.
    if len(clean) > 2 and clean[0] == "/" and clean[2] == ":":
        clean = clean[1:]
    if cwd is not None:
        try:
            return Path(clean).resolve().relative_to(cwd.resolve()).as_posix()
        except (ValueError, OSError):
            pass
    return clean.lstrip("./")


def _looks_like_text_tool_call(text: str) -> bool:
    blob = (text or "").strip()
    return blob.startswith("{") and '"name"' in blob and ('"arguments"' in blob or '"parameters"' in blob)


class ClaudeStreamParser:
    """Разбирает `--output-format stream-json`: текст в чат, правки файлов, команды, итог."""

    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = cwd
        self.reply_parts: list[str] = []
        self.files: list[str] = []
        self.commands: list[str] = []
        self.result: dict[str, Any] | None = None
        self.text_tool_calls = 0

    def feed(self, raw: str) -> list[ClaudeCodeEvent]:
        line = (raw or "").strip()
        if not line.startswith("{"):
            return [ClaudeCodeEvent("noise", text=line[:200])] if line else []
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return [ClaudeCodeEvent("noise", text=line[:200])]
        if not isinstance(data, dict):
            return []

        kind = data.get("type")
        if kind == "assistant":
            return self._assistant_events(data.get("message") or {})
        if kind == "result" or ("duration_api_ms" in data and "usage" in data):
            self.result = data
            return [ClaudeCodeEvent("result", text=str(data.get("result") or ""), payload=data)]
        return [ClaudeCodeEvent("noise", text=str(kind or "")[:80])]

    def _assistant_events(self, message: dict[str, Any]) -> list[ClaudeCodeEvent]:
        events: list[ClaudeCodeEvent] = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = str(block.get("text") or "").strip()
                if not text:
                    continue
                if _looks_like_text_tool_call(text):
                    self.text_tool_calls += 1
                    events.append(ClaudeCodeEvent("noise", text=text[:200]))
                    continue
                self.reply_parts.append(text)
                events.append(ClaudeCodeEvent("reply", text=text))
            elif block_type == "tool_use":
                name = str(block.get("name") or "")
                tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                path_key = _FILE_TOOL_KEYS.get(name)
                if path_key and tool_input.get(path_key):
                    path = _relative_path(str(tool_input[path_key]), self.cwd)
                    if path and path not in self.files:
                        self.files.append(path)
                    events.append(ClaudeCodeEvent("file", path=path, text=name))
                elif name == "Bash" and tool_input.get("command"):
                    command = str(tool_input["command"]).strip()
                    self.commands.append(command)
                    events.append(ClaudeCodeEvent("command", text=command))
                else:
                    events.append(ClaudeCodeEvent("noise", text=name))
        return events

    @property
    def reply_text(self) -> str:
        final = str((self.result or {}).get("result") or "").strip()
        if final and not _looks_like_text_tool_call(final):
            return final
        return "\n\n".join(self.reply_parts).strip()

    @property
    def usage(self) -> TokenUsage | None:
        raw = (self.result or {}).get("usage")
        if not isinstance(raw, dict):
            return None
        prompt = (
            int(raw.get("input_tokens") or 0)
            + int(raw.get("cache_read_input_tokens") or 0)
            + int(raw.get("cache_creation_input_tokens") or 0)
        )
        completion = int(raw.get("output_tokens") or 0)
        if prompt + completion <= 0:
            return None
        return TokenUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion)


def public_claude_reply(text: str, edited: list[str] | None = None) -> str:
    blob = (text or "").strip()
    files = [item for item in (edited or []) if item]
    if blob and "```" not in blob:
        return blob if len(blob) <= _REPLY_MAX_CHARS else blob[: _REPLY_MAX_CHARS - 1] + "…"
    if files:
        return f"Готово: {', '.join(files[:8])}."
    return "Шаг завершён."


def _result_error(result: dict[str, Any] | None) -> str | None:
    if not result:
        return None
    if not result.get("is_error") and result.get("subtype") in (None, "success"):
        return None
    subtype = str(result.get("subtype") or "")
    if subtype == "error_max_turns":
        return "Claude Code упёрся в лимит шагов. Разбейте задачу на части."
    detail = str(result.get("result") or "").strip()
    return detail or f"Claude Code завершился с ошибкой ({subtype or 'unknown'})"


_SNAPSHOT_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".next", ".corex",
}
_SNAPSHOT_MAX_FILES = 5000


def snapshot_project_files(root: Path) -> dict[str, int] | None:
    """mtime всех файлов проекта; None — проект слишком большой для сравнения."""
    found: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _SNAPSHOT_SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                found[path.relative_to(root).as_posix()] = path.stat().st_mtime_ns
            except (OSError, ValueError):
                continue
            if len(found) > _SNAPSHOT_MAX_FILES:
                return None
    return found


def changed_project_files(before: dict[str, int] | None, after: dict[str, int] | None) -> list[str]:
    if before is None or after is None:
        return []
    return sorted(rel for rel, mtime in after.items() if before.get(rel) != mtime)


async def run_claude_code(
    launch: ClaudeCodeLaunch,
    *,
    on_event: Any = None,
    timeout_sec: float = 1800.0,
    process_holder: dict[str, Any] | None = None,
) -> ClaudeCodeRunResult:
    parser = ClaudeStreamParser(cwd=launch.cwd)
    # Модель может менять файлы через Bash (echo > file), а не через Edit/Write.
    before = snapshot_project_files(launch.cwd)

    async def _on_line(line: str) -> None:
        for event in parser.feed(line):
            if on_event is None or event.kind == "noise":
                continue
            maybe = on_event(event)
            if hasattr(maybe, "__await__"):
                await maybe

    try:
        outcome = await run_streaming_cli(
            launch.argv,
            env=launch.env,
            cwd=launch.cwd,
            on_line=_on_line,
            timeout_sec=timeout_sec,
            process_holder=process_holder,
            stdin_text=launch.stdin_text,
        )
    finally:
        for path in launch.temp_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    edited = list(parser.files)
    for rel in changed_project_files(before, snapshot_project_files(launch.cwd)):
        if rel not in edited:
            edited.append(rel)

    base = {
        "model": launch.model,
        "reply": parser.reply_text,
        "edited_files": edited,
        "commands": list(parser.commands),
        "usage": parser.usage,
        "text_tool_calls": parser.text_tool_calls,
    }
    if outcome.timed_out:
        return ClaudeCodeRunResult(ok=False, exit_code=-1, error="Claude Code превысил лимит времени", **base)
    if outcome.spawn_error is not None:
        tag, exc = outcome.spawn_error
        error = (
            claude_code_missing_message()
            if tag == "missing"
            else f"Не удалось запустить Claude Code: {type(exc).__name__}: {exc}"
        )
        return ClaudeCodeRunResult(ok=False, exit_code=outcome.exit_code, error=error, **base)

    error = _result_error(parser.result)
    if outcome.exit_code != 0 and error is None:
        tail = "\n".join(line for line in outcome.lines[-15:] if not line.startswith("{"))
        error = tail.strip() or f"Claude Code exit {outcome.exit_code}"
    if parser.result is None and error is None:
        error = "Claude Code не вернул итог (нет события result)"
    return ClaudeCodeRunResult(ok=error is None, exit_code=outcome.exit_code, error=error, **base)


async def ollama_model_supports_tools(base_url: str, model: str) -> bool | None:
    """None — не удалось узнать (старая Ollama, сеть); тогда не мешаем запуску."""
    import aiohttp

    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{base_url.rstrip('/')}/api/show", json={"model": model}) as response:
                if response.status != 200:
                    return None
                data = await response.json()
    except Exception:
        return None
    capabilities = data.get("capabilities") if isinstance(data, dict) else None
    if not isinstance(capabilities, list):
        return None
    return "tools" in capabilities
