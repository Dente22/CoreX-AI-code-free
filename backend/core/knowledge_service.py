"""Подключение core_x_knowledge к AI: контексты, правила, языки проекта."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.core_x_library import COREX_ROOT
from core.device_profile import detect_device_profile
from core.project_paths import collect_analysis_entries

KNOWLEDGE_ROOT = COREX_ROOT / "core_x_knowledge"
RULES_ROOT = KNOWLEDGE_ROOT / "rules"
CONTEXTS_ROOT = KNOWLEDGE_ROOT / "contexts"

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".mjs": "typescript",
    ".cjs": "typescript",
    ".html": "web",
    ".htm": "web",
    ".css": "web",
    ".scss": "web",
    ".less": "web",
    ".go": "golang",
    ".swift": "swift",
    ".php": "php",
    ".pl": "perl",
    ".pm": "perl",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

COMMON_RULE_FILES = (
    "coding-style.md",
    "security.md",
    "patterns.md",
    "testing.md",
    "development-workflow.md",
)

LANG_RULE_FILES = (
    "coding-style.md",
    "patterns.md",
    "security.md",
    "testing.md",
)

SUPPORTED_LANGUAGES = frozenset(
    {"python", "typescript", "golang", "swift", "php", "perl", "kotlin", "web"}
)


@dataclass(frozen=True)
class KnowledgeBundle:
    context: str
    languages: tuple[str, ...]
    sources: tuple[str, ...]
    text: str

    def summary_ru(self) -> str:
        langs = ", ".join(self.languages) if self.languages else "общие"
        return f"База знаний: контекст «{self.context}», языки: {langs}"


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text.strip()).strip()


def _read_md(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return _strip_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def _char_budget() -> int:
    tier = detect_device_profile().tier
    return {"low": 5_000, "medium": 9_000, "high": 14_000}.get(tier, 9_000)


def detect_project_languages(project_root: Path, *, max_scan: int = 120) -> list[str]:
    found: set[str] = set()
    for entry in collect_analysis_entries(project_root, max_files=max_scan):
        line = entry.strip()
        rel = line.split("]", 1)[-1].strip() if "]" in line else line
        suffix = Path(rel).suffix.lower()
        lang = EXT_TO_LANGUAGE.get(suffix)
        if lang:
            found.add(lang)
        if len(found) >= 4:
            break

    if not found and project_root.is_dir():
        for path in project_root.rglob("*"):
            if path.is_file() and not any(part.startswith(".") for part in path.parts):
                lang = EXT_TO_LANGUAGE.get(path.suffix.lower())
                if lang:
                    found.add(lang)
            if len(found) >= 4:
                break

    order = ["python", "typescript", "web", "golang", "kotlin", "swift", "php", "perl"]
    return [lang for lang in order if lang in found]


def resolve_knowledge_context(
    user_task: str,
    persona_id: str | None = None,
    *,
    step_role: str | None = None,
) -> str:
    task = (user_task or "").lower()
    persona = (persona_id or "").lower()
    role = (step_role or "").lower()

    if any(word in task for word in ("исслед", "research", "архитектур", "analyze", "обзор кодовой")):
        return "research"
    if any(
        marker in persona
        for marker in ("code-reviewer", "security-auditor", "security-reviewer")
    ):
        return "review"
    if any(word in role for word in ("ревью", "review", "аудит", "security")):
        return "review"
    if "agent:qa-engineer" in persona and any(word in task for word in ("исслед", "research")):
        return "research"
    if any(word in task for word in ("ревью", "review", "code review", "проверь код")):
        return "review"
    return "dev"


def _append_section(
    parts: list[str],
    sources: list[str],
    *,
    title: str,
    body: str,
    rel_path: str,
    budget: int,
) -> int:
    body = body.strip()
    if not body:
        return budget
    block = f"### {title}\n{body}\n"
    if len(block) > budget:
        block = block[: budget - 80] + "\n... (обрезано)\n"
    parts.append(block)
    sources.append(rel_path)
    return budget - len(block)


@lru_cache(maxsize=32)
def _load_bundle_cached(
    context: str,
    languages_key: str,
    budget: int,
) -> KnowledgeBundle:
    languages = tuple(languages_key.split(",")) if languages_key else ()
    parts: list[str] = []
    sources: list[str] = []
    remaining = budget

    ctx_path = CONTEXTS_ROOT / f"{context}.md"
    ctx_body = _read_md(ctx_path)
    if ctx_body:
        remaining = _append_section(
            parts,
            sources,
            title=f"Context: {context}",
            body=ctx_body,
            rel_path=f"contexts/{context}.md",
            budget=remaining,
        )

    for filename in COMMON_RULE_FILES:
        if remaining < 400:
            break
        path = RULES_ROOT / "common" / filename
        body = _read_md(path)
        if not body:
            continue
        remaining = _append_section(
            parts,
            sources,
            title=f"common/{filename}",
            body=body,
            rel_path=f"rules/common/{filename}",
            budget=remaining,
        )

    for lang in languages:
        if lang not in SUPPORTED_LANGUAGES:
            continue
        for filename in LANG_RULE_FILES:
            if remaining < 400:
                break
            path = RULES_ROOT / lang / filename
            body = _read_md(path)
            if not body:
                continue
            remaining = _append_section(
                parts,
                sources,
                title=f"{lang}/{filename}",
                body=body,
                rel_path=f"rules/{lang}/{filename}",
                budget=remaining,
            )

    text = "\n".join(parts).strip()
    return KnowledgeBundle(
        context=context,
        languages=languages,
        sources=tuple(sources),
        text=text,
    )


def build_knowledge_bundle(
    project_root: Path,
    user_task: str,
    persona_id: str | None = None,
    *,
    step_role: str | None = None,
    char_cap: int | None = None,
) -> KnowledgeBundle:
    if not KNOWLEDGE_ROOT.is_dir():
        return KnowledgeBundle(context="dev", languages=(), sources=(), text="")

    context = resolve_knowledge_context(user_task, persona_id, step_role=step_role)
    languages = detect_project_languages(project_root)
    if not languages and any(ext in user_task.lower() for ext in (".py", "python", "pygame")):
        languages = ["python"]
    if not languages and any(ext in user_task.lower() for ext in (".ts", "typescript", "react", ".js")):
        languages = ["typescript"]
    if not languages and any(ext in user_task.lower() for ext in ("html", ".html", "css", ".css", "javascript", "dom")):
        languages = ["web"]

    budget = char_cap if char_cap is not None else _char_budget()
    lang_key = ",".join(languages)
    return _load_bundle_cached(context, lang_key, budget)


def knowledge_meta(project_root: Path, user_task: str = "", persona_id: str | None = None) -> dict:
    bundle = build_knowledge_bundle(project_root, user_task, persona_id)
    return {
        "root": str(KNOWLEDGE_ROOT),
        "context": bundle.context,
        "languages": list(bundle.languages),
        "sources": list(bundle.sources),
        "chars": len(bundle.text),
        "summary": bundle.summary_ru(),
        "available_contexts": [
            p.stem for p in sorted(CONTEXTS_ROOT.glob("*.md"))
        ] if CONTEXTS_ROOT.is_dir() else [],
        "available_languages": sorted(SUPPORTED_LANGUAGES),
    }


def invalidate_knowledge_cache() -> None:
    _load_bundle_cached.cache_clear()
