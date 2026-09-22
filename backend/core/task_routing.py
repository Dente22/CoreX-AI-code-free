"""Маршрутизация запросов: small talk vs код vs вопросы."""

from __future__ import annotations

import re
import unicodedata


def normalize_task_text(user_task: str) -> str:
    text = unicodedata.normalize("NFKC", user_task or "")
    return text.strip().strip("\ufeff").strip("\u200b")


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
    r"продолж|доделай|продолжай|"
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

_FIX_TASK_PATTERNS = re.compile(
    r"исправь|исправить|почини|починить|fix|bug|баг|ошибк|error|traceback|"
    r"nameerror|syntaxerror|не\s+работает|не\s+запуска|код\s+выхода|"
    r"доста[ёе]т|отсутствует|missing|undefined|not\s+defined|crash|падает",
    re.IGNORECASE,
)

_CODING_CONTEXT_PATTERNS = re.compile(
    r"код|файл|функци|класс|модуль|скрипт|api|backend|frontend|база|тест|"
    r"игр|приложени|программ|проект|сайт|pygame|flask|react|html|python|"
    r"import|def |class |\.py|\.ts|\.js|\.tsx|main\.py|requirements",
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


def history_suggests_coding(history: list[dict] | None) -> bool:
    for msg in (history or [])[-8:]:
        content = msg.get("content", "")
        if _CODING_CONTEXT_PATTERNS.search(content):
            return True
        if _WRITE_TASK_PATTERNS.search(content):
            return True
    return False


def looks_like_fix_request(user_task: str) -> bool:
    task = normalize_task_text(user_task)
    if not task:
        return False
    return bool(_FIX_TASK_PATTERNS.search(task))


_GUI_WINDOW_PATTERNS = re.compile(
    r"окн|"
    r"не\s+в\s+консол|не\s+консол|"
    r"отдельн\w*\s+(?:окн|window)|игрово\w*\s+окн|"
    r"\bgui\b|tkinter|"
    r"game\s+window|separate\s+window",
    re.IGNORECASE,
)


def looks_like_gui_window_request(user_task: str) -> bool:
    task = normalize_task_text(user_task)
    if not task:
        return False
    return bool(_GUI_WINDOW_PATTERNS.search(task))


def looks_like_build_request(user_task: str) -> bool:
    task = normalize_task_text(user_task)
    if not task:
        return False
    if _WRITE_TASK_PATTERNS.search(task):
        return True
    if _CREATE_INTENT_PATTERNS.search(task):
        return True
    if _FIX_TASK_PATTERNS.search(task):
        return True
    if _CODING_CONTEXT_PATTERNS.search(task):
        return True
    return False


def looks_like_question(user_task: str) -> bool:
    task = normalize_task_text(user_task)
    if not task:
        return False
    if _QUESTION_ONLY_PATTERNS.match(task):
        return True
    if task.endswith("?") and not looks_like_build_request(task):
        return True
    return False


def is_conversational_message(user_task: str, history: list[dict] | None = None) -> bool:
    task = normalize_task_text(user_task)
    if _CONVERSATIONAL_PATTERNS.match(task):
        return True
    if looks_like_build_request(task):
        return False
    if history_suggests_coding(history):
        return False
    return False


def response_length_instruction(user_task: str, *, conversational: bool) -> str:
    """Подсказка модели: длина ответа по запросу пользователя."""
    task = normalize_task_text(user_task).lower()
    if not task:
        return ""

    m = re.search(r"в\s+(\d+)\s+предложени", task)
    if m:
        n = max(1, min(12, int(m.group(1))))
        return f"В поле message напиши ровно {n} полных предложений."

    if re.search(r"\b(кратко|коротко|лаконично|brief|short)\b", task):
        return "Краткий ответ: 1–2 предложения в message."

    if re.search(r"\b(подробно|развёрнуто|развернуто|детально|detailed|thorough)\b", task):
        return "Развёрнутый ответ: столько предложений, сколько нужно для полного объяснения."

    if conversational:
        return (
            "Отвечай естественно по-русски: приветствие — 1–2 дружелюбных предложения; "
            "на вопрос — полный ответ. Не односложно, если пользователь не просил кратко."
        )
    return ""


def infer_task_route(user_task: str, history: list[dict] | None = None) -> str:
    """conversational | question | code"""
    task = normalize_task_text(user_task)
    if is_conversational_message(task, history):
        return "conversational"
    if looks_like_question(task):
        if not _WRITE_TASK_PATTERNS.search(task) and not _FIX_TASK_PATTERNS.search(task):
            return "question"
    if looks_like_build_request(task):
        return "code"
    if history_suggests_coding(history):
        return "code"
    return "conversational"


OPENROUTER_CHAT_ECONOMY_MODEL = "openrouter/free"
GEMINI_CHAT_ECONOMY_MODEL = "gemini-2.5-flash-lite"
_ECONOMY_MODEL_MARKERS = (
    ":mini",
    "-mini",
    "mini:",
    "nano",
    "-lite",
    ":lite",
    "flash-lite",
    "oss-20b",
    ":7b",
    ":8b",
    ":1b",
    ":3b",
    ":4b",
)


def looks_like_economy_model(model_name: str) -> bool:
    lowered = f":{(model_name or '').strip().lower()}"
    return any(marker in lowered for marker in _ECONOMY_MODEL_MARKERS)


def resolve_online_model_for_route(
    route: str,
    selected: str,
    *,
    api_type: str = "openai",
    is_openrouter: bool = False,
) -> str:
    """Chat/questions use a small free model; code keeps the user's selected model."""
    selected_name = str(selected or "").strip()
    if not selected_name or route == "code":
        return selected_name
    if api_type == "gemini":
        if looks_like_economy_model(selected_name):
            return selected_name
        return GEMINI_CHAT_ECONOMY_MODEL
    if not is_openrouter:
        return selected_name
    if selected_name.lower() == OPENROUTER_CHAT_ECONOMY_MODEL:
        return selected_name
    return OPENROUTER_CHAT_ECONOMY_MODEL


LOCAL_CHAT_MODEL = "phi3:mini"
LOCAL_CODE_MODEL = "qwen2.5-coder:3b"
_PINNED_LARGER_LOCAL = (":7b", ":8b", ":13b", ":14b", ":32b", ":70b")


def looks_like_pinned_larger_local(model_name: str) -> bool:
    lowered = f":{(model_name or '').strip().lower()}"
    return any(marker in lowered for marker in _PINNED_LARGER_LOCAL)


def _installed_match(installed: list[str], target: str) -> str:
    from core.ollama_model_service import model_name_matches

    for name in installed:
        if model_name_matches(name, target):
            return str(name).strip()
    return ""


def local_pair_available(installed: list[str]) -> bool:
    return bool(
        _installed_match(installed, LOCAL_CHAT_MODEL)
        and _installed_match(installed, LOCAL_CODE_MODEL)
    )


def resolve_local_model_for_route(
    route: str,
    selected: str,
    installed: list[str],
) -> str:
    """If Phi-3 Mini and Qwen 3B are both installed: chat→Phi-3, code→Qwen 3B."""
    selected_name = str(selected or "").strip()
    if looks_like_pinned_larger_local(selected_name):
        return selected_name
    chat = _installed_match(installed, LOCAL_CHAT_MODEL)
    code = _installed_match(installed, LOCAL_CODE_MODEL)
    if not chat or not code:
        return selected_name
    if route == "code":
        return code
    return chat


def should_run_planning_phase(user_task: str, history: list[dict] | None = None) -> bool:
    """Полное планирование + база знаний — только для задач на код/правки."""
    return infer_task_route(user_task, history) == "code"


def should_include_knowledge_in_prompt(user_task: str, history: list[dict] | None = None) -> bool:
    return should_run_planning_phase(user_task, history)
