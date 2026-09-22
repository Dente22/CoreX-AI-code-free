from core.web_search import (
    format_search_for_prompt,
    is_web_search_tool,
    sanitize_search_query,
    search_web,
    _parse_html_results,
    _unwrap_ddg_url,
)

_HTML = """
<html><body>
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F3%2Flibrary%2Ftkinter.html">
tkinter — Python 3 docs
</a>
<a class="result__snippet">Tkinter is the standard Python GUI library.</a>
<a href="https://example.com/minesweeper" class="result__a">Minesweeper tkinter example</a>
<a class="result__snippet">A 9x9 grid with left-click reveal and right-click flags.</a>
</body></html>
"""


def test_sanitize_drops_paths_and_caps_length():
    query = sanitize_search_query("сделай окно  D:\\\\TEST\\\\main.py  и добавь кнопку")
    assert "main.py" not in query
    assert len(query) <= 80


def test_parse_html_and_unwrap_uddg():
    rows = _parse_html_results(_HTML)
    assert len(rows) == 2
    assert rows[0]["title"].startswith("tkinter")
    assert rows[0]["url"] == "https://docs.python.org/3/library/tkinter.html"
    assert "GUI" in rows[0]["snippet"]
    assert "9x9" in rows[1]["snippet"]
    assert _unwrap_ddg_url("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com") == (
        "https://example.com"
    )


def test_format_search_is_short_hints():
    text = format_search_for_prompt(
        "tkinter minesweeper",
        [{"title": "Example", "snippet": "Use Button grid", "url": "https://example.com"}],
    )
    assert "WEB SEARCH" in text
    assert "Button grid" in text
    assert "example.com" not in text


def test_search_web_uses_html_then_lite(monkeypatch):
    calls: list[str] = []

    def fake_http(url: str, *, data: bytes | None = None) -> str:
        calls.append(url)
        if "html.duckduckgo.com" in url:
            return _HTML
        raise AssertionError("lite should not run when html works")

    monkeypatch.setattr("core.web_search._http", fake_http)
    payload = search_web("tkinter minesweeper example")
    assert payload["ok"] is True
    assert len(payload["results"]) == 2
    assert "WEB SEARCH" in payload["text"]
    assert calls and "html.duckduckgo.com" in calls[0]


def test_search_web_falls_back_to_lite(monkeypatch):
    def fake_http(url: str, *, data: bytes | None = None) -> str:
        if "html.duckduckgo.com" in url:
            raise OSError("blocked")
        return (
            '<a href="https://example.com/a" class="result-link">Lite hit</a>'
            '<td class="result-snippet">Short snippet</td>'
        )

    monkeypatch.setattr("core.web_search._http", fake_http)
    payload = search_web("pygame collision")
    assert payload["ok"] is True
    assert payload["results"][0]["title"] == "Lite hit"


def test_is_web_search_tool():
    assert is_web_search_tool("web", "search_web") is True
    assert is_web_search_tool("filesystem", "search_web") is True
    assert is_web_search_tool("filesystem", "view_file") is False
