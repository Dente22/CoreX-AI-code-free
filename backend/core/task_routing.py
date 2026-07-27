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


def should_run_planning_phase(user_task: str, history: list[dict] | None = None) -> bool:
    """Полное планирование + база знаний — только для задач на код/правки."""
    return infer_task_route(user_task, history) == "code"


def should_include_knowledge_in_prompt(user_task: str, history: list[dict] | None = None) -> bool:
    return should_run_planning_phase(user_task, history)
