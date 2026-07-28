"""Режим AI: локально (Ollama) или онлайн (пользовательские API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from core.ai_online_provider_service import AiOnlineProviderService, default_online_provider_service
from core.ai_provider_service import AiProviderService, default_provider_service
from core.llm_runtime import resolve_active_llm

AiMode = Literal["local", "online"]
CONFIG_FILENAME = "ai_runtime.json"


class AiRuntimeService:
    def __init__(
        self,
        config_path: Path | None = None,
        project_root: Path | None = None,
        local_service: AiProviderService | None = None,
        online_service: AiOnlineProviderService | None = None,
    ):
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        self._config_path = config_path or (root / "chat" / CONFIG_FILENAME)
        self.local_service = local_service or default_provider_service(project_root=root)
        self.online_service = online_service or default_online_provider_service(project_root=root)

    def _load(self) -> dict[str, Any]:
        if not self._config_path.is_file():
            return {"mode": "local"}
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"mode": "local"}
        mode = str(data.get("mode") or "local").strip().lower()
        if mode not in {"local", "online"}:
            mode = "local"
        return {"mode": mode}

    def _save(self, mode: AiMode) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps({"mode": mode}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def get_mode(self) -> AiMode:
        return self._load()["mode"]

    def set_mode(self, mode: str) -> dict[str, Any]:
        normalized = (mode or "").strip().lower()
        if normalized not in {"local", "online"}:
            return {"success": False, "error": f"Неизвестный режим: {mode}"}
        self._save(normalized)
        return {"success": True, "mode": normalized}

    def get_snapshot(self) -> dict[str, Any]:
        local = self.local_service.list_with_selection()
        online = self.online_service.list_with_selection()
        mode = self.get_mode()
        active_name = ""
        active_model = ""
        if mode == "local":
            preset = self.local_service.get_selected_preset()
            active_name = preset.name
            active_model = preset.model_name
        else:
            selected = self.online_service.get_selected_provider()
            if selected:
                active_name = selected["name"]
                active_model = selected["model_name"]
        return {
            "mode": mode,
            "active_name": active_name,
            "active_model": active_model,
            "local": local,
            "online": online,
        }

    def select_local(self, provider_id: str) -> dict[str, Any]:
        result = self.local_service.set_selected_id(provider_id)
        if result.get("success"):
            self._save("local")
        return result

    def select_online(self, provider_id: str) -> dict[str, Any]:
        result = self.online_service.set_selected_id(provider_id)
        if result.get("success"):
            self._save("online")
        return result

    def normalize_startup_mode(self) -> bool:
        """На старте: online без провайдера -> local, чтобы backend не падал."""
        if self.get_mode() == "online" and not self.online_service.get_selected_id():
            self._save("local")
            return True
        return False

    def apply_active_client(self, ollama_client: Any, online_client: Any) -> dict[str, Any]:
        mode = self.get_mode()
        if mode == "online":
            provider = self.online_service.apply_to_client(online_client)
            if not provider:
                return {"mode": mode, "provider": None, "warning": "online_provider_missing"}
            return {"mode": mode, "provider": provider}
        preset = self.local_service.apply_to_client(ollama_client)
        return {"mode": mode, "preset": preset.to_dict()}

    def get_active_llm(self, ollama_client: Any, online_client: Any) -> Any:
        return resolve_active_llm(self, ollama_client, online_client).client


def default_runtime_service(project_root: Path | None = None) -> AiRuntimeService:
    return AiRuntimeService(project_root=project_root)
