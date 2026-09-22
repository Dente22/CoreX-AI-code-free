"""Поэтапное выполнение задач: «съесть слона по кусочкам» (offline и online)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionStep:
    id: str
    title: str
    instruction: str
    tool_hint: str


def web_developer_plan(*, design_folder: str = "design-system") -> list[ExecutionStep]:
    df = design_folder.strip().rstrip("/\\") or "design-system"
    return [
        ExecutionStep(
            id="read_design",
            title="Прочитать дизайн",
            instruction=(
                f"Сейчас ТОЛЬКО view_file {df}/MASTER.md. "
                "Не пиши HTML/CSS в этом ходе."
            ),
            tool_hint=f'view_file path="{df}/MASTER.md"',
        ),
        ExecutionStep(
            id="read_page",
            title="Прочитать страницу",
            instruction=(
                f"Сейчас ТОЛЬКО view_file {df}/pages/index.md. "
                "Не пиши HTML/CSS в этом ходе."
            ),
            tool_hint=f'view_file path="{df}/pages/index.md"',
        ),
        ExecutionStep(
            id="html_structure",
            title="HTML-структура",
            instruction=(
                "Сейчас ТОЛЬКО write_file index.html (≥1200 символов): DOCTYPE, lang=ru, "
                '<link href="style.css">, <script src="script.js" defer>, '
                "sticky nav с якорями, большой hero с текстом+CTA, 3 богатые секции с списками, footer. "
                "Не короткий скелет."
            ),
            tool_hint='write_file path="index.html"',
        ),
        ExecutionStep(
            id="css_layout",
            title="CSS layout",
            instruction=(
                "Сейчас ТОЛЬКО write_file style.css (≥1400 символов): тёмный фон, "
                "gradient hero, .container, .card, .btn, hover, @media. Много правил, не 40 строк."
            ),
            tool_hint='write_file path="style.css"',
        ),
        ExecutionStep(
            id="js_interact",
            title="JavaScript",
            instruction=(
                "Сейчас ТОЛЬКО write_file script.js (≥500 символов): DOMContentLoaded, "
                "mobile nav, smooth scroll, CTA, хотя бы 1 доп. эффект (подсветка секции / toast)."
            ),
            tool_hint='write_file path="script.js"',
        ),
        ExecutionStep(
            id="verify_link",
            title="Проверка связки",
            instruction=(
                'Сейчас ТОЛЬКО view_file index.html — проверь style.css и script.js в <head>.'
            ),
            tool_hint='view_file path="index.html"',
        ),
        ExecutionStep(
            id="polish",
            title="Полировка",
            instruction=(
                "Если сайт всё ещё плоский — write_file style.css или script.js ЦЕЛИКОМ. "
                "patch_file для html/css/js ЗАПРЕЩЁН. Иначе done."
            ),
            tool_hint="write_file style.css/script.js или done",
        ),
    ]


def designer_plan(*, design_folder: str = "design-system") -> list[ExecutionStep]:
    df = design_folder.strip().rstrip("/\\") or "design-system"
    return [
        ExecutionStep(
            id="master",
            title="Design Spec MASTER",
            instruction=(
                f"Сейчас ТОЛЬКО write_file {df}/MASTER.md — полный Design Spec "
                "(цель, цвета #9A5EFF/#00D2FF, типографика, layout, компоненты, 3 anti-patterns, a11y). "
                "Не пиши другие файлы в этом ходе."
            ),
            tool_hint=f'write_file path="{df}/MASTER.md"',
        ),
        ExecutionStep(
            id="page",
            title="Страница index",
            instruction=(
                f"Сейчас ТОЛЬКО write_file {df}/pages/index.md — hero, nav, секции, footer. "
                "Не пиши другие файлы в этом ходе."
            ),
            tool_hint=f'write_file path="{df}/pages/index.md"',
        ),
        ExecutionStep(
            id="block_hero",
            title="Блок hero",
            instruction=f"Сейчас ТОЛЬКО write_file {df}/blocks/hero.md — детали hero.",
            tool_hint=f'write_file path="{df}/blocks/hero.md"',
        ),
        ExecutionStep(
            id="block_nav",
            title="Блок navigation",
            instruction=f"Сейчас ТОЛЬКО write_file {df}/blocks/navigation.md — nav/links.",
            tool_hint=f'write_file path="{df}/blocks/navigation.md"',
        ),
        ExecutionStep(
            id="block_sections",
            title="Блок sections",
            instruction=f"Сейчас ТОЛЬКО write_file {df}/blocks/sections.md — секции страницы.",
            tool_hint=f'write_file path="{df}/blocks/sections.md"',
        ),
    ]


def _code_target_name(coding_language: str) -> str:
    from core.coding_language import validate_language_id

    return {
        "python": "main.py",
        "javascript": "main.js",
        "typescript": "main.ts",
        "react": "App.tsx",
    }.get(validate_language_id(coding_language), "один исходный файл")


def gui_window_bites_plan(*, path: str, user_task: str = "") -> list[ExecutionStep]:
    """Игру с окном пишем кусками: модель сама пишет код, шаблон не подставляем."""
    rel = (path or "game.py").replace("\\", "/")
    from core.game_gui_upgrade import looks_like_doom_task

    doom = looks_like_doom_task(user_task)
    world = (
        "вид сверху: стены-прямоугольники, столкновение, выход. "
        "НЕ raycasting и НЕ копия id Software."
        if doom
        else "правила той игры, которую просили, на Canvas."
    )
    return [
        ExecutionStep(
            id="gui_window",
            title="Окно",
            instruction=(
                f"Сейчас ТОЛЬКО write_file {rel}: "
                "import tkinter as tk; root = tk.Tk(); canvas = tk.Canvas(root, width=640, height=400); "
                "один create_rectangle (игрок); title; mainloop. "
                "Нельзя писать Tk и Canvas в одном import вместе с tkinter — "
                "только import tkinter as tk, затем tk.Tk и tk.Canvas. "
                "один create_rectangle (игрок), title, mainloop. Без лабиринта и без raycast. "
                "Короткий файл. Не list_directory."
            ),
            tool_hint=f'write_file path="{rel}"',
        ),
        ExecutionStep(
            id="gui_move",
            title="Ходьба",
            instruction=(
                f"Сейчас write_file {rel} ЦЕЛИКОМ: оставь окно и игрока, ДОБАВЬ ходьбу. "
                "Только так: pressed=set(); bind('<KeyPress>'/'<KeyRelease>'); "
                "в tick: if 'Left' in pressed: canvas.move(player, -5, 0); after(ms, tick); mainloop. "
                "НИКОГДА winfo_keysym — такого метода у Tk нет, шаг не засчитается."
            ),
            tool_hint=f'write_file path="{rel}"',
        ),
        ExecutionStep(
            id="gui_world",
            title="Мир",
            instruction=(
                f"Сейчас write_file {rel} ЦЕЛИКОМ: {world} "
                "Всё ещё tkinter Canvas, один файл."
            ),
            tool_hint=f'write_file path="{rel}"',
        ),
    ]


def gui_app_window_plan(*, path: str, user_task: str = "") -> list[ExecutionStep]:
    """Окно-приложение (калькулятор, сапёр): один файл, без Canvas-игрока."""
    rel = (path or "app.py").replace("\\", "/")
    from core.game_gui_upgrade import looks_like_calculator_task, looks_like_minesweeper_task

    if looks_like_calculator_task(user_task):
        instruction = (
            f"Сейчас ТОЛЬКО write_file {rel}: калькулятор на tkinter. "
            "Entry + кнопки цифр и операций (или Entry + «Вычислить»). "
            "БЕЗ Canvas, БЕЗ create_rectangle, БЕЗ tick/after, БЕЗ «игрока». mainloop."
        )
    elif looks_like_minesweeper_task(user_task):
        instruction = (
            f"Сейчас write_file {rel}: сапёр на tkinter — сетка tk.Button, флаги ПКМ. "
            "БЕЗ Canvas с движущимся прямоугольником. mainloop."
        )
    else:
        instruction = (
            f"Сейчас write_file {rel}: tkinter-приложение — Label/Entry/Button под задачу. "
            "Не игровой Canvas. mainloop."
        )
    return [
        ExecutionStep(
            id="gui_app",
            title="Приложение",
            instruction=instruction,
            tool_hint=f'write_file path="{rel}"',
        ),
        ExecutionStep(
            id="verify",
            title="Проверка",
            instruction="CoreX сам запустит файл. Если упало — исправь, не done.",
            tool_hint="run_file",
        ),
    ]


MAX_GUI_FILE_WRITES = 4


def is_gui_app_plan(steps: list[ExecutionStep]) -> bool:
    return any(str(step.id) == "gui_app" for step in steps)


def gui_app_satisfied(source: str) -> bool:
    """Калькулятор/утилита: кнопки или поле ввода, не Canvas-игрок."""
    blob = source or ""
    low = blob.lower()
    if "tkinter" not in low or "mainloop" not in low:
        return False
    has_controls = bool(
        re.search(r"\bButton\s*\(|tk\.Button\s*\(", blob)
        or re.search(r"\bEntry\s*\(|tk\.Entry\s*\(", blob)
    )
    if not has_controls:
        return False
    if re.search(r"create_rectangle", blob, re.I) and not re.search(
        r"\bButton\s*\(|tk\.Button\s*\(", blob
    ):
        return False
    if re.search(r"(?<![.\w])after\s*\(", blob) and re.search(r"\btick\b", blob, re.I):
        return False
    return True


def sync_gui_app_from_source(
    steps: list[ExecutionStep],
    completed_ids: set[str],
    source: str,
) -> set[str]:
    done = set(completed_ids)
    if is_gui_app_plan(steps) and gui_app_satisfied(source):
        done.add("gui_app")
    return done


def gui_bite_satisfied(step_id: str, source: str) -> bool:
    """Шаг окна/ходьбы/мира — по содержимому файла, не по факту write_file."""
    blob = source or ""
    low = blob.lower()
    if step_id == "gui_window":
        return "tkinter" in low and "canvas" in low and "mainloop" in low
    if step_id == "gui_move":
        if re.search(r"winfo_keysym", blob, re.I):
            return False
        return bool(
            re.search(
                r"\.bind\s*\(\s*['\"](?:<Key|KeyPress)",
                blob,
                re.I,
            )
        )
    if step_id == "gui_world":
        rects = len(re.findall(r"create_rectangle", blob, re.I))
        return rects >= 3 or bool(
            re.search(r"\bwalls?\b|\bmaze\b|collide|collision|выход|\bexit\b", blob, re.I)
        )
    return False


def sync_gui_bites_from_source(
    steps: list[ExecutionStep],
    completed_ids: set[str],
    source: str,
) -> set[str]:
    done = set(completed_ids)
    for step in steps:
        if not str(step.id).startswith("gui_"):
            continue
        if gui_bite_satisfied(step.id, source):
            done.add(step.id)
        elif step.id != "gui_window":
            done.discard(step.id)
    return done


def is_gui_bite_plan(steps: list[ExecutionStep]) -> bool:
    return any(str(step.id).startswith("gui_") for step in steps)


def pending_gui_bite(steps: list[ExecutionStep], completed_ids: set[str]) -> str | None:
    done = completed_ids or set()
    for step in steps:
        if str(step.id).startswith("gui_") and step.id not in done:
            return step.id
    return None


def gui_partial_stop_message(steps: list[ExecutionStep], completed_ids: set[str], path: str) -> str:
    rel = (path or "game.py").replace("\\", "/")
    done = completed_ids or set()
    if "gui_window" in done and "gui_move" not in done:
        return (
            f"Окно есть в {rel}. Ходьбу (WASD) модель не дописала — "
            f"скажи: добавь WASD в /{rel}"
        )
    if "gui_move" in done and "gui_world" not in done:
        return (
            f"Окно и ходьба есть в {rel}. Мир (стены) не дописан — "
            f"скажи: добавь стены в /{rel}"
        )
    if "gui_window" in done:
        return f"Файл {rel} записан. Можно открыть и дописать следующим запросом."
    return f"Не удалось дописать {rel}. Повтори запрос короче: только окно, без всего Doom сразу."


def create_code_plan(*, coding_language: str = "auto") -> list[ExecutionStep]:
    target = _code_target_name(coding_language)
    return [
        ExecutionStep(
            id="write_complete",
            title="Полный файл",
            instruction=(
                f"Сейчас запиши ПОЛНЫЙ рабочий {target} за один ход. "
                "JSON не обязателен: достаточно блока ```python ... ``` — CoreX сохранит файл. "
                "Или JSON write_file и тот же код в ``` после него. "
                "Не заглушка из двух print. Не list_directory. Не каркас."
            ),
            tool_hint=f'```python fence or write_file path="{target}"',
        ),
        ExecutionStep(
            id="verify",
            title="Проверка",
            instruction=(
                "CoreX сам проверит синтаксис. Игры с while True / pygame не запускай. "
                "Затем done."
            ),
            tool_hint="done",
        ),
    ]


def generic_code_plan(*, coding_language: str = "auto") -> list[ExecutionStep]:
    target = _code_target_name(coding_language)
    return [
        ExecutionStep(
            id="inspect",
            title="Осмотр",
            instruction="Сейчас ТОЛЬКО list_directory — понять структуру. Не читай design-system, если задача не про сайт.",
            tool_hint="list_directory",
        ),
        ExecutionStep(
            id="view",
            title="Прочитать",
            instruction=f"Сейчас view_file {target}. Номер слева = line. Запомни его перед правкой.",
            tool_hint=f'view_file path="{target}"',
        ),
        ExecutionStep(
            id="patch",
            title="Правка",
            instruction=(
                f"Сейчас patch_file {target}: одна правка, line из view_file. "
                "replace — изменить эту строку, delete — удалить её. "
                "Не угадывай номер. CoreX поправит отступы сам."
            ),
            tool_hint=f'patch_file path="{target}"',
        ),
        ExecutionStep(
            id="verify",
            title="Проверка",
            instruction="Сейчас CoreX сам запустит файл. Если упало — чини причину, не done.",
            tool_hint="run_file",
        ),
    ]


def pick_execution_plan(
    *,
    user_task: str,
    goal: str = "",
    agent_id: str = "",
    design_folder: str = "design-system",
    has_design_folder: bool = False,
    coding_language: str = "auto",
) -> list[ExecutionStep]:
    from core.coding_language import (
        language_forces_code,
        language_forces_web,
        resolve_effective_language,
    )

    agent = (agent_id or "").replace("agent:", "").lower()
    effective = resolve_effective_language(coding_language, user_task, goal)
    blob = f"{user_task} {goal}".lower()
    is_web = any(
        token in blob
        for token in ("сайт", "site", "html", "css", "landing", "веб", "web", "страниц")
    )

    from core.task_routing import looks_like_fix_request

    if language_forces_code(effective):
        if looks_like_fix_request(user_task) or looks_like_fix_request(goal):
            return generic_code_plan(coding_language=effective)
        return create_code_plan(coding_language=effective)
    if language_forces_web(effective):
        if "designer" in agent or "ui-ux" in agent:
            return designer_plan(design_folder=design_folder)
        return web_developer_plan(design_folder=design_folder)
    if "designer" in agent or "ui-ux" in agent:
        return designer_plan(design_folder=design_folder)
    if is_web or (has_design_folder and ("developer" in agent or "lead" in agent) and is_web):
        return web_developer_plan(design_folder=design_folder)
    if looks_like_fix_request(user_task) or looks_like_fix_request(goal):
        return generic_code_plan(coding_language=effective)
    return create_code_plan(coding_language=effective)


def path_from_tool_hint(tool_hint: str) -> str:
    match = re.search(r'path="([^"]+)"', tool_hint or "")
    return (match.group(1) if match else "").replace("\\", "/")


def current_write_target(
    steps: list[ExecutionStep],
    completed_ids: set[str],
) -> str | None:
    """Путь файла текущего шага write_file — куда CoreX должен писать сейчас."""
    done = completed_ids or set()
    for step in steps:
        if step.id in done:
            continue
        if "write_file" not in (step.tool_hint or ""):
            continue
        path = path_from_tool_hint(step.tool_hint)
        if path:
            return path
    return None


def format_current_bite(
    steps: list[ExecutionStep],
    completed_ids: set[str],
) -> str:
    """Один кусочек: только текущий шаг."""
    total = len(steps)
    for index, step in enumerate(steps, start=1):
        if step.id in completed_ids:
            continue
        return (
            f"=== СЕЙЧАС ШАГ {index}/{total} [{step.id}] ===\n"
            f"{step.title}\n"
            f"{step.instruction}\n"
            f"Tool: {step.tool_hint}\n"
            "Один tool за этот ход. Не done и не перескакивай вперёд.\n"
            f"=== КОНЕЦ ШАГА {index}/{total} ==="
        )
    return (
        "=== ВСЕ ШАГИ ПЛАНА ВЫПОЛНЕНЫ ===\n"
        'Можно завершить: {"status":"done","message":"что сделано — 1–2 предложения, без шаблонных фраз"}\n'
    )


def format_plan_overview(steps: list[ExecutionStep]) -> str:
    titles = ", ".join(f"{i + 1}.{s.title}" for i, s in enumerate(steps))
    return f"План ({len(steps)} шагов): {titles}. CoreX выдаёт по одному шагу."


def format_plan_for_prompt(steps: list[ExecutionStep]) -> str:
    return format_plan_overview(steps) + "\n\n" + format_current_bite(steps, set())


def next_step_hint(steps: list[ExecutionStep], completed_ids: set[str]) -> str | None:
    return "System:\n" + format_current_bite(steps, completed_ids)


def mark_step_completed(
    steps: list[ExecutionStep],
    completed_ids: set[str],
    *,
    tool: str,
    path: str,
    success: bool,
) -> set[str]:
    if not success:
        return completed_ids
    rel = (path or "").replace("\\", "/").lower()
    done = set(completed_ids)
    if tool in {"write_file", "append_file"}:
        for step in steps:
            if str(step.id).startswith("gui_"):
                continue
            hinted = path_from_tool_hint(step.tool_hint).lower()
            if hinted and hinted == rel:
                done.add(step.id)
                break

    if tool in {"view_file", "list_directory"}:
        if "master.md" in rel:
            done.add("read_design")
            done.add("inspect")
        if "/pages/" in rel and rel.endswith(".md"):
            done.add("read_page")
            done.add("read_design")
        if any(token in rel for token in ("/blocks/", "design-system", "design/")) and rel.endswith(".md"):
            done.add("read_design")
        if tool == "list_directory":
            done.add("inspect")
        if rel.endswith("index.html"):
            done.add("verify_html")
            done.add("verify_link")
        if rel.endswith(".css"):
            done.add("verify_css")

    if tool in {"write_file", "append_file"}:
        if "master.md" in rel:
            done.add("master")
            done.add("read_design")
        if "/pages/" in rel and rel.endswith(".md"):
            done.add("page")
        if "/blocks/hero" in rel:
            done.add("block_hero")
            done.add("blocks")
        if "/blocks/navigation" in rel:
            done.add("block_nav")
            done.add("blocks")
        if "/blocks/sections" in rel:
            done.add("block_sections")
            done.add("blocks")
        if "/blocks/" in rel and rel.endswith(".md"):
            done.add("blocks")
        if rel.endswith("index.html"):
            done.add("html_structure")
        if rel.endswith(".css"):
            done.add("css_layout")
            done.add("polish")
        if rel.endswith(".js"):
            done.add("js_interact")
            done.add("polish")

    if tool == "patch_file" and (rel.endswith(".css") or rel.endswith(".js")):
        done.add("polish")

    if tool in {"run_file", "run_command"}:
        done.add("verify")

    if "verify_html" in done and "verify_css" in done:
        done.add("verify_link")

    if tool == "view_file" and not rel.endswith((".html", ".css", ".md")):
        done.add("view")
    if tool == "patch_file" and not rel.endswith((".html", ".css", ".md")):
        done.add("patch")
        done.add("extend")
        done.add("implement")
    if tool == "write_file" and not rel.endswith((".html", ".css", ".md")):
        done.add("write_complete")
        done.add("skeleton")
        done.add("implement")
        done.add("write_game")
    if tool == "append_file" and not rel.endswith((".html", ".css", ".md")):
        done.add("extend")
        done.add("implement")
        done.add("write_complete")

    return done


def all_steps_done(steps: list[ExecutionStep], completed_ids: set[str]) -> bool:
    optional = {"polish", "verify"}
    required = {step.id for step in steps if step.id not in optional}
    return required.issubset(completed_ids)


def should_block_done_for_plan(
    steps: list[ExecutionStep],
    completed_ids: set[str],
    *,
    is_web: bool = False,
) -> bool:
    """Сайт и GUI-куски: нельзя done, пока текущий план не закрыт по содержимому."""
    if not steps:
        return False
    if not (is_web or is_gui_bite_plan(steps) or is_gui_app_plan(steps)):
        return False
    return not all_steps_done(steps, completed_ids)
