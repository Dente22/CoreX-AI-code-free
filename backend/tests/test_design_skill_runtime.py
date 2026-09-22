from pathlib import Path

from core.design_handoff import ensure_design_scaffold
from core.design_skill_runtime import (
    SEARCH_SCRIPT,
    design_search_query,
    parse_design_tokens,
    persist_uiux_pro_max,
)
from core.web_delivery_layers import salvage_web_project, starter_style_css


SAMPLE_MASTER = """# Design System Master File

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#FF2D95` | `--color-primary` |
| Accent/CTA | `#7CFF6B` | `--color-accent` |
| Background | `#0A0514` | `--color-background` |
| Foreground | `#F4F1FF` | `--color-foreground` |
| Muted | `#9B8FB0` | `--color-muted` |
| Card | `#1A1028` | `--color-card` |

### Typography

- **Heading Font:** Orbitron
- **Body Font:** Inter

## Style Guidelines

**Style:** Cyberpunk Neon

**Pattern Name:** Hero + Cards
"""


def test_parse_design_tokens_from_pro_max_master():
    tokens = parse_design_tokens(SAMPLE_MASTER)
    assert tokens.primary == "#FF2D95"
    assert tokens.accent == "#7CFF6B"
    assert tokens.background == "#0A0514"
    assert tokens.heading_font == "Orbitron"
    assert tokens.style_name == "Cyberpunk Neon"
    assert tokens.source == "ui-ux-pro-max"


def test_starter_css_uses_skill_tokens():
    tokens = parse_design_tokens(SAMPLE_MASTER)
    css = starter_style_css(title="Club", tokens=tokens)
    assert "#FF2D95" in css
    assert "Orbitron" in css
    assert "#9A5EFF" not in css


def test_salvage_follows_master_tokens(tmp_path: Path):
    master = tmp_path / "design-system" / "MASTER.md"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(SAMPLE_MASTER, encoding="utf-8")
    (tmp_path / "style.css").write_text("body { font-family: Arial; }", encoding="utf-8")

    changed = salvage_web_project(tmp_path, user_task="создай сайт для компьютерного клуба")
    assert "style.css" in changed
    css = (tmp_path / "style.css").read_text(encoding="utf-8")
    assert "#FF2D95" in css
    assert "Orbitron" in css


def test_design_search_query_for_club():
    query = design_search_query("создай сайт для компьютерного клуба")
    assert "landing" in query.lower() or "club" in query.lower() or "клуб" in query.lower()
    assert "neon" in query.lower() or "gaming" in query.lower()


def test_persist_uiux_pro_max_writes_skill_master(tmp_path: Path):
    if not SEARCH_SCRIPT.is_file():
        return
    created = persist_uiux_pro_max(tmp_path, user_task="создай сайт для компьютерного клуба")
    master = tmp_path / "design-system" / "MASTER.md"
    assert master.is_file(), created
    text = master.read_text(encoding="utf-8")
    assert "Design System Master File" in text
    tokens = parse_design_tokens(text)
    assert tokens.primary.startswith("#")
    assert tokens.heading_font


def test_ensure_scaffold_keeps_skill_master(tmp_path: Path):
    master = tmp_path / "design-system" / "MASTER.md"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(SAMPLE_MASTER, encoding="utf-8")
    ensure_design_scaffold(
        tmp_path,
        user_task="создай сайт для компьютерного клуба",
        app_root=tmp_path,
    )
    kept = master.read_text(encoding="utf-8")
    assert "#FF2D95" in kept
    assert "#9A5EFF" not in kept
    assert (tmp_path / "design-system" / "pages" / "index.md").is_file()
