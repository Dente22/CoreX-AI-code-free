"""Мост между системной Ollama (11434) и экземпляром CoreX (11435)."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import aiohttp

from core.ollama_lifecycle import (
    DESKTOP_OLLAMA_PORT,
    detect_installed_models_from_disk,
    resolve_ollama_models_dir,
)

DESKTOP_OLLAMA_BASE_URL = f"http://127.0.0.1:{DESKTOP_OLLAMA_PORT}"
LIST_TIMEOUT_SEC = 10


def resolve_desktop_ollama_models_dir() -> Path | None:
    path = Path.home() / ".ollama" / "models"
    return path if path.is_dir() else None


def parse_model_ref(model_name: str) -> tuple[str, str]:
    normalized = (model_name or "").strip()
    if not normalized:
        return "", ""
    if ":" in normalized:
        base, tag = normalized.rsplit(":", 1)
        return base.strip(), tag.strip() or "latest"
    return normalized, "latest"


def _manifest_path(models_root: Path, model_name: str, *, must_exist: bool = True) -> Path | None:
    base, tag = parse_model_ref(model_name)
    if not base:
        return None
    path = (
        models_root
        / "manifests"
        / "registry.ollama.ai"
        / "library"
        / base
        / tag
    )
    if must_exist and not path.is_file():
        return None
    return path


def detect_desktop_models_from_disk() -> list[dict[str, str]]:
    root = resolve_desktop_ollama_models_dir()
    if root is None:
        return []
    return detect_installed_models_from_disk(models_root=root)


def collect_manifest_digests(manifest_text: str) -> set[str]:
    data = json.loads(manifest_text)
    digests: set[str] = set()
    config = data.get("config") or {}
    digest = str(config.get("digest") or "").strip()
    if digest:
        digests.add(digest)
    for layer in data.get("layers") or []:
        layer_digest = str(layer.get("digest") or "").strip()
        if layer_digest:
            digests.add(layer_digest)
    return digests


def digest_to_blob_filename(digest: str) -> str:
    normalized = digest.strip()
    if normalized.startswith("sha256:"):
        return f"sha256-{normalized.split(':', 1)[1]}"
    return normalized


def import_model_from_desktop(model_name: str) -> dict[str, Any]:
    """Скопировать manifest и blobs из системной Ollama в папку CoreX."""
    normalized = (model_name or "").strip()
    if not normalized:
        return {"success": False, "error": "Не указано имя модели"}

    desktop_root = resolve_desktop_ollama_models_dir()
    if desktop_root is None:
        return {
            "success": False,
            "error": "Системная Ollama не найдена (~/.ollama/models).",
        }

    source_manifest = _manifest_path(desktop_root, normalized, must_exist=True)
    if source_manifest is None:
        return {
            "success": False,
            "error": (
                f"Модель «{normalized}» не найдена в системной Ollama. "
                "Скачайте её через ollama pull или кнопку «Скачать» в CoreX."
            ),
        }

    corex_root = resolve_ollama_models_dir()
    target_manifest = _manifest_path(corex_root, normalized, must_exist=True)
    if target_manifest is not None and target_manifest.is_file():
        return {
            "success": True,
            "already_imported": True,
            "model_name": normalized,
            "message": "Модель уже есть в CoreX.",
        }

    try:
        manifest_text = source_manifest.read_text(encoding="utf-8")
        digests = collect_manifest_digests(manifest_text)
    except (OSError, json.JSONDecodeError) as exc:
        return {"success": False, "error": f"Не удалось прочитать manifest: {exc}"}

    desktop_blobs = desktop_root / "blobs"
    corex_blobs = corex_root / "blobs"
    corex_blobs.mkdir(parents=True, exist_ok=True)

    copied_blobs = 0
    reused_blobs = 0
    bytes_copied = 0
    for digest in digests:
        blob_name = digest_to_blob_filename(digest)
        source_blob = desktop_blobs / blob_name
        target_blob = corex_blobs / blob_name
        if target_blob.is_file():
            reused_blobs += 1
            continue
        if not source_blob.is_file():
            return {
                "success": False,
                "error": (
                    f"Файл blob отсутствует в системной Ollama: {blob_name}. "
                    "Перекачайте модель через ollama pull qwen2.5-coder:3b."
                ),
            }
        shutil.copy2(source_blob, target_blob)
        copied_blobs += 1
        try:
            bytes_copied += target_blob.stat().st_size
        except OSError:
            pass

    target_manifest = _manifest_path(corex_root, normalized, must_exist=False)
    if target_manifest is None:
        return {"success": False, "error": "Не удалось определить путь manifest в CoreX."}
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_manifest, target_manifest)

    return {
        "success": True,
        "model_name": normalized,
        "imported": True,
        "copied_blobs": copied_blobs,
        "reused_blobs": reused_blobs,
        "bytes_copied": bytes_copied,
        "message": (
            f"Модель «{normalized}» импортирована из системной Ollama "
            f"(скопировано blob-файлов: {copied_blobs})."
        ),
    }


async def list_desktop_ollama_models() -> dict[str, Any]:
    root = DESKTOP_OLLAMA_BASE_URL.rstrip("/")
    try:
        timeout = aiohttp.ClientTimeout(total=LIST_TIMEOUT_SEC)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{root}/api/tags") as response:
                if response.status != 200:
                    disk = detect_desktop_models_from_disk()
                    return {
                        "success": bool(disk),
                        "models": disk,
                        "source": "disk" if disk else "api_error",
                        "error": f"Системная Ollama вернула {response.status}",
                    }
                data = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        disk = detect_desktop_models_from_disk()
        return {
            "success": bool(disk),
            "models": disk,
            "source": "disk" if disk else "unavailable",
        }

    models = [
        {"name": str(item.get("name") or item.get("model") or "").strip()}
        for item in data.get("models") or []
        if str(item.get("name") or item.get("model") or "").strip()
    ]
    return {"success": True, "models": models, "source": "api"}
