"""Учёт и лимиты токенов для онлайн API (Gemini, OpenAI-compatible)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

USAGE_FILENAME = "token_usage.json"
LIMITS_FILENAME = "ai_usage_limits.json"

# Счётчик «сессии» — только текущий запуск CoreX (не пишется на диск).
# Раньше он копился в token_usage.json между днями и перезапусками — из‑за этого
# блокировка срабатывала при живой квоте Gemini.
_runtime_session: dict[str, int] | None = None


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> TokenUsage:
        if not isinstance(data, dict):
            return cls()
        prompt = int(data.get("prompt_tokens") or data.get("promptTokenCount") or 0)
        completion = int(
            data.get("completion_tokens")
            or data.get("candidatesTokenCount")
            or data.get("completionTokenCount")
            or 0
        )
        total = int(data.get("total_tokens") or data.get("totalTokenCount") or 0)
        if total <= 0:
            total = prompt + completion
        return cls(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class UsageLimits:
    enabled: bool = True
    session_limit: int = 120_000
    daily_limit: int = 500_000
    warn_at_percent: int = 80

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "session_limit": self.session_limit,
            "daily_limit": self.daily_limit,
            "warn_at_percent": self.warn_at_percent,
        }


def _chat_dir(app_root: Path) -> Path:
    return app_root / "chat"


def _usage_path(app_root: Path) -> Path:
    return _chat_dir(app_root) / USAGE_FILENAME


def _limits_path(app_root: Path) -> Path:
    return _chat_dir(app_root) / LIMITS_FILENAME


def _empty_bucket() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}


def _session_bucket() -> dict[str, int]:
    global _runtime_session
    if _runtime_session is None:
        _runtime_session = _empty_bucket()
    return _runtime_session


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default.copy()
    return data if isinstance(data, dict) else default.copy()


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_limits(app_root: Path) -> UsageLimits:
    raw = _load_json(_limits_path(app_root), UsageLimits().to_dict())
    return UsageLimits(
        enabled=bool(raw.get("enabled", True)),
        session_limit=max(1_000, int(raw.get("session_limit") or 120_000)),
        daily_limit=max(1_000, int(raw.get("daily_limit") or 500_000)),
        warn_at_percent=min(99, max(50, int(raw.get("warn_at_percent") or 80))),
    )


def set_limits(app_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_limits(app_root)
    limits = UsageLimits(
        enabled=bool(payload.get("enabled", current.enabled)),
        session_limit=max(1_000, int(payload.get("session_limit") or current.session_limit)),
        daily_limit=max(1_000, int(payload.get("daily_limit") or current.daily_limit)),
        warn_at_percent=min(
            99,
            max(50, int(payload.get("warn_at_percent") or current.warn_at_percent)),
        ),
    )
    _save_json(_limits_path(app_root), limits.to_dict())
    return {"success": True, "limits": limits.to_dict()}


def _normalize_usage_state(raw: dict[str, Any]) -> dict[str, Any]:
    today = date.today().isoformat()
    daily = raw.get("daily") if isinstance(raw.get("daily"), dict) else _empty_bucket()
    if daily.get("date") != today:
        daily = {**_empty_bucket(), "date": today}
    return {"session": dict(_session_bucket()), "daily": daily}


def _load_usage_state(app_root: Path) -> dict[str, Any]:
    raw = _load_json(_usage_path(app_root), {"daily": _empty_bucket()})
    if "session" in raw:
        daily_only = {"daily": raw.get("daily")}
        _save_json(_usage_path(app_root), daily_only)
        raw = daily_only
    return _normalize_usage_state(raw)


def reset_session_usage(app_root: Path) -> dict[str, Any]:
    global _runtime_session
    _runtime_session = _empty_bucket()
    state = _load_usage_state(app_root)
    _save_json(_usage_path(app_root), {"daily": state["daily"]})
    return {"success": True}


def _add_bucket(bucket: dict[str, int], usage: TokenUsage) -> None:
    bucket["prompt_tokens"] = int(bucket.get("prompt_tokens") or 0) + usage.prompt_tokens
    bucket["completion_tokens"] = int(bucket.get("completion_tokens") or 0) + usage.completion_tokens
    bucket["total_tokens"] = int(bucket.get("total_tokens") or 0) + usage.total_tokens
    bucket["requests"] = int(bucket.get("requests") or 0) + 1


def get_usage_summary(app_root: Path) -> dict[str, Any]:
    limits = get_limits(app_root)
    state = _load_usage_state(app_root)
    session_total = int(state["session"].get("total_tokens") or 0)
    daily_total = int(state["daily"].get("total_tokens") or 0)
    return {
        "success": True,
        "limits": limits.to_dict(),
        "session": state["session"],
        "daily": state["daily"],
        "remaining_session": max(0, limits.session_limit - session_total),
        "remaining_daily": max(0, limits.daily_limit - daily_total),
        "session_percent": round(session_total / limits.session_limit * 100, 1) if limits.session_limit else 0,
        "daily_percent": round(daily_total / limits.daily_limit * 100, 1) if limits.daily_limit else 0,
    }


def check_budget(app_root: Path, *, mode: str = "online") -> tuple[bool, str]:
    if mode != "online":
        return True, ""
    limits = get_limits(app_root)
    if not limits.enabled:
        return True, ""

    state = _load_usage_state(app_root)
    session_total = int(state["session"].get("total_tokens") or 0)
    daily_total = int(state["daily"].get("total_tokens") or 0)

    if session_total >= limits.session_limit:
        return (
            False,
            f"Лимит токенов за сессию исчерпан ({session_total:,} / {limits.session_limit:,}). "
            "Перезапустите CoreX или сбросьте счётчик кнопкой ↺ рядом с полосой токенов.",
        )
    if daily_total >= limits.daily_limit:
        return (
            False,
            f"Дневной лимит токенов исчерпан ({daily_total:,} / {limits.daily_limit:,}). "
            "Увеличьте лимит в настройках или дождитесь нового дня.",
        )
    return True, ""


def record_usage(
    app_root: Path,
    usage: TokenUsage,
    *,
    mode: str = "online",
    label: str = "",
) -> dict[str, Any]:
    if mode != "online" or usage.total_tokens <= 0:
        return {"recorded": False}

    limits = get_limits(app_root)
    state = _load_usage_state(app_root)
    session = _session_bucket()
    _add_bucket(session, usage)
    _add_bucket(state["daily"], usage)
    _save_json(_usage_path(app_root), {"daily": state["daily"]})

    session_total = int(session.get("total_tokens") or 0)
    daily_total = int(state["daily"].get("total_tokens") or 0)
    warning = ""
    if limits.enabled:
        session_pct = session_total / limits.session_limit * 100 if limits.session_limit else 0
        if session_pct >= limits.warn_at_percent:
            warning = (
                f"Использовано {session_total:,} / {limits.session_limit:,} токенов за сессию "
                f"({session_pct:.0f}%)."
            )

    return {
        "recorded": True,
        "label": label,
        "usage": usage.to_dict(),
        "session_total": session_total,
        "daily_total": daily_total,
        "warning": warning,
        "blocked": session_total >= limits.session_limit or daily_total >= limits.daily_limit,
    }


def estimate_tokens(*texts: str) -> TokenUsage:
    chars = sum(len(text or "") for text in texts)
    total = max(1, chars // 4) if chars else 0
    return TokenUsage(prompt_tokens=total, completion_tokens=0, total_tokens=total)
