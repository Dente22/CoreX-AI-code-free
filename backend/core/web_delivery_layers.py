"""Слои и проверки качества для веб-проектов в локальном конвейере."""

from __future__ import annotations

import re
from pathlib import Path

WEB_TASK_RE = re.compile(
    r"сайт|site|страниц|landing|веб|web|html|css|клуб|магазин|портал|лендинг",
    re.IGNORECASE,
)

BRAND_PRIMARY = "#9A5EFF"
BRAND_ACCENT = "#00D2FF"

CSS_MIN_CHARS = 1400
HTML_MIN_CHARS = 1200
JS_MIN_CHARS = 500


def is_web_site_task(*texts: str) -> bool:
    blob = " ".join(t for t in texts if t)
    return bool(WEB_TASK_RE.search(blob))


def designer_layers_prompt_ru(*, user_task: str) -> str:
    from core.design_handoff import designer_handoff_prompt_ru

    return designer_handoff_prompt_ru(user_task=user_task)


def developer_layers_prompt_ru(*, user_task: str) -> str:
    from core.design_handoff import developer_handoff_prompt_ru

    return developer_handoff_prompt_ru(user_task=user_task) + (
        "\nОбязательно: index.html (≥1200) + style.css (≥1400) + script.js (≥500).\n"
        "Только style.css (НЕ styles.css). Один stylesheet.\n"
        "HTML: <link style.css>, <script src=\"script.js\" defer>, hero CTA, section id=.\n"
        "Title/logo/h1 — короткое имя бренда, НЕ текст задания.\n"
        "CSS: тёмный фон #0b1020, gradient hero, .container, cards, hover, @media.\n"
        "JS: mobile nav + smooth scroll + CTA + ещё один эффект. Не done без script.js.\n"
        f"Brand: {BRAND_PRIMARY}, {BRAND_ACCENT}.\n"
    )


def qa_web_polish_prompt_ru() -> str:
    return (
        "\n=== QA WEB POLISH ===\n"
        "1) view_file index.html, style.css, script.js\n"
        "2) Если нет script.js / слабый CSS / белый фон — допиши файлы\n"
        "3) nav href=#id должны совпадать с section id. Отчёт на русском.\n"
    )


def starter_style_css(*, title: str = "CoreX Site") -> str:
    """Креативная CSS-основа (тёмная тема, hero, карточки)."""
    safe_title = title.replace('"', "'")[:60]
    return f"""/* {safe_title} */
:root {{
  --brand: {BRAND_PRIMARY};
  --accent: {BRAND_ACCENT};
  --bg: #0b1020;
  --surface: #151c2e;
  --text: #e8eef7;
  --muted: #94a3b8;
  --radius: 14px;
  --shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: Inter, system-ui, sans-serif;
  background:
    radial-gradient(ellipse 80% 50% at 20% -10%, rgba(154, 94, 255, 0.35), transparent),
    radial-gradient(ellipse 60% 40% at 90% 10%, rgba(0, 210, 255, 0.2), transparent),
    var(--bg);
  color: var(--text);
  line-height: 1.65;
}}
.container {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}
.site-header {{
  position: sticky; top: 0; z-index: 20;
  backdrop-filter: blur(12px);
  background: rgba(11, 16, 32, 0.85);
  border-bottom: 1px solid rgba(154, 94, 255, 0.25);
}}
.nav {{
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 14px 0;
}}
.logo {{ font-weight: 800; letter-spacing: 0.04em; color: #fff; text-decoration: none; }}
.nav-links {{ display: flex; gap: 18px; list-style: none; margin: 0; padding: 0; }}
.nav-links a {{ color: var(--muted); text-decoration: none; font-weight: 600; }}
.nav-links a:hover {{ color: var(--accent); }}
.nav-toggle {{
  display: none; background: transparent; border: 1px solid var(--brand);
  color: #fff; border-radius: 8px; padding: 8px 10px; cursor: pointer;
}}
.hero {{
  padding: 72px 0 56px;
  background: linear-gradient(135deg, rgba(154, 94, 255, 0.35), rgba(0, 210, 255, 0.12));
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}}
.hero h1 {{
  margin: 0 0 12px;
  font-size: clamp(2rem, 4vw, 3.2rem);
  line-height: 1.15;
}}
.hero p {{ color: var(--muted); max-width: 560px; margin: 0 0 24px; }}
.btn {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 20px; border-radius: 999px; border: none; cursor: pointer;
  background: linear-gradient(90deg, var(--brand), var(--accent));
  color: #081018; font-weight: 700; text-decoration: none;
  box-shadow: 0 10px 30px rgba(154, 94, 255, 0.35);
  transition: transform 0.2s ease, filter 0.2s ease;
}}
.btn:hover {{ transform: translateY(-2px); filter: brightness(1.08); }}
.grid {{
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
  padding: 40px 0 56px;
}}
.card {{
  background: var(--surface); border-radius: var(--radius); padding: 22px;
  box-shadow: var(--shadow); border: 1px solid rgba(255, 255, 255, 0.05);
}}
.card h2 {{ margin-top: 0; font-size: 1.2rem; }}
.card p {{ color: var(--muted); margin-bottom: 0; }}
.site-footer {{
  padding: 28px 0; text-align: center; color: var(--muted);
  border-top: 1px solid rgba(154, 94, 255, 0.2);
}}
@media (max-width: 800px) {{
  .nav-toggle {{ display: inline-flex; }}
  .nav-links {{
    display: none; position: absolute; left: 20px; right: 20px; top: 64px;
    flex-direction: column; background: #12182a; padding: 16px;
    border-radius: 12px; border: 1px solid rgba(154, 94, 255, 0.3);
  }}
  .nav-links.open {{ display: flex; }}
  .grid {{ grid-template-columns: 1fr; }}
}}
"""


