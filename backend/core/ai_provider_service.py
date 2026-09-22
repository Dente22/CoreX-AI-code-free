"""Сохранение и применение выбранного локального AI-провайдера."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.ai_provider_catalog import (
    DEFAULT_PROVIDER_ID,
    AiProviderPreset,
    get_default_preset,
    get_preset,
    list_preset_dicts,
    validate_provider_id,
)

CONFIG_FILENAME = "ai_provider.json"


class AiProviderService:
    def __init__(self, config_path: Path | None = None, project_root: Path | None = None):
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        self._config_path = config_path or (root / "chat" / CONFIG_FILENAME)

    @property
    def config_path(self) -> Path:
        return self._config_path

    def get_selected_id(self) -> str:
        if not self._config_path.is_file():
            return DEFAULT_PROVIDER_ID
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_PROVIDER_ID
        provider_id = str(data.get("provider_id") or "").strip()
        if validate_provider_id(provider_id):
            return provider_id
        return DEFAULT_PROVIDER_ID

    def get_selected_preset(self) -> AiProviderPreset:
        return get_preset(self.get_selected_id())

    def set_selected_id(self, provider_id: str) -> dict[str, Any]:
        normalized = (provider_id or "").strip()
        if not validate_provider_id(normalized):
            return {
                "success": False,
                "error": f"Неизвестный провайдер: {provider_id}",
                "selected_id": self.get_selected_id(),
            }

        preset = get_preset(normalized)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider_id": preset.id,
            "model_name": preset.model_name,
            "provider_type": preset.provider_type,
        }
        self._config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "success": True,
            "selected_id": preset.id,
            "preset": preset.to_dict(),
        }

    def list_with_selection(self) -> dict[str, Any]:
        selected_id = self.get_selected_id()
        providers = []
        for item in list_preset_dicts():
            providers.append({**item, "selected": item["id"] == selected_id})
        return {
            "selected_id": selected_id,
            "providers": providers,
            "install_hint": (
                "Если открыто приложение Ollama, CoreX подключается к нему (порт 11434). "
                "Иначе поднимает свой сервер на 11435. "
                "Модели из системной Ollama видны сразу — отдельный импорт не нужен."
            ),
        }

    def resolve_ollama_config(self) -> dict[str, str]:
        preset = self.get_selected_preset()
        return {
            "provider_id": preset.id,
            "model_name": preset.model_name,
            "base_url": preset.base_url,
            "pull_command": preset.pull_command,
        }

    def apply_to_client(self, client: Any) -> AiProviderPreset:
        """Применить выбранный пресет к OllamaClient (или совместимому клиенту)."""
        from core.ollama_lifecycle import bind_client_to_live_endpoint

        preset = self.get_selected_preset()
        client.model_name = preset.model_name
        bind_client_to_live_endpoint(client)
        return preset


def default_provider_service(project_root: Path | None = None) -> AiProviderService:
    return AiProviderService(project_root=project_root)
