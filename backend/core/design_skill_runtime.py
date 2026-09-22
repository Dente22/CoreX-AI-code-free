"""Запуск скилла ui-ux-pro-max: палитра и шрифты на диск, не через локальную модель."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.core_x_library import COREX_ROOT

SEARCH_SCRIPT = (
    COREX_ROOT
    / "core_x_skills"
    / "design"
    / "ui_ux"
    / "ui-ux-pro-max"
    / "scripts"
    / "search.py"
)

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_TABLE_COLOR = re.compile(
    r"\|\s*(Primary|Accent/?CTA|Accent|Secondary|Background|Foreground|Muted|Card)\s*"
    r"\|\s*`?(#[0-9A-Fa-f]{3,8})`?",
    re.I,
)
_HEADING_FONT = re.compile(r"\*\*Heading Font:\*\*\s*(.+)$", re.I | re.M)
_BODY_FONT = re.compile(r"\*\*Body Font:\*\*\s*(.+)$", re.I | re.M)
_STYLE_NAME = re.compile(r"\*\*Style:\*\*\s*(.+)$", re.I | re.M)
_PATTERN_NAME = re.compile(r"\*\*Pattern Name:\*\*\s*(.+)$", re.I | re.M)
_GOOGLE_FONTS = re.compile(r"\*\*Google Fonts:\*\*.*\((https://fonts\.google[^)]+)\)", re.I)


@dataclass(frozen=True)
class DesignTokens:
    primary: str = "#9A5EFF"
    accent: str = "#00D2FF"
    background: str = "#0b1020"
    surface: str = "#151c2e"
    text: str = "#e8eef7"
    muted: str = "#94a3b8"
    heading_font: str = "Inter"
    body_font: str = "Inter"
    style_name: str = ""
    pattern_name: str = ""
    google_fonts_url: str = ""
    source: str = "fallback"


def design_search_query(user_task: str) -> str:
    from core.web_delivery_layers import infer_page_title

    title = infer_page_title(user_task)
    lower = (user_task or "").lower()
    bits = [title]
    if any(word in lower for word in ("клуб", "club", "кибер", "game", "игр", "компьютерн")):
        bits.append("gaming computer club entertainment dark neon cyberpunk")
    if any(word in lower for word in ("сайт", "landing", "лендинг", "страниц", "site")):
        bits.append("landing page")
    bits.append("dark mode modern")
    return " ".join(part for part in bits if part).strip()


def is_skill_generated_master(text: str) -> bool:
    blob = text or ""
    return "Design System Master File" in blob or "| Role | Hex |" in blob


def is_generic_corex_spec(text: str) -> bool:
    blob = text or ""
    return "# Design Spec —" in blob and "#9A5EFF" in blob and not is_skill_generated_master(blob)


def parse_design_tokens(master_md: str) -> DesignTokens:
    text = master_md or ""
    found: dict[str, str] = {}
    for match in _TABLE_COLOR.finditer(text):
        role = match.group(1).lower().replace("/cta", "").replace(" ", "")
        found[role] = match.group(2)

    heading_match = _HEADING_FONT.search(text)
    body_match = _BODY_FONT.search(text)
    heading = (heading_match.group(1) if heading_match else "Inter").split("(")[0].strip().strip("*").strip()
    body = (body_match.group(1) if body_match else "Inter").split("(")[0].strip().strip("*").strip()
    style_match = _STYLE_NAME.search(text)
    pattern_match = _PATTERN_NAME.search(text)
    style = style_match.group(1).strip() if style_match else ""
    pattern = pattern_match.group(1).strip() if pattern_match else ""
    fonts = _GOOGLE_FONTS.search(text)

    primary = found.get("primary") or DesignTokens.primary
    accent = found.get("accent") or found.get("secondary") or DesignTokens.accent
    background = found.get("background") or DesignTokens.background
    text_color = found.get("foreground") or DesignTokens.text
    muted = found.get("muted") or DesignTokens.muted
    surface = found.get("card") or DesignTokens.surface
    if not _HEX_RE.fullmatch(surface or ""):
        surface = DesignTokens.surface

    source = "ui-ux-pro-max" if is_skill_generated_master(text) else "parsed"
    return DesignTokens(
        primary=primary,
        accent=accent,
        background=background,
        surface=surface,
        text=text_color,
        muted=muted,
        heading_font=heading or "Inter",
        body_font=body or "Inter",
        style_name=style,
        pattern_name=pattern,
        google_fonts_url=(fonts.group(1).strip() if fonts else ""),
        source=source,
    )


def load_project_design_tokens(project_root: Path) -> DesignTokens:
    master = Path(project_root) / "design-system" / "MASTER.md"
    try:
        text = master.read_text(encoding="utf-8")
    except OSError:
        return DesignTokens()
    if not text.strip():
        return DesignTokens()
    return parse_design_tokens(text)


def google_fonts_href(tokens: DesignTokens) -> str:
    if tokens.google_fonts_url:
        return tokens.google_fonts_url
    families: list[str] = []
    seen: set[str] = set()
    for font in (tokens.heading_font, tokens.body_font):
        name = (font or "").strip()
        key = name.lower()
        if not name or key in seen or key in {"system-ui", "sans-serif", "arial", "serif"}:
            continue
        seen.add(key)
        families.append(f"family={name.replace(' ', '+')}:wght@400;600;800")
    if not families:
        return ""
    return "https://fonts.googleapis.com/css2?" + "&".join(families) + "&display=swap"


def design_skill_digest(project_root: Path, *, max_chars: int = 4500) -> str:
    master = Path(project_root) / "design-system" / "MASTER.md"
    try:
        text = master.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    if not text:
        return ""
    tokens = parse_design_tokens(text)
    body = text if len(text) <= max_chars else text[: max_chars - 20] + "\n…"
    return (
        "=== UI/UX PRO MAX (скилл уже выполнен, spec на диске) ===\n"
        f"Стиль: {tokens.style_name or 'из MASTER.md'}. "
        f"Primary {tokens.primary}, accent {tokens.accent}, "
        f"шрифты {tokens.heading_font} / {tokens.body_font}.\n"
        "Не выдумывай другую палитру и не ставь серый Arial.\n"
        f"{body}\n"
        "=== END DESIGN SKILL ===\n"
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def promote_persisted_design(project_root: Path) -> list[str]:
    """Скилл пишет design-system/<slug>/MASTER.md — поднимаем в design-system/MASTER.md."""
    ds = Path(project_root) / "design-system"
    if not ds.is_dir():
        return []
    nested = sorted(ds.glob("*/MASTER.md"))
    canonical = ds / "MASTER.md"
    promoted: list[str] = []
    source: Path | None = None
    if nested:
        source = max(nested, key=lambda path: (len(_read_text(path)), path.stat().st_mtime))
    if source and source.is_file():
        src_text = _read_text(source)
        dest_text = _read_text(canonical)
        should_write = (
            not dest_text.strip()
            or is_generic_corex_spec(dest_text)
            or (is_skill_generated_master(src_text) and not is_skill_generated_master(dest_text))
        )
        if should_write and src_text.strip():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_text(src_text, encoding="utf-8")
            promoted.append("design-system/MASTER.md")
        src_pages = source.parent / "pages"
        dest_pages = ds / "pages"
        if src_pages.is_dir():
            dest_pages.mkdir(parents=True, exist_ok=True)
            for page in src_pages.glob("*.md"):
                dest = dest_pages / page.name
                existing = _read_text(dest)
                if not existing.strip() or is_generic_corex_spec(existing):
                    dest.write_text(_read_text(page), encoding="utf-8")
                    promoted.append(f"design-system/pages/{page.name}")
    return promoted


def persist_uiux_pro_max(project_root: Path, *, user_task: str) -> list[str]:
    """Прогнать search.py --design-system --persist в папку проекта."""
    if not SEARCH_SCRIPT.is_file():
        return []
    canonical = Path(project_root) / "design-system" / "MASTER.md"
    if canonical.is_file() and is_skill_generated_master(_read_text(canonical)):
        return promote_persisted_design(project_root)

    from core.web_delivery_layers import infer_page_title

    title = infer_page_title(user_task)
    query = design_search_query(user_task)
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    argv = [
        sys.executable,
        str(SEARCH_SCRIPT),
        query,
        "--design-system",
        "--persist",
        "-p",
        title,
        "--page",
        "index",
        "-o",
        str(Path(project_root).resolve()),
    ]
    kwargs: dict = {
        "cwd": str(SEARCH_SCRIPT.parent),
        "env": env,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": 90,
    }
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.run(argv, **kwargs)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return promote_persisted_design(project_root)


def with_fallback(tokens: DesignTokens | None) -> DesignTokens:
    return tokens if tokens is not None else DesignTokens()
