"""Локальный Git SCM для панели CoreX: status, stage, commit, discard, push, init."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from core.project_paths import ensure_chat_gitignored, is_corex_internal_path

GIT_TIMEOUT_SEC = 60
PUSH_TIMEOUT_SEC = 120


def safe_rel_path(raw: str) -> str | None:
    text = str(raw or "").replace("\\", "/").strip()
    if not text or text in {".", ".."}:
        return None
    if text.startswith("-") or text.startswith("/") or "\x00" in text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return None
    parts = candidate.parts
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return Path(*parts).as_posix()


def _git_env() -> dict:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _run_git(root: Path, args: list[str], timeout: int = GIT_TIMEOUT_SEC) -> dict:
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "env": _git_env(),
        "cwd": str(root),
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(["git", *args], **kwargs)
    except FileNotFoundError:
        return {"error": "Git не найден. Установите Git и добавьте его в PATH."}
    except subprocess.TimeoutExpired:
        return {"error": "Команда git заняла слишком много времени."}
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode != 0:
        detail = (stderr or stdout).strip()[:800]
        return {"error": detail or "git завершился с ошибкой", "code": completed.returncode}
    return {"success": True, "stdout": stdout, "stderr": stderr}


def parse_porcelain(text: str) -> list[dict]:
    files: list[dict] = []
    for raw in (text or "").splitlines():
        if len(raw) < 3:
            continue
        index_code = raw[0]
        worktree_code = raw[1]
        rest = raw[3:] if raw[2] == " " else raw[2:]
        if " -> " in rest and index_code in {"R", "C"}:
            path = rest.split(" -> ", 1)[1].strip().strip('"')
        else:
            path = rest.strip().strip('"')
        rel = safe_rel_path(path)
        if not rel or is_corex_internal_path(rel):
            continue
        untracked = index_code == "?" and worktree_code == "?"
        staged = (not untracked) and index_code not in {" ", "?"}
        unstaged = untracked or worktree_code not in {" ", "?"}
        files.append(
            {
                "path": rel,
                "name": Path(rel).name,
                "index": index_code,
                "worktree": worktree_code,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
            }
        )
    return files


def _normalize_paths(paths: list[str]) -> dict:
    cleaned: list[str] = []
    for item in paths:
        rel = safe_rel_path(item)
        if not rel:
            return {"error": f"Некорректный путь: {item}"}
        if is_corex_internal_path(rel):
            return {"error": "Служебные файлы CoreX нельзя менять через Git-панель"}
        cleaned.append(rel)
    if not cleaned:
        return {"error": "Не указаны файлы"}
    return {"success": True, "paths": cleaned}


def get_status(root: Path) -> dict:
    folder = Path(root)
    if not folder.is_dir():
        return {"error": "Папка проекта не найдена"}

    inside = _run_git(folder, ["rev-parse", "--is-inside-work-tree"])
    if inside.get("error"):
        err = str(inside.get("error") or "")
        if "Git не найден" in err or "слишком много времени" in err:
            return inside
        return {
            "success": True,
            "is_repo": False,
            "branch": "",
            "files": [],
            "has_origin": False,
            "upstream": False,
        }

    ensure_chat_gitignored(folder)

    porcelain = _run_git(folder, ["status", "--porcelain=v1", "-uall"])
    if porcelain.get("error"):
        return porcelain

    branch_run = _run_git(folder, ["branch", "--show-current"])
    branch = (branch_run.get("stdout") or "").strip() if not branch_run.get("error") else ""

    remotes = _run_git(folder, ["remote"])
    remote_names = (remotes.get("stdout") or "").split() if not remotes.get("error") else []
    has_origin = "origin" in remote_names

    upstream_run = _run_git(folder, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    upstream = not bool(upstream_run.get("error"))

    files = parse_porcelain(porcelain.get("stdout") or "")
    return {
        "success": True,
        "is_repo": True,
        "branch": branch or "HEAD",
        "files": files,
        "has_origin": has_origin,
        "upstream": upstream,
        "staged_count": sum(1 for item in files if item["staged"]),
        "unstaged_count": sum(1 for item in files if item["unstaged"]),
    }


def init_repository(root: Path) -> dict:
    folder = Path(root)
    if not folder.is_dir():
        return {"error": "Папка проекта не найдена"}
    probe = _run_git(folder, ["rev-parse", "--is-inside-work-tree"])
    if not probe.get("error"):
        return {"error": "Репозиторий уже создан"}
    if "Git не найден" in str(probe.get("error") or ""):
        return probe
    result = _run_git(folder, ["init"])
    if result.get("error"):
        return result
    ensure_chat_gitignored(folder)
    return get_status(folder)


def stage_paths(root: Path, paths: list[str]) -> dict:
    normalized = _normalize_paths(paths)
    if normalized.get("error"):
        return normalized
    result = _run_git(Path(root), ["add", "--", *normalized["paths"]])
    if result.get("error"):
        return result
    return get_status(root)


def unstage_paths(root: Path, paths: list[str]) -> dict:
    normalized = _normalize_paths(paths)
    if normalized.get("error"):
        return normalized
    result = _run_git(Path(root), ["restore", "--staged", "--", *normalized["paths"]])
    if result.get("error"):
        return result
    return get_status(root)


def discard_paths(root: Path, paths: list[str]) -> dict:
    normalized = _normalize_paths(paths)
    if normalized.get("error"):
        return normalized
    status = get_status(root)
    if status.get("error"):
        return status
    by_path = {item["path"]: item for item in status.get("files") or []}
    folder = Path(root)
    for rel in normalized["paths"]:
        info = by_path.get(rel)
        if info and info.get("untracked"):
            result = _run_git(folder, ["clean", "-f", "--", rel])
        else:
            result = _run_git(folder, ["restore", "--worktree", "--", rel])
        if result.get("error"):
            return result
    return get_status(root)


def commit_staged(root: Path, message: str) -> dict:
    text = str(message or "").strip()
    if not text:
        return {"error": "Напишите сообщение коммита"}
    if "\x00" in text:
        return {"error": "Некорректное сообщение коммита"}
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": GIT_TIMEOUT_SEC,
        "env": _git_env(),
        "cwd": str(root),
        "input": text + "\n",
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(["git", "commit", "-F", "-"], **kwargs)
    except FileNotFoundError:
        return {"error": "Git не найден. Установите Git и добавьте его в PATH."}
    except subprocess.TimeoutExpired:
        return {"error": "Команда git заняла слишком много времени."}
    if completed.returncode != 0:
        detail = ((completed.stderr or completed.stdout) or "").strip()[:800]
        return {"error": detail or "Не удалось создать коммит"}
    status = get_status(root)
    status["committed"] = True
    return status


def push_repository(root: Path) -> dict:
    folder = Path(root)
    status = get_status(folder)
    if status.get("error"):
        return status
    if not status.get("is_repo"):
        return {"error": "Это не git-репозиторий"}

    result = _run_git(folder, ["push"], timeout=PUSH_TIMEOUT_SEC)
    if not result.get("error"):
        status["pushed"] = True
        return status

    err = str(result.get("error") or "").lower()
    no_upstream = "no upstream" in err or "has no upstream" in err or "specify a remote" in err
    if no_upstream and status.get("has_origin"):
        retry = _run_git(folder, ["push", "-u", "origin", "HEAD"], timeout=PUSH_TIMEOUT_SEC)
        if retry.get("error"):
            return retry
        status = get_status(folder)
        status["pushed"] = True
        return status
    return result
