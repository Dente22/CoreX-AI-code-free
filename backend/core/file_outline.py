"""Карта строк файла: модель видит номер для replace/delete."""

from __future__ import annotations

import ast
import re

from core.file_patch import number_file_content

_DEF = re.compile(r"^(?:async\s+)?def\s+(\w+)\s*\(")
_CLASS = re.compile(r"^class\s+(\w+)\b")
_CALL = re.compile(r"^(\w+)\s*\(\s*\)\s*$")


def _is_top_level(line: str) -> bool:
    return bool(line) and not line[0].isspace()


def iter_symbols(content: str) -> list[dict]:
    items: list[dict] = []
    for index, line in enumerate((content or "").splitlines(), start=1):
        if not _is_top_level(line):
            continue
        stripped = line.rstrip()
        match = _DEF.match(stripped)
        if match:
            items.append(
                {"line": index, "kind": "def", "name": match.group(1), "text": stripped}
            )
            continue
        match = _CLASS.match(stripped)
        if match:
            items.append(
                {"line": index, "kind": "class", "name": match.group(1), "text": stripped}
            )
            continue
        match = _CALL.match(stripped)
        if match:
            items.append(
                {"line": index, "kind": "call", "name": match.group(1), "text": stripped}
            )
    return items


def duplicate_def_names(content: str) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = {}
    for item in iter_symbols(content):
        if item["kind"] in {"def", "class"}:
            seen.setdefault(item["name"], []).append(item["line"])
    return {name: lines for name, lines in seen.items() if len(lines) > 1}


def line_map_for_prompt(content: str, *, path: str = "main.py") -> str:
    lines = (content or "").splitlines()
    symbols = iter_symbols(content)
    dups = duplicate_def_names(content)
    out = [
        f"Карта {path}: {len(lines)} строк. Номер слева = line для patch_file."
    ]
    kind_ru = {"def": "def", "class": "class", "call": "вызов"}
    if not symbols:
        preview = number_file_content("\n".join(lines[:16])) if lines else "    1| "
        out.append(preview)
    else:
        for item in symbols:
            mark = ""
            if item["kind"] in {"def", "class"} and item["name"] in dups:
                first = dups[item["name"]][0]
                if item["line"] != first:
                    mark = (
                        f"  << ПОВТОР {item['kind']} {item['name']}, "
                        f"удали: patch_file op=delete line={item['line']}"
                    )
                else:
                    mark = f"  (первый {item['kind']})"
            out.append(
                f"  {item['line']:>4}| [{kind_ru[item['kind']]}] {item['name']}{mark}"
            )
    out.append(
        f'Изменить строку N: {{"status":"act","server":"filesystem","tool":"patch_file",'
        f'"arguments":{{"path":"{path}","op":"replace","line":N,"content":"текст строки"}}}}'
    )
    out.append(
        f'Удалить строку N: {{"op":"delete","line":N}} — номер только из этой карты или view_file.'
    )
    return "\n".join(out)


def numbered_window(content: str, line: int, *, radius: int = 5) -> str:
    rows = (content or "").splitlines()
    if not rows:
        return "    1| "
    idx = max(1, int(line or 1)) - 1
    start = max(0, idx - radius)
    end = min(len(rows), idx + radius + 1)
    out: list[str] = []
    for i in range(start, end):
        mark = " <<" if i == idx else ""
        out.append(f"{i + 1:4d}| {rows[i]}{mark}")
    return "\n".join(out)


def looks_like_truncated_source(text: str) -> bool:
    blob = (text or "").rstrip()
    if not blob:
        return True
    last = blob.splitlines()[-1].strip()
    if not last:
        return False
    if last.endswith(("\\", ",", "(", "[", "{")):
        return True
    if last.startswith(("def ", "class ", "async def ")) and ":" not in last:
        return True
    if last.endswith(":") and last.startswith(
        ("def ", "class ", "async def ", "if ", "elif ", "else", "for ", "while ", "try", "except", "with ")
    ):
        return True
    import ast

    try:
        ast.parse(blob + "\n")
        return False
    except SyntaxError as exc:
        msg = (exc.msg or "").lower()
        if any(
            token in msg
            for token in (
                "unterminated",
                "unexpected eof",
                "was never closed",
                "eof while scanning",
            )
        ):
            return True
        last_no = len(blob.splitlines())
        if exc.lineno and int(exc.lineno) >= last_no:
            return True
        return False


def drop_duplicate_top_level_blocks(existing: str, chunk: str) -> str:
    """Выкинуть из куска def/class, имя которых уже есть в файле."""
    known = {
        item["name"]
        for item in iter_symbols(existing)
        if item["kind"] in {"def", "class"}
    }
    known_calls = {
        item["name"]
        for item in iter_symbols(existing)
        if item["kind"] == "call"
    }
    if (not known and not known_calls) or not (chunk or "").strip():
        return chunk or ""
    lines = chunk.replace("\r\n", "\n").splitlines()
    kept: list[str] = []
    skipping = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if skipping:
            if line.strip() and _is_top_level(line):
                skipping = False
                continue
            index += 1
            continue
        if line.strip() and _is_top_level(line):
            match = _DEF.match(line) or _CLASS.match(line)
            if match and match.group(1) in known:
                skipping = True
                index += 1
                continue
            call = _CALL.match(line.strip())
            if call and call.group(1) in known_calls:
                index += 1
                continue
        kept.append(line)
        index += 1
    if not kept:
        return ""
    body = "\n".join(kept).strip("\n")
    return body + "\n" if body else ""