def starter_index_html(*, title: str, hero: str, nav_labels: list[str] | None = None) -> str:
    labels = nav_labels or ["О нас", "Мероприятия", "Контакты"]
    ids = ["about", "events", "contact"]
    nav_items = "".join(
        f'<li><a href="#{ids[i]}">{labels[i] if i < len(labels) else "Раздел"}</a></li>'
        for i in range(min(3, len(labels)))
    )
    safe_title = title.replace("<", "").replace(">", "")[:80]
    safe_hero = hero.replace("<", "").replace(">", "")[:120]
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <link rel="stylesheet" href="style.css">
  <script src="script.js" defer></script>
</head>
<body>
  <header class="site-header">
    <div class="container nav">
      <a class="logo" href="#">{safe_title}</a>
      <button class="nav-toggle" type="button" aria-label="Меню">☰</button>
      <ul class="nav-links">
        {nav_items}
      </ul>
    </div>
  </header>
  <section class="hero">
    <div class="container">
      <h1>{safe_hero}</h1>
      <p>Комьюнити геймеров и разработчиков: турниры, стримы и мастер-классы.</p>
      <a class="btn" href="#events" data-cta>Записаться</a>
    </div>
  </section>
  <main class="container grid">
    <section class="card" id="about">
      <h2>О нас</h2>
      <p>Мощные ПК, уютный зал и регулярные события для новичков и профи.</p>
    </section>
    <section class="card" id="events">
      <h2>Мероприятия</h2>
      <p>LAN-турниры, game night и воркшопы по Unity / веб-разработке.</p>
    </section>
    <section class="card" id="contact">
      <h2>Контакты</h2>
      <p>Email: club@example.com · Telegram: @corex_club</p>
    </section>
  </main>
  <footer class="site-footer">
    <div class="container">© {safe_title}</div>
  </footer>
</body>
</html>
"""


def starter_script_js(*, title: str = "CoreX Site") -> str:
    safe = title.replace("'", "")[:40]
    return f"""/* {safe} interactions */
