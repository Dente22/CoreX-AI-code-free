import asyncio
import json
from typing import AsyncGenerator

import aiohttp

from core.device_profile import detect_device_profile
from core.ollama_lifecycle import (
    MODEL_KEEP_ALIVE,
    begin_ollama_generation,
    end_ollama_generation,
    ensure_ollama_serve_running,
    get_ollama_start_error,
    merge_ollama_runtime_env,
    note_ollama_activity,
    resolve_ollama_base_url,
)
from core.ollama_model_session import activate_ollama_model, clear_active_ollama_model, verify_model_installed

CHAT_TIMEOUT = aiohttp.ClientTimeout(total=900, connect=30, sock_read=600)
_STREAM_RETRY_DELAY_SEC = 1.5
_OVERFLOW_MARKERS = ("exceed_context_size_error", "exceeds the available context size")


def format_ollama_connection_error(exc: Exception, *, model_name: str) -> str:
    raw = str(exc)
    lowered = raw.lower()
    if "10054" in raw or "forcibly closed" in lowered or "connection reset" in lowered:
        profile = detect_device_profile()
        hint = ""
        if profile.ram_available_gb < 6 or "llama" in model_name.lower():
            hint = (
                " Похоже, не хватает RAM для этой модели — закройте лишние программы "
                "или выберите Phi-3 / Qwen в настройках."
            )
        return (
            "Ollama оборвала соединение при загрузке модели."
            f"{hint} Повторите сообщение через несколько секунд."
        )
    if "timed out" in lowered or "timeout" in lowered:
        return (
            "Ollama слишком долго не отвечала (модель грузится в память). "
            "Подождите и отправьте сообщение снова."
        )
    if "cannot connect to host" in lowered or "connect call failed" in lowered:
        return (
            "Ollama не запущена на 127.0.0.1:11435. "
            "CoreX попробует перезапустить её — отправьте сообщение ещё раз."
        )
    return raw


