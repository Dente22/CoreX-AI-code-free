"""Handoff дизайнера → разработчика: артефакты на диске + контекст в промпт."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.web_delivery_layers import BRAND_ACCENT, BRAND_PRIMARY, infer_page_title

DESIGN_ROOT = "design-system"

MASTER_MIN_CHARS = 380
PAGE_MIN_CHARS = 180
BLOCK_MIN_CHARS = 120


@dataclass(frozen=True)
class DesignRoots:
    read_root: Path
    label: str

    @property
    def master_path(self) -> str:
        return f"{self.label}/MASTER.md"

    @property
    def page_index_path(self) -> str:
        return f"{self.label}/pages/index.md"

    @property
    def blocks_dir(self) -> str:
        return f"{self.label}/blocks"


def resolve_design_roots(project_root: Path, app_root: Path | None) -> DesignRoots:
    from core.workload_limits_service import get_design_folder_path

    raw = get_design_folder_path(app_root)
    candidate = Path(raw)
    if candidate.is_absolute():
        return DesignRoots(read_root=candidate, label=str(candidate))
    label = raw.strip("/\\") or DESIGN_ROOT
    return DesignRoots(read_root=project_root / label, label=label)


def recommended_block_paths(label: str) -> tuple[str, ...]:
    blocks = f"{label}/blocks"
    return (
        f"{blocks}/hero.md",
        f"{blocks}/navigation.md",
        f"{blocks}/sections.md",
    )


def required_rel_paths(roots: DesignRoots) -> tuple[str, ...]:
    return (roots.master_path, roots.page_index_path)


@dataclass(frozen=True)
class DesignHandoffValidation:
    ok: bool
    missing: tuple[str, ...]
    weak: tuple[str, ...]
    files: tuple[str, ...]

    @property
    def error(self) -> str:
        parts: list[str] = []
        if self.missing:
            parts.append("нет файлов: " + ", ".join(self.missing))
        if self.weak:
            parts.append("слишком короткие: " + ", ".join(self.weak))
        return "; ".join(parts) or "design handoff не готов"

    @property
    def summary(self) -> str:
        if not self.ok:
            return self.error
        return ", ".join(self.files)


def _read_rel(root: Path, rel: str) -> str:
    path = root / rel.replace("/", "\\") if "\\" in str(root) else root / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _char_ok(rel: str, content: str) -> bool:
    text = (content or "").strip()
    if rel.endswith("MASTER.md"):
        return len(text) >= MASTER_MIN_CHARS
    if rel.endswith("pages/index.md"):
        return len(text) >= PAGE_MIN_CHARS
    if "/blocks/" in rel.replace("\\", "/"):
        return len(text) >= BLOCK_MIN_CHARS
    return len(text) >= 80


def _read_abs(read_root: Path, rel: str, label: str) -> str:
    rel_norm = rel.replace("\\", "/")
    label_norm = label.replace("\\", "/").rstrip("/")
    if rel_norm.startswith(label_norm + "/"):
        rel_norm = rel_norm[len(label_norm) + 1 :]
    path = read_root / rel_norm.replace("/", "\\") if "\\" in str(read_root) else read_root / rel_norm
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def validate_design_handoff(project_root: Path, app_root: Path | None = None) -> DesignHandoffValidation:
    roots = resolve_design_roots(project_root, app_root)
    missing: list[str] = []
    weak: list[str] = []
    files: list[str] = []

    for rel in required_rel_paths(roots):
        content = _read_abs(roots.read_root, rel, roots.label)
        if not content.strip():
            missing.append(rel)
            continue
        files.append(rel)
        if not _char_ok(rel, content):
            weak.append(rel)

    for rel in recommended_block_paths(roots.label):
        content = _read_abs(roots.read_root, rel, roots.label)
        if content.strip():
            files.append(rel)
            if not _char_ok(rel, content):
                weak.append(rel)

    ok = not missing and not weak
    return DesignHandoffValidation(
        ok=ok,
        missing=tuple(missing),
        weak=tuple(weak),
        files=tuple(files),
    )


def starter_master_md(*, user_task: str) -> str:
    title = infer_page_title(user_task)
    return f"""# Design Spec — {title}

## 1. Цель и аудитория
- Задача: {user_task.strip()[:240]}
- Аудитория: посетители сайта, desktop + mobile

## 2. Цвета и типографика
- Primary: {BRAND_PRIMARY}
- Accent: {BRAND_ACCENT}
- Background: #0f1720, Surface: #1a2332, Text: #e8eef7
- Шрифт: Inter, system-ui, sans-serif
- H1: clamp(1.8rem, 3vw, 2.6rem), body: 1rem / 1.65

