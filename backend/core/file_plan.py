"""План файлов: модель предлагает имена, CoreX режет до 3 валидных."""

from __future__ import annotations

import json
import re

from core.project_paths import is_corex_internal_path, normalize_rel_path
from core.step_execution import ExecutionStep
from core.task_routing import looks_like_fix_request
from core.write_target import (
    classify_mention_kind,
    filename_has_extension,
    is_locked_write_path,
    suggest_created_filename,
)

MAX_FILES = 3
_ALLOWED_EXT = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".txt",
}
_SKIP_PARTS = {"chat", ".git", "node_modules", "__pycache__", ".venv", "dist"}

FILE_PLAN_SYSTEM = (
    "List files to create for this coding task.\n"
    'Reply JSON only: {"files":["name.ext"]}\n'
    "Rules: max 3 files; relative paths; each name needs an extension; "
    "at most one folder (src/app.py ok); no chat/; no code.\n"
    "One file is enough for a single script, game, or window app.\n"
)


def should_ask_file_plan(
    user_task: str,
    *,
    is_web: bool = False,
    write_dest: str | None = None,
    persona_id: str | None = None,
) -> bool:
    if is_web or looks_like_fix_request(user_task):
        return False
    from core.task_routing import looks_like_gui_window_request

    if looks_like_gui_window_request(user_task):
        return False
    agent = (persona_id or "").replace("agent:", "").lower()
    if "designer" in agent or "ui-ux" in agent:
        return False
    if is_locked_write_path(user_task, write_dest):
        return False
    return True


def folder_hint_for_plan(user_task: str, write_dest: str | None = None) -> str | None:
    dest = normalize_rel_path(write_dest or "")
    if dest and classify_mention_kind(dest) == "folder":
        return dest
    from core.write_target import _mentioned_paths

    for path in _mentioned_paths(user_task or ""):
        if classify_mention_kind(path) == "folder":
            return path
    return None


def parse_file_plan(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    blob = text
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob, count=1, flags=re.I)
        blob = re.sub(r"\s*```$", "", blob)
    data: object | None = None
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", blob, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None
    names: list[str] = []
    if isinstance(data, dict):
        payload = data.get("files") or data.get("file") or data.get("paths") or data.get("filenames")
        if isinstance(payload, str):
            names = [payload]
        elif isinstance(payload, list):
            names = [str(item) for item in payload]
    elif isinstance(data, list):
        names = [str(item) for item in data]
    if names:
        return names
    quoted = re.findall(r'["\']([^"\']+\.[A-Za-z]{1,8})["\']', blob)
    return quoted


def _valid_ext(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name.startswith(".") and filename_has_extension(name):
        return True
    if "." not in name:
        return False
    ext = "." + name.rsplit(".", 1)[-1].lower()
    return ext in _ALLOWED_EXT


def _clean_one(raw: str, *, folder_hint: str | None) -> str | None:
    path = normalize_rel_path(str(raw or "").strip("`'\" "))
    path = path.split("?", 1)[0].split("#", 1)[0]
    if not path or path in {".", ".."} or ".." in path.split("/"):
        return None
    if ":" in path or is_corex_internal_path(path):
        return None
    parts = [part for part in path.split("/") if part and part not in {".", ".."}]
    if any(part.lower() in _SKIP_PARTS or part.startswith(".") for part in parts[:-1]):
        return None
    if len(parts) > 2:
        parts = parts[-2:]
    path = "/".join(parts)
    if not filename_has_extension(path) or not _valid_ext(path):
        return None
    if folder_hint:
        hint = normalize_rel_path(folder_hint).strip("/")
        if hint and classify_mention_kind(hint) == "folder":
            if not path.startswith(hint + "/") and "/" not in path:
                path = f"{hint}/{path}"
    return path


def sanitize_file_plan(
    names: list[str] | None,
    *,
    user_task: str = "",
    folder_hint: str | None = None,
    fallback: str | None = None,
    max_files: int = MAX_FILES,
) -> list[str]:
    cleaned: list[str] = []
    for raw in names or []:
        item = _clean_one(raw, folder_hint=folder_hint)
        if not item or item in cleaned:
            continue
        cleaned.append(item)
        if len(cleaned) >= max(1, min(MAX_FILES, max_files)):
            break
    hinted = (fallback or "").strip() or suggest_created_filename(user_task)
    hinted = _clean_one(hinted, folder_hint=folder_hint) or hinted
    if len(cleaned) == 1 and cleaned[0].rsplit("/", 1)[-1] in {"main.py", "app.py"}:
        leaf = hinted.rsplit("/", 1)[-1]
        if leaf not in {"main.py", "app.py"}:
            folder = cleaned[0].rsplit("/", 1)[0] if "/" in cleaned[0] else ""
            cleaned = [f"{folder}/{leaf}" if folder else leaf]
    if not cleaned:
        return [hinted]
    return cleaned


def steps_from_file_plan(files: list[str]) -> list[ExecutionStep]:
    names = [item for item in files if item]
    if not names:
        names = ["app.py"]
    total = len(names)
    overview = ", ".join(names)
    steps: list[ExecutionStep] = []
    for index, path in enumerate(names):
        steps.append(
            ExecutionStep(
                id=f"write_{index}",
                title=path,
                instruction=(
                    f"Сейчас ТОЛЬКО write_file {path} — полный рабочий файл "
                    f"({index + 1}/{total}). План: {overview}. "
                    "Не пиши другие файлы в этом ходе. Не list_directory."
                ),
                tool_hint=f'write_file path="{path}"',
            )
        )
    return steps