class OllamaClient:
    def __init__(self, model_name: str = "qwen2.5-coder:7b", base_url: str | None = None):
        self.model_name = model_name
        self.root_url = (base_url or resolve_ollama_base_url()).rstrip("/")
        self.chat_url = f"{self.root_url}/api/chat"
        self._daemon_checked = False
        self._daemon_lock = asyncio.Lock()
        self.last_error = ""

    def _log(self, message: str) -> None:
        print(f"[OllamaClient] {message}")

    def _runtime_options(self, *, temperature: float, num_predict: int | None = None) -> dict[str, int | float]:
        profile = detect_device_profile()
        num_ctx = profile.ollama_num_ctx()
        if profile.ram_available_gb < 5 and profile.tier != "low":
            num_ctx = min(num_ctx, 4096)
        default_predict = 768 if profile.tier == "low" else 2048
        return {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_batch": 128 if profile.tier == "low" else 256,
            "num_predict": num_predict if num_predict is not None else default_predict,
        }

    @staticmethod
    def _is_context_overflow_error(body: str) -> bool:
        text = (body or "").lower()
        return any(marker in text for marker in _OVERFLOW_MARKERS)

    @staticmethod
    def _trim_text(text: str, max_chars: int) -> str:
        clean = (text or "").strip()
        if len(clean) <= max_chars:
            return clean
        if max_chars <= 400:
            return clean[:max_chars]
        head = int(max_chars * 0.7)
        tail = max_chars - head - 20
        return f"{clean[:head]}\n...[truncated]...\n{clean[-tail:]}"

    def _compact_messages(self, messages: list[dict], *, aggressive: bool) -> list[dict]:
        if not messages:
            return messages

        system = messages[0] if messages and messages[0].get("role") == "system" else None
        user = messages[-1] if messages else None
        history = messages[1:-1] if system is not None else messages[:-1]

        keep_history = 2 if aggressive else 4
        history_tail = history[-keep_history:] if history else []
        max_system = 1600 if aggressive else 2600
        max_user = 2400 if aggressive else 3800
        max_history = 900 if aggressive else 1400

        compact: list[dict] = []
        if system is not None:
            compact.append(
                {
                    "role": "system",
                    "content": self._trim_text(str(system.get("content") or ""), max_system),
                }
            )
        for msg in history_tail:
            compact.append(
                {
                    "role": msg.get("role", "user"),
                    "content": self._trim_text(str(msg.get("content") or ""), max_history),
                }
            )
        if user is not None:
            compact.append(
                {
                    "role": user.get("role", "user"),
                    "content": self._trim_text(str(user.get("content") or ""), max_user),
                }
            )
        return compact

    async def ensure_daemon_running(self) -> bool:
        return await self.ensure_ready()

    async def ensure_ready(self) -> bool:
        async with self._daemon_lock:
            if await ensure_ollama_serve_running():
                if not self._daemon_checked:
                    self._log("Ollama server is running")
                    self._daemon_checked = True
                return True
            self.last_error = get_ollama_start_error()
            self._log(self.last_error)
            return False

    async def prepare_for_generation(self) -> bool:
        self.last_error = ""
        for attempt in range(2):
            if not await self.ensure_ready():
                if attempt == 0:
                    await self._recover_from_disconnect()
                    continue
                return False

            verify = await verify_model_installed(self.model_name, self.root_url)
            if not verify.get("installed"):
                self.last_error = str(verify.get("error") or f"Модель «{self.model_name}» недоступна.")
                if attempt == 0 and "11435" in self.last_error.lower():
                    await self._recover_from_disconnect()
                    continue
                self._log(self.last_error)
                return False

            switch = await activate_ollama_model(self.model_name, self.root_url, preload=False)
            if not switch.get("success"):
                self.last_error = str(switch.get("error") or "Не удалось подготовить модель.")
                if attempt == 0 and (
                    "11435" in self.last_error.lower() or "connect" in self.last_error.lower()
                ):
                    await self._recover_from_disconnect()
                    continue
                self._log(self.last_error)
                return False

            if switch.get("switched"):
                self._log(f"Переключено на модель: {self.model_name}")
            else:
                self._log(f"Готова к генерации: {self.model_name}")
            return True
        return False

    def _build_messages(self, system_prompt: str, user_prompt: str, history: list[dict] | None = None) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def _recover_from_disconnect(self) -> None:
        self._log("Восстанавливаю соединение с Ollama...")
        clear_active_ollama_model()
        self._daemon_checked = False
        from core.ollama_lifecycle import cleanup_zombie_llama_workers, stop_ollama_serve

        await stop_ollama_serve(reason="manual")
        await cleanup_zombie_llama_workers()
        await ensure_ollama_serve_running()
        await asyncio.sleep(_STREAM_RETRY_DELAY_SEC)

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict] | None = None,
        temperature: float = 0.1,
        json_mode: bool = False,
        num_predict: int | None = None,
    ) -> AsyncGenerator[str, None]:
        begin_ollama_generation()
        try:
            if not await self.prepare_for_generation():
                yield f"\n[CoreX Critical Error]: {self.last_error}"
                return

            payload = {
                "model": self.model_name,
                "messages": self._build_messages(system_prompt, user_prompt, history),
                "stream": True,
                "keep_alive": MODEL_KEEP_ALIVE,
                "options": self._runtime_options(temperature=temperature, num_predict=num_predict),
            }
            if json_mode:
                payload["format"] = "json"

            async for chunk in self._stream_payload(payload):
                yield chunk
        finally:
            end_ollama_generation()

    async def chat_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict] | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        num_predict: int | None = None,
    ) -> str:
        begin_ollama_generation()
        try:
            if not await self.prepare_for_generation():
                return f"[CoreX Critical Error]: {self.last_error}"

            payload = {
                "model": self.model_name,
                "messages": self._build_messages(system_prompt, user_prompt, history),
                "stream": False,
                "keep_alive": MODEL_KEEP_ALIVE,
                "options": self._runtime_options(
                    temperature=temperature,
                    num_predict=num_predict,
                ),
            }
            if json_mode:
                payload["format"] = "json"

            for attempt in range(3):
                try:
                    async with aiohttp.ClientSession(timeout=CHAT_TIMEOUT) as session:
                        async with session.post(self.chat_url, json=payload) as response:
                            if response.status != 200:
                                body = await response.text()
                                if response.status == 400 and self._is_context_overflow_error(body):
                                    payload["messages"] = self._compact_messages(
                                        payload.get("messages") or [],
                                        aggressive=attempt > 0,
                                    )
                                    continue
                                self.last_error = f"Ollama returned status {response.status}: {body[:200]}"
                                return f"[CoreX Critical Error]: {self.last_error}"
                            data = await response.json()
                            note_ollama_activity()
                            return data.get("message", {}).get("content", "")
                except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError, ConnectionResetError, OSError) as exc:
                    if attempt == 0:
                        await self._recover_from_disconnect()
                        continue
                    self.last_error = format_ollama_connection_error(exc, model_name=self.model_name)
                    return f"[CoreX Critical Error]: {self.last_error}"
                except aiohttp.ClientConnectorError as exc:
                    if attempt == 0:
                        await self._recover_from_disconnect()
                        continue
                    self.last_error = format_ollama_connection_error(exc, model_name=self.model_name)
                    return f"[CoreX Critical Error]: {self.last_error}"
                except Exception as e:
                    self.last_error = format_ollama_connection_error(e, model_name=self.model_name)
                    return f"[CoreX Critical Error]: {self.last_error}"
            return f"[CoreX Critical Error]: {self.last_error or 'Не удалось получить ответ'}"
        finally:
            end_ollama_generation()

    async def _stream_payload(self, payload: dict) -> AsyncGenerator[str, None]:
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=CHAT_TIMEOUT) as session:
                    async with session.post(self.chat_url, json=payload) as response:
                        if response.status != 200:
                            body = await response.text()
                            if response.status == 400 and self._is_context_overflow_error(body):
                                payload["messages"] = self._compact_messages(
                                    payload.get("messages") or [],
                                    aggressive=attempt > 0,
                                )
                                continue
                            self.last_error = f"Ollama returned status {response.status}: {body[:200]}"
                            yield f"\n[CoreX Critical Error]: {self.last_error}"
                            return

                        async for line in response.content:
                            if not line:
                                continue
                            note_ollama_activity()
                            chunk = json.loads(line.decode("utf-8"))
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                return
            except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError, ConnectionResetError, OSError) as exc:
                if attempt == 0:
                    await self._recover_from_disconnect()
                    continue
                self.last_error = format_ollama_connection_error(exc, model_name=self.model_name)
                yield f"\n[CoreX Critical Error]: {self.last_error}"
                return
            except aiohttp.ClientConnectorError as exc:
                if attempt == 0:
                    await self._recover_from_disconnect()
                    continue
                self.last_error = format_ollama_connection_error(exc, model_name=self.model_name)
                yield f"\n[CoreX Critical Error]: {self.last_error}"
                return
            except json.JSONDecodeError:
                continue
            except Exception as e:
                self.last_error = format_ollama_connection_error(e, model_name=self.model_name)
                yield f"\n[CoreX Critical Error]: {self.last_error}"
                return

    @staticmethod
    def merge_env(base: dict[str, str] | None = None) -> dict[str, str]:
        return merge_ollama_runtime_env(base)
