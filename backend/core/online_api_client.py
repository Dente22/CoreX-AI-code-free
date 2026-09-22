"""Online API client for CoreX (OpenAI-compatible + Gemini)."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import AsyncGenerator, Iterator, Literal

import aiohttp

from core.conversation_memory import trim_history_for_llm
from core.gemini_models import normalize_gemini_model_name
from core.online_api_errors import format_online_api_error, is_model_unavailable_error
from core.token_usage_service import TokenUsage

# Stable free router first, then concrete :free slugs that are currently published.
OPENROUTER_FREE_FALLBACK_MODELS = (
    "openrouter/free",
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-4-26b-a4b-it:free",
)

ONLINE_HISTORY_MAX_TURNS = 8
ONLINE_HISTORY_MSG_CHARS = 2500


@dataclass(frozen=True)
class LlmUsageStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_token_usage(self) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )


class OnlineApiClient:
    def __init__(
        self,
        model_name: str = "",
        base_url: str = "",
        api_key: str = "",
        api_type: Literal["openai", "gemini"] = "openai",
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_type = api_type
        self.chat_url = f"{self.base_url}/chat/completions" if self.base_url else ""
        self._last_usage: LlmUsageStats | None = None
        self.on_model_switched: Callable[[str, str], None] | None = None
        self._model_switch_notices: list[str] = []

    def get_last_usage(self) -> LlmUsageStats | None:
        return self._last_usage

    def clear_last_usage(self) -> None:
        self._last_usage = None

    def consume_model_switch_notices(self) -> list[str]:
        notices = list(self._model_switch_notices)
        self._model_switch_notices.clear()
        return notices

    def _is_openrouter(self) -> bool:
        return "openrouter.ai" in (self.base_url or "").lower()

    def _apply_model_switch(self, old_model: str, new_model: str) -> None:
        self.model_name = new_model
        notice = f"Модель {old_model} недоступна → переключаюсь на {new_model}"
        self._model_switch_notices.append(notice)
        callback = self.on_model_switched
        if callback:
            try:
                callback(old_model, new_model)
            except Exception:
                pass

    def _try_switch_on_unavailable(self, status: int, body: str, tried: set[str]) -> bool:
        if self.api_type != "openai" or not self._is_openrouter():
            return False
        if not is_model_unavailable_error(status, body):
            return False
        current = (self.model_name or "").strip()
        if current:
            tried.add(current.lower())
        for candidate in OPENROUTER_FREE_FALLBACK_MODELS:
            if candidate.lower() in tried:
                continue
            self._apply_model_switch(current or "(empty)", candidate)
            return True
        return False

    @contextmanager
    def temporary_model(self, model_name: str | None) -> Iterator[str]:
        target = str(model_name or "").strip()
        current = str(self.model_name or "").strip()
        if not target or target == current:
            yield current
            return
        previous = self.model_name
        self.model_name = target
        try:
            yield target
        finally:
            self.model_name = previous

    @staticmethod
    def _usage_from_openai_payload(payload: dict) -> LlmUsageStats | None:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None
        stats = TokenUsage.from_mapping(usage)
        if stats.total_tokens <= 0:
            return None
        return LlmUsageStats(
            prompt_tokens=stats.prompt_tokens,
            completion_tokens=stats.completion_tokens,
            total_tokens=stats.total_tokens,
        )

    @staticmethod
    def _usage_from_gemini_payload(payload: dict) -> LlmUsageStats | None:
        usage = payload.get("usageMetadata")
        if not isinstance(usage, dict):
            return None
        stats = TokenUsage.from_mapping(usage)
        if stats.total_tokens <= 0:
            return None
        return LlmUsageStats(
            prompt_tokens=stats.prompt_tokens,
            completion_tokens=stats.completion_tokens,
            total_tokens=stats.total_tokens,
        )

    def _store_usage(
        self,
        payload: dict | None,
        *,
        system_prompt: str = "",
        user_prompt: str = "",
        response_text: str = "",
    ) -> None:
        usage: LlmUsageStats | None = None
        if isinstance(payload, dict):
            if self.api_type == "gemini":
                usage = self._usage_from_gemini_payload(payload)
            else:
                usage = self._usage_from_openai_payload(payload)
        if usage is None and (system_prompt or user_prompt or response_text):
            estimated = TokenUsage(
                prompt_tokens=max(1, (len(system_prompt) + len(user_prompt)) // 4),
                completion_tokens=max(0, len(response_text) // 4),
                total_tokens=0,
            )
            usage = LlmUsageStats(
                prompt_tokens=estimated.prompt_tokens,
                completion_tokens=estimated.completion_tokens,
                total_tokens=estimated.prompt_tokens + estimated.completion_tokens,
            )
        self._last_usage = usage

    async def ensure_daemon_running(self) -> bool:
        return await self.ensure_ready()

    async def ensure_ready(self) -> bool:
        return bool(self.base_url and self.api_key and self.model_name)

    def _headers(self) -> dict[str, str]:
        if self.api_type == "gemini":
            return {"Content-Type": "application/json"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self._is_openrouter():
            headers["HTTP-Referer"] = "https://corex.local"
            headers["X-Title"] = "CoreX"
        return headers

    def _resolved_gemini_model(self) -> str:
        return normalize_gemini_model_name(self.model_name)

    def _gemini_generate_url(self, stream: bool = False) -> str:
        if not self.base_url or not self.model_name:
            return ""
        model = self._resolved_gemini_model()
        suffix = ":streamGenerateContent?alt=sse" if stream else ":generateContent"
        joiner = "&" if "?" in suffix else "?"
        return f"{self.base_url}/models/{model}{suffix}{joiner}key={self.api_key}"

    def _lean_history(self, history: list[dict] | None) -> list[dict]:
        return trim_history_for_llm(
            history,
            max_turns=ONLINE_HISTORY_MAX_TURNS,
            max_chars=ONLINE_HISTORY_MSG_CHARS,
        )

    def _build_gemini_contents(
        self,
        user_prompt: str,
        history: list[dict] | None = None,
    ) -> list[dict]:
        items: list[dict] = []
        for entry in self._lean_history(history):
            role = entry.get("role")
            content = str(entry.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant":
                items.append({"role": "model", "parts": [{"text": content}]})
            elif role == "user":
                items.append({"role": "user", "parts": [{"text": content}]})
        items.append({"role": "user", "parts": [{"text": user_prompt}]})
        return items

    @staticmethod
    def _extract_gemini_text(payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        chunks: list[str] = []
        for part in parts:
            text = part.get("text")
            if text:
                chunks.append(text)
        return "".join(chunks)

    def _build_messages(self, system_prompt: str, user_prompt: str, history: list[dict] | None = None) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for item in self._lean_history(history):
            role = item.get("role")
            content = item.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _error_model_label(self) -> str:
        if self.api_type == "gemini":
            return self._resolved_gemini_model()
        return self.model_name

    async def chat_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict] | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        if not await self.ensure_daemon_running():
            return (
                "[CoreX Critical Error]: Онлайн API не настроен. "
                "Добавьте провайдера в режиме «Онлайн» и выберите модель."
            )

        timeout = aiohttp.ClientTimeout(total=120)
        tried: set[str] = set()
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                if self.api_type == "gemini":
                    payload = {
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": self._build_gemini_contents(user_prompt, history),
                        "generationConfig": {"temperature": temperature},
                    }
                    request_url = self._gemini_generate_url(stream=False)
                else:
                    payload = {
                        "model": self.model_name,
                        "messages": self._build_messages(system_prompt, user_prompt, history),
                        "temperature": temperature,
                        "stream": False,
                    }
                    request_url = self.chat_url

                try:
                    async with session.post(request_url, headers=self._headers(), json=payload) as response:
                        if response.status != 200:
                            text = await response.text()
                            if self._try_switch_on_unavailable(response.status, text, tried):
                                continue
                            return format_online_api_error(
                                response.status,
                                text,
                                api_type=self.api_type,
                                model_name=self._error_model_label(),
                            )
                        data = await response.json()
                        if self.api_type == "gemini":
                            content = self._extract_gemini_text(data)
                            self._store_usage(
                                data,
                                system_prompt=system_prompt,
                                user_prompt=user_prompt,
                                response_text=content,
                            )
                            if not content:
                                return "[CoreX Critical Error]: Gemini API returned empty candidates."
                            return content
                        choices = data.get("choices") or []
                        if not choices:
                            return "[CoreX Critical Error]: Online API returned empty choices."
                        message = choices[0].get("message") or {}
                        content = message.get("content", "")
                        self._store_usage(
                            data,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            response_text=content,
                        )
                        return content
                except aiohttp.ClientError as exc:
                    return f"[CoreX Critical Error]: Online API connection failed: {exc}"
                except Exception as exc:
                    return f"[CoreX Critical Error]: {exc}"

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict] | None = None,
        temperature: float = 0.1,
        json_mode: bool = False,
        num_predict: int | None = None,
    ) -> AsyncGenerator[str, None]:
        if not await self.ensure_daemon_running():
            yield (
                "\n[CoreX Critical Error]: Онлайн API не настроен. "
                "Добавьте провайдера в режиме «Онлайн»."
            )
            return

        timeout = aiohttp.ClientTimeout(total=None)
        tried: set[str] = set()
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                if self.api_type == "gemini":
                    payload = {
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": self._build_gemini_contents(user_prompt, history),
                        "generationConfig": {
                            "temperature": temperature,
                            **({"responseMimeType": "application/json"} if json_mode else {}),
                        },
                    }
                    request_url = self._gemini_generate_url(stream=True)
                else:
                    payload = {
                        "model": self.model_name,
                        "messages": self._build_messages(system_prompt, user_prompt, history),
                        "temperature": temperature,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    }
                    if json_mode:
                        payload["response_format"] = {"type": "json_object"}
                    request_url = self.chat_url

                try:
                    async with session.post(request_url, headers=self._headers(), json=payload) as response:
                        if response.status != 200:
                            text = await response.text()
                            if self._try_switch_on_unavailable(response.status, text, tried):
                                continue
                            yield format_online_api_error(
                                response.status,
                                text,
                                api_type=self.api_type,
                                model_name=self._error_model_label(),
                            )
                            return

                        response_text = ""
                        last_payload: dict | None = None
                        async for raw_line in response.content:
                            line = raw_line.decode("utf-8").strip()
                            if not line or not line.startswith("data:"):
                                continue
                            data_part = line[5:].strip()
                            if data_part == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_part)
                            except json.JSONDecodeError:
                                continue
                            last_payload = chunk
                            if self.api_type == "gemini":
                                content = self._extract_gemini_text(chunk)
                            else:
                                choices = chunk.get("choices") or []
                                if not choices:
                                    continue
                                delta = choices[0].get("delta") or {}
                                content = delta.get("content", "")
                            if content:
                                response_text += content
                                yield content
                        self._store_usage(
                            last_payload,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            response_text=response_text,
                        )
                        return
                except aiohttp.ClientError as exc:
                    yield f"\n[CoreX Critical Error]: Online API connection failed: {exc}"
                    return
                except Exception as exc:
                    yield f"\n[CoreX Critical Error]: {exc}"
                    return