_PRINT_CALL = re.compile(r"\bprint\s*\(")
_STUB_MARKERS = re.compile(
    r"CoreX stub|# fix\b|TODO:\s*implement|pass\s*#\s*stub",
    re.I,
)
_TRIVIAL_STUB_LINE = re.compile(
    r"^(pass|return(?:\s+None)?|main\(\)|play\(\)|play_game\(\)|if\s+__name__.+)$"
)
_GAME_TOKEN_RE = re.compile(
    r"mine|bomb|сап[её]р|minesweeper|sapper|змейк|"
    r"snake_list|game_loop|gameloop|tetris|"
    r"\bcells?\b|\bboard\b|reveal|\bflag\b|"
    r"enter (row|column)|number of (rows|mines)|"
    r"pygame\.draw|\.blit\s*\(|MOUSEBUTTON",
    re.I,
)
EMPTY_WINDOW_ERROR = (
    "Пустое окно (pygame.init + чёрный экран) отклонено. "
    "Нужна программа в окне под текущую задачу: виджеты или отрисовка, не пустой цикл."
)
DESTRUCTIVE_OVERWRITE_ERROR = (
    "Файл уже содержит программу. Нельзя стереть её пустым окном. "
    "Перепишите ТУ ЖЕ программу с окном."
)


def _is_trivial_stub_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True
    if stripped.startswith(("def ", "async def ", "class ")):
        return True
    return bool(_TRIVIAL_STUB_LINE.match(stripped))


def extract_game_tokens(content: str) -> set[str]:
    return {match.group(0).lower() for match in _GAME_TOKEN_RE.finditer(content or "")}


def looks_like_empty_window_skeleton(content: str) -> bool:
    """pygame/tk окно без игровой логики — шаблон «чёрный экран», не сапёр."""
    blob = content or ""
    if not blob.strip():
        return False
    if extract_game_tokens(blob):
        return False
    lowered = blob.lower()
    if "pygame" in lowered:
        has_init = "pygame.init" in lowered
        has_mode = "set_mode" in lowered
        has_loop = "pygame.event" in lowered or "pygame.quit" in lowered
        has_play = bool(re.search(r"pygame\.draw|\.blit\s*\(|MOUSEBUTTON|sprite", blob))
        if has_init and has_mode and has_loop and not has_play:
            return True
    if "tkinter" in lowered:
        has_root = bool(re.search(r"\bTk\s*\(", blob))
        has_loop = "mainloop" in lowered
        has_ui = bool(re.search(r"\b(Button|Canvas|Label|Frame|Entry|Text)\s*\(", blob))
        if has_root and has_loop and not has_ui:
            return True
    return False


BROKEN_OVERWRITE_ERROR = (
    "Не затираю рабочий файл кодом с синтаксической ошибкой или служебным текстом. "
    "Пришлите только исходник без JSON и без строк System."
)


def compiles_as_python(source: str) -> bool:
    try:
        ast.parse(source or "")
    except SyntaxError:
        return False
    return bool((source or "").strip())


def is_destructive_game_overwrite(existing: str, incoming: str) -> bool:
    old = (existing or "").strip()
    new = (incoming or "").strip()
    if not old or not new:
        return False
    if looks_like_empty_window_skeleton(new) and not looks_like_empty_window_skeleton(old):
        if len(old) >= 80:
            return True
    old_tokens = extract_game_tokens(old)
    new_tokens = extract_game_tokens(new)
    if old_tokens and not new_tokens and len(old) > 200:
        return True
    return False


