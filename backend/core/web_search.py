"""Поиск по вебу без API-ключа: DuckDuckGo HTML, короткие сниппеты."""

from __future__ import annotations

import html as html_lib
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAX_RESULTS = 3
SNIPPET_CHARS = 180
QUERY_CHARS = 80
PROMPT_MAX_CHARS = 1400
TIMEOUT_SEC = 8

_UDDG_RE = re.compile(r"[?&]uddg=([^&]+)")
_TAG_RE = re.compile(r"<[^>]+>")
_ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.I | re.S)
_SNIPPET_RE = re.compile(
    r'class="result__snippet"[^>]*>(.*?)</(?:a|td|span|div)>',
    re.I | re.S,
)
_LITE_SNIP_RE = re.compile(
    r'class="result-snippet"[^>]*>(.*?)</(?:td|span|div)>',
    re.I | re.S,
)


def sanitize_search_query(text: str) -> str:
    blob = re.sub(r"\s+", " ", (text or "").strip())
    blob = re.sub(r"[\\/].+\.(py|js|ts|html|css)\b", " ", blob, flags=re.I)
    blob = blob.replace("\n", " ")[:QUERY_CHARS].strip()
    return blob


def _anchors_with_class(page: str, class_name: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    needle = class_name.lower()
    for match in _ANCHOR_RE.finditer(page or ""):
        attrs = match.group(1) or ""
        if needle not in attrs.lower():
            continue
        href_match = re.search(r'href="([^"]+)"', attrs, re.I)
        if not href_match:
            continue
        rows.append((href_match.group(1), match.group(2) or ""))
    return rows


def _strip_tags(raw: str) -> str:
    text = html_lib.unescape(_TAG_RE.sub(" ", raw or ""))
    return re.sub(r"\s+", " ", text).strip()


def _unwrap_ddg_url(url: str) -> str:
    match = _UDDG_RE.search(url or "")
    if match:
        return urllib.parse.unquote(match.group(1))
    return url


def _http(url: str, *, data: bytes | None = None) -> str:
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; CoreX) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def _parse_html_results(page: str) -> list[dict[str, str]]:
    titles = _anchors_with_class(page or "", "result__a")
    snippets = [_strip_tags(item) for item in _SNIPPET_RE.findall(page or "")]
    rows: list[dict[str, str]] = []
    for index, (href, title_html) in enumerate(titles[:MAX_RESULTS]):
        snippet = snippets[index] if index < len(snippets) else ""
        rows.append(
            {
                "title": _strip_tags(title_html)[:160],
                "url": _unwrap_ddg_url(html_lib.unescape(href))[:300],
                "snippet": snippet[:SNIPPET_CHARS],
            }
        )
    return [row for row in rows if row["title"]]


def _parse_lite_results(page: str) -> list[dict[str, str]]:
    titles = _anchors_with_class(page or "", "result-link")
    snippets = [_strip_tags(item) for item in _LITE_SNIP_RE.findall(page or "")]
    rows: list[dict[str, str]] = []
    for index, (href, title_html) in enumerate(titles[:MAX_RESULTS]):
        snippet = snippets[index] if index < len(snippets) else ""
        rows.append(
            {
                "title": _strip_tags(title_html)[:160],
                "url": _unwrap_ddg_url(html_lib.unescape(href))[:300],
                "snippet": snippet[:SNIPPET_CHARS],
            }
        )
    return [row for row in rows if row["title"]]


def _search_html(query: str) -> list[dict[str, str]]:
    payload = urllib.parse.urlencode({"q": query, "kl": "wt-wt"}).encode("utf-8")
    page = _http("https://html.duckduckgo.com/html/", data=payload)
    return _parse_html_results(page)


def _search_lite(query: str) -> list[dict[str, str]]:
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
    page = _http(url)
    return _parse_lite_results(page)


def format_search_for_prompt(query: str, results: list[dict[str, str]]) -> str:
    if not results:
        return ""
    lines = [
        "=== WEB SEARCH (DuckDuckGo, подсказки) ===",
        f"Запрос: {query}",
    ]
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. {item.get('title') or ''}")
        snippet = (item.get("snippet") or "").strip()
        if snippet:
            lines.append(f"   {snippet}")
    lines.append("Это только подсказки. Пиши рабочий код под этот проект, не копируй слепо.")
    blob = "\n".join(lines)
    if len(blob) > PROMPT_MAX_CHARS:
        blob = blob[:PROMPT_MAX_CHARS].rsplit("\n", 1)[0]
    return blob


def is_web_search_tool(server: str | None, tool: str | None) -> bool:
    s = (server or "").strip().lower()
    t = (tool or "").strip().lower()
    if t in {"search_web", "web_search", "internet_search"}:
        return True
    return s in {"web", "internet"} and t in {"search", "lookup"}


def search_web(query: str, *, limit: int = MAX_RESULTS) -> dict[str, Any]:
    q = sanitize_search_query(query)
    if not q:
        return {"ok": False, "error": "Пустой запрос", "query": "", "results": []}
    results: list[dict[str, str]] = []
    error = ""
    try:
        results = _search_html(q)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        error = str(exc)
    if not results:
        try:
            results = _search_lite(q)
            error = ""
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            error = error or str(exc)
    results = results[: max(1, min(int(limit or MAX_RESULTS), MAX_RESULTS))]
    return {
        "ok": bool(results),
        "query": q,
        "results": results,
        "text": format_search_for_prompt(q, results),
        "error": "" if results else (error or "Нет результатов"),
    }