document.addEventListener("DOMContentLoaded", () => {{
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {{
    toggle.addEventListener("click", () => links.classList.toggle("open"));
  }}

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {{
    anchor.addEventListener("click", (event) => {{
      const id = anchor.getAttribute("href");
      const target = id && document.querySelector(id);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({{ behavior: "smooth", block: "start" }});
      links?.classList.remove("open");
    }});
  }});

  const cta = document.querySelector("[data-cta]");
  if (cta) {{
    cta.addEventListener("click", () => {{
      window.setTimeout(() => {{
        alert("Заявка принята! Мы скоро свяжемся.");
      }}, 200);
    }});
  }}
}});
"""


def is_stub_style_css(content: str) -> bool:
    text = (content or "").strip()
    if len(text) < CSS_MIN_CHARS:
        return True
    required = (":root", "body", "header", "nav", "footer", ".container")
    if not all(token in text for token in required):
        return True
    # Слишком «светлый/плоский» сайт без атмосферы
    dark_or_gradient = any(
        token in text.lower()
        for token in ("#0f1720", "#0b1020", "#111", "gradient", "--bg", "--brand")
    )
    if not dark_or_gradient:
        return True
    if "@media" not in text:
        return True
    return False


def is_stub_script_js(content: str) -> bool:
    text = (content or "").strip()
    if len(text) < JS_MIN_CHARS:
        return True
    # Обрезанный/битый файл (частый сбой локальной модели)
    if text.count('"') % 2 != 0 or text.count("'") % 2 != 0:
        return True
    if text.rstrip().endswith(("=", "(", ",", "[", "{", "+", "-", "*")):
        return True
    markers = ("addEventListener", "querySelector", "DOMContentLoaded")
    return not any(marker in text for marker in markers)


def web_file_quality_issues(path: str, content: str) -> list[str]:
    rel = (path or "").replace("\\", "/").lower()
    body = content or ""
    issues: list[str] = []

    if rel.endswith(".html"):
        lower = body.lower()
        if "<!doctype html" not in lower:
            issues.append("index.html: нет <!DOCTYPE html>")
        if 'href="style.css"' not in body and "href='style.css'" not in body:
            issues.append('index.html: нет <link rel="stylesheet" href="style.css">')
        if "script.js" not in lower:
            issues.append('index.html: нет <script src="script.js">')
        if "<main" not in lower and "<section" not in lower:
            issues.append("index.html: добавьте <main>/<section> с id")
        if 'id="' not in body and "id='" not in body:
            issues.append("index.html: секции должны иметь id для якорной навигации")
        if "btn" not in lower and "<button" not in lower:
            issues.append("index.html: нужна CTA-кнопка (.btn или button)")
        if len(body) < HTML_MIN_CHARS:
            issues.append("index.html: слишком короткий — нужны hero + 3 секции + footer")

    if rel.endswith(".css"):
        if is_stub_style_css(body):
            issues.append(
                "style.css: слишком слабый — тёмный фон, gradient hero, .container, "
                f"cards, hover, @media, ≥{CSS_MIN_CHARS} символов"
            )

    if rel.endswith(".js"):
        if is_stub_script_js(body):
            issues.append(
                f"script.js: слишком слабый — DOMContentLoaded, nav/smooth scroll/CTA, ≥{JS_MIN_CHARS} символов"
            )

    return issues


def web_quality_hint(path: str, issues: list[str]) -> str:
    joined = "; ".join(issues)
    rel = path.replace("\\", "/").lower()
    if rel.endswith(".css"):
        return (
            f"\nSystem Error: Качество style.css недостаточное: {joined}\n"
            "Следующий ход: write_file style.css — тёмный фон #0b1020, gradient hero, "
            f"brand {BRAND_PRIMARY}/{BRAND_ACCENT}, cards, @media.\n"
        )
    if rel.endswith(".js"):
        return (
            f"\nSystem Error: Качество script.js недостаточное: {joined}\n"
            "Следующий ход: write_file script.js — mobile nav toggle + smooth scroll + CTA.\n"
        )
    return (
        f"\nSystem Error: Качество {path} недостаточное: {joined}\n"
        "Следующий ход: write_file index.html с link style.css, script.js, hero CTA, section id=.\n"
    )


def infer_page_title(user_task: str) -> str:
    """Короткое имя бренда — не сырой текст инструкции пользователя."""
    text = (user_task or "").strip()
    if not text:
        return "CoreX Club"
    first = text.splitlines()[0].strip()
    for left, right in (("«", "»"), ('"', '"'), ("'", "'")):
        if left in first and right in first:
            start = first.find(left) + 1
            end = first.find(right, start)
            if end > start:
                name = first[start:end].strip()
                if 2 <= len(name) <= 60:
                    return name
    lower = text.lower()
    instruction_markers = (
        "сделай",
        "создай",
        "напиши",
        "полноценн",
        "длинный",
        "заглуш",
        "html",
        "css",
        "javascript",
        "landing",
    )
    looks_like_instruction = any(m in lower for m in instruction_markers)
    if "компьютерн" in lower and "клуб" in lower:
        return "Компьютерный клуб"
    if "game" in lower and "club" in lower:
        return "Game Club"
    if looks_like_instruction or len(first) > 48:
        return "CoreX Club"
    cleaned = re.sub(r"\s+", " ", first)
    return cleaned[:80] if cleaned else "CoreX Club"


def maybe_autofill_salvaged_web(path: str, content: str, *, user_task: str) -> str:
    """Подменить слишком короткую заглушку на стартовый шаблон CoreX."""
    rel = (path or "").replace("\\", "/").lower()
    title = infer_page_title(user_task)
    if rel.endswith(".css") and is_stub_style_css(content):
        return starter_style_css(title=title)
    if rel.endswith(".html") and (
        len(content or "") < HTML_MIN_CHARS or "script.js" not in (content or "").lower()
    ):
        if len(content or "") < HTML_MIN_CHARS:
            return starter_index_html(title=title, hero=title)
    if rel.endswith(".js") and is_stub_script_js(content):
        return starter_script_js(title=title)
    return content


def missing_web_deliverables(project_root: Path) -> list[str]:
    """Что ещё не готово на диске для веб-задачи."""
    root = Path(project_root)
    missing: list[str] = []
    checks = (
        ("index.html", lambda t: web_file_quality_issues("index.html", t)),
        ("style.css", lambda t: web_file_quality_issues("style.css", t)),
        ("script.js", lambda t: web_file_quality_issues("script.js", t)),
    )
    for name, checker in checks:
        path = root / name
        if not path.is_file():
            missing.append(f"нет файла {name}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            missing.append(f"не читается {name}")
            continue
        issues = checker(text)
        missing.extend(issues)
    # Дубль stylesheet путает агента и браузер
    styles_dup = root / "styles.css"
    style_ok = (root / "style.css").is_file()
    if styles_dup.is_file() and style_ok:
        missing.append("лишний styles.css — оставьте только style.css")
    html_path = root / "index.html"
    if html_path.is_file():
        try:
            html = html_path.read_text(encoding="utf-8")
        except OSError:
            html = ""
        if "styles.css" in html and "style.css" not in html.replace("styles.css", ""):
            missing.append('index.html ссылается на styles.css — нужен href="style.css"')
    return missing
