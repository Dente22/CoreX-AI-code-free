import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from core.core_x_library import resolve_persona_prompt
from core.persona_service import ensure_personas_dir
from core.pipeline_service import ensure_pipelines_dir
from core.device_profile import detect_device_profile
from core.knowledge_service import build_knowledge_bundle
from core.local_pipeline_profile import (
    COMPACT_AGENT_SYSTEM_PROMPT,
    build_local_pipeline_profile,
    compact_persona_for_local,
    local_team_suggestion_ru,
)
from core.resource_limits import ResourceBudget
from core.file_mentions import expand_file_mentions
from core.project_paths import collect_analysis_entries, is_corex_internal_path
from core.write_target import (
    infer_task_write_path,
    mention_intent,
    mention_prompt_hint,
    remap_write_path,
    resolve_gui_fallback_path,
)
from core.task_routing import (
    history_suggests_coding,
    infer_task_route,
    is_conversational_message,
    looks_like_build_request,
    looks_like_fix_request,
    looks_like_gui_window_request,
    looks_like_question,
    normalize_task_text,
    resolve_local_model_for_route,
    resolve_online_model_for_route,
    response_length_instruction,
    should_include_knowledge_in_prompt,
    should_run_planning_phase,
    local_pair_available,
    looks_like_pinned_larger_local,
)
from core.conversation_memory import (
    format_history_for_prompt,
    load_history,
    merge_history,
    save_history,
    trim_history_for_llm,
)
from core.agent_json import (
    compact_tool_result_for_prompt,
    json_retry_hint,
    normalize_agent_action,
    parse_agent_json,
    _strip_fences,
)
from core.file_outline import (
    edit_guidance_after_patch,
    edit_guidance_after_write,
    idle_stop_chat,
    looks_like_truncated_source,
)
from core.staged_write import (
    is_protocol_leak,
    sanitize_code_chunk,
)
from core.code_verify import (
    compact_runtime_detail,
    looks_like_interactive_python,
    smoke_run_python,
    verify_python_file,
    verify_python_syntax,
)
from core.error_remediation import remediate_python_error
from core.syntax_repair import repair_file_on_disk
from core.ollama_client import OllamaClient
from core.trace_events import build_trace_payload, new_task_id
from core.trace_store import (
    append_error,
    append_event,
    make_detail,
    trim_detail_for_ws,
)
from core.online_api_client import OnlineApiClient
from core.online_api_errors import is_online_api_failure
from core.llm_runtime import (
    ActiveLlm,
    ensure_llm_ready,
    llm_readiness_error,
    llm_thinking_label,
    resolve_active_llm,
    resolve_ready_llm,
)
from core.token_usage_service import check_budget, get_usage_summary, record_usage, set_limits
from core.mcp_manager import MCPManager
from core.terminal_service import run_command, run_file
from core.ai_provider_service import AiProviderService, default_provider_service
from core.ai_runtime_service import AiRuntimeService, default_runtime_service

MEMORY_DIR = "chat"
MEMORY_FILENAME = "project_memory.md"
MEMORY_REL_PATH = os.path.join(MEMORY_DIR, MEMORY_FILENAME)
MAX_JSON_PARSE_RETRIES = 6
MAX_BLOCKED_DONE_RETRIES = 3
IDLE_NO_CODE_TURNS = 8
_ENTRY_SCRIPTS = ("main.py", "app.py", "run.py", "game.py", "start.py")


def filesystem_tool_succeeded(result: object) -> bool:
    """Успех записи/патча. Текст «File written to …» — не ошибка."""
    return isinstance(result, dict) and str(result.get("status") or "") == "Success"


def _find_balanced_json(text: str, opener: str, closer: str) -> list[str]:
    """Извлечь сбалансированные JSON-фрагменты (поддержка вложенных объектов)."""
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


_CONVERSATIONAL_PATTERNS = re.compile(
    r"^("
    r"привет|здравствуй|здравствуйте|добрый\s+(день|утро|вечер)|"
    r"как\s+дела|как\s+ты|что\s+нового|спасибо|пока|до\s+свидания|"
    r"hello|hi|hey|how\s+are\s+you|thanks|thank\s+you|bye|good\s+(morning|evening|afternoon)"
    r")"
    r"[\s!?.,]*$",
    re.IGNORECASE,
)

_WRITE_TASK_PATTERNS = re.compile(
    r"создай|создать|напиши|написать|добавь|добавить|измени|изменить|перепиши|"
    r"сделай|сделать|реализуй|реализовать|исправь|исправить|обнови|обновить|"
    r"сверстай|свёрстай|разработай|разработать|запрограммируй|запрограммировать|"
    r"собери|собрать|воплоти|воплотить|хочу|нужен|нужна|нужно|давай|можешь|"
    r"create|write|add|make|build|generate|implement|fix|update|refactor|develop|"
    r"program|code|scaffold|setup",
    re.IGNORECASE,
)

_CREATE_INTENT_PATTERNS = re.compile(
    r"змейк|snake|тетрис|tetris|игр[ауы]|game|калькулятор|calculator|таймер|timer|"
    r"todo|список\s+дел|бот|bot|парсер|parser|скрипт|script|программ|приложени|"
    r"проект|сайт|site|страниц|landing|веб|web|api|backend|frontend|консольн|"
    r"gui|интерфейс|чат|chat|блог|blog|магазин|shop|календар|calendar|"
    r"pygame|flask|django|fastapi|react|vue|html|css|javascript|typescript|python|"
    r"hello\s*world|привет\s*мир|виселица|hangman|шахмат|chess|пинг|pong|"
    r"викторин|quiz|конвертер|converter|генератор|generator|анализатор|analyzer|"
    r"простой|простая|простое|simple|минимальн|basic|легкий|лёгкий|easy",
    re.IGNORECASE,
)

_QUESTION_ONLY_PATTERNS = re.compile(
    r"^(?:"
    r"что\s+такое|что\s+это|кто\s+такой|как\s+работает|как\s+устроен|"
    r"объясни|расскажи|опиши|в\s+чём\s+разница|чем\s+отличается|"
    r"what\s+is|what\s+are|how\s+does|how\s+do|explain|describe|why\s+is"
    r")",
    re.IGNORECASE,
)

_FIX_TASK_PATTERNS = re.compile(
    r"исправь|исправить|почини|починить|fix|bug|баг|ошибк|error|traceback|"
    r"nameerror|syntaxerror|не\s+работает|не\s+запуска|код\s+выхода|"
    r"доста[ёе]т|отсутствует|missing|undefined|not\s+defined|crash|падает",
    re.IGNORECASE,
)

_FAUX_DONE_PATTERNS = re.compile(
    r"нужно\s+(добавить|исправить|изменить)|следует\s+(добавить|исправить)|"
    r"рекомендую\s+(добавить|исправить)|should\s+(add|fix|change)|"
    r"you\s+should|must\s+add|missing\s+\w+|not\s+defined|добавьте\s+|"
    r"исправьте\s+|отсутствует\s+\w+",
    re.IGNORECASE,
)

_CODING_CONTEXT_PATTERNS = re.compile(
    r"код|файл|функци|класс|модуль|скрипт|api|backend|frontend|база|тест|"
    r"игр|приложени|программ|проект|сайт|pygame|flask|react|html|python|"
    r"import|def |class |\.py|\.ts|\.js|\.tsx|main\.py|requirements",
    re.IGNORECASE,
)

PLANNING_SYSTEM_PROMPT = (
    "You are CoreX planning module. Analyze the user request using conversation history and project context.\n"
    "Think step by step, then output ONLY one JSON object (no markdown):\n"
    "{\n"
    '  "intent": "code_task|question|chat",\n'
    '  "understanding": "краткое понимание запроса на русском с учётом контекста",\n'
    '  "plan": ["шаг 1: ...", "шаг 2: ..."],\n'
    '  "files_to_inspect": ["relative/path"],\n'
    '  "files_to_create_or_update": ["relative/path"]\n'
    "}\n\n"
    "Rules:\n"
    "- intent=code_task: user wants ANY deliverable in project files — create, change, fix, extend.\n"
    "- IMPLICIT code_task (no words 'create/make'): 'змейка', 'калькулятор', 'простой таймер', "
    "'игра на pygame', 'сайт-визитка', 'hello world' → still code_task.\n"
    "- When user describes WHAT they want built (game, app, script, page) → code_task, NOT chat.\n"
    "- If unsure between question and code_task but user expects a working file → code_task.\n"
    "- Bug fixes / errors (NameError, Traceback): intent=code_task; put broken files in files_to_inspect "
    "and files_to_create_or_update; plan must include view_file then write_file with full file content.\n"
    "- intent=question: ONLY pure theory ('что такое Flask?') with NO request to build anything now.\n"
    "- intent=chat: ONLY greetings, thanks, small talk ('привет', 'спасибо').\n"
    "- Use history: short follow-ups like 'добавь тесты', 'сделай это на Flask' inherit prior task.\n"
    "- plan: concrete ordered steps the executor will follow.\n"
    "- files_to_inspect: existing files to read first (view_file).\n"
    "- files_to_create_or_update: files that will be written (relative paths in the ACTIVE project root, no extra project subfolder).\n"
    "- When user asks to create a project, plan files in the open folder root (main.py, README.md), not MyProject/main.py.\n"
    "- Ignore chat/ folder for analysis (CoreX internal). Only chat/project_memory.md may be updated after writes.\n"
    "- Standards from core_x_knowledge (rules + context) are injected into the executor — align plan with them.\n"
)


