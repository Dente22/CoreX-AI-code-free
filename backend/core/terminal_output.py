"""Очистка и подсказки для вывода терминала CoreX."""

from __future__ import annotations

import re

_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_SPINNER_LINE_RE = re.compile(r"^pulling manifest\b", re.IGNORECASE)
_GATHERING_SPINNER_RE = re.compile(r"^gathering model components\b", re.IGNORECASE)
_COPY_PROGRESS_RE = re.compile(r"^copying file sha256:[a-f0-9]+ \d+%", re.IGNORECASE)
_OLLAMA_NETWORK_RE = re.compile(
    r"forcibly closed|connection (?:was )?reset|timed out|timeout|"
    r"no such host|failed to connect|wsarecv|dial tcp|i/o timeout",
    re.IGNORECASE,
)


def strip_ansi_escapes(text: str) -> str:
    if not text:
        return ""
    return _ANSI_ESCAPE_RE.sub("", text)


def sanitize_terminal_output(text: str) -> str:
    """Убрать ANSI и схлопнуть спиннер ollama pull/create в короткий вывод."""
    cleaned = strip_ansi_escapes(text)
    cleaned = cleaned.replace("\r", "\n")
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

    manifest_seen = False
    gathering_seen = False
    result: list[str] = []
    for line in lines:
        lowered = line.lower()
        if "error:" in lowered:
            idx = lowered.find("error:")
            result.append(line[idx:].strip())
            continue
        if _SPINNER_LINE_RE.match(line) or line == "pulling manifest…":
            manifest_seen = True
            continue
        if _GATHERING_SPINNER_RE.match(line) or "gathering model components" in lowered:
            gathering_seen = True
            continue
        if _COPY_PROGRESS_RE.match(line):
            continue
        result.append(line)

    if manifest_seen:
        result.insert(0, "pulling manifest…")
    if gathering_seen and not any(item.lower().startswith("error:") for item in result):
        result.insert(0, "gathering model components…")

    return "\n".join(result).strip()


def append_ollama_pull_hints(result: dict) -> dict:
    command = str(result.get("command") or "")
    if not re.search(r"\bollama\s+pull\b", command, re.IGNORECASE):
        return result

    combined = f"{result.get('output') or ''}\n{result.get('error') or ''}"
    if not _OLLAMA_NETWORK_RE.search(combined):
        return result

    hint = (
        "\n\n── Подсказка CoreX ──\n"
        "Не удалось скачать модель с registry.ollama.ai — проблема сети, не CoreX.\n"
        "Что попробовать:\n"
        "• Проверьте интернет и VPN/прокси (Ollama может блокироваться)\n"
        "• Убедитесь, что Ollama запущен: `ollama serve` или приложение в трее\n"
        "• Повторите команду через 1–2 минуты\n"
        "• Скачайте модель в обычном PowerShell/CMD вне CoreX и проверьте `ollama list`\n"
        "• На слабом ПК начните с лёгкой модели: `ollama pull phi3:mini`"
    )
    output = (result.get("output") or "").rstrip()
    result["output"] = output + hint
    result["hint"] = "Проверьте сеть и повторите ollama pull"
    return result


def command_timeout_sec(command: str, default: int) -> int:
    if re.search(r"\bollama\s+pull\b", (command or "").strip(), re.IGNORECASE):
        return max(default, 3600)
    return default
