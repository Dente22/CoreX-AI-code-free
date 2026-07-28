"""Поэтапное выполнение задач: «съесть слона по кусочкам» (offline и online)."""

from __future__ import annotations

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


def generic_code_plan() -> list[ExecutionStep]:
    return [
        ExecutionStep(
            id="inspect",
            title="Осмотр",
            instruction="Сейчас ТОЛЬКО list_directory или view_file — понять структуру.",
            tool_hint="view_file или list_directory",
        ),
        ExecutionStep(
            id="implement",
            title="Реализация",
            instruction="Сейчас ТОЛЬКО write_file или patch_file — один файл за ход.",
            tool_hint="write_file / patch_file",
        ),
        ExecutionStep(
            id="verify",
            title="Проверка",
            instruction="Сейчас run_file / run_command. Затем done.",
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
) -> list[ExecutionStep]:
    agent = (agent_id or "").replace("agent:", "").lower()
    blob = f"{user_task} {goal}".lower()
    is_web = any(
        token in blob
        for token in ("сайт", "site", "html", "css", "landing", "веб", "web", "страниц")
    )
    if "designer" in agent or "ui-ux" in agent:
        return designer_plan(design_folder=design_folder)
    if is_web or has_design_folder or "developer" in agent or "lead" in agent:
        return web_developer_plan(design_folder=design_folder)
    return generic_code_plan()


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
        'Можно завершить: {"status":"done","message":"краткий отчёт на русском"}\n'
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

    if tool == "write_file":
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

    if tool == "write_file" and not rel.endswith((".html", ".css", ".md")):
        done.add("implement")

    return done


def all_steps_done(steps: list[ExecutionStep], completed_ids: set[str]) -> bool:
    optional = {"polish", "verify"}
    required = {step.id for step in steps if step.id not in optional}
    return required.issubset(completed_ids)
