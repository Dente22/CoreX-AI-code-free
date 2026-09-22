"""Куда писать: /путь — файл или папка; без / — агент сам выбирает имя."""

from __future__ import annotations

import re
from pathlib import Path

from core.project_paths import is_corex_internal_path, normalize_rel_path
from core.task_routing import looks_like_fix_request, looks_like_question, normalize_task_text

_FILE_EXT = {".py", ".html", ".css", ".js", ".ts", ".tsx", ".json", ".md"}
_STOP = {
    "python",
    "питон",
    "питоне",
    "pygame",
    "tkinter",
    "javascript",
    "html",
    "css",
    "окне",
    "окно",
    "консоли",
    "консоль",
    "чате",
    "проекте",
    "коде",
    "файле",
    "файл",
    "папке",
    "папку",
    "каталоге",
    "том",
    "этом",
    "нем",
    "нём",
    "ней",
    "корне",
}

_IN_RE = re.compile(
    r"(?:^|[\s,;])(?:в|into|in)\s+"
    r"(?:папк[уеи]\s+|каталог[еу]?\s+|folder\s+|dir(?:ectory)?\s+)?"
    r"/?(?P<path>[A-Za-z_][\w.\-]{0,48}(?:/[A-Za-z_][\w.\-]{0,48}){0,6})",
    re.IGNORECASE,
)

_READ_HINT = re.compile(
    r"что\s+(?:делает|в|это|лежит|находится)|посмотри|покажи|прочитай|открой|"
    r"объясни|расскажи|опиши|как\s+(?:устроен|работает|устроена)|"
    r"what(?:'s|\s+is|\s+does)|show\s+me|\bread\b|look\s+at|explain|open",
    re.I,
)
_EDIT_HINT = re.compile(
    r"исправь|почини|измени|перепиши|обнови|замени|удали|допиши|вставь|"
    r"поправь|отредактируй|добавь|продолж|доделай|"
    r"\bfix\b|\bupdate\b|\brefactor\b|\bedit\b|\bchange\b|\bdelete\b|"
    r"\breplace\b|\bpatch\b|\bcontinue\b",
    re.I,
)
_CREATE_HINT = re.compile(
    r"создай|сделай|напиши|реализуй|собери|начни|"
    r"\bcreate\b|\bmake\b|\bbuild\b|\bgenerate\b|\bscaffold\b|\bimplement\b",
    re.I,
)

_NAME_HINTS = (
    (re.compile(r"змейк|\bsnake\b", re.I), "snake.py"),
    (re.compile(r"сап[её]р|minesweeper|\bsapper\b", re.I), "minesweeper.py"),
    (re.compile(r"калькулятор|\bcalculator\b", re.I), "calculator.py"),
    (re.compile(r"doom|wolfenstein|\bдум\b", re.I), "doom.py"),
    (re.compile(r"тетрис|\btetris\b", re.I), "tetris.py"),
    (re.compile(r"телеграм|telegram|\bбот\b|\bbot\b", re.I), "bot.py"),
    (re.compile(r"таймер|\btimer\b", re.I), "timer.py"),
    (re.compile(r"виселица|\bhangman\b", re.I), "hangman.py"),
    (re.compile(r"todo|список\s+дел", re.I), "todo.py"),
    (re.compile(r"скрипт|\bscript\b", re.I), "script.py"),
    (re.compile(r"игр[ауые]|game", re.I), "game.py"),
)

_WINDOW_ADD = re.compile(r"добав\w*\s+(?:игров\w*\s+)?окн", re.I)


def suggest_created_filename(user_task: str) -> str:
    task = re.sub(r"/[^\s/,;:)»\"'`]+", " ", user_task or "")
    lowered = task.lower()
    if any(word in lowered for word in ("сайт", "html", "страниц", "landing", "веб")):
        return "index.html"
    for pattern, name in _NAME_HINTS:
        if pattern.search(task):
            return name
    return "app.py"


NO_EXTENSION_ERROR = (
    "Нельзя сохранить файл без расширения — одно название недостаточно. "
    "Укажите имя с расширением, например snake.py или index.html."
)


