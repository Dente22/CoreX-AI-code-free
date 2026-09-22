"""Клонирование git-репозитория в выбранную папку."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

CLONE_TIMEOUT_SEC = 180
_GIT_SCP = re.compile(r"^git@[\w.-]+:[\w./~+-]+(?:\.git)?$", re.IGNORECASE)


def is_allowed_git_remote(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw or any(ch.isspace() for ch in raw):
        return False
    if raw.lower().startswith("https://"):
        parsed = urlparse(raw)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        path = (parsed.path or "").strip("/")
        return bool(path)
    if _GIT_SCP.match(raw):
        return True
    if raw.lower().startswith("ssh://"):
        parsed = urlparse(raw)
        if parsed.scheme.lower() != "ssh" or not parsed.hostname:
            return False
        return bool((parsed.path or "").strip("/"))
    return False


def folder_name_from_remote(url: str) -> str:
    raw = str(url or "").strip().rstrip("/")
    if raw.lower().endswith(".git"):
        raw = raw[:-4]
    if raw.startswith("git@") and ":" in raw:
        path = raw.split(":", 1)[1]
    else:
        path = unquote(urlparse(raw).path or "")
    name = Path(path).name.strip()
    name = re.sub(r"[<>:\"|?*]", "", name)
    return name or "repo"


def clone_repository(url: str, parent_path: Path, timeout_sec: int = CLONE_TIMEOUT_SEC) -> dict:
    remote = str(url or "").strip()
    if not is_allowed_git_remote(remote):
        return {"error": "Нужна ссылка https://… или git@хост:путь (без логина в URL)."}

    parent = Path(parent_path).expanduser()
    try:
        parent = parent.resolve()
    except OSError:
        return {"error": f"Не удалось открыть папку: {parent_path}"}
    if not parent.is_dir():
        return {"error": f"Родительская папка не найдена: {parent}"}

    name = folder_name_from_remote(remote)
    dest = parent / name
    if dest.exists():
        try:
            if any(dest.iterdir()):
                return {"error": f"Папка уже существует и не пуста: {dest}"}
        except OSError:
            return {"error": f"Не удалось проверить папку: {dest}"}

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": timeout_sec,
        "env": env,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        completed = subprocess.run(
            ["git", "clone", "--", remote, str(dest)],
            **kwargs,
        )
    except FileNotFoundError:
        return {"error": "Git не найден. Установите Git и добавьте его в PATH."}
    except subprocess.TimeoutExpired:
        return {"error": "Клонирование заняло слишком много времени."}

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:800]
        return {"error": detail or "git clone завершился с ошибкой"}

    return {
        "success": True,
        "root": str(dest),
        "name": name,
        "remote": remote,
    }