## 3. Layout (index)
- Header: логотип/название + tagline
- Nav: 3 ссылки → #about, #events, #contact
- Hero: заголовок + подзаголовок + CTA-кнопка
- Main: 3 секции-карточки с отступами
- Footer: copyright + контакты

## 4. Компоненты
- `.container` max-width 1100px
- Кнопки: gradient primary→accent, radius 12px, hover lift
- Карточки секций: surface bg, shadow, padding 24px

## 5. Anti-patterns (не делать)
- Одноцветный белый фон без структуры
- Ссылки без hover-состояния
- Секции без заголовков h2

## 6. a11y
- Конtrast ≥ 4.5:1 для текста
- focus-visible на nav и кнопках
- lang=ru, semantic header/nav/main/footer
"""


def starter_page_index_md(*, user_task: str) -> str:
    title = infer_page_title(user_task)
    return f"""# Page: index (главная)

## Meta
- title: {title}
- lang: ru

## Hero
- H1: {title}
- Subtitle: краткое описание ценности (1–2 предложения)
- CTA: «Узнать больше» → #about

## Navigation
- О нас → #about
- Мероприятия → #events
- Контакты → #contact

## Sections
### #about
- H2: О нас
- Текст + 2–3 буллета преимуществ

### #events
- H2: Мероприятия / программа
- Список из 3 пунктов (карточки или ul)

### #contact
- H2: Контакты
- Email, адрес или форма-заглушка