def filename_has_extension(path: str) -> bool:
    """Файл должен быть name.ext; точка в начале (.env) тоже ок. Папка test — нет."""
    name = (path or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if not name or name in {".", ".."}:
        return False
    if name.startswith(".") and len(name) > 1:
        return True
    if "." not in name:
        return False
    stem, ext = name.rsplit(".", 1)
    return bool(stem.strip()) and bool(ext.strip())


def _has_file_ext(path: str) -> bool:
    last = (path or "").rsplit("/", 1)[-1]
    if "." not in last:
        return False
    suffix = "." + last.rsplit(".", 1)[-1].lower()
    return suffix in _FILE_EXT


def _clean_candidate(raw: str) -> str | None:
    path = normalize_rel_path((raw or "").strip("`'\"")).strip("/")
    if not path or path in {".", ".."} or ".." in path.split("/"):
        return None
    if ":" in path or is_corex_internal_path(path):
        return None
    top = path.split("/", 1)[0].lower()
    if top in _STOP:
        return None
    return path


def _mentioned_paths(user_task: str) -> list[str]:
    text = user_task or ""
    seen: list[str] = []
    from core.file_mentions import extract_mention_paths

    for raw in extract_mention_paths(text):
        cleaned = _clean_candidate(raw)
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    for match in _IN_RE.finditer(text):
        cleaned = _clean_candidate(match.group("path") or "")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _in_slash_target(user_task: str) -> str | None:
    """Путь после «в /folder» или «in /file» — куда пользователь указал писать."""
    match = re.search(
        r"(?:в|into|in)\s+/"
        r"([^\s/,;:)»\"'`]+(?:/[^\s/,;:)»\"'`]+)*)",
        user_task or "",
        re.I,
    )
    if not match:
        return None
    return _clean_candidate(match.group(1) or "")


def _as_root(project_root: Path | str | None) -> Path | None:
    if project_root is None:
        return None
    try:
        return Path(project_root).resolve()
    except (OSError, TypeError, ValueError):
        return None


def classify_mention_kind(path: str, project_root: Path | str | None = None) -> str:
    """file — имя с расширением; folder — без расширения, даже если на диске ошибочно файл."""
    del project_root
    rel = normalize_rel_path(path)
    if not rel:
        return "folder"
    if filename_has_extension(rel):
        return "file"
    return "folder"


def mention_intent(user_task: str) -> str:
    """read — посмотреть; edit — изменить этот файл; create — создать по указанному пути."""
    task = normalize_task_text(user_task)
    if not _mentioned_paths(task) and not _IN_RE.search(task or ""):
        if looks_like_fix_request(task):
            return "edit"
        if _CREATE_HINT.search(task or ""):
            return "create"
        if _WINDOW_ADD.search(task or ""):
            return "edit"
        if looks_like_question(task) or _READ_HINT.search(task or ""):
            return "read"
        return "create" if task else "read"
    if looks_like_fix_request(task) or _EDIT_HINT.search(task):
        if _CREATE_HINT.search(task):
            in_target = _in_slash_target(task)
            if in_target and not _has_file_ext(in_target):
                return "create"
            if not in_target:
                first = (_mentioned_paths(task) or [""])[0]
                if first and not _has_file_ext(first):
                    return "create"
        return "edit"
    if _CREATE_HINT.search(task):
        in_target = _in_slash_target(task)
        if in_target and _has_file_ext(in_target):
            return "edit"
        return "create"
    if looks_like_question(task) or _READ_HINT.search(task):
        return "read"
    if _in_slash_target(task) or _mentioned_paths(task):
        return "edit"
    return "read"


def infer_task_write_path(
    user_task: str,
    project_root: Path | str | None = None,
) -> str | None:
    """Куда писать. Папка → папка/имя.py (не main.py). Без / — подсказка имени."""
    intent = mention_intent(user_task)
    if intent == "read":
        return None
    seen = _mentioned_paths(user_task)
    suggested = suggest_created_filename(user_task)
    folders = [path for path in seen if classify_mention_kind(path, project_root) == "folder"]
    files = [path for path in seen if classify_mention_kind(path, project_root) == "file"]
    in_target = _in_slash_target(user_task)
    if in_target:
        if classify_mention_kind(in_target, project_root) == "folder":
            return f"{in_target}/{suggested}"
        return in_target
    if intent == "create":
        if folders:
            return f"{folders[0]}/{suggested}"
        if files:
            return files[0]
        return suggested
    if files:
        return files[0]
    if folders:
        return f"{folders[0]}/{suggested}"
    return None


def is_locked_write_path(
    user_task: str,
    dest: str | None,
    project_root: Path | str | None = None,
) -> bool:
    if not dest:
        return False
    intent = mention_intent(user_task)
    if intent == "edit":
        return True
    dest_n = normalize_rel_path(dest)
    return any(
        normalize_rel_path(path) == dest_n
        and classify_mention_kind(path, project_root) == "file"
        for path in _mentioned_paths(user_task)
    )


def remap_write_path(
    requested: str | None,
    target: str | None,
    *,
    user_task: str = "",
    project_root: Path | str | None = None,
) -> str:
    dest = normalize_rel_path(target or "")
    rel = normalize_rel_path(requested or "")
    if not dest:
        return rel or suggest_created_filename(user_task)
    if is_corex_internal_path(rel):
        return rel
    if user_task and is_locked_write_path(user_task, dest, project_root):
        return dest
    folder, sep, suggested = dest.rpartition("/")
    if not sep:
        folder = ""
        suggested = dest
    name = rel.rsplit("/", 1)[-1] if rel else ""
    if not name or name in {".", "main.py"}:
        name = suggested or suggest_created_filename(user_task)
    if folder:
        if rel in {folder, folder + "/"}:
            return f"{folder}/{suggested or name}"
        if rel.startswith(folder + "/") and rel.rsplit("/", 1)[-1] not in {"", "main.py"}:
            return rel
        return f"{folder}/{name}"
    if rel and "/" not in rel and rel != "main.py":
        return rel
    return name


def resolve_gui_fallback_path(
    user_task: str,
    rel_path: str | None = None,
    project_root: Path | str | None = None,
) -> str:
    """Куда писать шаблон окна: папка из /path, не чужой main.py/snake.py."""
    inferred = infer_task_write_path(user_task, project_root)
    requested = normalize_rel_path(rel_path or "")
    if inferred and inferred.lower().endswith(".py"):
        return inferred
    if requested and requested.lower().endswith(".py"):
        return requested
    folder = inferred or requested
    if folder:
        kind = classify_mention_kind(folder, project_root)
        if kind == "folder" or not folder.lower().endswith(".py"):
            name = suggest_created_filename(user_task)
            return f"{folder.rstrip('/')}/{name}"
    return inferred or requested or suggest_created_filename(user_task)


def mention_prompt_hint(
    user_task: str,
    write_dest: str | None,
    project_root: Path | str | None = None,
) -> str:
    intent = mention_intent(user_task)
    if intent == "read" and _mentioned_paths(user_task):
        return (
            "\n/file is to READ. Use the attached content. "
            "Do not write or create files unless the user asked to change them.\n"
        )
    if intent == "edit" and write_dest:
        return (
            f"\nEDIT {write_dest}. The file content is attached. "
            "patch_file or write_file the SAME path. Do not create another file or folder.\n"
        )
    if intent == "create" and write_dest:
        folder, sep, name = write_dest.rpartition("/")
        mentions = _mentioned_paths(user_task)
        if mentions and classify_mention_kind(mentions[0], project_root) == "file":
            return (
                f"\nWRITE TO {write_dest}. User chose this file with /path. "
                "Do not write a different path.\n"
            )
        if sep:
            return (
                f"\nWRITE a NEW file inside {folder}/. "
                f"Choose a fitting filename yourself (hint: {name}). "
                "Do not write root main.py. Do not name it main.py just because.\n"
            )
        return (
            f"\nCreate a NEW file with a fitting name (hint: {write_dest}). "
            "Do not overwrite an unrelated existing main.py.\n"
        )
    return ""


def is_write_destination_mention(mention: str, dest: str | None) -> bool:
    if not dest:
        return False
    rel = normalize_rel_path(mention or "")
    if not rel:
        return False
    dest_n = normalize_rel_path(dest)
    top = dest_n.split("/", 1)[0]
    return rel == dest_n or rel == top or dest_n.startswith(rel + "/")