def is_stub_python(content: str) -> bool:
    """Два print без игры/функций, явная заглушка CoreX, пустой файл, def + pass."""
    blob = (content or "").replace("\r\n", "\n")
    if not blob.strip():
        return True
    if looks_like_empty_window_skeleton(blob):
        return True
    if _STUB_MARKERS.search(blob):
        return True
    code_lines = [
        line
        for line in blob.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not code_lines:
        return True
    joined = "\n".join(code_lines)
    nontrivial = [line for line in code_lines if not _is_trivial_stub_line(line)]
    if not nontrivial:
        return True
    has_structure = bool(
        re.search(r"(?m)^(def |async def |class |while |for )", joined)
    )
    has_game = bool(
        re.search(r"pygame|\bturtle\b|game_loop|gameLoop|змейк", joined, re.I)
    )
    prints = len(_PRINT_CALL.findall(joined))
    if has_structure or has_game:
        return False
    return prints >= 2


def dedupe_top_level_defs(content: str) -> str:
    """Оставить первое def/class с каждым именем, повторные блоки выкинуть."""
    lines = (content or "").replace("\r\n", "\n").splitlines()
    if not lines:
        return content or ""
    seen_defs: set[str] = set()
    seen_calls: set[str] = set()
    kept: list[str] = []
    skipping = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if skipping:
            if line.strip() and _is_top_level(line):
                skipping = False
                continue
            index += 1
            continue
        if line.strip() and _is_top_level(line):
            match = _DEF.match(line) or _CLASS.match(line)
            if match:
                name = match.group(1)
                if name in seen_defs:
                    skipping = True
                    index += 1
                    continue
                seen_defs.add(name)
            else:
                call = _CALL.match(line.strip())
                if call:
                    name = call.group(1)
                    if name in seen_calls:
                        index += 1
                        continue
                    seen_calls.add(name)
        kept.append(line)
        index += 1
    if not kept:
        return ""
    body = "\n".join(kept).strip("\n")
    return body + "\n"


def prepare_source_write(
    path: str,
    content: str,
    existing: str | None = None,
) -> dict:
    """Перед записью .py: отбросить заглушку, пустое окно и повторные def."""
    name = (path or "").replace("\\", "/").lower()
    body = content or ""
    if not name.endswith(".py"):
        return {"content": body}
    from core.staged_write import sanitize_code_chunk

    body = sanitize_code_chunk(body)
    from core.python_deps import rewrite_tkinter_gui_mistakes

    body = rewrite_tkinter_gui_mistakes(body)
    from core.staged_write import is_protocol_leak

    if is_protocol_leak(body):
        return {"error": BROKEN_OVERWRITE_ERROR}
    if existing and compiles_as_python(existing) and not compiles_as_python(body):
        return {"error": BROKEN_OVERWRITE_ERROR}
    if looks_like_empty_window_skeleton(body):
        return {"error": EMPTY_WINDOW_ERROR}
    from core.game_gui_upgrade import INCOMPLETE_GUI_ERROR, looks_like_incomplete_gui_game

    if looks_like_incomplete_gui_game(body):
        return {"error": INCOMPLETE_GUI_ERROR}
    if existing and is_destructive_game_overwrite(existing, body):
        return {"error": DESTRUCTIVE_OVERWRITE_ERROR}
    if is_stub_python(body):
        return {
            "error": (
                "Заглушка отклонена (мало кода / только print). "
                "Пришлите полную программу одним файлом: def, цикл, не два print."
            )
        }
    deduped = dedupe_top_level_defs(body)
    if looks_like_empty_window_skeleton(deduped) or is_stub_python(deduped):
        return {
            "error": (
                "После удаления повторных def файл стал пустым. "
                "Пришлите одну полную программу без второго gameLoop."
            )
        }
    return {
        "content": deduped,
        "stripped_duplicates": deduped != body,
    }


def numbered_snapshot(content: str, *, path: str = "main.py", max_lines: int = 160) -> str:
    map_text = line_map_for_prompt(content, path=path)
    rows = (content or "").splitlines()
    if len(rows) <= max_lines:
        return map_text + "\n---\n" + number_file_content(content or "")
    start = max(0, len(rows) - 40)
    tail = "\n".join(f"{i + 1:4d}| {rows[i]}" for i in range(start, len(rows)))
    return map_text + "\n--- хвост файла ---\n" + tail


def idle_stop_chat(
    confirmed_writes: list[str] | None = None,
    *,
    turns: int = 8,
) -> tuple[str, str]:
    writes = [
        item.replace("\\", "/")
        for item in (confirmed_writes or [])
        if item and "project_memory" not in item.replace("\\", "/")
    ]
    unique = list(dict.fromkeys(writes))
    if unique:
        shown = ", ".join(unique[:4])
        return (
            "CoreX Status",
            f"Код уже в {shown}. Модель {turns} ходов не меняла строки — стоп. "
            "Чтобы править конкретную строку — назовите номер или что удалить.",
        )
    return (
        "CoreX Error",
        f"Модель {turns} ходов подряд не записала новый код. "
        "Останавливаю, чтобы не крутить генерацию бесконечно. "
        "Повторите запрос или упростите задачу.",
    )


def edit_guidance_after_write(
    path: str,
    content: str,
    *,
    truncated: bool,
) -> str:
    ctx = numbered_snapshot(content, path=path)
    if truncated:
        return (
            f"System: {path} записан частично. Смотри номера строк:\n{ctx}\n"
            "Допиши ТОЛЬКО хвост через append_file. "
            "Не повторяй def/class, которые уже в карте. "
            "Нельзя done, пока файл не компилируется.\n"
        )
    return (
        f"System: {path} на диске. Смотри номера строк:\n{ctx}\n"
        "Если программа полная — {\"status\":\"done\",\"message\":\"Готово\"}. "
        "Иначе patch_file с line из карты (replace или delete). "
        "Не append второй def с тем же именем.\n"
    )


def edit_guidance_after_patch(path: str, content: str, line: int) -> str:
    around = numbered_window(content, line)
    return (
        f"System: изменена строка {line} в {path}:\n{around}\n"
        "Следующий patch — другой номер из карты. Не угадывай line.\n"
        f"{line_map_for_prompt(content, path=path)}\n"
    )