## Footer
- © {title}, ссылка на контакт
"""


def starter_block_md(*, name: str, user_task: str, tokens=None) -> str:
    from core.design_skill_runtime import with_fallback

    t = with_fallback(tokens)
    title = infer_page_title(user_task)
    primary = t.primary
    accent = t.accent
    blocks = {
        "hero": (
            f"# Block: Hero\n\n"
            f"- Заголовок: {title}\n"
            f"- Фон: gradient {primary} → {accent}\n"
            f"- Padding: 48px 0, text-align left\n"
            f"- CTA button: accent {accent}, radius 12px\n"
            f"- Стиль скилла: {t.style_name or 'из MASTER.md'}\n"
        ),
        "navigation": (
            "# Block: Navigation\n\n"
            f"- Sticky optional, bg {accent}\n"
            "- Links: 3 anchor, font-weight 600, hover underline\n"
            "- Mobile: wrap или stack\n"
        ),
        "sections": (
            "# Block: Sections\n\n"
            "- `.container` wrapper\n"
            f"- Each section: surface {t.surface}, margin-bottom 20px, padding 24px\n"
            f"- H2 margin-top 0, body muted {t.muted} for secondary text\n"
        ),
    }
    return blocks.get(name, f"# Block: {name}\n\nSpec for {title}.\n")


def ensure_design_scaffold(
    project_root: Path,
    *,
    user_task: str,
    app_root: Path | None = None,
) -> list[str]:
    """Сначала скилл ui-ux-pro-max, затем недостающие файлы (не затирая spec скилла)."""
    from core.design_skill_runtime import (
        is_generic_corex_spec,
        is_skill_generated_master,
        load_project_design_tokens,
        persist_uiux_pro_max,
    )

    created: list[str] = []
    created.extend(persist_uiux_pro_max(project_root, user_task=user_task))

    roots = resolve_design_roots(project_root, app_root)
    write_root = project_root / roots.label if not Path(roots.label).is_absolute() else roots.read_root
    tokens = load_project_design_tokens(project_root)

    specs: list[tuple[str, str]] = [
        (roots.master_path, starter_master_md(user_task=user_task)),
        (roots.page_index_path, starter_page_index_md(user_task=user_task)),
        (f"{roots.blocks_dir}/hero.md", starter_block_md(name="hero", user_task=user_task, tokens=tokens)),
        (f"{roots.blocks_dir}/navigation.md", starter_block_md(name="navigation", user_task=user_task, tokens=tokens)),
        (f"{roots.blocks_dir}/sections.md", starter_block_md(name="sections", user_task=user_task, tokens=tokens)),
    ]

    for rel, content in specs:
        rel_norm = rel.replace("\\", "/")
        label_norm = roots.label.replace("\\", "/").rstrip("/")
        if rel_norm.startswith(label_norm + "/"):
            rel_norm = rel_norm[len(label_norm) + 1 :]
        path = write_root / rel_norm.replace("/", "\\") if "\\" in str(write_root) else write_root / rel_norm
        existing = ""
        if path.is_file():
            try:
                existing = path.read_text(encoding="utf-8")
            except OSError:
                existing = ""
        if existing.strip():
            if rel_norm.endswith("MASTER.md") and (
                is_skill_generated_master(existing) or not is_generic_corex_spec(existing)
            ):
                continue
            if not rel_norm.endswith("MASTER.md"):
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(rel)

    return created


def collect_design_bundle(
    project_root: Path,
    *,
    app_root: Path | None = None,
    max_chars: int = 12_000,
) -> dict[str, str]:
    roots = resolve_design_roots(project_root, app_root)
    bundle: dict[str, str] = {}
    candidates = list(required_rel_paths(roots)) + list(recommended_block_paths(roots.label))
    for rel in candidates:
        content = _read_abs(roots.read_root, rel, roots.label).strip()
        if content:
            bundle[rel] = content

    blocks_path = roots.read_root / "blocks"
    if blocks_path.is_dir():
        for path in sorted(blocks_path.glob("*.md")):
            rel = f"{roots.blocks_dir}/{path.name}"
            if rel in bundle:
                continue
            content = path.read_text(encoding="utf-8").strip()
            if content:
                bundle[rel] = content

    pages_path = roots.read_root / "pages"
    if pages_path.is_dir():
        for path in sorted(pages_path.glob("*.md")):
            rel = f"{roots.label}/pages/{path.name}".replace("\\", "/")
            if rel in bundle:
                continue
            content = path.read_text(encoding="utf-8").strip()
            if content:
                bundle[rel] = content

    trimmed: dict[str, str] = {}
    total = 0
    for rel, content in bundle.items():
        if total >= max_chars:
            trimmed[rel] = content[: max(200, max_chars - total)] + "\n…"
            break
        if total + len(content) > max_chars:
            trimmed[rel] = content[: max_chars - total] + "\n…"
            total = max_chars
            break
        trimmed[rel] = content
        total += len(content)
    return trimmed


def load_design_context_from_folder(project_root: Path, app_root: Path | None = None) -> str:
    bundle = collect_design_bundle(project_root, app_root=app_root)
    if not bundle:
        roots = resolve_design_roots(project_root, app_root)
        return (
            f"Папка дизайна ({roots.label}) пуста или не найдена. "
            f"list_directory {roots.label} и view_file spec-файлы."
        )
    return format_design_bundle_for_prompt(bundle)


def format_design_bundle_for_prompt(bundle: dict[str, str]) -> str:
    if not bundle:
        return (
            "Design handoff пуст. list_directory папки дизайна и view_file MASTER.md / pages/index.md."
        )
    parts = [
        "Ниже — Design Spec из папки дизайна. Реализуй HTML/CSS строго по этим файлам.",
        "Порядок: MASTER.md → pages/index.md → blocks/*.md",
        "",
    ]
    for rel, content in bundle.items():
        parts.append(f"--- FILE: {rel} ---")
        parts.append(content)
        parts.append("")
    return "\n".join(parts).strip()


def designer_handoff_prompt_ru(*, user_task: str, design_folder: str = DESIGN_ROOT) -> str:
    task = (user_task or "").strip()[:220]
    df = design_folder.strip().rstrip("/\\") or DESIGN_ROOT
    return (
        "\n=== DESIGN HANDOFF (обязательно сохранить на диск) ===\n"
        "Дизайнер ОБЯЗАН записать spec файлами — разработчик читает только их.\n"
        "Порядок (отдельный write_file на каждый файл, минимум 3 хода):\n"
        f"1) write_file {df}/MASTER.md — полный Design Spec (≥{MASTER_MIN_CHARS} симв.)\n"
        f"2) write_file {df}/pages/index.md — структура главной страницы\n"
        f"3) write_file {df}/blocks/hero.md, navigation.md, sections.md\n"
        "Запрещено done без успешных write_file в папке дизайна.\n"
        "Не затирай палитру скилла ui-ux-pro-max серым Arial / #333.\n"
        f"Задача: {task}\n"
        "Цвета и шрифты бери из уже записанного MASTER.md (скилл), не выдумывай другую палитру.\n"
    )


def developer_handoff_prompt_ru(*, user_task: str, design_folder: str = DESIGN_ROOT) -> str:
    task = (user_task or "").strip()[:220]
    df = design_folder.strip().rstrip("/\\") or DESIGN_ROOT
    return (
        "\n=== DEVELOPER READS DESIGN (strict layers) ===\n"
        "Layer 1 — Прочитай DESIGN HANDOFF / view_file spec.\n"
        f"Layer 2 — view_file {df}/MASTER.md и {df}/pages/index.md\n"
        "Layer 3 — write_file index.html (link style.css + script.js, hero CTA, section id=)\n"
        "Layer 4 — write_file style.css (тёмный фон, gradient, cards, @media, ≥900)\n"
        "Layer 5 — write_file script.js (mobile nav + smooth scroll + CTA)\n"
        "Не done без script.js. Не белый плоский сайт.\n"
        "Цвета, шрифты и стиль — строго из MASTER.md (скилл ui-ux-pro-max), не дефолт CoreX.\n"
        f"Task: {task}\n"
    )
