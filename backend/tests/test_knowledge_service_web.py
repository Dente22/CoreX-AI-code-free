"""TDD: web правила должны подключаться для HTML/CSS проектов."""

from core.knowledge_service import knowledge_meta


def test_knowledge_meta_includes_web_for_html(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>Hello</body></html>", encoding="utf-8")

    meta = knowledge_meta(tmp_path)

    assert "web" in meta["languages"]
    assert any(s == "rules/web/coding-style.md" for s in meta["sources"])
    assert "web" in meta["available_languages"]

