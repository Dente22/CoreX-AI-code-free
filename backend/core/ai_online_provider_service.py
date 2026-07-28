"""Пользовательские онлайн AI-провайдеры (OpenAI-compatible API).

API-ключи хранятся только в машинном каталоге пользователя
(не в папке проекта), чтобы при копировании/публикации репозитория
секреты не переносились.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from core.gemini_models import normalize_gemini_model_name

ApiType = Literal["openai", "gemini"]

_STORE_VERSION = 1
_STORE_FILENAME = "ai_online_providers.json"

# OpenRouter retires :free slugs often; remap known dead defaults to the free router.
_RETIRED_FREE_MODEL_ALIASES = {
    "meta-llama/llama-3.3-70b-instruct:free": "openrouter/free",
    "deepseek/deepseek-r1:free": "openrouter/free",
    "google/gemma-3-27b-it:free": "openrouter/free",
}


def _normalize_openrouter_free_model(model_name: str, base_url: str = "") -> str:
    """Rewrite retired OpenRouter free model slugs to the free router."""
    clean = (model_name or "").strip()
    if not clean:
        return clean
    lowered = clean.lower()
    for old, new in _RETIRED_FREE_MODEL_ALIASES.items():
        if lowered == old.lower():
            return new
    return clean


def resolve_local_secrets_dir() -> Path:
    """Каталог секретов на этой машине (вне репозитория / папки проекта)."""
    override = (os.environ.get("COREX_SECRETS_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
        base = Path(xdg).expanduser() if xdg else (Path.home() / ".local" / "share")
    return (base / "CoreX" / "secrets").resolve()


def default_online_providers_store_path() -> Path:
    return resolve_local_secrets_dir() / _STORE_FILENAME


def project_legacy_online_providers_path(project_root: Path) -> Path:
    return (project_root.resolve() / "chat" / _STORE_FILENAME)


def _mask_api_key(api_key: str) -> str:
    value = (api_key or "").strip()
    if len(value) <= 4:
        return "****"
    return f"{'*' * max(4, len(value) - 4)}{value[-4:]}"


def _normalize_base_url(url: str) -> str:
    value = (url or "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url должен начинаться с http:// или https://")
    return value


def _empty_store() -> dict[str, Any]:
    return {
        "version": _STORE_VERSION,
        "selected_id": "",
        "providers": [],
    }


def _provider_has_secret(provider: dict[str, Any]) -> bool:
    return bool(str(provider.get("api_key") or "").strip())


def _read_json_store(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("providers"), list):
        data["providers"] = []
    data.setdefault("selected_id", "")
    data.setdefault("version", _STORE_VERSION)
    return data


def _write_json_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _scrub_legacy_project_file(path: Path) -> None:
    """Удаляет секреты из chat/ai_online_providers.json (файл в проекте)."""
    try:
        _write_json_store(path, _empty_store())
    except OSError:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


class AiOnlineProviderService:
    def __init__(
        self,
        store_path: Path | None = None,
        project_root: Path | None = None,
        *,
        migrate_legacy: bool = True,
    ):
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        self._project_root = root
        self._store_path = (store_path or default_online_providers_store_path()).resolve()
        self._legacy_path = project_legacy_online_providers_path(root)
        if migrate_legacy and store_path is None:
            self._migrate_legacy_project_secrets()

    @property
    def store_path(self) -> Path:
        return self._store_path

    @property
    def legacy_project_path(self) -> Path:
        return self._legacy_path

    def _migrate_legacy_project_secrets(self) -> None:
        """Переносит ключи из chat/ в LOCALAPPDATA и очищает файл в проекте."""
        legacy = _read_json_store(self._legacy_path)
        if legacy is None:
            return

        providers = [p for p in legacy.get("providers", []) if isinstance(p, dict)]
        secret_providers = [p for p in providers if _provider_has_secret(p)]
        if not secret_providers:
            if providers:
                _scrub_legacy_project_file(self._legacy_path)
            return

        local = _read_json_store(self._store_path) or _empty_store()
        existing_ids = {str(item.get("id")) for item in local.get("providers", [])}
        existing_fingerprints = {
            (
                str(item.get("name") or "").strip().lower(),
                str(item.get("base_url") or "").strip().rstrip("/").lower(),
                str(item.get("model_name") or "").strip().lower(),
            )
            for item in local.get("providers", [])
        }

        for raw in secret_providers:
            provider_id = str(raw.get("id") or "").strip() or str(uuid.uuid4())
            item = {**raw, "id": provider_id}
            fingerprint = (
                str(item.get("name") or "").strip().lower(),
                str(item.get("base_url") or "").strip().rstrip("/").lower(),
                str(item.get("model_name") or "").strip().lower(),
            )
            if provider_id in existing_ids or fingerprint in existing_fingerprints:
                continue
            local.setdefault("providers", []).append(item)
            existing_ids.add(provider_id)
            existing_fingerprints.add(fingerprint)

        selected = str(local.get("selected_id") or "").strip()
        if selected not in existing_ids:
            legacy_selected = str(legacy.get("selected_id") or "").strip()
            if legacy_selected in existing_ids:
                local["selected_id"] = legacy_selected
            elif local.get("providers"):
                local["selected_id"] = local["providers"][0]["id"]
            else:
                local["selected_id"] = ""

        _write_json_store(self._store_path, local)
        _scrub_legacy_project_file(self._legacy_path)

    def _rewrite_retired_free_models(self, data: dict[str, Any]) -> dict[str, Any]:
        changed = False
        providers = data.get("providers")
        if not isinstance(providers, list):
            return data
        for item in providers:
            if not isinstance(item, dict):
                continue
            base_url = str(item.get("base_url") or "")
            host = (urlparse(base_url).netloc or "").lower()
            if "openrouter.ai" not in host and not str(item.get("model_name") or "").endswith(":free"):
                continue
            current = str(item.get("model_name") or "").strip()
            next_model = _normalize_openrouter_free_model(current, base_url)
            if next_model != current:
                item["model_name"] = next_model
                changed = True
        if changed:
            self._save(data)
        return data

    def _load(self) -> dict[str, Any]:
        data = _read_json_store(self._store_path)
        if data is None:
            return _empty_store()
        return self._rewrite_retired_free_models(data)

    def _save(self, data: dict[str, Any]) -> None:
        if self._store_path.resolve() == self._legacy_path.resolve():
            raise RuntimeError(
                "Отказ: нельзя сохранять API-ключи в chat/ проекта. "
                "Используйте локальный каталог CoreX/secrets."
            )
        _write_json_store(self._store_path, data)

    def _public_provider(self, provider: dict[str, Any]) -> dict[str, Any]:
        api_type = provider.get("api_type", "openai")
        model_name = provider["model_name"]
        if api_type == "gemini":
            model_name = normalize_gemini_model_name(model_name)
        return {
            "id": provider["id"],
            "name": provider["name"],
            "base_url": provider["base_url"],
            "model_name": model_name,
            "api_type": api_type,
            "api_key_masked": _mask_api_key(provider.get("api_key", "")),
            "source": "local_machine",
        }

    def list_providers(self) -> list[dict[str, Any]]:
        data = self._load()
        return [self._public_provider(item) for item in data["providers"]]

    def get_selected_id(self) -> str:
        data = self._load()
        selected = str(data.get("selected_id") or "").strip()
        ids = {item["id"] for item in data["providers"]}
        return selected if selected in ids else ""

    def get_provider(self, provider_id: str, *, include_secret: bool = False) -> dict[str, Any] | None:
        data = self._load()
        for item in data["providers"]:
            if item.get("id") == provider_id:
                if include_secret:
                    return dict(item)
                return self._public_provider(item)
        return None

    def get_selected_provider(self, *, include_secret: bool = False) -> dict[str, Any] | None:
        selected_id = self.get_selected_id()
        if not selected_id:
            return None
        return self.get_provider(selected_id, include_secret=include_secret)

    def list_with_selection(self) -> dict[str, Any]:
        selected_id = self.get_selected_id()
        providers = []
        for item in self.list_providers():
            providers.append({**item, "selected": item["id"] == selected_id})
        return {
            "selected_id": selected_id,
            "providers": providers,
            "storage": "local_machine",
            "storage_hint": (
                "API-ключи хранятся только на этом ПК "
                f"({resolve_local_secrets_dir()}) и не копируются вместе с проектом."
            ),
            "empty_hint": (
                "База для старта — OpenRouter Free: openrouter.ai → Keys → ключ → модель openrouter/free. "
                "Ключ сохранится локально на этом компьютере и не попадёт в папку проекта."
            ),
        }

    def create_provider(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model_name: str,
        api_type: ApiType = "openai",
    ) -> dict[str, Any]:
        clean_name = (name or "").strip()
        clean_model = _normalize_openrouter_free_model((model_name or "").strip(), base_url)
        clean_key = (api_key or "").strip()
        if api_type == "gemini":
            clean_model = normalize_gemini_model_name(clean_model)
        try:
            clean_url = _normalize_base_url(base_url)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        if not clean_name or not clean_url or not clean_key or not clean_model:
            return {"success": False, "error": "Заполните название, URL, API-ключ и модель."}

        data = self._load()
        provider = {
            "id": str(uuid.uuid4()),
            "name": clean_name,
            "base_url": clean_url,
            "api_key": clean_key,
            "model_name": clean_model,
            "api_type": api_type if api_type in {"openai", "gemini"} else "openai",
        }
        data["providers"].append(provider)
        data["selected_id"] = provider["id"]
        self._save(data)
        return {"success": True, "provider": self._public_provider(provider)}

    def set_selected_id(self, provider_id: str) -> dict[str, Any]:
        normalized = (provider_id or "").strip()
        data = self._load()
        if not any(item.get("id") == normalized for item in data["providers"]):
            return {"success": False, "error": f"Онлайн-провайдер не найден: {provider_id}"}
        data["selected_id"] = normalized
        self._save(data)
        provider = self.get_provider(normalized)
        return {"success": True, "selected_id": normalized, "provider": provider}

    def update_selected_model(self, model_name: str) -> dict[str, Any]:
        clean = _normalize_openrouter_free_model((model_name or "").strip())
        if not clean:
            return {"success": False, "error": "Пустое имя модели"}
        data = self._load()
        selected = str(data.get("selected_id") or "").strip()
        for item in data["providers"]:
            if item.get("id") != selected:
                continue
            if item.get("api_type") == "gemini":
                clean = normalize_gemini_model_name(clean)
            item["model_name"] = clean
            self._save(data)
            return {"success": True, "model_name": clean, "provider_id": selected}
        return {"success": False, "error": "Онлайн-провайдер не выбран"}

    def delete_provider(self, provider_id: str) -> dict[str, Any]:
        normalized = (provider_id or "").strip()
        data = self._load()
        before = len(data["providers"])
        data["providers"] = [item for item in data["providers"] if item.get("id") != normalized]
        if len(data["providers"]) == before:
            return {"success": False, "error": f"Онлайн-провайдер не найден: {provider_id}"}
        if data.get("selected_id") == normalized:
            data["selected_id"] = data["providers"][0]["id"] if data["providers"] else ""
        self._save(data)
        return {"success": True, "selected_id": data.get("selected_id", "")}

    def apply_to_client(self, client: Any) -> dict[str, Any] | None:
        provider = self.get_selected_provider(include_secret=True)
        if not provider:
            return None
        client.model_name = provider["model_name"]
        if provider.get("api_type") == "gemini":
            from core.gemini_models import normalize_gemini_model_name

            client.model_name = normalize_gemini_model_name(client.model_name)
        client.base_url = provider["base_url"].rstrip("/")
        client.api_key = provider["api_key"]
        client.api_type = provider.get("api_type", "openai")
        client.chat_url = f"{client.base_url}/chat/completions"
        # Persist auto-fallback (retired :free → openrouter/free, etc.).
        def _on_model_switched(_old: str, new_model: str) -> None:
            self.update_selected_model(new_model)

        client.on_model_switched = _on_model_switched
        return provider


def default_online_provider_service(project_root: Path | None = None) -> AiOnlineProviderService:
    return AiOnlineProviderService(project_root=project_root, migrate_legacy=True)
