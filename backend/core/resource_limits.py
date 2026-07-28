"""Лимиты нагрузки для локального запуска Ollama."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from core.device_profile import detect_device_profile, resolve_limits


def get_default_limits(app_root: Path | None = None) -> dict[str, int]:
    """Лимиты по характеристикам текущего устройства и ползунку настроек."""
    return resolve_limits(None, app_root=app_root)


# Обратная совместимость — вычисляется при импорте модуля
DEFAULT_LIMITS = get_default_limits()


@dataclass
class ResourceBudget:
    max_total_turns: int = DEFAULT_LIMITS["max_total_turns"]
    max_turns_per_step: int = DEFAULT_LIMITS["max_turns_per_step"]
    max_file_writes: int = DEFAULT_LIMITS["max_file_writes"]
    delay_between_turns_ms: int = DEFAULT_LIMITS["delay_between_turns_ms"]
    delay_between_steps_ms: int = DEFAULT_LIMITS["delay_between_steps_ms"]

    turns_used: int = 0
    writes_used: int = 0
    step_turns: int = 0
    _current_step_limit: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self._current_step_limit <= 0:
            self._current_step_limit = self.max_turns_per_step

    @classmethod
    def from_dict(cls, data: dict | None, app_root: Path | None = None) -> ResourceBudget:
        base = resolve_limits(data, app_root=app_root)
        return cls(
            max_total_turns=int(base["max_total_turns"]),
            max_turns_per_step=int(base["max_turns_per_step"]),
            max_file_writes=int(base["max_file_writes"]),
            delay_between_turns_ms=int(base["delay_between_turns_ms"]),
            delay_between_steps_ms=int(base["delay_between_steps_ms"]),
        )

    @classmethod
    def for_device(cls, pipeline_limits: dict | None = None, app_root: Path | None = None) -> ResourceBudget:
        return cls.from_dict(pipeline_limits, app_root=app_root)

    @classmethod
    def for_online(cls, pipeline_limits: dict | None = None) -> ResourceBudget:
        """
        Онлайн-режим: ограничения по "железу" не должны преждевременно останавливать задачу.

        Вместо этого опираемся на бюджет токенов (token_usage_service), а turn/write лимиты
        делаем достаточно высокими.
        """
        limits = pipeline_limits or {}

        # Heuristic caps for online mode. Token budget is the real limiter.
        # Keep them comfortably above typical pipeline settings.
        max_total_turns = int(limits.get("max_total_turns") or 0) or 0
        max_turns_per_step = int(limits.get("max_turns_per_step") or 0) or 0
        max_file_writes = int(limits.get("max_file_writes") or 0) or 0

        return cls(
            max_total_turns=max(200, max_total_turns),
            max_turns_per_step=max(60, max_turns_per_step),
            max_file_writes=max(50, max_file_writes),
            # Online calls should not be slowed down artificially.
            delay_between_turns_ms=0,
            delay_between_steps_ms=0,
        )

    def begin_step(self, max_turns: int | None = None) -> None:
        self.step_turns = 0
        self._current_step_limit = max_turns if max_turns is not None else self.max_turns_per_step

    def reset_step(self) -> None:
        self.begin_step()

    def can_turn(self) -> bool:
        return (
            self.turns_used < self.max_total_turns
            and self.step_turns < self._current_step_limit
        )

    def can_write(self) -> bool:
        return self.writes_used < self.max_file_writes

    def record_turn(self) -> None:
        self.record_llm_call()
        self.record_step_turn()

    def record_llm_call(self) -> None:
        self.turns_used += 1

    def record_step_turn(self) -> None:
        self.step_turns += 1

    def record_write(self) -> None:
        self.writes_used += 1

    def stop_reason(self) -> str | None:
        if self.turns_used >= self.max_total_turns:
            return f"Достигнут лимит ходов LLM ({self.max_total_turns}). Остановка для защиты ПК."
        if self.step_turns >= self._current_step_limit:
            return (
                f"Лимит ходов на этап ({self.step_turns}/{self._current_step_limit}). "
                "Увеличьте лимит в настройках нагрузки или упростите задачу."
            )
        if self.writes_used >= self.max_file_writes:
            return f"Лимит записей файлов ({self.max_file_writes})."
        return None

    async def pause_turn(self) -> None:
        if self.delay_between_turns_ms > 0:
            await asyncio.sleep(self.delay_between_turns_ms / 1000)

    async def pause_step(self) -> None:
        if self.delay_between_steps_ms > 0:
            await asyncio.sleep(self.delay_between_steps_ms / 1000)

    def status_line(self) -> str:
        profile = detect_device_profile()
        return (
            f"Нагрузка ({profile.tier}): ходы {self.turns_used}/{self.max_total_turns}, "
            f"записи {self.writes_used}/{self.max_file_writes}"
        )
