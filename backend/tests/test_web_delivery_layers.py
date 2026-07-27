"""TDD: слои доставки веб-сайта и проверки качества."""

from core.web_delivery_layers import (
    infer_page_title,
    is_stub_script_js,
    is_stub_style_css,
    is_web_site_task,
    missing_web_deliverables,
    starter_index_html,
    starter_script_js,
    starter_style_css,
    web_file_quality_issues,
)


def test_is_web_site_task():
    assert is_web_site_task("сделай сайт компьютерного клуба")
    assert not is_web_site_task("напиши калькулятор на python")


def test_infer_page_title_ignores_instruction_text():
    assert infer_page_title("сделай полноценный сайт: длинный HTML, большой CSS") == "CoreX Club"
    assert infer_page_title("сайт компьютерного клуба с турнирами") == "Компьютерный клуб"
    assert infer_page_title('сайт «Neon Arena»') == "Neon Arena"


def test_stub_css_detected():
    assert is_stub_style_css("body{margin:0}")
    weak_light = """
:root { --primary-color: #9A5EFF; }
body { font-family: Inter; background: #f4f4f4; color: #333; }
.container { max-width: 1200px; }
header, nav, footer { background: white; }
"""
    assert is_stub_style_css(weak_light)
    assert not is_stub_style_css(starter_style_css())


def test_stub_js_detected():
    assert is_stub_script_js("console.log(1)")
    assert is_stub_script_js(
        "document.addEventListener('DOMContentLoaded', function() {\n"
        "  const links = document.querySelectorAll('a[href^=\n"
    )
    assert not is_stub_script_js(starter_script_js())


def test_quality_issues_for_plain_css():
    issues = web_file_quality_issues("style.css", "body{margin:0;color:#fff}")
    assert any("style.css" in item for item in issues)


def test_quality_issues_for_good_css():
    issues = web_file_quality_issues("style.css", starter_style_css())
    assert issues == []


def test_quality_issues_html_needs_stylesheet_and_script():
    issues = web_file_quality_issues(
        "index.html",
        "<!DOCTYPE html><html><body><h1>Hi</h1></body></html>",
    )
    assert any("style.css" in item for item in issues)
    assert any("script.js" in item for item in issues)


def test_quality_issues_html_starter_ok():
    html = starter_index_html(title="Club", hero="Club")
    assert web_file_quality_issues("index.html", html) == []
    assert "script.js" in html


def test_missing_web_deliverables(tmp_path):
    missing = missing_web_deliverables(tmp_path)
    assert any("index.html" in item for item in missing)
    assert any("script.js" in item for item in missing)

    (tmp_path / "index.html").write_text(
        starter_index_html(title="Club", hero="Club"),
        encoding="utf-8",
    )
    (tmp_path / "style.css").write_text(starter_style_css(title="Club"), encoding="utf-8")
    (tmp_path / "script.js").write_text(starter_script_js(title="Club"), encoding="utf-8")
    assert missing_web_deliverables(tmp_path) == []


def test_missing_flags_styles_css_duplicate(tmp_path):
    (tmp_path / "index.html").write_text(
        starter_index_html(title="Club", hero="Club"),
        encoding="utf-8",
    )
    (tmp_path / "style.css").write_text(starter_style_css(title="Club"), encoding="utf-8")
    (tmp_path / "script.js").write_text(starter_script_js(title="Club"), encoding="utf-8")
    (tmp_path / "styles.css").write_text("/* dup */", encoding="utf-8")
    missing = missing_web_deliverables(tmp_path)
    assert any("styles.css" in item for item in missing)