class CoreXOrchestrator:
    def __init__(
        self,
        ollama_client: OllamaClient,
        mcp_manager: MCPManager,
        gui,
        file_service=None,
        ai_provider_service: AiProviderService | None = None,
        ai_runtime_service: AiRuntimeService | None = None,
        online_client: OnlineApiClient | None = None,
    ):
        self.ollama = ollama_client
        self.online = online_client or OnlineApiClient()
        self.mcp = mcp_manager
        self.file_service = file_service
        self.gui = gui
        self.ai_provider_service = ai_provider_service or default_provider_service()
        self.ai_runtime_service = ai_runtime_service or default_runtime_service()
        self.ai_runtime_service.apply_active_client(self.ollama, self.online)
        self.websocket_server = None
        self.current_task = None
        self.project_root: Optional[Path] = None
        self._budget: ResourceBudget | None = None
        self._trace_task_id: str | None = None
        self._last_trace_event_id: str | None = None
        self._active_reply_model: str | None = None
        self._web_search_block = ""
        self._lesson_recorded = False
        self._pending_lesson: dict[str, Any] = {}
        self._coding_engine = "aider"
        self._aider_proc: dict[str, Any] = {}

        self._base_system_prompt = (
            "You are CoreX, an autonomous AI Engineer inside a strict execution pipeline.\n"
            "Pipeline: receive task -> analyze -> physically write files in the ACTIVE project folder "
            "-> receive tool Success proof -> only then report done to the user.\n\n"
            "=== UNDERSTAND ANY REQUEST ===\n"
            "Users describe tasks in natural language. They may NOT say 'create' or 'make'.\n"
            "Examples that REQUIRE write_file: 'змейка', 'калькулятор', 'простой сайт', "
            "'игра на pygame', 'таймер', 'парсер цен', 'бот для telegram'.\n"
            "Infer the deliverable (main.py, index.html, etc.) and build it in the open project folder.\n"
            "Short messages naming an app/game/tool are code tasks, not small talk.\n\n"
            "Available tools:\n"
            "filesystem:\n"
            "- list_directory (arguments: {path: '.'})\n"
            "- view_file (arguments: {path: 'relative/path'}) — returns numbered lines (1| code)\n"
            "- patch_file — PREFERRED for edits. ONE line per call. SIMPLE JSON:\n"
            '  {"status":"act","server":"filesystem","tool":"patch_file",'
            '"arguments":{"path":"main.py","op":"replace","line":60,"content":"    pygame.quit()"}}\n'
            "  ops: replace | insert_after | insert_before | delete\n"
            "  Escape quotes in content as \\\". Keep content short, one line if possible.\n"
            "- write_file (arguments: {path}) — NEW complete file. JSON header optional; code in a ``` fence.\n"
            "- append_file (arguments: {path}) — append only when extending an existing file.\n"
            "terminal (run code to verify it works):\n"
            "- run_file (arguments: {path: 'main.py'}) — запуск файла проекта\n"
            "- run_command (arguments: {command: 'python -m py_compile main.py', cwd: '.'})\n"
            "web (optional, only if settings allow; do not search before writing a new file):\n"
            '- search_web (arguments: {query: "short topic"})\n\n'
            "=== EXECUTION PIPELINE (CRITICAL) ===\n"
            "0. PLAN: A structured plan is injected in the user prompt — follow it step by step.\n"
            "1. ANALYZE: Read conversation history, project memory, and inspect files from the plan.\n"
            "2. GENERATE: If the plan requires file changes, your FIRST response MUST be "
            '{"status": "act", "server": "filesystem", "tool": "write_file", ...}.\n'
            "   You CANNOT return done until files are physically created and you received Success from the tool.\n"
            "3. PROOF: Wait for tool result with status Success before the next step.\n"
            "4. REPORT: Only after confirmed write_file Success, you may return "
            '{"status": "done", "message": "Файлы успешно созданы"} in Russian.\n\n'
            "=== FILE CREATION RULES (CRITICAL) ===\n"
            "If the user asks to create a file or project, your first answer MUST be status act calling write_file. "
            "You cannot output done until files are created.\n"
            "The ACTIVE project folder is already open in CoreX — write ALL new files directly in its ROOT.\n"
            "Do NOT create a new subfolder with the project name unless the user explicitly asks for a subfolder.\n"
            "Do NOT put an entire multi-file project into one dump. "
            "Small app = one complete file per turn (usually main.py). Next turn may add requirements.txt.\n"
            "A ```python fence is a valid first action — CoreX saves it. JSON write_file is optional.\n"
            "Do not write a two-line stub. Do not inspect an empty folder first. "
            "CoreX fixes indent and truncated writes, not game logic. There is no baked-in template.\n"
            "Never simulate work. Never claim files exist without a successful write_file tool result.\n\n"
            "=== EDIT EXISTING FILES (CRITICAL) ===\n"
            "Workflow: view_file(path) → analyze numbered lines → patch_file ONE line change per turn.\n"
            "Use patch_file ops:\n"
            '  replace: {"op":"replace","line":12,"content":"new line text"}\n'
            '  insert_after: {"op":"insert_after","line":5,"content":"new line"}\n'
            '  delete: {"op":"delete","line":8}\n'
            "Forbidden: write_file on existing code files — use patch_file instead.\n"
            "write_file is only for brand-new files (main.py when missing).\n"
            "Forbidden: describing a fix in done without successful patch_file/write_file.\n\n"
            "=== CODE VERIFICATION (CRITICAL) ===\n"
            "After every write_file on .py, CoreX auto-checks syntax. "
            "Before done CoreX itself runs the program. "
            "Games/GUI (tkinter, pygame, mainloop) are launched with a short timeout: "
            "no traceback = OK; crash = not done, fix the error.\n"
            "If auto-verify fails with SyntaxError/IndentationError, fix the file and patch_file again.\n"
            "If the error is No module named / ModuleNotFoundError: do NOT patch or rewrite the source. "
            "That is a missing pip package, not a bug. Keep the game/code. Add the package to requirements.txt.\n"
            "NameError (key, screen, clock) in a game: add input() or pygame — do not patch the same if-line forever.\n"
            "Never replace working code with a stub or an empty pygame window.\n"
            "If the user asks for a window (окно, GUI, не в консоли): keep the SAME game "
            "(mines, grid, clicks, rules). Prefer tkinter (stdlib, no pip). "
            "pygame is OK only if the file still contains the game, not just init + black screen. "
            "On Python 3.14 CoreX installs pygame-ce (import pygame still works).\n"
            "Never write_file/patch_file to path '.' or the project folder — always a file name (main.py).\n"
            "done только после успешного запуска (сам CoreX гоняет файл). "
            "Если упало — чини причину, не пиши done.\n"
            "QA/reviewer MUST run the project and fix errors found — not only read code.\n\n"
            "=== EXTERNAL MEMORY / SCRATCHPAD ===\n"
            "Memory file: chat/project_memory.md inside the active project folder.\n"
            "If you created or modified project files, BEFORE done you MUST write_file to update "
            "chat/project_memory.md with Markdown: architecture, created files, next steps.\n\n"
            "=== CONVERSATIONAL EXCEPTION ===\n"
            "If the user only chats ('привет', 'как дела'), do NOT call tools. Reply immediately:\n"
            '{"status": "done", "message": "Привет! Я CoreX — чем помочь с проектом?"}\n'
            "Match response length to the user: greetings 1–2 sentences; questions — full answer; "
            "if they ask for N sentences — use exactly N.\n\n"
            "=== TOOL ARGUMENTS (CRITICAL) ===\n"
            "path: clean relative path INSIDE the active project (e.g. src/index.js, main.py, chat/project_memory.md). "
            "Never use absolute paths or Russian text in path.\n"
            "content: optional. Prefer a ``` fence AFTER the JSON object so quotes need no escaping.\n"
            "Do not put binary, base64, or 0/1 dumps in content.\n\n"
            "=== EXAMPLES ===\n"
            "Chat: Input 'привет' -> {\"status\": \"done\", \"message\": \"Привет!\"}\n"
            "Create file: JSON header then fenced code, or ONLY a ```python fence.\n"
            '{"status": "act", "server": "filesystem", "tool": "write_file", '
            '"arguments": {"path": "main.py"}}\n'
            "```python\nprint(\"Hello\")\n```\n"
            "After Success look at the line map. Edit with patch_file line=N. "
            "Delete a duplicate def with op=delete line=N. Do not append a second gameLoop.\n"
            "After Success -> {\"status\": \"done\", \"message\": \"Файлы успешно созданы\"}\n\n"
            "=== OUTPUT FORMAT ===\n"
            "One JSON object per turn. For write_file/append_file you MAY add a ``` code fence after the JSON.\n"
            "Action: {\"status\": \"act\", \"server\": \"filesystem|terminal\", \"tool\": \"...\", \"arguments\": {}}\n"
            "Finish: {\"status\": \"done\", \"message\": \"...\"}"
        )
        self.system_prompt = self._base_system_prompt

    def _build_system_prompt(
        self,
        project_root: Path,
        persona_id: str | None,
        *,
        user_task: str = "",
        step_role: str | None = None,
        include_knowledge: bool = True,
        compact: bool = False,
        knowledge_char_cap: int | None = None,
    ) -> str:
        knowledge_block = ""
        if include_knowledge:
            knowledge = build_knowledge_bundle(
                project_root,
                user_task,
                persona_id,
                step_role=step_role,
                char_cap=knowledge_char_cap,
            )
            if knowledge.text:
                knowledge_block = (
                    f"\n=== COREX KNOWLEDGE (core_x_knowledge) ===\n"
                    f"{knowledge.summary_ru()}\n"
                    f"Follow these standards when writing or reviewing code.\n"
                    f"{knowledge.text}\n"
                    f"=== END KNOWLEDGE ===\n"
                )

        persona_name, persona_body = resolve_persona_prompt(
            project_root,
            persona_id,
            for_orchestrator=True,
        )
        json_reminder = (
            "CRITICAL: For a NEW program prefer a complete ```python fence. JSON is optional. "
            "One complete file per turn. Not a stub. "
            'Patch: {"status":"act","server":"filesystem","tool":"patch_file",'
            '"arguments":{"path":"main.py","op":"replace","line":3,"content":"    return result"}} '
            'View: {"status":"act","server":"filesystem","tool":"view_file","arguments":{"path":"main.py"}} '
            "Never replace working code with a stub. Missing pip packages are not syntax errors."
        )
        if not persona_body:
            base = COMPACT_AGENT_SYSTEM_PROMPT if compact else self._base_system_prompt
            return f"{base}{knowledge_block}"

        label = persona_name or persona_id or "Persona"
        base = COMPACT_AGENT_SYSTEM_PROMPT if compact else self._base_system_prompt
        body = persona_body
        if compact:
            body = compact_persona_for_local(
                persona_body,
                persona_id,
                coding_language=getattr(self, "_coding_language", "auto"),
                user_task=user_task,
            )
        lang_prompt = ""
        try:
            from core.coding_language import language_prompt_ru

            lang_prompt = language_prompt_ru(getattr(self, "_coding_language", "auto"))
        except Exception:
            lang_prompt = ""
        lang_block = f"\n{lang_prompt}" if lang_prompt else ""
        return (
            f"{base}{knowledge_block}{lang_block}\n"
            f"=== ACTIVE PERSONA: {label} ===\n"
            f"{body}\n"
            f"=== END PERSONA ===\n"
            f"{json_reminder}\n"
            "Follow the persona and knowledge standards while obeying all JSON and tool rules above."
        )

    def _resolve_llm(self) -> ActiveLlm:
        return resolve_active_llm(self.ai_runtime_service, self.ollama, self.online)

    def _installed_local_model_names(self) -> list[str]:
        from core.ollama_lifecycle import detect_installed_models_from_disk

        return [str(item.get("name") or "") for item in detect_installed_models_from_disk()]

    def _selected_local_model_name(self) -> str:
        try:
            return str(self.ai_runtime_service.local_service.get_selected_preset().model_name or "")
        except Exception:
            return str(getattr(self.ollama, "model_name", "") or "")

    def _local_model_override_for_task(self, user_task: str, history: list[dict]) -> str | None:
        if self.ai_runtime_service.get_mode() == "online":
            return None
        selected = self._selected_local_model_name()
        routed = resolve_local_model_for_route(
            infer_task_route(user_task, history),
            selected,
            self._installed_local_model_names(),
        )
        return routed or None

    async def _resolve_ready_llm(self, local_model_override: str | None = None) -> ActiveLlm:
        return await resolve_ready_llm(
            self.ai_runtime_service,
            self.ollama,
            self.online,
            local_model_override=local_model_override,
        )

    def _active_llm(self):
        return self._resolve_llm().client

    def register_websocket_server(self, websocket_server):
        self.websocket_server = websocket_server

    def set_ai_mode(self, mode: str) -> dict:
        result = self.ai_runtime_service.set_mode(mode)
        if result.get("success"):
            applied = self.ai_runtime_service.apply_active_client(self.ollama, self.online)
            if applied.get("warning"):
                result = {**result, "warning": "Онлайн-провайдер не выбран"}
            if self.gui and hasattr(self.gui, "print_log"):
                provider = applied.get("provider") or {}
                preset = applied.get("preset") or {}
                label = preset.get("name") or provider.get("name") or mode
                self.gui.print_log("System", f"AI режим: {mode} · {label}")
        return result

    def set_ai_provider(self, provider_id: str) -> dict:
        result = self.ai_runtime_service.select_local(provider_id)
        if result.get("success"):
            preset = self.ai_provider_service.apply_to_client(self.ollama)
            if self.gui and hasattr(self.gui, "print_log"):
                self.gui.print_log("System", f"AI локально: {preset.name} ({preset.model_name})")
            self._schedule_local_model_switch(preset.model_name)
        return result

    def _schedule_local_model_switch(self, model_name: str) -> None:
        async def _switch() -> None:
            from core.ollama_lifecycle import ensure_ollama_serve_running
            from core.ollama_model_session import activate_ollama_model

            if not await ensure_ollama_serve_running():
                return
            result = await activate_ollama_model(model_name, self.ollama.root_url, preload=True)
            if self.gui and hasattr(self.gui, "print_log"):
                if result.get("success"):
                    if result.get("switched"):
                        self.gui.print_log("System", f"Ollama: переключено на {model_name}")
                    elif not result.get("already_loaded"):
                        self.gui.print_log("System", f"Ollama: загружена {model_name}")
                elif result.get("error"):
                    self.gui.print_log("System", f"Ollama: {result['error']}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_switch())
        except RuntimeError:
            pass

    def set_online_provider(self, provider_id: str) -> dict:
        result = self.ai_runtime_service.select_online(provider_id)
        if result.get("success"):
            provider = self.ai_runtime_service.online_service.apply_to_client(self.online)
            if self.gui and hasattr(self.gui, "print_log") and provider:
                self.gui.print_log("System", f"AI онлайн: {provider['name']} ({provider['model_name']})")
        return result

    def create_online_provider(self, payload: dict) -> dict:
        return self.ai_runtime_service.online_service.create_provider(
            name=str(payload.get("name") or ""),
            base_url=str(payload.get("base_url") or ""),
            api_key=str(payload.get("api_key") or ""),
            model_name=str(payload.get("model_name") or ""),
            api_type=str(payload.get("api_type") or "openai"),
        )

    def delete_online_provider(self, provider_id: str) -> dict:
        return self.ai_runtime_service.online_service.delete_provider(provider_id)

    def get_ai_runtime_snapshot(self) -> dict:
        return self.ai_runtime_service.get_snapshot()

    def list_ai_providers(self) -> dict:
        return self.ai_provider_service.list_with_selection()

    async def get_ollama_models_snapshot(self) -> dict:
        from core.ollama_model_service import get_models_snapshot

        return await get_models_snapshot()

    async def pull_ollama_model(self, provider_id: str | None = None, model_name: str | None = None) -> dict:
        from core.ollama_model_service import pull_model, pull_provider_model

        if provider_id:
            return await pull_provider_model(provider_id)
        if model_name:
            return await pull_model(model_name)
        return {"success": False, "error": "Укажите provider_id или model_name"}

    async def start_ollama_pull(self, provider_id: str | None = None, model_name: str | None = None) -> dict:
        from core.ollama_model_service import start_pull_model, start_pull_provider_model

        if provider_id:
            return await start_pull_provider_model(provider_id)
        if model_name:
            return await start_pull_model(model_name)
        return {"success": False, "error": "Укажите provider_id или model_name"}

    def get_ollama_pull_progress(self, job_id: str) -> dict:
        from core.ollama_model_service import get_pull_job_progress

        return get_pull_job_progress(job_id)

    async def delete_ollama_model(self, provider_id: str | None = None, model_name: str | None = None) -> dict:
        from core.ollama_model_service import delete_model, delete_provider_model

        if provider_id:
            return await delete_provider_model(provider_id)
        if model_name:
            return await delete_model(model_name)
        return {"success": False, "error": "Укажите provider_id или model_name"}

    def _app_root(self) -> Path:
        return self.ai_runtime_service._config_path.parent.parent

    def get_token_usage(self) -> dict:
        return get_usage_summary(self._app_root())

    def update_token_limits(self, payload: dict) -> dict:
        return set_limits(self._app_root(), payload)

    def update_workload_limits(self, payload: dict) -> dict:
        from core.device_profile import detect_device_profile
        from core.workload_limits_service import get_workload_settings, save_workload_settings

        tier = detect_device_profile().tier
        root = self._app_root()
        save_workload_settings(root, payload)
        settings = get_workload_settings(root, tier=tier)
        return {"success": True, **settings}

    async def _ensure_online_token_budget(self, active: ActiveLlm) -> bool:
        ok, message = check_budget(self._app_root(), mode=active.mode)
        if not ok:
            self._broadcast("chat", "CoreX Error", message)
            return False
        return True

    def _record_online_usage(self, active: ActiveLlm, label: str = "") -> bool:
        if active.mode != "online":
            return True
        getter = getattr(active.client, "get_last_usage", None)
        if not callable(getter):
            return True
        stats = getter()
        if not stats:
            return True
        result = record_usage(
            self._app_root(),
            stats.to_token_usage(),
            mode=active.mode,
            label=label,
        )
        if result.get("warning"):
            self._broadcast_thinking(result["warning"])
        if result.get("blocked"):
            self._broadcast(
                "chat",
                "CoreX Error",
                "Лимит токенов API исчерпан. Задача остановлена.",
            )
            return False
        return True

    async def set_project_root(self, path: str) -> dict:
        """Синхронизировать активный проект между UI, FileService и оркестратором."""
        try:
            new_root = Path(path).resolve()
            if not new_root.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            self.project_root = new_root
            if self.gui is not None:
                self.gui.project_dir = str(new_root)

            ensure_personas_dir(new_root)
            ensure_pipelines_dir(new_root)

            if self.file_service is not None:
                return await self.file_service.set_project_root(str(new_root))

            return {"success": True, "root": str(new_root)}
        except Exception as e:
            return {"error": str(e)}

    def stop_current_task(self):
        proc = self._aider_proc.get("process")
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            return True
        return bool(proc)

    def _get_project_root(self) -> Path:
        if self.project_root is not None:
            return self.project_root

        if self.file_service is not None:
            return self.file_service.project_root

        project_dir = getattr(self.gui, "project_dir", None)
        if project_dir:
            return Path(project_dir).resolve()

        return Path(os.getcwd()).resolve()

    def _sync_project_root(self) -> Path:
        root = self._get_project_root()
        self.project_root = root
        if self.file_service is not None:
            self.file_service.project_root = root.resolve()
        if self.gui is not None:
            self.gui.project_dir = str(root)
        return root

    def _history_suggests_coding_context(self, history: list[dict]) -> bool:
        return history_suggests_coding(history)

    def _looks_like_build_request(self, user_task: str) -> bool:
        return looks_like_build_request(user_task)

    def _looks_like_question(self, user_task: str) -> bool:
        return looks_like_question(user_task)

    def _is_conversational_task(self, user_task: str, history: list[dict] | None = None) -> bool:
        """Только явное small talk — не короткие запросы на создание."""
        return is_conversational_message(user_task, history)

    def _suggest_files_for_task(self, user_task: str) -> list[str]:
        dest = infer_task_write_path(user_task)
        if dest:
            files = [dest]
        elif any(word in user_task.lower() for word in ("сайт", "html", "страниц", "landing", "веб", "web page")):
            files = ["index.html", "style.css", "script.js"]
        elif any(word in user_task.lower() for word in ("react", "tsx", "typescript", "vite")):
            files = ["package.json", "src/App.tsx", "src/main.tsx"]
        else:
            files = ["main.py"]
        task = user_task.lower()
        if dest:
            return files
        if any(word in task for word in ("сайт", "html", "страниц", "landing", "веб", "web page")):
            return files
        if any(word in task for word in ("react", "tsx", "typescript", "vite")):
            return files
        if any(word in task for word in ("pygame", "flask", "django", "fastapi", "requests", "python", ".py")):
            files.append("requirements.txt")
        elif "requirements" in task or "зависимост" in task:
            files.append("requirements.txt")
        if any(word in task for word in ("readme", "документац", "описание")):
            files.append("README.md")
        return list(dict.fromkeys(files))

    def _fallback_plan(self, user_task: str) -> dict:
        files = self._suggest_files_for_task(user_task)
        return {
            "intent": "code_task",
            "understanding": user_task,
            "plan": [
                "Понять запрос пользователя и выбрать стек",
                f"Создать файлы: {', '.join(files)}",
                "Проверить запуск / синтаксис",
                "Обновить память проекта",
            ],
            "files_to_inspect": [],
            "files_to_create_or_update": files,
        }

    def _normalize_plan(
        self,
        plan: dict | None,
        user_task: str,
        history: list[dict],
    ) -> dict | None:
        looks_like_code = (
            self._looks_like_build_request(user_task)
            or self._history_suggests_coding_context(history)
        )
        if plan is None:
            if should_run_planning_phase(user_task, history):
                return self._fallback_plan(user_task)
            return None

        intent = (plan.get("intent") or "").strip().lower()
        write_files = plan.get("files_to_create_or_update") or []
        if write_files:
            plan["intent"] = "code_task"
            return plan

        if looks_like_code and intent in {"", "chat", "question"}:
            plan["intent"] = "code_task"
            if not write_files:
                plan["files_to_create_or_update"] = self._suggest_files_for_task(user_task)
            if not plan.get("plan"):
                plan["plan"] = self._fallback_plan(user_task)["plan"]
            if not plan.get("understanding"):
                plan["understanding"] = user_task
            return plan

        if intent == "code_task":
            if not write_files:
                plan["files_to_create_or_update"] = self._suggest_files_for_task(user_task)
            return plan

        return plan

    def _infer_task_mode(
        self,
        user_task: str,
        history: list[dict],
        plan: dict | None,
    ) -> tuple[bool, bool, bool]:
        """Возвращает (conversational, is_question, requires_writes)."""
        route = infer_task_route(user_task, history)
        if route == "conversational":
            return True, False, False
        if route == "question":
            return False, True, False

        looks_like_code = (
            self._looks_like_build_request(user_task)
            or self._history_suggests_coding_context(history)
            or bool(isinstance(plan, dict) and plan.get("files_to_create_or_update"))
        )
        plan_intent = (plan.get("intent") or "").strip().lower() if isinstance(plan, dict) else ""

        if plan_intent == "code_task" or looks_like_code:
            return False, False, True

        if plan_intent == "question" or self._looks_like_question(user_task):
            return False, True, False

        if plan_intent == "chat":
            return True, False, False

        return False, False, True

    def _requires_physical_writes(
        self,
        user_task: str,
        history: list[dict] | None = None,
        plan_intent: str | None = None,
    ) -> bool:
        _, _, requires_writes = self._infer_task_mode(
            user_task,
            history or [],
            {"intent": plan_intent} if plan_intent else None,
        )
        return requires_writes

    def _online_client_is_openrouter(self, client: Any) -> bool:
        checker = getattr(client, "_is_openrouter", None)
        if callable(checker):
            return bool(checker())
        return "openrouter.ai" in str(getattr(client, "base_url", "") or "").lower()

    def _routed_online_model(self, user_task: str, history: list[dict], active: ActiveLlm) -> str:
        selected = str(getattr(active, "model_name", "") or "").strip()
        if getattr(active, "mode", "") != "online":
            return selected
        route = infer_task_route(user_task, history)
        return resolve_online_model_for_route(
            route,
            selected,
            api_type=str(getattr(active, "api_type", "openai") or "openai"),
            is_openrouter=self._online_client_is_openrouter(active.client),
        )

    async def _gather_project_snapshot(self, project_root: Path, max_entries: int = 80) -> str:
        lines = collect_analysis_entries(project_root, max_files=max_entries)
        if not lines:
            return "Project folder is empty (chat/ excluded from analysis).\n"
        header = (
            "Project files (chat/ is CoreX internal — excluded from analysis):\n"
        )
        return header + "\n".join(lines) + "\n"

    def _build_fast_local_plan(self, user_task: str) -> dict:
        """Упрощённый план для локального конвейера — без отдельного LLM-вызова."""
        return {
            "intent": "code_task",
            "understanding": user_task,
            "plan": [
                "Просмотреть структуру открытого проекта",
                "Создать или обновить нужные файлы по задаче",
                "Проверить запуск и базовое качество результата",
            ],
            "files_to_inspect": [],
            "files_to_create_or_update": [],
        }

    def _emit_plan_ready_trace(self, plan: dict | None) -> None:
        intent = (plan or {}).get("intent", "—") if isinstance(plan, dict) else "—"
        self._broadcast_trace(
            "planning",
            "plan_ready",
            f"План готов: {intent}",
            node="plan",
            status="done",
            meta={"intent": intent, "steps": len((plan or {}).get("plan") or [])},
        )

    async def _run_planning_phase(
        self,
        user_task: str,
        active_root: Path,
        history: list[dict],
        project_snapshot: str,
    ) -> dict | None:
        if not should_run_planning_phase(user_task, history):
            return None

        history_text = format_history_for_prompt(history)
        memory_path = active_root / MEMORY_REL_PATH
        memory_text = ""
        if memory_path.is_file():
            try:
                memory_text = memory_path.read_text(encoding="utf-8").strip()
            except OSError:
                pass

        knowledge = build_knowledge_bundle(active_root, user_task)
        knowledge_note = ""
        if knowledge.text:
            knowledge_note = (
                f"Knowledge base: {knowledge.summary_ru()}\n"
                f"Apply standards from core_x_knowledge when planning file changes.\n"
            )

        planning_prompt = (
            f"{history_text}"
            f"Active project: {active_root}\n"
            f"{project_snapshot}"
            f"{knowledge_note}"
            f"{'Project memory:\\n' + memory_text + '\\n' if memory_text else ''}"
            f"Current user message: {user_task}\n"
            "Produce the planning JSON."
        )

        if knowledge.text:
            self._broadcast_thinking(knowledge.summary_ru())

        self._broadcast_thinking("Анализирую контекст и составляю план...")
        active = await self._resolve_ready_llm()
        if not await ensure_llm_ready(active):
            message = llm_readiness_error(active)
            self._broadcast("chat", "CoreX Error", message)
            self._broadcast_thinking(f"Модель недоступна: {llm_thinking_label(active)}")
            return None
        if not await self._ensure_online_token_budget(active):
            return None
        self._broadcast_thinking(f"Планирование: {llm_thinking_label(active)}")
        raw = await active.client.chat_complete(
            PLANNING_SYSTEM_PROMPT,
            planning_prompt,
            history=history[:-1] if history else None,
            temperature=0.2,
            json_mode=active.mode == "local",
        )
        self._drain_model_switch_notices(active.client)
        if not self._record_online_usage(active, label="planning"):
            return None

        if is_online_api_failure(raw):
            self._broadcast("chat", "CoreX Error", raw.strip())
            return None

        plan = self._extract_json_payload(self._clean_response(raw))
        if not isinstance(plan, dict):
            self._broadcast_thinking("Не удалось разобрать план, продолжаю без него...")
            return None

        understanding = plan.get("understanding", "")
        steps = plan.get("plan", [])
        if understanding:
            self._broadcast_thinking(f"Понял: {understanding}")
        for index, step in enumerate(steps[:8], start=1):
            self._broadcast_thinking(f"План {index}: {step}")

        return plan

    def _format_plan_for_execution(self, plan: dict | None) -> str:
        if not plan:
            return ""
        lines = ["=== EXECUTION PLAN (follow strictly) ==="]
        if plan.get("understanding"):
            lines.append(f"Goal: {plan['understanding']}")
        for index, step in enumerate(plan.get("plan", []), start=1):
            lines.append(f"{index}. {step}")
        inspect_files = plan.get("files_to_inspect") or []
        write_files = plan.get("files_to_create_or_update") or []
        if inspect_files:
            lines.append(f"Read first: {', '.join(inspect_files)}")
        if write_files:
            lines.append(f"Create/update: {', '.join(write_files)}")
        lines.append("=== END PLAN ===\n")
        return "\n".join(lines)

    def _inject_project_memory(
        self,
        current_prompt: str,
        project_root: Path,
        *,
        max_chars: int | None = None,
    ) -> str:
        memory_dir = project_root / MEMORY_DIR
        memory_path = project_root / MEMORY_REL_PATH

        os.makedirs(memory_dir, exist_ok=True)

        if memory_path.is_file():
            try:
                memory_content = memory_path.read_text(encoding="utf-8").strip()
                if memory_content:
                    if max_chars and len(memory_content) > max_chars:
                        half = max_chars // 2
                        memory_content = memory_content[:half] + "\n…\n" + memory_content[-half:]
                    self._broadcast_thinking("Загружаю внешнюю память проекта...")
                    return (
                        f"Вот твоя текущая память о проекте:\n"
                        f"{memory_content}\n"
                        f"Опирайся на неё.\n\n"
                        f"{current_prompt}"
                    )
            except OSError as e:
                self._broadcast("chat", "CoreX Warning", f"Не удалось прочитать project_memory.md: {e}")

        return current_prompt

    async def _maybe_inject_web_search(
        self,
        current_prompt: str,
        *,
        user_query: str,
        conversational: bool,
        is_question: bool,
        compact: bool,
    ) -> str:
        from core.web_access import should_search_web
        from core.web_search import search_web

        self._web_search_block = ""
        if not should_search_web(
            user_query,
            conversational=conversational,
            is_question=is_question,
        ):
            return current_prompt
        self._broadcast_thinking("Ищу короткие подсказки в интернете...")
        try:
            payload = await asyncio.to_thread(search_web, user_query)
        except Exception:
            self._broadcast_thinking("Поиск недоступен")
            return current_prompt
        text = str(payload.get("text") or "").strip()
        cap = 1200 if compact else 1400
        if len(text) > cap:
            text = text[:cap].rsplit("\n", 1)[0]
        if not text:
            self._broadcast_thinking("Поиск недоступен")
            return current_prompt
        query = str(payload.get("query") or user_query).strip()
        self._broadcast_thinking(f"Нашёл подсказки: {query[:80]}")
        self._web_search_block = text
        return f"{current_prompt}\n{text}\n"

    def _drain_model_switch_notices(self, client: Any = None) -> None:
        target = client
        if target is None:
            try:
                target = self._resolve_llm().client
            except Exception:
                return
        consume = getattr(target, "consume_model_switch_notices", None)
        if not callable(consume):
            return
        for notice in consume():
            self._broadcast_thinking(notice)

    def _normalize_rel_path(self, path: str) -> str:
        cleaned = (path or ".").replace("\\", "/").strip()
        if not cleaned or cleaned in (".", "./"):
            return "."
        try:
            root = self._get_project_root().resolve()
            candidate = Path(cleaned)
            if candidate.is_absolute():
                rel = candidate.resolve().relative_to(root)
                return rel.as_posix()
        except (ValueError, OSError):
            pass
        return cleaned.lstrip("/")

    def _message_claims_fix_without_write(self, message: str) -> bool:
        return bool(_FAUX_DONE_PATTERNS.search(message))

    def _verify_file_on_disk(self, rel_path: str) -> bool:
        root = self._get_project_root().resolve()
        full_path = (root / self._normalize_rel_path(rel_path)).resolve()
        try:
            full_path.relative_to(root)
        except ValueError:
            return False
        return full_path.is_file()

    async def _execute_filesystem_tool(self, tool: str, args: dict) -> dict:
        """Выполнить инструмент через FileService с записью строго в активный проект."""
        if self.file_service is None:
            return {"status": "Error", "message": "File service not available"}

        rel_path = self._normalize_rel_path(args.get("path", "."))

        if tool in {"write_file", "append_file", "patch_file"}:
            if not rel_path or rel_path in (".", "./"):
                return {
                    "status": "Error",
                    "message": (
                        "path — это папка проекта, не файл. "
                        "Укажите имя файла, например main.py."
                    ),
                }

        if tool == "list_directory" and is_corex_internal_path(rel_path):
            return {
                "status": "Success",
                "tool": tool,
                "result": {
                    "contents": [],
                    "note": "chat/ is CoreX internal storage — skipped in project analysis.",
                },
            }

        if tool == "list_directory":
            raw = await self.file_service.list_directory(rel_path)
        elif tool == "view_file":
            try:
                full_path = (self._get_project_root() / rel_path).resolve()
            except (ValueError, OSError):
                full_path = None
            if full_path is not None and full_path.is_dir():
                listing = await self.file_service.list_directory(rel_path)
                return {
                    "status": "Success",
                    "tool": "list_directory",
                    "path": rel_path,
                    "result": {
                        **(listing if isinstance(listing, dict) else {"raw": listing}),
                        "note": (
                            "Это папка, не файл. Для папок — list_directory. "
                            "view_file только для файлов (.md, .html, .py). "
                            "Дизайнер: сразу write_file → design-system/MASTER.md"
                        ),
                    },
                }
            raw = await self.file_service.read_file(rel_path)
            if isinstance(raw, dict) and "error" not in raw:
                numbered = raw.get("numbered_content", "")
                return {
                    "status": "Success",
                    "tool": tool,
                    "path": rel_path,
                    "line_count": raw.get("line_count", 0),
                    "result": {
                        "content": raw.get("content", ""),
                        "numbered_content": numbered,
                        "content": raw.get("content", ""),
                        "hint": (
                            "Номер слева = line. "
                            "Изменить: patch_file op=replace line=N. "
                            "Удалить: op=delete line=N."
                        ),
                    },
                }
        elif tool == "patch_file":
            operations = args.get("operations") or []
            if not operations and args.get("op"):
                operations = [args]
            raw = await self.file_service.patch_file(rel_path, operations)
        elif tool == "write_file":
            raw = await self.file_service.write_file(rel_path, args.get("content", ""))
        elif tool == "append_file":
            raw = await self.file_service.append_file(rel_path, args.get("content", ""))
        else:
            return {"status": "Error", "message": f"Unsupported tool: {tool}"}

        if isinstance(raw, dict) and raw.get("error"):
            return {"status": "Error", "message": raw["error"]}

        if tool == "patch_file":
            if isinstance(raw, dict) and raw.get("success"):
                abs_path = raw.get("absolute_path") or str(
                    self._get_project_root() / rel_path
                )
                highlights = raw.get("highlights") or []
                self._broadcast_editor_patch(rel_path, raw.get("content", ""), highlights)
                return {
                    "status": "Success",
                    "path": rel_path,
                    "absolute_path": abs_path,
                    "highlights": highlights,
                    "warnings": raw.get("warnings") or [],
                    "message": f"Patched {rel_path} ({len(highlights)} change(s))",
                }
            if isinstance(raw, dict) and raw.get("error"):
                return {"status": "Error", "message": raw["error"]}

        if tool in {"write_file", "append_file"}:
            if isinstance(raw, dict) and raw.get("success"):
                abs_path = raw.get("absolute_path") or str(
                    self._get_project_root() / rel_path
                )
                return {
                    "status": "Success",
                    "path": rel_path,
                    "absolute_path": abs_path,
                    "message": f"File written to {abs_path}",
                    "unchanged": bool(raw.get("unchanged")),
                }
            if self._verify_file_on_disk(rel_path):
                full_path = (self._get_project_root() / rel_path).resolve()
                return {
                    "status": "Success",
                    "path": rel_path,
                    "absolute_path": str(full_path),
                    "message": f"File written to {full_path}",
                }
            root = self._get_project_root()
            return {
                "status": "Error",
                "message": (
                    f"Write failed: file not found on disk: {rel_path} "
                    f"(project root: {root})"
                ),
            }

        return {"status": "Success", "tool": tool, "result": raw}

    async def _execute_terminal_tool(
        self,
        tool: str,
        args: dict,
        active_root: Path,
    ) -> dict:
        if tool == "run_file":
            rel_path = self._normalize_rel_path(args.get("path", ""))
            if not rel_path:
                return {"status": "Error", "message": "path is required"}
            if not self._verify_file_on_disk(rel_path):
                stub = await asyncio.to_thread(
                    remediate_python_error,
                    active_root,
                    rel_path,
                    f"файл не найден: {rel_path}",
                    mode="stub",
                )
                if stub.get("ok"):
                    self._broadcast(
                        "chat",
                        "CoreX",
                        f"Создана заготовка: {rel_path} — откройте и доработайте",
                    )
                else:
                    return {
                        "status": "Error",
                        "message": f"Файл не найден: {rel_path}",
                    }
            timeout = 8 if self._script_is_interactive(rel_path) else 120
            raw = await run_file(active_root, rel_path, timeout=timeout)
        elif tool == "run_command":
            command = (args.get("command") or "").strip()
            if not command:
                return {"status": "Error", "message": "command is required"}
            cwd = args.get("cwd")
            raw = await run_command(active_root, command, cwd=cwd)
        else:
            return {"status": "Error", "message": f"Unsupported terminal tool: {tool}"}

        if raw.get("error") and not raw.get("output"):
            return {"status": "Error", "message": raw["error"], "result": raw}

        output = (raw.get("output") or "").strip()
        error_text = (raw.get("error") or "").strip()
        combined = f"{output}\n{error_text}".strip()
        runtime_failed = self._terminal_output_indicates_failure(combined)
        success = bool(raw.get("success")) and not runtime_failed

        if runtime_failed and not success:
            return {
                "status": "Error",
                "message": "Команда завершилась с ошибкой выполнения",
                "exit_code": raw.get("exit_code"),
                "output": combined[:8000],
                "result": raw,
            }

        timed_out = "Превышен лимит" in error_text
        if timed_out and not runtime_failed:
            success = True

        return {
            "status": "Success" if success else "Error",
            "message": "Команда выполнена" if success else (combined[:2000] or error_text),
            "exit_code": raw.get("exit_code"),
            "output": combined[:8000],
            "result": raw,
        }

    @staticmethod
    def _terminal_output_indicates_failure(text: str) -> bool:
        from core.code_verify import _RUNTIME_ERROR_MARKERS as markers

        return bool(markers.search(text or ""))

    @staticmethod
    def _is_python_source(rel_path: str) -> bool:
        return rel_path.lower().endswith(".py")

    @staticmethod
    def _extract_error_line(detail: str) -> int | None:
        match = re.search(r"line\s+(\d+)", detail or "", re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _file_context_around(
        self,
        active_root: Path,
        rel_path: str,
        line_no: int,
        radius: int = 6,
    ) -> str:
        full_path = (active_root / self._normalize_rel_path(rel_path)).resolve()
        if not full_path.is_file():
            return ""
        lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            return ""
        start = max(0, line_no - radius - 1)
        end = min(len(lines), line_no + radius)
        snippet_lines = [f"{index + 1:4d}| {lines[index]}" for index in range(start, end)]
        return "\n".join(snippet_lines)

    def _pick_entry_script(self, preferred: list[str] | None = None) -> str | None:
        seen: list[str] = []
        for candidate in list(preferred or []) + list(_ENTRY_SCRIPTS):
            if not candidate or candidate in seen:
                continue
            seen.append(candidate)
            if self._verify_file_on_disk(candidate):
                return candidate
        return None

    def _script_is_interactive(self, rel_path: str) -> bool:
        try:
            root = self._get_project_root()
            text = (root / self._normalize_rel_path(rel_path)).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except (OSError, TypeError):
            return False
        return looks_like_interactive_python(text)

    def _needs_runtime_blocker(
        self,
        *,
        require_verification: bool,
        py_files_written: set[str],
        verified_py_files: set[str],
        terminal_checks_ok: int,
        confirmed_writes: list[str],
    ) -> bool:
        if not require_verification or terminal_checks_ok > 0:
            return False
        if not py_files_written:
            return False
        return True

    def _pick_smoke_script(
        self,
        confirmed_writes: list[str] | None = None,
        py_files_written: set[str] | None = None,
    ) -> str | None:
        preferred: list[str] = []
        for path in list(confirmed_writes or []) + list(py_files_written or []):
            if path and self._is_python_source(path) and path not in preferred:
                preferred.append(path)
        return self._pick_entry_script(preferred=preferred)

    async def _self_test_python(self, active_root: Path, rel_path: str) -> dict:
        """CoreX сам запускает продукт. GUI/игры: короткий таймаут без traceback = успех."""
        timeout = 5 if self._script_is_interactive(rel_path) else 8
        self._broadcast_thinking(f"Сам запускаю проверку: {rel_path}")
        result = await smoke_run_python(active_root, rel_path, timeout=timeout)
        detail = compact_runtime_detail(str(result.get("detail") or ""))
        if not result.get("ok"):
            if await self._try_repair_python_on_disk(active_root, rel_path, detail):
                self._broadcast_thinking(f"Исправил импорт/ошибку в {rel_path}, запускаю снова")
                result = await smoke_run_python(active_root, rel_path, timeout=timeout)
                detail = compact_runtime_detail(str(result.get("detail") or ""))
        if result.get("ok"):
            self._last_smoke_detail = ""
            self._broadcast("chat", "CoreX", f"Запуск OK: {rel_path} — {detail[:240]}")
        else:
            self._last_smoke_detail = detail
            self._broadcast("chat", "CoreX Error", f"Запуск упал: {rel_path}\n{detail[:1500]}")
        return result

    def _lesson_file_names(self, items) -> list[str]:
        names: list[str] = []
        for item in items or []:
            if not item or is_corex_internal_path(str(item)):
                continue
            norm = str(item).replace("\\", "/")
            if norm not in names:
                names.append(norm)
        return names

    def _snapshot_lesson(
        self,
        confirmed_writes,
        verified_py_files,
        *,
        how: str = "",
        error: str = "",
        ok: bool | None = None,
    ) -> None:
        prev = getattr(self, "_pending_lesson", None) or {}
        self._pending_lesson = {
            "files": self._lesson_file_names(confirmed_writes),
            "verified": self._lesson_file_names(verified_py_files),
            "how": how or str(prev.get("how") or ""),
            "error": error or str(prev.get("error") or ""),
            "ok": prev.get("ok") if ok is None else ok,
        }

    def _remember_code_lesson(
        self,
        user_task: str,
        *,
        ok: bool,
        how: str,
        files: list[str] | None = None,
        error: str = "",
    ) -> None:
        if getattr(self, "_lesson_recorded", False):
            return
        task = (user_task or "").strip()
        if not task:
            return
        try:
            from core.lesson_store import remember_task_outcome

            lesson = remember_task_outcome(
                task=task,
                ok=ok,
                how=how,
                files=files,
                error=error,
            )
        except OSError:
            return
        if lesson is not None:
            self._lesson_recorded = True

    def _flush_pending_lesson(self, user_task: str) -> None:
        pending = getattr(self, "_pending_lesson", None) or {}
        files = list(pending.get("files") or [])
        verified = list(pending.get("verified") or [])
        how = str(pending.get("how") or "")
        error = str(pending.get("error") or "")
        ok = pending.get("ok")
        if ok is None:
            ok = bool(verified) or bool(files)
            how = how or ("verified" if verified else ("wrote" if files else "fail"))
        elif not how:
            how = "verified" if ok and verified else ("wrote" if ok else "fail")
        self._remember_code_lesson(
            user_task,
            ok=bool(ok),
            how=how,
            files=files or verified,
            error=error,
        )

    async def _propose_file_plan(
        self,
        user_task: str,
        *,
        write_dest: str | None = None,
    ) -> list[str]:
        from core.file_plan import (
            FILE_PLAN_SYSTEM,
            folder_hint_for_plan,
            parse_file_plan,
            sanitize_file_plan,
        )
        from core.write_target import suggest_created_filename

        folder_hint = folder_hint_for_plan(user_task, write_dest)
        fallback = suggest_created_filename(user_task)
        active = self._resolve_llm()
        raw = ""
        try:
            self._broadcast_thinking("Составляю список файлов...")
            kwargs: dict = {
                "history": None,
                "temperature": 0.1,
                "json_mode": True,
            }
            if getattr(active, "mode", "") == "local":
                kwargs["num_predict"] = 96
            raw = await active.client.chat_complete(
                FILE_PLAN_SYSTEM,
                f"Task: {user_task}\nJSON only.",
                **kwargs,
            )
            if self._budget:
                self._budget.record_llm_call()
            self._record_online_usage(active, label="file_plan")
        except (OSError, TypeError, RuntimeError, asyncio.TimeoutError):
            raw = ""
        files = sanitize_file_plan(
            parse_file_plan(raw),
            user_task=user_task,
            folder_hint=folder_hint,
            fallback=fallback,
        )
        self._broadcast_thinking("План файлов: " + ", ".join(files))
        return files

    async def _try_gui_window_fallback(
        self,
        active_root: Path,
        user_task: str,
        confirmed_writes: list[str],
        rel_path: str | None = None,
    ) -> str | None:
        """Шаблон окна — только если задача/файл совпадают с этим шаблоном."""
        from core.game_gui_upgrade import (
            maybe_upgrade_console_game_to_window,
            read_entry_source,
        )
        from core.write_target import resolve_gui_fallback_path

        path = resolve_gui_fallback_path(user_task, rel_path, active_root)
        source = read_entry_source(active_root, path)
        upgrade = maybe_upgrade_console_game_to_window(
            user_task=user_task,
            source=source,
            rel_path=path,
        )
        if not upgrade:
            return None
        result = await self.file_service.write_file(upgrade["path"], upgrade["content"])
        if not filesystem_tool_succeeded(result) and not (
            isinstance(result, dict) and result.get("success")
        ):
            err = (result or {}).get("error") if isinstance(result, dict) else result
            self._broadcast("chat", "CoreX Error", f"Не удалось записать окно: {err}")
            return None
        self._broadcast_editor_patch(upgrade["path"], upgrade["content"], [])
        message = upgrade["message"]
        self._broadcast("chat", "CoreX Status", message)
        self._remember_code_lesson(
            user_task,
            ok=True,
            how="gui_template",
            files=[upgrade["path"]],
        )
        return message

    async def _drop_broken_syntax_from_verified(
        self,
        active_root: Path,
        py_files_written: set[str],
        verified_py_files: set[str],
    ) -> set[str]:
        """Не держать в verified файл, который на диске не компилируется."""
        verified = set(verified_py_files)
        for rel_path in list(py_files_written | verified):
            if not self._is_python_source(rel_path):
                continue
            syntax = await asyncio.to_thread(verify_python_syntax, active_root, rel_path)
            if not syntax.get("ok"):
                verified.discard(rel_path)
        return verified

    def _sync_editor_from_disk(self, active_root: Path, rel_path: str) -> None:
        full_path = (active_root / self._normalize_rel_path(rel_path)).resolve()
        if not full_path.is_file():
            return
        try:
            content = full_path.read_text(encoding="utf-8")
        except OSError:
            return
        self._broadcast_editor_patch(rel_path, content, [])

    async def _auto_view_file(
        self,
        rel_path: str,
        *,
        active_root: Path,
        verify_fail_streak: dict[str, tuple[str, int]],
    ) -> str:
        """Прочитать файл перед правкой и вернуть сериализованный результат для промпта."""
        if not is_corex_internal_path(rel_path):
            self._broadcast_thinking(f"Авто-чтение перед правкой: {rel_path}")
        view_result = await self._execute_filesystem_tool("view_file", {"path": rel_path})
        focus_line = None
        if rel_path in verify_fail_streak:
            focus_line = self._extract_error_line(verify_fail_streak[rel_path][0])
        compact = compact_tool_result_for_prompt(
            "view_file",
            view_result if isinstance(view_result, dict) else {},
            focus_line=focus_line,
        )
        return self._serialize_tool_result(compact)

    async def _ensure_python_module(
        self,
        active_root: Path,
        rel_path: str,
        module: str,
    ) -> dict:
        """Пакет в requirements + pip install. Исходник не трогаем."""
        from core.python_deps import (
            ensure_requirements_line,
            install_module,
            is_pip_installable_module,
            pip_package_name,
        )
        from core.terminal_service import resolve_project_python

        if not is_pip_installable_module(module):
            return {"installed": False, "verify": {"ok": False}, "module": module}

        pkg = pip_package_name(module)
        added = await asyncio.to_thread(ensure_requirements_line, active_root, module)
        if added:
            self._broadcast("chat", "CoreX", f"В requirements.txt добавлен пакет {pkg}")
        self._broadcast_thinking(f"Устанавливаю {pkg} (pip)")
        python_exe, _venv = resolve_project_python(active_root, active_root)
        result = await asyncio.to_thread(
            install_module, active_root, module, python_exe=python_exe
        )
        if result.get("ok"):
            self._broadcast("chat", "CoreX", f"Установлен пакет {pkg}")
            verify = await self._auto_verify_python_write(active_root, rel_path)
            return {"installed": True, "verify": verify, "module": module}

        err = (result.get("error") or "")[:500]
        self._broadcast(
            "chat",
            "CoreX",
            f"Код в {rel_path} синтаксически верный. Нет пакета {pkg}. "
            f"Установите: pip install {pkg}. {err}".strip(),
        )
        return {
            "installed": False,
            "verify": {
                "ok": True,
                "phase": "dependency",
                "missing_module": module,
                "detail": f"Модуль {module} не установлен — это не ошибка кода",
            },
            "module": module,
        }

    async def _try_repair_python_on_disk(
        self,
        active_root: Path,
        rel_path: str,
        error_hint: str,
    ) -> bool:
        """Синтаксис/заготовки на диске + обновление редактора. True если verify прошёл."""
        from core.python_deps import extract_missing_module

        if not rel_path or rel_path in (".", "./"):
            return False

        module = extract_missing_module(error_hint)
        if module:
            handled = await self._ensure_python_module(active_root, rel_path, module)
            return bool((handled.get("verify") or {}).get("ok"))

        hint = error_hint or ""
        is_syntax = "SyntaxError" in hint or "IndentationError" in hint
        is_tk_import = bool(
            re.search(
                r"No module named ['\"](?:Tk|Canvas|Button|Frame|Label|Entry|Text)['\"]",
                hint,
                re.I,
            )
        )
        is_tk_keysym = "winfo_keysym" in hint
        is_bare_after = bool(
            re.search(r"NameError:.*\bafter\b", hint, re.I)
            or re.search(r"name 'after' is not defined", hint, re.I)
        )
        if not is_tk_keysym:
            try:
                on_disk = (active_root / self._normalize_rel_path(rel_path)).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                on_disk = ""
            is_tk_keysym = "winfo_keysym" in on_disk
            is_bare_after = is_bare_after or bool(
                re.search(r"(?<![.\w])after\s*\(", on_disk)
            )
        if not is_syntax and not is_tk_import and not is_tk_keysym and not is_bare_after:
            return False

        syntax_fix = await asyncio.to_thread(
            repair_file_on_disk,
            active_root,
            rel_path,
            error_hint,
        )
        if syntax_fix.get("ok"):
            self._broadcast_editor_patch(
                rel_path,
                syntax_fix.get("content", ""),
                syntax_fix.get("highlights") or [],
            )
            self._broadcast(
                "chat",
                "CoreX",
                f"Авто-ремонт синтаксиса: {syntax_fix.get('message', rel_path)}",
            )
            verify = await self._auto_verify_python_write(active_root, rel_path)
            if verify.get("ok"):
                return True
        return False

    async def _auto_resolve_done_blockers(
        self,
        *,
        active_root: Path,
        blockers: list[str],
        confirmed_writes: list[str],
        verified_py_files: set[str],
        py_files_written: set[str],
        verify_fail_streak: dict[str, tuple[str, int]],
        terminal_checks_ok: int,
        memory_updated_this_task: bool,
        project_files_written: bool,
    ) -> dict[str, Any]:
        """Снять блокеры завершения, если модель зациклилась на done без правок."""
        resolved: list[str] = []

        if "memory" in blockers and project_files_written and not memory_updated_this_task:
            memory_body = (
                "# Project memory\n\n"
                "_Авто-обновление CoreX после правок в проекте._\n\n"
                f"- Файлы в сессии: {', '.join(sorted(set(confirmed_writes))) or '—'}\n"
            )
            if self.file_service is not None:
                raw = await self.file_service.write_file(MEMORY_REL_PATH, memory_body)
                if isinstance(raw, dict) and raw.get("success"):
                    memory_updated_this_task = True
                    resolved.append("memory")

        if "unverified" in blockers:
            for rel_path in sorted(py_files_written - verified_py_files):
                error_hint = verify_fail_streak.get(rel_path, ("", 0))[0]
                if await self._try_repair_python_on_disk(active_root, rel_path, error_hint):
                    verified_py_files.add(rel_path)
                    verify_fail_streak.pop(rel_path, None)
                    if rel_path not in confirmed_writes:
                        confirmed_writes.append(rel_path)
                    resolved.append(f"verify:{rel_path}")

        if "runtime" in blockers and terminal_checks_ok == 0:
            entry = self._pick_smoke_script(confirmed_writes, py_files_written)
            if entry:
                smoke = await self._self_test_python(active_root, entry)
                if smoke.get("ok"):
                    terminal_checks_ok += 1
                    verified_py_files.add(entry)
                    resolved.append(f"run:{entry}")
                else:
                    output = str(smoke.get("detail") or "")[:2000]
                    if await self._try_repair_python_on_disk(active_root, entry, output):
                        retry = await self._self_test_python(active_root, entry)
                        if retry.get("ok"):
                            terminal_checks_ok += 1
                            verified_py_files.add(entry)
                            resolved.append(f"run_fix:{entry}")

        if "no_writes" in blockers and not confirmed_writes:
            for rel_path in sorted(verify_fail_streak.keys()):
                error_hint = verify_fail_streak[rel_path][0]
                if await self._try_repair_python_on_disk(active_root, rel_path, error_hint):
                    confirmed_writes.append(rel_path)
                    verified_py_files.add(rel_path)
                    py_files_written.add(rel_path)
                    project_files_written = True
                    verify_fail_streak.pop(rel_path, None)
                    resolved.append(f"fix:{rel_path}")
                    break
            if not confirmed_writes:
                entry = self._pick_entry_script()
                if entry and await self._try_repair_python_on_disk(
                    active_root,
                    entry,
                    verify_fail_streak.get(entry, ("", 0))[0],
                ):
                    confirmed_writes.append(entry)
                    verified_py_files.add(entry)
                    py_files_written.add(entry)
                    project_files_written = True
                    resolved.append(f"fix:{entry}")

        return {
            "resolved": bool(resolved),
            "resolved_items": resolved,
            "memory_updated_this_task": memory_updated_this_task,
            "terminal_checks_ok": terminal_checks_ok,
            "verified_py_files": verified_py_files,
            "confirmed_writes": confirmed_writes,
            "py_files_written": py_files_written,
            "project_files_written": project_files_written,
        }

    def _build_verify_failure_hint(
        self,
        *,
        rel_path: str,
        detail: str,
        active_root: Path,
        repeat_count: int,
    ) -> str:
        line_no = self._extract_error_line(detail)
        hint = (
            f"System Error: Auto-verify FAILED: {detail[:3000]}\n"
            "Fix with view_file then patch_file. Check if/else/try blocks and indentation.\n"
        )
        if line_no and repeat_count >= 1:
            context = self._file_context_around(active_root, rel_path, line_no)
            if context:
                hint += f"Context around line {line_no}:\n{context}\n"
        if repeat_count >= 2:
            hint += (
                f"REPEATED ERROR ({repeat_count}x) on {rel_path}. "
                "Do NOT patch the same line again. "
                "Use patch_file op delete to remove orphan else:/bad lines, "
                "or fix the whole if/else block (lines shown above).\n"
            )
        if repeat_count >= 3:
            hint += (
                "STOP patching line 60. Delete broken lines with "
                '{"op":"delete","line":N} one per turn from bottom to top.\n'
            )
        hint += "done is blocked until verify passes.\n"
        return hint

    async def _auto_verify_python_write(self, active_root: Path, rel_path: str) -> dict:
        return await verify_python_file(active_root, rel_path)

    def _extract_json_payload(self, text: str):
        cleaned = self._clean_response(text.strip())
        if not cleaned:
            return None

        for candidate in (cleaned, text.strip()):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        for opener, closer in (("{", "}"), ("[", "]")):
            for fragment in _find_balanced_json(cleaned, opener, closer):
                try:
                    parsed = json.loads(fragment)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and "status" in parsed:
                    return parsed
            for fragment in _find_balanced_json(text, opener, closer):
                try:
                    parsed = json.loads(fragment)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and "status" in parsed:
                    return parsed

        for opener, closer in (("{", "}"), ("[", "]")):
            for fragment in _find_balanced_json(cleaned, opener, closer):
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    continue
        return None

    def _clean_response(self, response_text: str):
        return _strip_fences(response_text)

    def _serialize_tool_result(self, result: Any) -> str:
        try:
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            if hasattr(result, "model_dump"):
                return json.dumps(result.model_dump(), ensure_ascii=False)
            if hasattr(result, "dict"):
                return json.dumps(result.dict(), ensure_ascii=False)
            return json.dumps({"status": "Success", "raw": str(result)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "Error", "message": str(e)}, ensure_ascii=False)

    def _broadcast(self, target: str, sender: str, text: str, *, model: str | None = None):
        if target == "terminal":
            if self.gui and hasattr(self.gui, "print_terminal"):
                self.gui.print_terminal(sender, text)
        else:
            if self.gui and hasattr(self.gui, "print_log"):
                self.gui.print_log(sender, text)

        if self.websocket_server:
            payload = {
                "target": target,
                "sender": sender,
                "text": text,
            }
            reply_model = model or (
                self._active_reply_model
                if target == "chat" and sender in {"CoreX", "CoreX Status"}
                else None
            )
            if reply_model:
                payload["model"] = reply_model
            asyncio.create_task(self.websocket_server.broadcast(payload))

    def _broadcast_thinking_done(self):
        if self.websocket_server:
            asyncio.create_task(self.websocket_server.broadcast({
                "target": "thinking_done",
            }))

    def _broadcast_thinking(self, thought: str):
        if self.websocket_server:
            asyncio.create_task(self.websocket_server.broadcast({
                "target": "thinking",
                "sender": "CoreX",
                "text": thought,
            }))

    def begin_trace_task(
        self,
        task_text: str,
        *,
        work_mode: str = "single",
        persona_id: str | None = None,
        pipeline_id: str | None = None,
    ) -> None:
        self._trace_task_id = new_task_id()
        self._last_trace_event_id = None
        self._broadcast_trace(
            "ws",
            "ws_in",
            "Запрос получен",
            node="request",
            status="done",
            meta={
                "preview": (task_text or "")[:160],
                "work_mode": work_mode,
                "persona_id": persona_id,
                "pipeline_id": pipeline_id,
            },
        )
        self._broadcast_trace(
            "ws",
            "ws_route",
            "Маршрутизация в оркестратор",
            node="ws",
            status="active",
        )

    def _broadcast_trace(
        self,
        phase: str,
        kind: str,
        label: str,
        *,
        node: str,
        status: str = "active",
        meta: dict | None = None,
        detail: dict | None = None,
        error_message: str | None = None,
    ) -> str | None:
        if not self._trace_task_id or not self.websocket_server:
            return None
        payload = build_trace_payload(
            task_id=self._trace_task_id,
            phase=phase,
            kind=kind,
            label=label,
            node=node,
            status=status,
            meta=meta,
            parent=self._last_trace_event_id,
            detail=detail,
        )
        self._last_trace_event_id = payload["id"]
        ws_payload = dict(payload)
        if detail:
            ws_payload["detail"] = trim_detail_for_ws(detail) or detail

        root = self.project_root
        if root is not None:
            try:
                append_event(Path(root), payload)
            except OSError:
                pass

        if status == "error" or error_message:
            message = (error_message or label or "Ошибка").strip()
            error_record = None
            if root is not None:
                try:
                    error_record = append_error(
                        Path(root),
                        task_id=self._trace_task_id,
                        event_id=payload["id"],
                        label=label,
                        message=message,
                        kind=kind,
                        node=node,
                        ts=payload.get("ts"),
                    )
                except OSError:
                    error_record = {
                        "id": payload["id"],
                        "task_id": self._trace_task_id,
                        "event_id": payload["id"],
                        "ts": payload.get("ts"),
                        "label": label,
                        "message": message,
                        "kind": kind,
                        "node": node,
                    }
            if error_record:
                asyncio.create_task(
                    self.websocket_server.broadcast({
                        "target": "trace_error",
                        "error": error_record,
                    })
                )

        asyncio.create_task(
            self.websocket_server.broadcast({
                "target": "trace",
                "event": ws_payload,
            })
        )
        return payload["id"]

    def _trace_llm_meta(self, active: ActiveLlm) -> dict:
        mode = getattr(active, "mode", "local")
        label = llm_thinking_label(active)
        return {"mode": mode, "model": label}

    def _broadcast_editor_patch(
        self,
        rel_path: str,
        content: str,
        highlights: list[dict],
    ) -> None:
        if is_corex_internal_path(rel_path):
            return
        if not self.websocket_server:
            return
        self._broadcast_trace(
            "editor",
            "editor_patch",
            f"Патч в редактор: {rel_path}",
            node="editor",
            status="done",
            meta={"path": rel_path, "highlights": len(highlights)},
            detail=make_detail(
                "file_content",
                title=rel_path,
                path=rel_path,
                body=content,
                language="html" if rel_path.endswith(".html") else "text",
            ),
        )
        asyncio.create_task(
            self.websocket_server.broadcast({
                "target": "editor",
                "action": "file_patch",
                "path": rel_path,
                "content": content,
                "highlights": highlights,
            })
        )

    async def execute_task(
        self,
        user_task: str,
        project_root: str | None = None,
        history: list[dict] | None = None,
        persona_id: str | None = None,
        pipeline_id: str | None = None,
        work_mode: str = "single",
        coding_language: str | None = None,
        coding_engine: str | None = None,
    ):
        """Конвейер: контекст -> план -> (команда скиллов | один скил) -> отчёт."""
        self.current_task = asyncio.current_task()
        try:
            await self._execute_task_body(
                user_task=user_task,
                project_root=project_root,
                history=history,
                persona_id=persona_id,
                pipeline_id=pipeline_id,
                work_mode=work_mode,
                coding_language=coding_language,
                coding_engine=coding_engine,
            )
        except asyncio.CancelledError:
            if self._trace_task_id:
                self._broadcast_trace(
                    "task",
                    "task_cancelled",
                    "Задача прервана",
                    node="response",
                    status="error",
                )
            self._broadcast(
                "chat",
                "CoreX",
                "Запрос прерван (новое сообщение или остановка). Отправьте задачу снова.",
            )
            raise
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}".strip()
            if detail.endswith(":"):
                detail = f"{type(exc).__name__} (без текста)"
            if self._trace_task_id:
                self._broadcast_trace(
                    "task",
                    "task_failed",
                    f"Сбой задачи: {detail}",
                    node="response",
                    status="error",
                    detail=make_detail("error", title="Исключение", body=detail, language="text"),
                    error_message=detail,
                )
            self._broadcast("chat", "CoreX Error", f"Ошибка выполнения задачи: {detail}")
        finally:
            await asyncio.sleep(0)
            if self.websocket_server and hasattr(self.websocket_server, "clear_inflight_task_key"):
                self.websocket_server.clear_inflight_task_key()
            self._broadcast_thinking_done()
            if self._trace_task_id:
                self._broadcast_trace(
                    "task",
                    "task_end",
                    "Задача завершена",
                    node="response",
                    status="done",
                )
            self._budget = None
            self._active_reply_model = None
            self.current_task = None

    async def _execute_task_body(
        self,
        *,
        user_task: str,
        project_root: str | None,
        history: list[dict] | None,
        persona_id: str | None,
        pipeline_id: str | None,
        work_mode: str,
        coding_language: str | None = None,
        coding_engine: str | None = None,
    ):
        assistant_reply = ""
        conversation: list[dict] = []
        active_root = Path.cwd()
        self._lesson_recorded = False
        self._pending_lesson = {}
        from core.coding_engine import get_coding_engine, validate_coding_engine

        if coding_engine:
            self._coding_engine = validate_coding_engine(coding_engine)
        else:
            self._coding_engine = get_coding_engine(self._app_root())

        self._broadcast_trace(
            "task",
            "orchestrator_start",
            "Оркестратор запущен",
            node="ws",
            status="done",
            meta={"work_mode": work_mode, "coding_engine": self._coding_engine},
        )
        self._broadcast_trace(
            "ws",
            "ws_route",
            "Маршрутизация в оркестратор",
            node="ws",
            status="done",
        )

        if project_root:
            result = await self.set_project_root(project_root)
            if isinstance(result, dict) and result.get("error"):
                self._broadcast("chat", "CoreX Error", f"Не удалось открыть проект: {result['error']}")
                return

        active_root = self._sync_project_root()
        stored_history = load_history(active_root)
        conversation = merge_history(stored_history, history)

        task_for_agent = normalize_task_text(user_task)
        web_query_source = task_for_agent
        write_dest = infer_task_write_path(task_for_agent, active_root)
        from core.coding_language import (
            get_coding_language,
            resolve_effective_language,
            validate_language_id,
        )

        if coding_language:
            stored_language = validate_language_id(coding_language)
        else:
            stored_language = get_coding_language(active_root)
        self._coding_language = resolve_effective_language(
            stored_language,
            task_for_agent,
        )
        attached_files: list[str] = []
        if self.file_service is not None:
            task_for_agent, attached_files = await expand_file_mentions(
                task_for_agent,
                self.file_service,
            )
            if attached_files:
                names = ", ".join(attached_files)
                intent = mention_intent(user_task)
                if intent == "read":
                    self._broadcast_thinking(f"Читаю: {names}")
                elif intent == "edit":
                    self._broadcast_thinking(f"Изменю: {names}")
                else:
                    self._broadcast_thinking(f"Прикреплены файлы: {names}")
            elif write_dest:
                self._broadcast_thinking(f"Пишу в {write_dest}")

        route_history = list(conversation)
        run_planning = should_run_planning_phase(task_for_agent, route_history)
        include_knowledge = should_include_knowledge_in_prompt(task_for_agent, route_history)

        last = conversation[-1] if conversation else None
        if not (
            isinstance(last, dict)
            and last.get("role") == "user"
            and normalize_task_text(str(last.get("content") or "")) == task_for_agent
        ):
            conversation.append({"role": "user", "content": task_for_agent})

        active_for_route = await self._resolve_ready_llm(
            local_model_override=self._local_model_override_for_task(task_for_agent, route_history),
        )
        online_mode = getattr(active_for_route, "mode", "") == "online"
        local_profile = build_local_pipeline_profile(active_for_route)
        use_fast_local_plan = (
            run_planning
            and (
                online_mode
                or (
                    local_profile is not None
                    and (
                        (work_mode == "pipeline" and bool(pipeline_id))
                        or local_profile.model_tier == "low"
                    )
                )
            )
        )

        plan: dict | None = None
        project_snapshot = ""
        snapshot_entries = 24 if online_mode else 80
        if local_profile and local_profile.model_tier == "low":
            snapshot_entries = 12
        if use_fast_local_plan:
            self._broadcast_trace(
                "planning",
                "plan_start",
                "Планирование задачи (локальный конвейер)" if not online_mode else "Планирование задачи (online lean)",
                node="plan",
                status="active",
            )
            self._broadcast_thinking(
                "Онлайн: короткий план без отдельного вызова модели..."
                if online_mode
                else "Локальный конвейер: упрощённый план без отдельного вызова модели..."
            )
            try:
                project_snapshot = await self._gather_project_snapshot(
                    active_root, max_entries=snapshot_entries
                )
                plan = self._build_fast_local_plan(task_for_agent)
                self._emit_plan_ready_trace(plan)
            except asyncio.CancelledError:
                self._broadcast_trace(
                    "planning",
                    "plan_failed",
                    "Планирование прервано",
                    node="plan",
                    status="error",
                )
                raise
            except Exception as exc:
                self._broadcast_trace(
                    "planning",
                    "plan_failed",
                    f"Ошибка планирования: {exc}",
                    node="plan",
                    status="error",
                )
                self._broadcast("chat", "CoreX Error", f"Ошибка планирования: {exc}")
        elif run_planning:
            self._broadcast_trace(
                "planning",
                "plan_start",
                "Планирование задачи",
                node="plan",
                status="active",
            )
            try:
                project_snapshot = await self._gather_project_snapshot(
                    active_root, max_entries=snapshot_entries
                )
                plan = await self._run_planning_phase(
                    task_for_agent, active_root, conversation, project_snapshot
                )
                self._emit_plan_ready_trace(plan)
            except asyncio.CancelledError:
                self._broadcast_trace(
                    "planning",
                    "plan_failed",
                    "Планирование прервано",
                    node="plan",
                    status="error",
                )
                raise
            except Exception as exc:
                self._broadcast_trace(
                    "planning",
                    "plan_failed",
                    f"Ошибка планирования: {exc}",
                    node="plan",
                    status="error",
                )
                self._broadcast("chat", "CoreX Error", f"Ошибка планирования: {exc}")
                plan = None
        else:
            if is_conversational_message(task_for_agent, conversation):
                self._broadcast_thinking("Короткий диалог — отвечаю без планирования...")
            else:
                self._broadcast_thinking("Отвечаю на вопрос...")
            project_snapshot = ""
            plan = None
            if online_mode and not is_conversational_message(task_for_agent, conversation):
                try:
                    project_snapshot = await self._gather_project_snapshot(
                        active_root, max_entries=snapshot_entries
                    )
                except Exception:
                    project_snapshot = ""

        plan = self._normalize_plan(plan, task_for_agent, conversation)
        if self._looks_like_build_request(task_for_agent):
            self._broadcast_thinking("Запрос распознан как задача на код — буду создавать/менять файлы")

        conversational, is_question, requires_writes = self._infer_task_mode(
            task_for_agent,
            conversation,
            plan,
        )

        if requires_writes and isinstance(plan, dict) and plan.get("intent") != "code_task":
            plan["intent"] = "code_task"

        if requires_writes and self.project_root is None:
            self._broadcast(
                "chat",
                "CoreX Error",
                "Сначала откройте папку проекта в CoreX (Файл → Открыть папку).",
            )
            return

        if requires_writes and not active_root.is_dir():
            self._broadcast(
                "chat",
                "CoreX Error",
                "Папка проекта недоступна. Откройте проект заново.",
            )
            return

        plan_text = self._format_plan_for_execution(plan)

        if conversational:
            length_hint = response_length_instruction(task_for_agent, conversational=True)
            current_prompt = (
                f"Task: {task_for_agent}\n"
                "Conversational message. Do NOT use tools.\n"
                f"{length_hint}\n"
                'Reply: {"status": "done", "message": "..."} in Russian.\n'
            )
        elif is_question:
            length_hint = response_length_instruction(task_for_agent, conversational=True)
            current_prompt = (
                f"{plan_text}"
                f"Active project root: {active_root}\n"
                f"Task: {task_for_agent}\n"
                "User asks a question. Do NOT use tools unless you must read a file to answer accurately.\n"
                f"{length_hint}\n"
                "Prefer view_file if plan lists files_to_inspect, then done with a helpful Russian answer.\n"
                'Reply: {"status": "done", "message": "..."}\n'
            )
        else:
            if online_mode:
                current_prompt = (
                    f"{plan_text}"
                    f"Project: {active_root}\n"
                    f"{project_snapshot}"
                    f"Task: {task_for_agent}\n"
                    "Lean online mode — keep context small.\n"
                    "Rules: one JSON tool per turn; write_file for new files; "
                    "view_file then patch_file to edit; relative paths only; "
                    "done only after write Success on disk.\n"
                    'Finish: {"status":"done","message":"кратко по-русски"}\n'
                )
            else:
                current_prompt = (
                    f"{plan_text}"
                    f"Active project root: {active_root}\n"
                    f"{project_snapshot}"
                    f"All file paths are relative to this folder.\n"
                    f"{'Write in ' + write_dest + '. If that is a folder/name hint, pick a fitting filename yourself — never default to main.py.' if write_dest else 'Write new project files in this folder root — do not create a nested project subfolder unless asked. Pick a fitting filename; do not default to main.py.'}\n"
                    f"Folder chat/ is CoreX internal — do not analyze or list it; update chat/project_memory.md after writes.\n"
                    f"/path is a file or folder: edit that file, or create a new named file inside the folder.\n"
                    f"Task: {task_for_agent}\n"
                    "Pipeline rules:\n"
                    "- User may describe the task without words 'create'/'make' — still write files.\n"
                    "- NEW app: write the COMPLETE working file this turn. A ```python fence is enough.\n"
                    "- Do not list_directory an empty project first. One file per turn.\n"
                    "- FIRST code-changing response MUST create a real file. No done before Success.\n"
                    "- One tool per turn. Wait for tool Success proof.\n"
                    "- After writes, update chat/project_memory.md, then done.\n"
                    "- To edit existing code: view_file then patch_file (one line per turn).\n"
                    "- GUI window: THIS TURN only the current plan step (short tkinter Canvas). "
                    "Do not raycast. Do not write a full AAA game. Do not substitute a different app.\n"
                    "- Never report a fix in done without write_file Success on disk.\n"
                    "- After writes CoreX auto-verifies .py syntax; games with while True are not smoke-run.\n"
                    "- JSON is optional for new files. Code fence is valid.\n"
                )

        current_prompt = self._inject_project_memory(
            current_prompt,
            active_root,
            max_chars=1200 if online_mode else 1600,
        )
        if looks_like_gui_window_request(task_for_agent) and not conversational and not is_question:
            from core.game_gui_upgrade import window_hint_for_task

            current_prompt += window_hint_for_task(task_for_agent)
        mention_hint = mention_prompt_hint(user_task, write_dest, active_root)
        if mention_hint and not conversational:
            current_prompt += mention_hint
        if requires_writes and not conversational and not is_question:
            try:
                from core.lesson_store import format_lessons_for_prompt

                lesson_hint = format_lessons_for_prompt(task_for_agent)
            except OSError:
                lesson_hint = ""
            if lesson_hint:
                current_prompt += "\n" + lesson_hint
        llm_history = conversation[:-1]
        if online_mode:
            llm_history = trim_history_for_llm(llm_history, max_turns=8, max_chars=2500)
        else:
            llm_history = trim_history_for_llm(llm_history, max_turns=4, max_chars=1600)

        active = active_for_route
        if not await ensure_llm_ready(active):
            self._broadcast("chat", "CoreX Error", llm_readiness_error(active))
            return

        if not await self._ensure_online_token_budget(active):
            return

        current_prompt = await self._maybe_inject_web_search(
            current_prompt,
            user_query=web_query_source,
            conversational=conversational,
            is_question=is_question,
            compact=bool(online_mode or (local_profile and local_profile.compact_prompt)),
        )

        routed_model = self._routed_online_model(task_for_agent, conversation, active)
        self._active_reply_model = routed_model or active.model_name
        if active.mode == "online" and routed_model and routed_model != (active.model_name or ""):
            self._broadcast_thinking(
                f"Чат: {routed_model} (эконом). Код — {active.model_name}"
            )
        elif (
            active.mode == "local"
            and local_pair_available(self._installed_local_model_names())
            and not looks_like_pinned_larger_local(self._selected_local_model_name())
        ):
            route = infer_task_route(task_for_agent, conversation)
            if route == "code":
                self._broadcast_thinking("Код: Qwen 3B · чат на этом ПК — Phi-3 Mini")
            else:
                self._broadcast_thinking("Чат: Phi-3 Mini · код на этом ПК — Qwen 3B")
        else:
            self._broadcast_thinking(f"Модель: {llm_thinking_label(active)}")
        self._broadcast_trace(
            "llm",
            "mode_ready",
            f"Режим: {work_mode}",
            node="llm",
            status="active",
            meta={**self._trace_llm_meta(active), "reply_model": self._active_reply_model or ""},
        )

        use_pipeline = (
            work_mode == "pipeline"
            and pipeline_id
            and not conversational
            and not is_question
        )

        if use_pipeline:
            from core.pipeline_runner import run_team_pipeline

            await run_team_pipeline(
                self,
                user_task=task_for_agent,
                pipeline_id=pipeline_id,
                active_root=active_root,
                conversation=conversation,
                plan_text=plan_text,
                project_snapshot=project_snapshot,
                requires_writes=requires_writes,
                conversational=conversational,
                is_question=is_question,
                llm_history=llm_history,
            )
            return

        online_mode = getattr(active, "mode", "") == "online"
        device = detect_device_profile()
        from core.workload_limits_service import UNLIMITED_WORKLOAD, is_unlimited_limits

        if is_unlimited_limits(self._app_root()):
            self._budget = ResourceBudget.from_dict(UNLIMITED_WORKLOAD, app_root=self._app_root())
        elif online_mode:
            # For online providers token budget is the real limiter.
            # Device-based turn/write limits can cause Gemini/OpenAI quota errors
            # to look like local/offline stops.
            self._budget = ResourceBudget.for_online()
            try:
                usage = self.get_token_usage()
                session = usage.get("session") or {}
                daily = usage.get("daily") or {}
                limits = usage.get("limits") or {}
                self._broadcast_thinking(
                    f"Токены API (online): сессия {session.get('total_tokens', 0):,}/"
                    f"{limits.get('session_limit', 0):,}, день {daily.get('total_tokens', 0):,}/"
                    f"{limits.get('daily_limit', 0):,}"
                )
            except Exception:
                pass
        else:
            if conversational:
                self._budget = ResourceBudget.for_device(app_root=self._app_root())
            else:
                self._broadcast_thinking(device.summary_ru())
                self._broadcast_thinking(device.limits_summary_ru())
                self._budget = ResourceBudget.for_device(app_root=self._app_root())
        self.system_prompt = self._build_system_prompt(
            active_root,
            persona_id,
            user_task=task_for_agent,
            include_knowledge=include_knowledge,
            compact=online_mode or bool(local_profile and local_profile.compact_prompt),
            knowledge_char_cap=(
                local_profile.knowledge_chars
                if local_profile
                else (2500 if online_mode else None)
            ),
        )
        if not conversational:
            if local_profile and local_profile.hint_ru and not conversational:
                self._broadcast_thinking(local_profile.hint_ru)
            persona_name, _ = resolve_persona_prompt(active_root, persona_id)
            if persona_name:
                self._broadcast_thinking(f"Персона: {persona_name}")
            self._broadcast_thinking(f"Выполняю задачу в проекте: {active_root}")
            self._broadcast_thinking(self._budget.status_line())

        try:
            enforce_writes = requires_writes or bool(_FIX_TASK_PATTERNS.search(task_for_agent))
            reply = await self._run_agent_loop(
                current_prompt=current_prompt,
                llm_history=llm_history,
                active_root=active_root,
                conversational=conversational,
                is_question=is_question,
                requires_writes=requires_writes,
                enforce_writes=enforce_writes,
                require_verification=requires_writes,
                persona_id=persona_id,
                local_num_predict=(
                    local_profile.num_predict_agent if local_profile else None
                ),
                local_compact=bool(local_profile and local_profile.compact_prompt),
                user_task=task_for_agent,
                json_target_path=write_dest,
            )
            if reply:
                assistant_reply = reply
                conversation.append({"role": "assistant", "content": reply})
                save_history(active_root, conversation)
        except asyncio.CancelledError:
            self._broadcast("chat", "CoreX Status", "Генерация остановлена пользователем.")
            raise
        except Exception as e:
            detail = f"{type(e).__name__}: {e}".strip()
            if detail.endswith(":"):
                detail = f"{type(e).__name__} (без текста)"
            self._broadcast("chat", "CoreX Error", f"Ошибка выполнения задачи: {detail}")
            if requires_writes and not conversational and not is_question:
                self._remember_code_lesson(
                    task_for_agent,
                    ok=False,
                    how="exception",
                    error=detail,
                )
        finally:
            self._budget = None
            self._active_reply_model = None
        return

    async def _run_via_aider(
        self,
        *,
        current_prompt: str,
        active_root: Path,
        conversational: bool,
        is_question: bool,
        requires_writes: bool,
        persona_id: str | None,
        require_verification: bool = False,
        json_target_path: str | None = None,
        user_task: str = "",
    ) -> str | None:
        """Aider вместо JSON-цикла: скилы/персона в промпте, без автокоммита."""
        from core.aider_service import (
            build_aider_launch,
            build_aider_message,
            run_aider,
        )
        from core.coding_language import language_prompt_ru
        from core.core_x_library import resolve_persona_prompt
        from core.knowledge_service import build_knowledge_bundle

        del conversational  # чат без кода не сюда попадает
        active = self._resolve_llm()
        if not await ensure_llm_ready(active):
            self._broadcast("chat", "CoreX Error", llm_readiness_error(active))
            return None
        if not await self._ensure_online_token_budget(active):
            return None

        persona_name, persona_body = resolve_persona_prompt(
            active_root, persona_id, for_orchestrator=True
        )
        knowledge = build_knowledge_bundle(active_root, user_task or current_prompt, persona_id)
        lang_hint = ""
        try:
            lang_hint = language_prompt_ru(getattr(self, "_coding_language", "auto"))
        except Exception:
            lang_hint = ""

        chat_mode = "ask" if (is_question and not requires_writes) else None
        message = build_aider_message(
            task=user_task or current_prompt,
            persona_label=persona_name or (persona_id or ""),
            persona_body=persona_body or "",
            knowledge_text=knowledge.text if knowledge else "",
            language_hint=lang_hint,
            write_dest=json_target_path or "",
            plan_text=current_prompt if current_prompt.strip() else "",
        )
        mode_label = chat_mode or "default"
        self._broadcast_thinking(
            f"Aider · {llm_thinking_label(active)} · режим {mode_label}"
        )
        if persona_name:
            self._broadcast_thinking(f"Персона/скил: {persona_name}")
        self._broadcast_trace(
            "llm",
            "aider_start",
            "Запуск Aider",
            node="llm",
            status="active",
            meta={**self._trace_llm_meta(active), "coding_engine": "aider"},
        )

        try:
            launch = build_aider_launch(
                project_root=active_root,
                active=active,
                message=message,
                chat_mode=chat_mode,
                for_question=bool(is_question and not requires_writes),
            )
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}".strip(": ")
            self._broadcast_trace(
                "llm",
                "aider_failed",
                f"Aider не запустился: {detail}",
                node="llm",
                status="error",
                error_message=detail,
            )
            self._broadcast("chat", "CoreX Error", f"Aider: {detail}")
            return None

        async def _on_line(line: str) -> None:
            text = (line or "").strip()
            if not text:
                return
            if len(text) > 240:
                text = text[:237] + "…"
            self._broadcast_thinking(text)

        result = await run_aider(
            launch,
            on_line=_on_line,
            process_holder=self._aider_proc,
        )
        if not result.ok:
            err = result.error or "Aider завершился с ошибкой"
            if "invalid choice" in err.lower() and "chat-mode" in err.lower():
                err = (
                    "Aider: неверный --chat-mode. "
                    "Обнови CoreX — для правок mode больше не передаётся как 'code'."
                )
            self._broadcast_trace(
                "llm",
                "aider_failed",
                "Aider завершился с ошибкой",
                node="llm",
                status="error",
                error_message=err[:500],
                detail=make_detail("error", title="Aider", body=err[:4000], language="text"),
            )
            self._broadcast("chat", "CoreX Error", err[:2000])
            self._snapshot_lesson([], set(), how="aider_error", error=err[:120], ok=False)
            return None

        self._broadcast_trace(
            "llm",
            "aider_done",
            "Aider завершил шаг",
            node="llm",
            status="done",
            meta={**self._trace_llm_meta(active), "coding_engine": "aider"},
        )

        edited = list(result.edited_files)
        if require_verification and not edited and json_target_path:
            candidate = Path(active_root) / json_target_path
            if candidate.is_file():
                edited = [json_target_path.replace("\\", "/")]

        verified: set[str] = set()
        for rel in edited:
            clean = rel.replace("\\", "/").lstrip("./")
            if not clean.endswith(".py"):
                continue
            abs_path = (active_root / clean).resolve()
            try:
                abs_path.relative_to(active_root.resolve())
            except ValueError:
                continue
            if not abs_path.is_file():
                continue
            try:
                content = abs_path.read_text(encoding="utf-8")
            except OSError:
                continue
            self._broadcast_editor_patch(clean, content, [])
            if require_verification:
                smoke = await self._self_test_python(active_root, clean)
                if smoke.get("ok"):
                    verified.add(clean)
                    self._broadcast("chat", "CoreX Status", f"Проверка OK: {clean}")
                else:
                    detail = compact_runtime_detail(str(smoke.get("detail") or ""))
                    self._broadcast(
                        "chat",
                        "CoreX Error",
                        f"После Aider запуск упал: {clean}\n{detail[:1500]}",
                    )

        summary_lines = [
            line
            for line in (result.stdout or "").splitlines()
            if line.strip() and not line.strip().startswith(">")
        ]
        tail = "\n".join(summary_lines[-40:]).strip()
        if edited:
            files = ", ".join(edited[:8])
            msg = f"Aider обновил: {files}."
            if verified:
                msg += f" Проверено: {', '.join(sorted(verified))}."
            if tail:
                msg += f"\n\n{tail[-1200:]}"
        elif tail:
            msg = tail[-2000:]
        else:
            msg = "Aider завершил шаг."

        if edited or verified:
            try:
                mem = (
                    "# Project memory\n\n"
                    f"- Aider: {', '.join(edited[:6]) or 'ответ без файлов'}\n"
                )
                if self.file_service is not None:
                    await self.file_service.write_file(MEMORY_REL_PATH, mem)
            except Exception:
                pass
            self._snapshot_lesson(edited, verified, how="aider", ok=True)
            self._remember_code_lesson(
                user_task or current_prompt,
                ok=True,
                how="aider",
                files=edited,
            )

        self._broadcast("chat", "CoreX", msg)
        return msg

    async def _run_agent_loop(
        self,
        *,
        current_prompt: str,
        llm_history: list[dict],
        active_root: Path,
        conversational: bool,
        is_question: bool,
        requires_writes: bool,
        persona_id: str | None,
        enforce_writes: bool = False,
        require_verification: bool = False,
        local_num_predict: int | None = None,
        json_target_path: str | None = None,
        local_compact: bool = False,
        user_task: str = "",
    ) -> str | None:
        if getattr(self, "_coding_engine", "aider") == "aider" and not conversational:
            return await self._run_via_aider(
                current_prompt=current_prompt,
                active_root=active_root,
                conversational=conversational,
                is_question=is_question,
                requires_writes=requires_writes,
                persona_id=persona_id,
                require_verification=require_verification,
                json_target_path=json_target_path,
                user_task=user_task,
            )
        cancelled = False
        try:
            return await self._run_agent_loop_body(
                current_prompt=current_prompt,
                llm_history=llm_history,
                active_root=active_root,
                conversational=conversational,
                is_question=is_question,
                requires_writes=requires_writes,
                persona_id=persona_id,
                enforce_writes=enforce_writes,
                require_verification=require_verification,
                local_num_predict=local_num_predict,
                json_target_path=json_target_path,
                local_compact=local_compact,
                user_task=user_task,
            )
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as exc:
            pending = getattr(self, "_pending_lesson", None) or {}
            self._pending_lesson = {
                **pending,
                "ok": False,
                "how": "exception",
                "error": str(exc)[:120],
            }
            raise
        finally:
            if (
                not cancelled
                and not conversational
                and not is_question
                and (requires_writes or enforce_writes)
            ):
                self._flush_pending_lesson(user_task)

    async def _run_agent_loop_body(
        self,
        *,
        current_prompt: str,
        llm_history: list[dict],
        active_root: Path,
        conversational: bool,
        is_question: bool,
        requires_writes: bool,
        persona_id: str | None,
        enforce_writes: bool = False,
        require_verification: bool = False,
        local_num_predict: int | None = None,
        json_target_path: str | None = None,
        local_compact: bool = False,
        user_task: str = "",
    ) -> str | None:
        """Один цикл агента (один скил или один этап конвейера)."""
        from core.web_delivery_layers import (
            is_web_site_task,
            maybe_autofill_salvaged_web,
            missing_web_deliverables,
            web_file_quality_issues,
            web_quality_hint,
        )

        confirmed_writes: list[str] = []
        viewed_files: set[str] = set()
        py_files_written: set[str] = set()
        verified_py_files: set[str] = set()
        terminal_checks_ok = 0
        memory_updated_this_task = False
        project_files_written = False
        json_parse_attempts = 0
        done_blocked_attempts = 0
        verify_fail_streak: dict[str, tuple[str, int]] = {}
        patch_line_history: dict[str, list[int]] = {}
        stalled_patch_skips: dict[str, int] = {}
        noop_append_counts: dict[str, int] = {}
        web_pending_polish: set[str] = set()
        web_task = is_web_site_task(
            user_task,
            current_prompt[:500],
            coding_language=getattr(self, "_coding_language", "auto"),
        )
        must_write = requires_writes or enforce_writes
        max_prompt_chars = 6_000 if local_compact else 28_000
        active_for_retries = self._resolve_llm()
        max_json_retries = (
            4 if active_for_retries.mode == "local" and local_compact else MAX_JSON_PARSE_RETRIES
        )

        from core.workload_limits_service import get_design_folder_path, is_step_by_step_enabled
        from core.step_execution import (
            MAX_GUI_FILE_WRITES,
            current_write_target,
            format_plan_for_prompt,
            format_plan_overview,
            gui_partial_stop_message,
            gui_app_window_plan,
            gui_window_bites_plan,
            is_gui_app_plan,
            is_gui_bite_plan,
            mark_step_completed,
            next_step_hint,
            pending_gui_bite,
            pick_execution_plan,
            should_block_done_for_plan,
            sync_gui_app_from_source,
            sync_gui_bites_from_source,
        )
        from core.file_plan import should_ask_file_plan, steps_from_file_plan

        app_root = self._app_root()
        design_folder = get_design_folder_path(app_root)
        execution_steps: list = []
        completed_plan_steps: set[str] = set()
        gui_stuck_writes = 0
        last_smoke_detail = ""
        if (
            is_step_by_step_enabled(app_root)
            and must_write
            and not conversational
            and not is_question
        ):
            from core.game_gui_upgrade import (
                looks_like_gui_window_request,
                should_use_gui_game_bites_plan,
            )

            if not web_task and should_use_gui_game_bites_plan(user_task):
                target = resolve_gui_fallback_path(
                    user_task, json_target_path, active_root
                )
                execution_steps = gui_window_bites_plan(
                    path=target, user_task=user_task
                )
                json_target_path = target
            elif not web_task and looks_like_gui_window_request(user_task):
                target = resolve_gui_fallback_path(
                    user_task, json_target_path, active_root
                )
                execution_steps = gui_app_window_plan(
                    path=target, user_task=user_task
                )
                json_target_path = target
            elif should_ask_file_plan(
                user_task,
                is_web=web_task,
                write_dest=json_target_path,
                persona_id=persona_id,
            ):
                planned = await self._propose_file_plan(
                    user_task,
                    write_dest=json_target_path,
                )
                execution_steps = steps_from_file_plan(planned)
                if planned:
                    json_target_path = planned[0]
            else:
                execution_steps = pick_execution_plan(
                    user_task=user_task,
                    agent_id=persona_id or "",
                    design_folder=design_folder,
                    has_design_folder=(active_root / design_folder).is_dir(),
                    coding_language=getattr(self, "_coding_language", "auto"),
                )
            # Съесть слона по кусочкам: только overview + текущий шаг (без всей простыни).
            current_prompt += "\n" + format_plan_for_prompt(execution_steps) + "\n"
            self._broadcast_thinking(
                f"Поэтапно: {format_plan_overview(execution_steps)}"
            )

        idle_llm_turns = 0
        while True:
            plan_target = current_write_target(execution_steps, completed_plan_steps)
            if plan_target:
                json_target_path = plan_target
            idle_llm_turns += 1
            if idle_llm_turns >= IDLE_NO_CODE_TURNS:
                if is_gui_bite_plan(execution_steps) and confirmed_writes:
                    target = (
                        current_write_target(execution_steps, completed_plan_steps)
                        or confirmed_writes[-1]
                    )
                    launch_ok = True
                    if self._is_python_source(target) and self._verify_file_on_disk(target):
                        smoke = await self._self_test_python(active_root, target)
                        launch_ok = bool(smoke.get("ok"))
                        if not launch_ok:
                            detail = compact_runtime_detail(str(smoke.get("detail") or ""))
                            msg = (
                                f"Запуск {target} падает, модель перестала чинить.\n{detail[:800]}"
                            )
                            self._broadcast_thinking("Стоп: запуск с ошибкой")
                            self._broadcast("chat", "CoreX Error", msg)
                            self._snapshot_lesson(
                                confirmed_writes,
                                verified_py_files,
                                how="gui_idle_crash",
                                ok=False,
                                error=detail[:400],
                            )
                            return msg
                    msg = gui_partial_stop_message(
                        execution_steps, completed_plan_steps, target
                    )
                    if launch_ok and "запуск" not in msg.lower():
                        msg = msg.rstrip(".") + ". Запуск без ошибок."
                    self._broadcast_thinking("Нет прогресса по шагам окна — стоп")
                    self._broadcast("chat", "CoreX Status", msg)
                    self._snapshot_lesson(
                        confirmed_writes,
                        verified_py_files,
                        how="gui_idle",
                        ok=True,
                    )
                    return msg
                fallback = await self._try_gui_window_fallback(
                    active_root, user_task, confirmed_writes, rel_path=json_target_path
                )
                if fallback:
                    return fallback
                self._snapshot_lesson(
                    confirmed_writes,
                    verified_py_files,
                    how="idle_no_code",
                    ok=False,
                )
                channel, message = idle_stop_chat(
                    confirmed_writes, turns=IDLE_NO_CODE_TURNS
                )
                self._broadcast("chat", channel, message)
                return message if channel == "CoreX Status" else None

            if len(current_prompt) > max_prompt_chars:
                current_prompt = current_prompt[-max_prompt_chars:]
            if self._budget and not self._budget.can_turn():
                reason = self._budget.stop_reason() or "Лимит нагрузки для защиты ПК."
                self._broadcast_thinking(reason)
                self._broadcast("chat", "CoreX", reason)
                return None

            if self._budget:
                await self._budget.pause_turn()

            self._broadcast_thinking(f"Генерирую ответ ({self._active_reply_model or llm_thinking_label(self._resolve_llm())})...")
            response_text = ""
            active = self._resolve_llm()
            llm_meta = self._trace_llm_meta(active)
            self._broadcast_trace(
                "llm",
                "llm_start",
                "Запрос к модели",
                node="llm",
                status="active",
                meta=llm_meta,
                detail=make_detail(
                    "llm_request",
                    title="Промпт агента",
                    body=current_prompt,
                    language="markdown",
                    request={"history_turns": len(llm_history or [])},
                ),
            )
            if not await self._ensure_online_token_budget(active):
                return None
            stream_temp = 0.5 if conversational else (0.25 if is_question else 0.1)
            predict = local_num_predict
            use_json_mode = not (
                active.mode == "local" and must_write and not conversational and not is_question
            )
            if active.mode == "local":
                if not predict:
                    predict = 512 if conversational or is_question or local_compact else 2048
                response_text = await active.client.chat_complete(
                    self.system_prompt,
                    current_prompt,
                    history=llm_history,
                    temperature=stream_temp,
                    json_mode=use_json_mode,
                    num_predict=predict,
                )
            else:
                stream_kwargs: dict = {
                    "temperature": stream_temp,
                    "json_mode": use_json_mode,
                }
                swap_model = getattr(active.client, "temporary_model", None)
                if callable(swap_model) and self._active_reply_model:
                    with swap_model(self._active_reply_model):
                        async for chunk in active.client.generate_stream(
                            self.system_prompt,
                            current_prompt,
                            history=llm_history,
                            **stream_kwargs,
                        ):
                            response_text += chunk
                else:
                    async for chunk in active.client.generate_stream(
                        self.system_prompt,
                        current_prompt,
                        history=llm_history,
                        **stream_kwargs,
                    ):
                        response_text += chunk
            self._drain_model_switch_notices(active.client)

            if self._budget:
                self._budget.record_llm_call()

            self._broadcast_trace(
                "llm",
                "llm_response",
                f"Ответ модели ({len(response_text)} симв.)",
                node="llm",
                status="done",
                meta={**llm_meta, "chars": len(response_text)},
                detail=make_detail(
                    "llm_response",
                    title="Ответ модели",
                    body=response_text,
                    language="json",
                ),
            )

            if not self._record_online_usage(active, label="agent"):
                return None

            if is_online_api_failure(response_text):
                self._broadcast("chat", "CoreX Error", response_text.strip())
                self._snapshot_lesson(
                    confirmed_writes,
                    verified_py_files,
                    how="llm_error",
                    error=response_text.strip()[:120],
                    ok=False,
                )
                return None

            cleaned_text = self._clean_response(response_text)
            raw_decision = parse_agent_json(
                cleaned_text, default_path=json_target_path
            ) or parse_agent_json(response_text, default_path=json_target_path)
            if json_target_path and isinstance(raw_decision, dict):
                tool_name = str(raw_decision.get("tool") or "")
                args = raw_decision.get("arguments")
                if tool_name in {
                    "write_file",
                    "append_file",
                    "patch_file",
                    "view_file",
                    "run_file",
                } and isinstance(args, dict):
                    raw_decision = {
                        **raw_decision,
                        "arguments": {
                            **args,
                            "path": remap_write_path(
                                args.get("path"),
                                json_target_path,
                                user_task=user_task,
                                project_root=active_root,
                            ),
                        },
                    }
            salvaged_truncated = bool(
                isinstance(raw_decision, dict) and raw_decision.pop("_salvaged_truncated", False)
            )
            decision = raw_decision

            if decision is None:
                json_parse_attempts += 1
                if json_parse_attempts >= max_json_retries:
                    self._broadcast(
                        "chat",
                        "CoreX Error",
                        "Модель не вернула ни JSON, ни код в блоке ```. "
                        "Упростите запрос или повторите.",
                    )
                    self._broadcast_trace(
                        "llm",
                        "json_error",
                        "Некорректный JSON от модели",
                        node="llm",
                        status="error",
                        detail=make_detail(
                            "error",
                            title="Сырой ответ",
                            body=cleaned_text or response_text,
                            language="json",
                        ),
                        error_message="Модель не вернула корректный JSON после нескольких попыток",
                    )
                    self._snapshot_lesson(
                        confirmed_writes,
                        verified_py_files,
                        how="json_fail",
                        ok=False,
                    )
                    return None
                self._broadcast_trace(
                    "llm",
                    "json_retry",
                    f"Повтор JSON ({json_parse_attempts}/{max_json_retries})",
                    node="llm",
                    status="error",
                    detail=make_detail(
                        "error",
                        title="Не удалось разобрать",
                        body=(cleaned_text or response_text)[:4000],
                        language="json",
                    ),
                    error_message=f"Ошибка формата JSON, попытка {json_parse_attempts}",
                )
                self._broadcast_thinking("Ошибка формата JSON, прошу исправить...")
                snippet = cleaned_text[:400].replace("\n", " ")
                retry_target = json_target_path
                if json_target_path and confirmed_writes:
                    written_lower = {p.replace("\\", "/").lower() for p in confirmed_writes}
                    if json_target_path.lower() == "index.html" and "index.html" in written_lower:
                        if "style.css" not in written_lower and "styles.css" not in written_lower:
                            retry_target = "style.css"
                current_prompt += json_retry_hint(
                    json_parse_attempts,
                    snippet,
                    target_path=retry_target,
                )
                continue

            if self._budget:
                self._budget.record_step_turn()

            json_parse_attempts = 0
            actions = [decision]

            if not actions:
                current_prompt += (
                    f"\nAssistant: {cleaned_text}\n"
                    "System Error: Empty JSON. Return act or done."
                )
                continue

            for action in actions:
                if not isinstance(action, dict):
                    break

                action = normalize_agent_action(action, raw_text=cleaned_text or response_text)
                status = action.get("status")

                if status == "done":
                    done_message = action.get("message", "Готово")
                    self._broadcast_trace(
                        "task",
                        "agent_done",
                        "Модель: готово",
                        node="response",
                        status="done",
                        meta={"message_preview": str(done_message)[:120]},
                    )

                    if conversational or is_question:
                        self._broadcast("chat", "CoreX Status", done_message)
                        return done_message

                    blockers: list[str] = []
                    if must_write and not confirmed_writes:
                        blockers.append("no_writes")
                    elif (
                        not confirmed_writes
                        and self._message_claims_fix_without_write(done_message)
                    ):
                        blockers.append("no_writes")

                    if project_files_written and not memory_updated_this_task:
                        blockers.append("memory")

                    if should_block_done_for_plan(
                        execution_steps, completed_plan_steps, is_web=web_task
                    ):
                        blockers.append("plan_incomplete")

                    if web_task and web_pending_polish:
                        blockers.append("web_polish")

                    if web_task:
                        missing_web = missing_web_deliverables(active_root)
                        if missing_web:
                            blockers.append("web_polish")
                            web_pending_polish.update(
                                name for name in ("index.html", "style.css", "script.js")
                                if any(name in item for item in missing_web)
                            )

                    if web_task and json_target_path and "design-system" in json_target_path.replace("\\", "/"):
                        from core.design_handoff import validate_design_handoff

                        handoff = validate_design_handoff(active_root, app_root=self._app_root())
                        if not handoff.ok:
                            blockers.append("design_handoff")

                    verified_py_files = await self._drop_broken_syntax_from_verified(
                        active_root, py_files_written, verified_py_files
                    )
                    unverified_py = py_files_written - verified_py_files
                    if unverified_py:
                        blockers.append("unverified")

                    if self._needs_runtime_blocker(
                        require_verification=require_verification,
                        py_files_written=py_files_written,
                        verified_py_files=verified_py_files,
                        terminal_checks_ok=terminal_checks_ok,
                        confirmed_writes=confirmed_writes,
                    ):
                        target = self._pick_smoke_script(
                            confirmed_writes, py_files_written
                        )
                        if target:
                            smoke = await self._self_test_python(active_root, target)
                            if smoke.get("ok"):
                                terminal_checks_ok += 1
                            else:
                                last_smoke_detail = compact_runtime_detail(
                                    str(smoke.get("detail") or "")
                                )
                                blockers.append("runtime")
                        else:
                            blockers.append("runtime")

                    if blockers:
                        done_blocked_attempts += 1
                        if done_blocked_attempts >= MAX_BLOCKED_DONE_RETRIES:
                            self._broadcast_thinking(
                                "Модель зациклилась на done — применяю авто-исправления на диске"
                            )
                            auto = await self._auto_resolve_done_blockers(
                                active_root=active_root,
                                blockers=blockers,
                                confirmed_writes=confirmed_writes,
                                verified_py_files=verified_py_files,
                                py_files_written=py_files_written,
                                verify_fail_streak=verify_fail_streak,
                                terminal_checks_ok=terminal_checks_ok,
                                memory_updated_this_task=memory_updated_this_task,
                                project_files_written=project_files_written,
                            )
                            memory_updated_this_task = auto["memory_updated_this_task"]
                            terminal_checks_ok = auto["terminal_checks_ok"]
                            verified_py_files = auto["verified_py_files"]
                            confirmed_writes = auto["confirmed_writes"]
                            py_files_written = auto["py_files_written"]
                            project_files_written = auto["project_files_written"]
                            verified_py_files = await self._drop_broken_syntax_from_verified(
                                active_root, py_files_written, verified_py_files
                            )
                            self._snapshot_lesson(confirmed_writes, verified_py_files)

                            blockers = []
                            if must_write and not confirmed_writes:
                                blockers.append("no_writes")
                            if project_files_written and not memory_updated_this_task:
                                blockers.append("memory")
                            if py_files_written - verified_py_files:
                                blockers.append("unverified")
                            if self._needs_runtime_blocker(
                                require_verification=require_verification,
                                py_files_written=py_files_written,
                                verified_py_files=verified_py_files,
                                terminal_checks_ok=terminal_checks_ok,
                                confirmed_writes=confirmed_writes,
                            ):
                                blockers.append("runtime")
                            if should_block_done_for_plan(
                                execution_steps, completed_plan_steps, is_web=web_task
                            ):
                                blockers.append("plan_incomplete")

                            if not blockers:
                                done_blocked_attempts = 0
                                note = ", ".join(auto.get("resolved_items") or [])
                                final_message = done_message
                                if note:
                                    final_message = f"{done_message}\n(авто: {note})"
                                if py_files_written and terminal_checks_ok > 0:
                                    if "запуск" not in final_message.lower():
                                        final_message = (
                                            final_message.rstrip(".") + ". Запуск без ошибок."
                                        )
                                self._broadcast_thinking("Готов с результатом")
                                self._broadcast("chat", "CoreX Status", final_message)
                                self._snapshot_lesson(
                                    confirmed_writes,
                                    verified_py_files,
                                    how="verified" if verified_py_files else "wrote",
                                    ok=True,
                                )
                                return final_message

                            hard_blockers = [
                                item
                                for item in blockers
                                if item not in {"plan_incomplete", "runtime"}
                            ]
                            if hard_blockers and is_gui_bite_plan(execution_steps):
                                target = (
                                    current_write_target(execution_steps, completed_plan_steps)
                                    or (confirmed_writes[-1] if confirmed_writes else "game.py")
                                )
                                msg = gui_partial_stop_message(
                                    execution_steps, completed_plan_steps, target
                                )
                                self._broadcast_thinking(
                                    "Останавливаю цикл done — шаги окна дальше не идут"
                                )
                                self._broadcast("chat", "CoreX Status", msg)
                                self._snapshot_lesson(
                                    confirmed_writes,
                                    verified_py_files,
                                    how="gui_partial",
                                    ok=True,
                                )
                                return msg

                            done_blocked_attempts = 0

                        blocker_lines = []
                        if "no_writes" in blockers:
                            target = self._pick_entry_script() or "main.py"
                            blocker_lines.append(
                                "System Error: Cannot return done before patch_file/write_file Success. "
                                f'Next: {{"status":"act","server":"filesystem","tool":"view_file","arguments":{{"path":"{target}"}}}}'
                            )
                        if "memory" in blockers:
                            blocker_lines.append(
                                'System Error: Update chat/project_memory.md before done. '
                                f'Next: {{"status":"act","server":"filesystem","tool":"write_file",'
                                f'"arguments":{{"path":"{MEMORY_REL_PATH}","content":"# memory\\n"}}}}'
                            )
                        if "unverified" in blockers:
                            names = ", ".join(sorted(py_files_written - verified_py_files))
                            blocker_lines.append(
                                f"System Error: Python files failed auto-verify: {names}. "
                                "Fix with view_file then patch_file (one line per turn). "
                                "Do NOT return done until verify passes."
                            )
                        if "runtime" in blockers:
                            entry = (
                                self._pick_smoke_script(confirmed_writes, py_files_written)
                                or "main.py"
                            )
                            crash = last_smoke_detail or getattr(self, "_last_smoke_detail", "") or ""
                            blocker_lines.append(
                                f"System Error: Запуск {entry} не прошёл — done нельзя. "
                                "Найди причину (traceback ниже) и исправь write_file/patch_file.\n"
                                f"{crash[:1800]}"
                            )
                        if "web_polish" in blockers:
                            pending = ", ".join(sorted(web_pending_polish)) or "style.css/script.js"
                            disk_gaps = missing_web_deliverables(active_root)
                            gap_text = "; ".join(disk_gaps[:4]) if disk_gaps else pending
                            blocker_lines.append(
                                f"System Error: Вёрстка сайта не готова ({gap_text}). "
                                "Нужны качественные index.html + style.css (тёмный gradient) + script.js "
                                "(nav/smooth scroll/CTA). Не возвращайте done."
                            )
                        if "design_handoff" in blockers:
                            blocker_lines.append(
                                "System Error: Design Spec не сохранён на диск. "
                                "Следующие ходы: write_file design-system/MASTER.md, "
                                "write_file design-system/pages/index.md, "
                                "write_file design-system/blocks/hero.md. "
                                "Нельзя done пока файлы не записаны."
                            )
                        if "plan_incomplete" in blockers:
                            pending = next_step_hint(execution_steps, completed_plan_steps)
                            blocker_lines.append(
                                pending
                                or "System Error: План не выполнен. Продолжайте поэтапно — один tool за ход."
                            )

                        current_prompt += (
                            f"\nAssistant: {cleaned_text}\n"
                            + "\n".join(blocker_lines)
                            + "\nSystem: done пока нельзя. Не копируй этот текст в файл. "
                            + "Исправь код или верни write_file с чистым исходником.\n"
                        )
                        break

                    done_blocked_attempts = 0
                    if py_files_written and terminal_checks_ok > 0:
                        if "запуск" not in done_message.lower():
                            done_message = done_message.rstrip(".") + ". Запуск без ошибок."
                    self._broadcast_thinking("Готов с результатом")
                    self._broadcast("chat", "CoreX Status", done_message)
                    self._snapshot_lesson(
                        confirmed_writes,
                        verified_py_files,
                        how="verified" if verified_py_files else "wrote",
                        ok=True,
                    )
                    return done_message

                if status != "act" or conversational or is_question:
                    break

                server = action.get("server")
                tool = action.get("tool")
                args = action.get("arguments", {})

                self._broadcast_trace(
                    "tool",
                    "tool_call",
                    f"{server}.{tool}",
                    node="tool",
                    status="active",
                    meta={
                        "server": server,
                        "tool": tool,
                        "path": args.get("path") or args.get("command", "")[:80],
                    },
                    detail=make_detail(
                        "tool_request",
                        title=f"{server}.{tool}",
                        arguments=args if isinstance(args, dict) else {},
                        path=str(args.get("path") or "") if isinstance(args, dict) else "",
                        body=json.dumps(args, ensure_ascii=False, indent=2) if isinstance(args, dict) else "",
                        language="json",
                    ),
                )

                if server == "terminal":
                    if tool not in {"run_file", "run_command"}:
                        break
                    if tool == "run_file":
                        rel_path = self._normalize_rel_path(args.get("path", ""))
                        self._broadcast_thinking(f"Запускаю файл: {rel_path}")
                    else:
                        self._broadcast_thinking(f"Команда: {args.get('command', '')[:80]}")

                    result = await self._execute_terminal_tool(tool, args, active_root)
                    serialized_result = self._serialize_tool_result(result)
                    term_ok = isinstance(result, dict) and result.get("status") == "Success"
                    self._broadcast_trace(
                        "tool",
                        "tool_result",
                        f"Терминал: {'OK' if term_ok else 'ошибка'}",
                        node="tool",
                        status="done" if term_ok else "error",
                        meta={"server": server, "tool": tool, "exit_code": result.get("exit_code") if isinstance(result, dict) else None},
                        detail=make_detail(
                            "tool_response",
                            title=f"Результат {tool}",
                            result=result if isinstance(result, dict) else {"raw": str(result)},
                            body=serialized_result,
                            language="json",
                        ),
                        error_message=None if term_ok else str(result.get("message", "Ошибка терминала") if isinstance(result, dict) else result),
                    )
                    if term_ok:
                        terminal_checks_ok += 1
                        self._broadcast(
                            "chat",
                            "CoreX",
                            f"Проверка OK: {tool} (код {result.get('exit_code', 0)})",
                        )
                    else:
                        err = result.get("message", "Unknown") if isinstance(result, dict) else str(result)
                        out = result.get("output", "") if isinstance(result, dict) else ""
                        self._broadcast("chat", "CoreX Error", f"Проверка не прошла: {err[:500]}")
                        if "command is required" in err.lower():
                            retry_hint = (
                                "System Error: run_command requires arguments.command "
                                '(example: {"status":"act","server":"terminal","tool":"run_command",'
                                '"arguments":{"command":"python main.py","cwd":"."}}). '
                                "For new files prefer write_file first.\n"
                            )
                        else:
                            retry_hint = (
                                "System Error: Run/check failed. Fix the code with patch_file, then run again.\n"
                            )
                        current_prompt += (
                            f"\nAssistant: {cleaned_text}\n"
                            f"Tool result: {serialized_result}\n"
                            f"{retry_hint}"
                        )
                        continue

                    current_prompt += (
                        f"\nAssistant: {cleaned_text}\n"
                        f"Tool result: {serialized_result}\n"
                    )
                    continue

                from core.web_access import get_web_access_mode
                from core.web_search import is_web_search_tool, search_web

                if is_web_search_tool(server, tool):
                    if get_web_access_mode() == "never":
                        result = {
                            "status": "Error",
                            "message": "Поиск в интернете выключен в настройках.",
                        }
                    else:
                        query = ""
                        if isinstance(args, dict):
                            query = str(args.get("query") or args.get("q") or "").strip()
                        if not query:
                            query = user_task
                        self._broadcast_thinking(f"Ищу в интернете: {query[:80]}")
                        try:
                            payload = await asyncio.to_thread(search_web, query)
                        except Exception as exc:
                            payload = {"ok": False, "error": str(exc), "text": ""}
                        text = str(payload.get("text") or payload.get("error") or "Нет результатов")
                        result = {
                            "status": "Success" if payload.get("ok") else "Error",
                            "message": text[:1400],
                            "query": payload.get("query") or query,
                        }
                    serialized_result = self._serialize_tool_result(result)
                    self._broadcast_trace(
                        "tool",
                        "tool_result",
                        "Поиск в интернете",
                        node="tool",
                        status="done" if result.get("status") == "Success" else "error",
                        meta={"server": "web", "tool": "search_web"},
                        detail=make_detail(
                            "tool_response",
                            title="search_web",
                            result=result,
                            body=serialized_result,
                            language="json",
                        ),
                    )
                    current_prompt += (
                        f"\nAssistant: {cleaned_text}\n"
                        f"Tool result: {serialized_result}\n"
                        "Use as hints. Next: write the complete working file. Do not search again.\n"
                    )
                    continue

                if server != "filesystem":
                    break
                if tool not in {"list_directory", "view_file", "write_file", "append_file", "patch_file"}:
                    break

                memory_paths = {MEMORY_REL_PATH, "chat/project_memory.md"}

                if tool in {"write_file", "append_file", "patch_file"}:
                    if self._budget and not self._budget.can_write():
                        self._broadcast("chat", "CoreX", self._budget.stop_reason() or "Лимит записей.")
                        return self._budget.stop_reason()

                if json_target_path and tool in {
                    "write_file",
                    "append_file",
                    "patch_file",
                    "view_file",
                }:
                    args = {
                        **args,
                        "path": remap_write_path(
                            args.get("path"),
                            json_target_path,
                            user_task=user_task,
                            project_root=active_root,
                        ),
                    }
                if tool in {"write_file", "append_file"} and ("content" not in args or "path" not in args):
                    break
                if tool in {"write_file", "append_file"}:
                    cleaned_chunk = sanitize_code_chunk(str(args.get("content") or ""))
                    if is_protocol_leak(cleaned_chunk) or not cleaned_chunk.strip():
                        current_prompt += (
                            "\nSystem: В файл попала инструкция, а не код. "
                            "Повтори ход: JSON с path, затем блок ``` только с исходником "
                            "(import/def/class). Не копируй текст System в файл.\n"
                        )
                        continue
                    args = {**args, "content": cleaned_chunk}
                    if tool == "write_file":
                        from core.file_outline import prepare_source_write

                        existing_text = ""
                        on_disk = await self.file_service.read_file(
                            str(args.get("path") or "")
                        )
                        if isinstance(on_disk, dict) and "error" not in on_disk:
                            existing_text = str(on_disk.get("content") or "")
                        gated = prepare_source_write(
                            str(args.get("path") or ""),
                            cleaned_chunk,
                            existing=existing_text,
                        )
                        if gated.get("error"):
                            fallback = await self._try_gui_window_fallback(
                                active_root, user_task, confirmed_writes, rel_path=json_target_path
                            )
                            if fallback:
                                return fallback
                            current_prompt += (
                                f"\nAssistant: {cleaned_text}\n"
                                f"System: {gated['error']} "
                                "Повтори ход: один полный блок ```python ... ``` без JSON-заглушки.\n"
                            )
                            continue
                        args = {**args, "content": gated.get("content") or cleaned_chunk}
                if tool == "patch_file":
                    if "path" not in args:
                        break
                    if not (args.get("operations") or args.get("op")):
                        break

                rel_path = self._normalize_rel_path(args.get("path", ""))
                if tool == "view_file":
                    viewed_files.add(rel_path)
                    if not is_corex_internal_path(rel_path):
                        self._broadcast_thinking(f"Читаю файл: {rel_path}")
                elif tool == "patch_file":
                    web_ext = rel_path.lower().endswith((".html", ".css", ".js"))
                    if web_task and web_ext:
                        current_prompt += (
                            f"\nAssistant: {cleaned_text}\n"
                            f"System Error: Для веб-файлов ({rel_path}) patch_file ЗАПРЕЩЁН. "
                            "Используй write_file с ПОЛНЫМ содержимым файла одним ходом. "
                            'Пример: {"status":"act","server":"filesystem","tool":"write_file",'
                            f'"arguments":{{"path":"{rel_path}","content":"..."}}}}\n'
                        )
                        continue
                    if (
                        self._verify_file_on_disk(rel_path)
                        and rel_path not in viewed_files
                    ):
                        view_payload = await self._auto_view_file(
                            rel_path,
                            active_root=active_root,
                            verify_fail_streak=verify_fail_streak,
                        )
                        viewed_files.add(rel_path)
                        current_prompt += (
                            f"\nSystem: Auto view_file before patch on {rel_path}.\n"
                            f"Tool result: {view_payload}\n"
                        )
                    op_line = ""
                    ops = args.get("operations") or [args]
                    target_line = None
                    if ops and isinstance(ops[0], dict):
                        target_line = ops[0].get("line")
                        op_line = f" (строка {target_line})"
                    if target_line and rel_path in verify_fail_streak:
                        fail_detail = verify_fail_streak[rel_path][0]
                        history = patch_line_history.setdefault(rel_path, [])
                        repeats = history.count(int(target_line))
                        if repeats >= 2 and (
                            "SyntaxError" in fail_detail
                            or "IndentationError" in fail_detail
                        ):
                            self._broadcast_thinking(
                                f"Строка {target_line} уже правилась {repeats}x — авто-ремонт синтаксиса"
                            )
                            syntax_fix = await asyncio.to_thread(
                                repair_file_on_disk,
                                active_root,
                                rel_path,
                                verify_fail_streak[rel_path][0],
                            )
                            if syntax_fix.get("ok"):
                                self._broadcast_editor_patch(
                                    rel_path,
                                    syntax_fix.get("content", ""),
                                    syntax_fix.get("highlights") or [],
                                )
                                self._broadcast(
                                    "chat",
                                    "CoreX",
                                    f"Авто-ремонт синтаксиса: {syntax_fix.get('message', rel_path)}",
                                )
                                verify = await self._auto_verify_python_write(
                                    active_root, rel_path
                                )
                                if verify.get("ok"):
                                    verified_py_files.add(rel_path)
                                    patch_line_history[rel_path] = []
                                    stalled_patch_skips.pop(rel_path, None)
                                    verify_fail_streak.pop(rel_path, None)
                                    self._snapshot_lesson(
                                        confirmed_writes,
                                        verified_py_files,
                                        how="repair",
                                    )
                                    current_prompt += (
                                        f"\nSystem: Syntax auto-repair OK on {rel_path}. "
                                        "Continue or return done.\n"
                                    )
                                    continue
                            skips = stalled_patch_skips.get(rel_path, 0) + 1
                            stalled_patch_skips[rel_path] = skips
                            if skips >= 3:
                                self._broadcast(
                                    "chat",
                                    "CoreX Error",
                                    f"Слишком много одинаковых правок {rel_path} "
                                    f"(строка {target_line}). Останавливаю цикл, "
                                    "чтобы модель не зациклилась на JSON_RETRY.",
                                )
                                self._snapshot_lesson(
                                    confirmed_writes,
                                    verified_py_files,
                                    how="patch_loop",
                                    error=f"{rel_path}:{target_line}",
                                    ok=False,
                                )
                                return None
                            current_prompt += (
                                f"\nAssistant: {cleaned_text}\n"
                                f"System Error: Line {target_line} failed {repeats} times. "
                                "Do NOT patch it again. Use op delete on orphan else: lines "
                                "from bottom to top, or view_file and fix the whole block. "
                                "Or append_file the next NEW functions only.\n"
                            )
                            continue
                        history.append(int(target_line))
                    if not is_corex_internal_path(rel_path):
                        self._broadcast_thinking(f"Правлю файл: {rel_path}{op_line}")
                elif tool == "write_file":
                    allow_web_rewrite = web_task and rel_path.lower().endswith((".css", ".html", ".js"))
                    allow_code_overwrite = (
                        self._is_python_source(rel_path)
                        and not looks_like_fix_request(user_task)
                    )
                    if (
                        not allow_web_rewrite
                        and not allow_code_overwrite
                        and self._verify_file_on_disk(rel_path)
                        and rel_path not in viewed_files
                        and rel_path not in memory_paths
                    ):
                        view_payload = await self._auto_view_file(
                            rel_path,
                            active_root=active_root,
                            verify_fail_streak=verify_fail_streak,
                        )
                        viewed_files.add(rel_path)
                        current_prompt += (
                            f"\nAssistant: {cleaned_text}\n"
                            f"System Error: {rel_path} already exists. "
                            "Use patch_file for edits (one line per turn).\n"
                            f"Auto view_file result: {view_payload}\n"
                        )
                        break
                    if (
                        not allow_web_rewrite
                        and not allow_code_overwrite
                        and self._verify_file_on_disk(rel_path)
                        and rel_path in viewed_files
                        and rel_path not in memory_paths
                    ):
                        current_prompt += (
                            f"\nAssistant: {cleaned_text}\n"
                            f"System Error: {rel_path} is open for editing. "
                            "Use patch_file (one line per turn), not write_file."
                        )
                        break
                    if not is_corex_internal_path(rel_path):
                        self._broadcast_thinking(f"Записываю на диск: {rel_path}")
                elif tool == "append_file":
                    if (
                        self._verify_file_on_disk(rel_path)
                        and rel_path not in viewed_files
                    ):
                        view_payload = await self._auto_view_file(
                            rel_path,
                            active_root=active_root,
                            verify_fail_streak=verify_fail_streak,
                        )
                        viewed_files.add(rel_path)
                        current_prompt += (
                            f"\nSystem: Текущий {rel_path} уже на диске. "
                            "append_file — только НОВЫЙ код. Не повторяй import и строки, которые уже есть. "
                            "Не пиши в файл служебные фразы.\n"
                            f"Tool result: {view_payload}\n"
                        )
                    if not is_corex_internal_path(rel_path):
                        self._broadcast_thinking(f"Дописываю файл: {rel_path}")
                elif not is_corex_internal_path(str(args.get("path", "."))):
                    self._broadcast_thinking(f"Просматриваю: {args.get('path', '.')}")

                result = await self._execute_filesystem_tool(tool, args)
                fs_ok = filesystem_tool_succeeded(result)
                focus_line = None
                if tool == "view_file" and rel_path in verify_fail_streak:
                    focus_line = self._extract_error_line(verify_fail_streak[rel_path][0])
                compact = compact_tool_result_for_prompt(
                    tool,
                    result if isinstance(result, dict) else {},
                    focus_line=focus_line,
                )
                serialized_result = self._serialize_tool_result(compact)
                file_body = ""
                file_lang = "json"
                if tool in {"write_file", "append_file"} and isinstance(args, dict):
                    file_body = str(args.get("content") or "")
                    ext = str(args.get("path", "")).lower()
                    if ext.endswith(".html"):
                        file_lang = "html"
                    elif ext.endswith(".md"):
                        file_lang = "markdown"
                    else:
                        file_lang = "text"
                elif tool == "view_file" and isinstance(result, dict):
                    inner = result.get("result") or {}
                    file_body = str(inner.get("numbered_content") or inner.get("content") or "")
                    file_lang = "text"
                self._broadcast_trace(
                    "tool",
                    "tool_result",
                    f"Файлы: {tool} — {'OK' if fs_ok else 'ошибка'}",
                    node="tool",
                    status="done" if fs_ok else "error",
                    meta={"tool": tool, "path": rel_path},
                    detail=make_detail(
                        "file_content" if file_body else "tool_response",
                        title=f"{tool}: {rel_path}" if rel_path else tool,
                        path=rel_path,
                        body=file_body or serialized_result,
                        language=file_lang,
                        result=result if isinstance(result, dict) else {"raw": str(result)},
                    ),
                    error_message=None if fs_ok else str(result.get("message", "Ошибка файловой операции") if isinstance(result, dict) else result),
                )

                if tool in {"write_file", "append_file", "patch_file"}:
                    if filesystem_tool_succeeded(result):
                        confirmed_writes.append(rel_path)
                        self._snapshot_lesson(confirmed_writes, verified_py_files)
                        if not result.get("unchanged"):
                            idle_llm_turns = 0
                        if self._budget:
                            self._budget.record_write()
                        if not is_corex_internal_path(rel_path):
                            if tool == "patch_file":
                                hl = result.get("highlights") or []
                                kinds = ", ".join(
                                    f"{item.get('type')}@{item.get('line')}" for item in hl[:3]
                                )
                                self._broadcast(
                                    "chat",
                                    "CoreX",
                                    f"Файл изменён (patch): {rel_path}"
                                    + (f" [{kinds}]" if kinds else ""),
                                )
                            else:
                                action = "обновлён" if rel_path in viewed_files else "записан"
                                self._broadcast(
                                    "chat",
                                    "CoreX",
                                    f"Файл {action}: {rel_path} -> {result.get('absolute_path', '')}",
                                )
                        if rel_path in {MEMORY_REL_PATH, "chat/project_memory.md"}:
                            memory_updated_this_task = True
                        else:
                            project_files_written = True
                            if self._is_python_source(rel_path):
                                py_files_written.add(rel_path)
                                if tool == "append_file" and result.get("unchanged"):
                                    noop_append_counts[rel_path] = (
                                        noop_append_counts.get(rel_path, 0) + 1
                                    )
                                    if noop_append_counts[rel_path] >= 2:
                                        indent_fix = await asyncio.to_thread(
                                            repair_file_on_disk,
                                            active_root,
                                            rel_path,
                                            verify_fail_streak.get(rel_path, ("", 0))[0],
                                        )
                                        if indent_fix.get("ok"):
                                            self._broadcast_editor_patch(
                                                rel_path,
                                                indent_fix.get("content", ""),
                                                indent_fix.get("highlights") or [],
                                            )
                                        verify_now = await self._auto_verify_python_write(
                                            active_root, rel_path
                                        )
                                        if verify_now.get("ok"):
                                            verified_py_files.add(rel_path)
                                            verify_fail_streak.pop(rel_path, None)
                                            self._snapshot_lesson(
                                                confirmed_writes,
                                                verified_py_files,
                                                how="repair",
                                            )
                                        current_prompt += (
                                            f"\nAssistant: {cleaned_text}\n"
                                            f"Tool result: {serialized_result}\n"
                                            f"System: Этот код уже есть в {rel_path}. "
                                            "Не повторяй строки. Верни "
                                            '{"status":"done","message":"Готово"}.\n'
                                        )
                                        if noop_append_counts[rel_path] >= 3:
                                            self._broadcast(
                                                "chat",
                                                "CoreX",
                                                "Куски кода повторяются — завершаю задачу.",
                                            )
                                            self._snapshot_lesson(
                                                confirmed_writes,
                                                verified_py_files,
                                                how="wrote",
                                                ok=True,
                                            )
                                            return "Готово. Код уже записан в файл."
                                        continue
                                elif tool == "append_file":
                                    noop_append_counts[rel_path] = 0
                                skip_verify = tool == "append_file" or salvaged_truncated
                                if skip_verify:
                                    self._broadcast_thinking(
                                        f"Кусок записан без проверки синтаксиса: {rel_path}"
                                    )
                                    indent_fix = await asyncio.to_thread(
                                        repair_file_on_disk,
                                        active_root,
                                        rel_path,
                                        "",
                                    )
                                    if indent_fix.get("ok"):
                                        self._broadcast_editor_patch(
                                            rel_path,
                                            indent_fix.get("content", ""),
                                            indent_fix.get("highlights") or [],
                                        )
                                        self._broadcast_thinking(
                                            f"Поправлены отступы: {rel_path}"
                                        )
                                    on_disk = await self.file_service.read_file(rel_path)
                                    body = str((on_disk or {}).get("content") or "")
                                    syntax_now = await asyncio.to_thread(
                                        verify_python_syntax, active_root, rel_path
                                    )
                                    if syntax_now.get("ok") and looks_like_interactive_python(body):
                                        verify = {
                                            "ok": True,
                                            "phase": "syntax",
                                            "path": rel_path,
                                            "detail": "Синтаксис OK (игру/цикл не запускаем автоматически)",
                                        }
                                    else:
                                        verify = None
                                else:
                                    self._broadcast_thinking(f"Проверяю код: {rel_path}")
                                    verify = await self._auto_verify_python_write(active_root, rel_path)
                                if verify is not None and verify.get("ok"):
                                    verified_py_files.add(rel_path)
                                    self._snapshot_lesson(confirmed_writes, verified_py_files)
                                    self._broadcast(
                                        "chat",
                                        "CoreX",
                                        f"Проверка кода OK: {rel_path} ({verify.get('phase')})",
                                    )
                                elif verify is not None:
                                    from core.python_deps import extract_missing_module

                                    detail = compact_runtime_detail(verify.get("detail", "ошибка"))
                                    missing = verify.get("missing_module") or extract_missing_module(detail)
                                    if verify.get("phase") == "dependency" or missing:
                                        module = missing or "unknown"
                                        handled = await self._ensure_python_module(
                                            active_root, rel_path, module
                                        )
                                        after = handled.get("verify") or {}
                                        if after.get("ok"):
                                            verified_py_files.add(rel_path)
                                            verify_fail_streak.pop(rel_path, None)
                                            self._snapshot_lesson(
                                                confirmed_writes,
                                                verified_py_files,
                                                how="repair",
                                            )
                                            pkg = module
                                            current_prompt += (
                                                f"\nAssistant: {cleaned_text}\n"
                                                f"Tool result: {serialized_result}\n"
                                                f"System: {rel_path} синтаксически верный. "
                                                f"Нет пакета {pkg} — это не баг кода. "
                                                "НЕ патчь и не переписывай файл из‑за ModuleNotFoundError. "
                                                "Можно done или продолжить.\n"
                                            )
                                            continue
                                        detail = after.get("detail") or detail

                                    error_key = detail[:240]
                                    prev = verify_fail_streak.get(rel_path)
                                    if prev and prev[0] == error_key:
                                        repeat_count = prev[1] + 1
                                    else:
                                        repeat_count = 1
                                    verify_fail_streak[rel_path] = (error_key, repeat_count)

                                    self._broadcast(
                                        "chat",
                                        "CoreX Error",
                                        f"Проверка кода не прошла: {rel_path}\n{detail[:1500]}",
                                    )
                                    if repeat_count >= 2:
                                        self._broadcast_thinking(
                                            f"Повторная ошибка ({repeat_count}x) — показываю контекст вокруг строки"
                                        )

                                    should_auto_fix = repeat_count >= 1 and (
                                        "SyntaxError" in detail
                                        or "IndentationError" in detail
                                    )
                                    if should_auto_fix:
                                        if await self._try_repair_python_on_disk(
                                            active_root, rel_path, detail
                                        ):
                                            verified_py_files.add(rel_path)
                                            verify_fail_streak.pop(rel_path, None)
                                            patch_line_history.pop(rel_path, None)
                                            self._snapshot_lesson(
                                                confirmed_writes,
                                                verified_py_files,
                                                how="repair",
                                            )
                                            self._broadcast(
                                                "chat",
                                                "CoreX",
                                                f"Проверка кода OK после авто-исправления: {rel_path}",
                                            )
                                            current_prompt += (
                                                f"\nAssistant: {cleaned_text}\n"
                                                f"Tool result: {serialized_result}\n"
                                                "System: Auto-repair applied on disk. "
                                                "Continue or return done.\n"
                                            )
                                            continue

                                    if repeat_count >= 3:
                                        fallback = await self._try_gui_window_fallback(
                                            active_root,
                                            user_task,
                                            confirmed_writes,
                                            rel_path=rel_path or json_target_path,
                                        )
                                        if fallback:
                                            return fallback
                                        self._broadcast(
                                            "chat",
                                            "CoreX Error",
                                            f"Одна и та же ошибка в {rel_path} повторяется. "
                                            "Останавливаю, чтобы не портить файл.",
                                        )
                                        self._snapshot_lesson(
                                            confirmed_writes,
                                            verified_py_files,
                                            how="syntax_loop",
                                            error=str(detail)[:120],
                                            ok=False,
                                        )
                                        return None

                                    hint = self._build_verify_failure_hint(
                                        rel_path=rel_path,
                                        detail=detail,
                                        active_root=active_root,
                                        repeat_count=repeat_count,
                                    )
                                    current_prompt += (
                                        f"\nAssistant: {cleaned_text}\n"
                                        f"Tool result: {serialized_result}\n"
                                        f"{hint}"
                                    )
                                    continue

                        if (
                            web_task
                            and tool == "write_file"
                            and fs_ok
                            and isinstance(args, dict)
                        ):
                            file_content = str(args.get("content") or "")
                            upgraded = maybe_autofill_salvaged_web(
                                rel_path,
                                file_content,
                                user_task=user_task,
                            )
                            if upgraded and upgraded != file_content:
                                upgrade = await self._execute_filesystem_tool(
                                    "write_file",
                                    {"path": rel_path, "content": upgraded},
                                )
                                if isinstance(upgrade, dict) and upgrade.get("status") == "Success":
                                    file_content = upgraded
                                    self._broadcast_thinking(
                                        f"CoreX: усилен шаблон {rel_path} (качество)"
                                    )
                            issues = web_file_quality_issues(rel_path, file_content)
                            rel_key = rel_path.replace("\\", "/").lower()
                            if issues:
                                web_pending_polish.add(rel_key)
                                current_prompt += (
                                    f"\nAssistant: {cleaned_text}\n"
                                    f"Tool result: {serialized_result}\n"
                                    f"{web_quality_hint(rel_path, issues)}"
                                )
                                continue
                            web_pending_polish.discard(rel_key)
                    else:
                        error_msg = (
                            result.get("message", "Unknown")
                            if isinstance(result, dict)
                            else str(result)
                        )
                        self._broadcast(
                            "chat",
                            "CoreX Error",
                            f"Запись не удалась: {error_msg}",
                        )
                        fallback = await self._try_gui_window_fallback(
                            active_root, user_task, confirmed_writes, rel_path=json_target_path
                        )
                        if fallback:
                            return fallback
                        hint = ""
                        if "заглушка" in str(error_msg).lower() or "повторных def" in str(error_msg).lower():
                            hint = (
                                "\nSystem: Файл на диск не записан. "
                                "Один полный рабочий main.py: один def gameLoop, без второго цикла, "
                                "не два print. Блок ```python ... ```.\n"
                            )
                        if tool == "patch_file" and "вне диапазона" in str(error_msg):
                            hint = (
                                "\nSystem Error: Неверный номер строки (файл короче). "
                                f"НЕ повторяй patch_file на {rel_path}. "
                                "Сделай write_file с полным содержимым файла.\n"
                            )
                            history = patch_line_history.setdefault(rel_path, [])
                            history.append(-1)
                            if history.count(-1) >= 2:
                                hint += (
                                    "System: После 2 ошибок диапазона patch_file заблокирован для этого файла. "
                                    "Только write_file.\n"
                                )
                        current_prompt += (
                            f"\nAssistant: {cleaned_text}\n"
                            f"Tool result: {serialized_result}\n{hint}"
                        )
                        continue

                if (
                    execution_steps
                    and (is_gui_bite_plan(execution_steps) or is_gui_app_plan(execution_steps))
                    and fs_ok
                    and tool in {"write_file", "append_file", "patch_file"}
                    and rel_path
                    and not is_corex_internal_path(rel_path)
                    and self.file_service is not None
                ):
                    on_disk = await self.file_service.read_file(rel_path)
                    gui_body = str((on_disk or {}).get("content") or "")
                    pending_before = None
                    if is_gui_bite_plan(execution_steps):
                        pending_before = pending_gui_bite(execution_steps, completed_plan_steps)
                        completed_plan_steps = sync_gui_bites_from_source(
                            execution_steps, completed_plan_steps, gui_body
                        )
                    elif is_gui_app_plan(execution_steps):
                        was_app = "gui_app" in completed_plan_steps
                        completed_plan_steps = sync_gui_app_from_source(
                            execution_steps, completed_plan_steps, gui_body
                        )
                        pending_before = "gui_app" if not was_app else None
                    if is_gui_app_plan(execution_steps):
                        if "gui_app" not in completed_plan_steps:
                            gui_stuck_writes += 1
                        else:
                            gui_stuck_writes = 0
                    elif pending_before and pending_before not in completed_plan_steps:
                        gui_stuck_writes += 1
                    else:
                        gui_stuck_writes = 0
                    if not memory_updated_this_task:
                        memory_body = (
                            "# Project memory\n\n"
                            f"- GUI-файл: {rel_path.replace('\\', '/')}\n"
                        )
                        raw = await self.file_service.write_file(MEMORY_REL_PATH, memory_body)
                        if isinstance(raw, dict) and raw.get("success"):
                            memory_updated_this_task = True
                    if gui_stuck_writes >= MAX_GUI_FILE_WRITES:
                        smoke = await self._self_test_python(active_root, rel_path)
                        if smoke.get("ok"):
                            fallback = await self._try_gui_window_fallback(
                                active_root,
                                user_task,
                                confirmed_writes,
                                rel_path=rel_path,
                            )
                            if fallback:
                                return fallback
                            msg = gui_partial_stop_message(
                                execution_steps, completed_plan_steps, rel_path
                            )
                            if "запуск" not in msg.lower():
                                msg = msg.rstrip(".") + ". Запуск без ошибок."
                            self._broadcast_thinking(
                                "Модель крутит один файл без прогресса — останавливаю"
                            )
                            self._broadcast("chat", "CoreX Status", msg)
                            self._snapshot_lesson(
                                confirmed_writes,
                                verified_py_files,
                                how="gui_stuck",
                                ok=True,
                            )
                            return msg
                        last_smoke_detail = compact_runtime_detail(
                            str(smoke.get("detail") or "")
                        )
                        current_prompt += (
                            f"\nSystem Error: {rel_path} записан, но запуск падает:\n"
                            f"{last_smoke_detail[:1800]}\n"
                            "Исправь причину. Не done.\n"
                        )

                if execution_steps and fs_ok and tool in {"view_file", "write_file", "append_file", "patch_file", "list_directory", "run_file", "run_command"}:
                    completed_plan_steps = mark_step_completed(
                        execution_steps,
                        completed_plan_steps,
                        tool=tool,
                        path=rel_path,
                        success=True,
                    )
                    step_hint = next_step_hint(execution_steps, completed_plan_steps)
                    if step_hint:
                        current_prompt += f"\n{step_hint}\n"

                current_prompt += (
                    f"\nAssistant: {cleaned_text}\n"
                    f"Tool result: {serialized_result}\n"
                )
                if (
                    fs_ok
                    and tool in {"write_file", "append_file", "patch_file"}
                    and rel_path
                    and not is_corex_internal_path(rel_path)
                    and not (
                        execution_steps
                        and (
                            is_gui_bite_plan(execution_steps)
                            or is_gui_app_plan(execution_steps)
                        )
                        and (
                            pending_gui_bite(execution_steps, completed_plan_steps)
                            or (
                                is_gui_app_plan(execution_steps)
                                and "gui_app" not in completed_plan_steps
                            )
                        )
                    )
                ):
                    on_disk = await self.file_service.read_file(rel_path)
                    body = str((on_disk or {}).get("content") or "")
                    if tool == "patch_file":
                        highlights = (result.get("highlights") or [{}]) if isinstance(result, dict) else [{}]
                        line_no = int((highlights[0] or {}).get("line") or 1)
                        current_prompt += "\n" + edit_guidance_after_patch(rel_path, body, line_no) + "\n"
                    else:
                        current_prompt += "\n" + edit_guidance_after_write(
                            rel_path,
                            body,
                            truncated=bool(salvaged_truncated)
                            or looks_like_truncated_source(body),
                        ) + "\n"
                if (
                    not fs_ok
                    and tool == "view_file"
                    and isinstance(result, dict)
                    and "not a file" in str(result.get("message", "")).lower()
                ):
                    current_prompt += (
                        "System Error: Путь указывает на ПАПКУ, не на файл. "
                        "Не используйте абсолютные пути (C:/...). "
                        "Относительные пути: design-system/MASTER.md, index.html. "
                        "Для папок — list_directory. Дизайнер: write_file design-system/MASTER.md.\n"
                    )
            continue

        return None
