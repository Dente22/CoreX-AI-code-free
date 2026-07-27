"""Прямая загрузка GGUF в папку CoreX (без registry.ollama.ai)."""

from __future__ import annotations

import asyncio
import contextlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import ClientPayloadError

from core.core_x_library import COREX_ROOT
from core.ollama_lifecycle import (
    begin_ollama_generation,
    end_ollama_generation,
    ensure_ollama_serve_running,
    merge_ollama_runtime_env,
    note_ollama_activity,
    resolve_ollama_executable,
    stop_ollama_serve,
)
from core.terminal_output import sanitize_terminal_output
from core.ollama_pull_progress import (
    apply_http_download_progress,
    apply_import_progress_start,
    apply_ollama_import_progress,
    apply_pull_event,
    format_bytes,
    friendly_pull_error,
    get_pull_progress,
    get_pull_progress_state,
    mark_pull_error,
)

DOWNLOAD_TIMEOUT_SEC = 7200
IMPORT_TIMEOUT_SEC = 3600
CHUNK_SIZE = 1024 * 1024
MAX_DOWNLOAD_ATTEMPTS = 12
RETRY_DELAY_SEC = 3
CURL_PROGRESS_INTERVAL_SEC = 2.0
SOCK_READ_TIMEOUT_SEC = 600
_OLLAMA_CREATE_COPY_RE = re.compile(r"copying file sha256:[a-f0-9]+ (\d+)%", re.IGNORECASE)


def parse_ollama_create_progress(text: str) -> int | None:
    matches = _OLLAMA_CREATE_COPY_RE.findall(text or "")
    if not matches:
        return None
    return int(matches[-1])


def resolve_file_size(path: Path, fallback: int = 0) -> int:
    try:
        if path.is_file():
            return max(0, path.stat().st_size)
    except OSError:
        pass
    return max(0, int(fallback))


@dataclass(frozen=True)
class DirectModelSource:
    provider_id: str
    model_name: str
    url: str
    filename: str
    size_hint: int


DIRECT_MODEL_SOURCES: dict[str, DirectModelSource] = {
    "ollama-lite": DirectModelSource(
        provider_id="ollama-lite",
        model_name="phi3:mini",
        url=(
            "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/"
            "resolve/main/Phi-3-mini-4k-instruct-q4.gguf"
        ),
        filename="phi3-mini-q4.gguf",
        size_hint=2_400_000_000,
    ),
    "ollama-qwen": DirectModelSource(
        provider_id="ollama-qwen",
        model_name="qwen2.5-coder:7b",
        url=(
            "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/"
            "resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        ),
        filename="qwen2.5-coder-7b-q4_k_m.gguf",
        size_hint=4_700_000_000,
    ),
    "ollama-claude": DirectModelSource(
        provider_id="ollama-claude",
        model_name="llama3.1:8b",
        url=(
            "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/"
            "resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
        ),
        filename="llama3.1-8b-q4_k_m.gguf",
        size_hint=4_900_000_000,
    ),
}


def resolve_models_storage_dir() -> Path:
    path = COREX_ROOT / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def has_direct_source(provider_id: str) -> bool:
    return provider_id in DIRECT_MODEL_SOURCES


def get_direct_source(provider_id: str) -> DirectModelSource | None:
    return DIRECT_MODEL_SOURCES.get(provider_id)


def resolve_gguf_path(provider_id: str) -> Path:
    source = get_direct_source(provider_id)
    if source is None:
        raise KeyError(provider_id)
    return resolve_models_storage_dir() / provider_id / source.filename


def direct_download_curl_command(provider_id: str) -> str:
    source = get_direct_source(provider_id)
    if source is None:
        return ""
    rel = Path("models") / provider_id / source.filename
    return f'curl -L -f -sS -C - -o "{rel.as_posix()}" "{source.url}"'


def build_curl_download_argv(curl_bin: str, part: Path, url: str) -> list[str]:
    """Флаги как в cmd; -sS отключает progress-meter (иначе stderr pipe тормозит curl)."""
    return [
        curl_bin,
        "-L",
        "-f",
        "-sS",
        "-C",
        "-",
        "--retry",
        "3",
        "--retry-delay",
        "2",
        "--connect-timeout",
        "30",
        "--max-time",
        str(DOWNLOAD_TIMEOUT_SEC),
        "-o",
        str(part),
        url,
    ]


def cleanup_direct_download(provider_id: str) -> dict[str, Any]:
    target = resolve_models_storage_dir() / provider_id
    if not target.is_dir():
        return {"removed": False}
    shutil.rmtree(target, ignore_errors=True)
    return {"removed": True, "path": str(target)}


def resolve_resume_byte(part: Path) -> int:
    if not part.is_file():
        return 0
    try:
        return max(0, part.stat().st_size)
    except OSError:
        return 0


def build_download_headers(start_byte: int) -> dict[str, str]:
    headers = {"User-Agent": "CoreX/1.0 (+https://github.com/corex)"}
    if start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"
    return headers


def is_retryable_download_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            ClientPayloadError,
            aiohttp.ClientOSError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientConnectorError,
            asyncio.TimeoutError,
            ConnectionResetError,
            BrokenPipeError,
        ),
    ):
        return True
    lowered = str(exc).lower()
    return (
        "content length" in lowered
        or "not enough data" in lowered
        or "connection reset" in lowered
        or "forcibly closed" in lowered
    )


def friendly_download_error(exc: BaseException) -> str:
    return friendly_pull_error(str(exc))


def _cleanup_partial_file(path: Path) -> None:
    part = path.with_suffix(path.suffix + ".part")
    if part.exists():
        with contextlib.suppress(OSError):
            part.unlink()


def _resolve_download_total(
    *,
    response: aiohttp.ClientResponse,
    start_byte: int,
    size_hint: int,
) -> int:
    content_length = response.headers.get("Content-Length")
    content_range = response.headers.get("Content-Range", "")
    total = size_hint

    if response.status == 206 and "/" in content_range:
        total = int(content_range.split("/")[-1])
    elif content_length:
        chunk_total = int(content_length)
        total = start_byte + chunk_total if response.status == 206 else chunk_total
    return total


async def _http_download_attempt(
    url: str,
    part: Path,
    *,
    job_id: str,
    size_hint: int,
) -> None:
    start_byte = resolve_resume_byte(part)
    headers = build_download_headers(start_byte)
    timeout = aiohttp.ClientTimeout(
        total=DOWNLOAD_TIMEOUT_SEC,
        connect=60,
        sock_read=SOCK_READ_TIMEOUT_SEC,
    )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers, allow_redirects=True) as response:
            if response.status not in (200, 206):
                body = await response.text()
                raise RuntimeError(
                    f"Hugging Face вернул статус {response.status}: {body[:200]}"
                )

            if start_byte > 0 and response.status == 200:
                start_byte = 0
                with contextlib.suppress(OSError):
                    part.unlink()

            mode = "ab" if start_byte > 0 and response.status == 206 else "wb"
            if mode == "wb" and part.exists():
                with contextlib.suppress(OSError):
                    part.unlink()
                start_byte = 0

            total = _resolve_download_total(
                response=response,
                start_byte=start_byte,
                size_hint=size_hint,
            )
            completed = start_byte
            state = get_pull_progress_state(job_id)
            if state is not None:
                apply_http_download_progress(
                    state,
                    completed,
                    total,
                    resumed=start_byte > 0,
                )

            with part.open(mode) as handle:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    completed += len(chunk)
                    state = get_pull_progress_state(job_id)
                    if state is not None:
                        apply_http_download_progress(state, completed, total)


async def _http_download_to_file(
    url: str,
    dest: Path,
    *,
    job_id: str,
    size_hint: int,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    last_error: BaseException | None = None

    for attempt in range(MAX_DOWNLOAD_ATTEMPTS):
        try:
            await _http_download_attempt(url, part, job_id=job_id, size_hint=size_hint)
            part.replace(dest)
            return
        except RuntimeError:
            raise
        except Exception as exc:
            last_error = exc
            if not is_retryable_download_error(exc) or attempt + 1 >= MAX_DOWNLOAD_ATTEMPTS:
                break
            state = get_pull_progress_state(job_id)
            if state is not None:
                resumed = resolve_resume_byte(part)
                state["message"] = (
                    f"Сеть оборвала загрузку, повтор {attempt + 2}/{MAX_DOWNLOAD_ATTEMPTS}…"
                )
                if resumed > 0:
                    state["resumed"] = True
                    apply_http_download_progress(state, resumed, size_hint, resumed=True)
            await asyncio.sleep(RETRY_DELAY_SEC * (attempt + 1))

    if last_error is not None:
        raise RuntimeError(friendly_download_error(last_error)) from last_error
    raise RuntimeError("Не удалось скачать модель")


async def _monitor_part_file_progress(
    part: Path,
    *,
    job_id: str,
    size_hint: int,
    done: threading.Event,
) -> None:
    try:
        while not done.is_set():
            completed = resolve_resume_byte(part)
            state = get_pull_progress_state(job_id)
            if state is not None and completed > 0:
                apply_http_download_progress(
                    state,
                    completed,
                    size_hint,
                    resumed=state.get("resumed", False),
                )
            await asyncio.sleep(CURL_PROGRESS_INTERVAL_SEC)
    except asyncio.CancelledError:
        raise


def run_curl_download_blocking(cmd: list[str]) -> int:
    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    completed = subprocess.run(cmd, **popen_kwargs)
    return int(completed.returncode)


async def _curl_download_to_file(
    url: str,
    dest: Path,
    *,
    job_id: str,
    size_hint: int,
) -> None:
    curl_bin = shutil.which("curl")
    if not curl_bin:
        raise RuntimeError("curl не найден в системе")

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    cmd = build_curl_download_argv(curl_bin, part, url)
    done = threading.Event()
    monitor = asyncio.create_task(
        _monitor_part_file_progress(part, job_id=job_id, size_hint=size_hint, done=done)
    )
    try:
        return_code = await asyncio.to_thread(run_curl_download_blocking, cmd)
    finally:
        done.set()
        monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor

    if return_code != 0:
        raise RuntimeError(f"curl завершился с кодом {return_code}")

    if not part.is_file() or part.stat().st_size <= 0:
        raise RuntimeError("curl не создал файл модели")

    part.replace(dest)


def run_ollama_create_with_progress(
    cmd: list[str],
    *,
    env: dict[str, str],
    cwd: str,
    timeout: int,
    file_size: int,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
        "cwd": cwd,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    stderr_parts: list[str] = []
    stdout_parts: list[str] = []

    try:
        process = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": "Команда Ollama не найдена. Установите с https://ollama.com/download",
            "command": " ".join(cmd),
        }
    except OSError as exc:
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": str(exc),
            "command": " ".join(cmd),
        }

    def _read_stderr() -> None:
        assert process.stderr is not None
        buffer = ""
        while True:
            line = process.stderr.readline()
            if not line:
                break
            note_ollama_activity()
            stderr_parts.append(line)
            buffer = (buffer + line)[-512:]
            percent = parse_ollama_create_progress(buffer)
            if percent is not None and state is not None and file_size > 0:
                completed = int(file_size * percent / 100)
                apply_ollama_import_progress(
                    state,
                    completed,
                    file_size,
                    percent=float(percent),
                )

    def _read_stdout() -> None:
        assert process.stdout is not None
        while True:
            line = process.stdout.readline()
            if not line:
                break
            stdout_parts.append(line)

    stderr_reader = threading.Thread(target=_read_stderr, daemon=True)
    stdout_reader = threading.Thread(target=_read_stdout, daemon=True)
    stderr_reader.start()
    stdout_reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        process.wait()
        stderr_reader.join(timeout=5)
        stdout_reader.join(timeout=5)
        return {
            "success": False,
            "exit_code": -1,
            "output": "",
            "error": "Импорт модели в Ollama превысил лимит времени (1 ч).",
            "command": " ".join(cmd),
        }
    stderr_reader.join(timeout=5)
    stdout_reader.join(timeout=5)

    combined = sanitize_terminal_output("".join(stdout_parts) + "".join(stderr_parts))
    code = process.returncode if process.returncode is not None else -1
    return {
        "success": code == 0,
        "exit_code": code,
        "output": combined,
        "error": "" if code == 0 else format_ollama_import_error(combined),
        "command": " ".join(cmd),
    }


def is_ollama_connection_error(message: str) -> bool:
    lowered = (message or "").lower()
    return (
        "11435" in (message or "")
        or "connection refused" in lowered
        or "connectex" in lowered
        or "dial tcp" in lowered
        or "actively refused" in lowered
    )


def format_ollama_import_error(raw: str) -> str:
    if is_ollama_connection_error(raw):
        return (
            "Ollama недоступна на 127.0.0.1:11435 при импорте GGUF. "
            "Нажмите «Скачать» снова — файл уже на диске, повторится только регистрация."
        )
    cleaned = sanitize_terminal_output(raw)
    if is_ollama_connection_error(cleaned):
        return (
            "Ollama недоступна на 127.0.0.1:11435 при импорте GGUF. "
            "Нажмите «Скачать» снова — файл уже на диске, повторится только регистрация."
        )
    for line in reversed(cleaned.splitlines()):
        stripped = line.strip()
        if stripped.lower().startswith("error:"):
            return stripped
    compact = " ".join(cleaned.split())
    if len(compact) > 240:
        return compact[:240] + "…"
    return compact or "Не удалось зарегистрировать модель в Ollama"


async def import_gguf_with_retry(
    model_name: str,
    gguf_path: Path,
    *,
    job_id: str,
) -> dict[str, Any]:
    state = get_pull_progress_state(job_id)
    last_result: dict[str, Any] = {"success": False, "error": "Не удалось импортировать"}

    for attempt in range(3):
        note_ollama_activity()
        ensured = await ensure_ollama_serve_running()
        if not ensured and state is not None:
            state["message"] = "Ollama запускается… повторяем регистрацию"
            state["indeterminate"] = True

        if state is not None and attempt > 0:
            state["message"] = "Повторная регистрация модели в Ollama…"

        result = await import_gguf_to_ollama(model_name, gguf_path, job_id=job_id)
        if result.get("success"):
            return result

        combined = f"{result.get('output') or ''}\n{result.get('error') or ''}"
        last_result = {
            **result,
            "error": format_ollama_import_error(combined),
            "output": format_ollama_import_error(combined),
        }
        if is_ollama_connection_error(combined) and attempt < 2:
            await stop_ollama_serve(reason="manual")
            await asyncio.sleep(1.5)
            continue
        break

    return last_result


async def import_gguf_to_ollama(
    model_name: str,
    gguf_path: Path,
    *,
    job_id: str = "",
) -> dict[str, Any]:
    if not gguf_path.is_file():
        return {"success": False, "error": f"Файл не найден: {gguf_path}"}

    file_size = resolve_file_size(gguf_path)
    state = get_pull_progress_state(job_id) if job_id else None
    if state is not None:
        apply_import_progress_start(state, file_size)

    modelfile_body = f"FROM {gguf_path.resolve().as_posix()}\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".Modelfile",
        delete=False,
        dir=str(gguf_path.parent),
    ) as tmp:
        tmp.write(modelfile_body)
        modelfile_path = Path(tmp.name)

    ollama_bin = resolve_ollama_executable()
    cmd = [ollama_bin, "create", model_name, "-f", str(modelfile_path)]
    env = merge_ollama_runtime_env()

    try:
        return await asyncio.to_thread(
            run_ollama_create_with_progress,
            cmd,
            env=env,
            cwd=str(COREX_ROOT),
            timeout=IMPORT_TIMEOUT_SEC,
            file_size=file_size,
            state=state,
        )
    finally:
        modelfile_path.unlink(missing_ok=True)


def resolve_download_urls(url: str) -> list[str]:
    """Основной URL Hugging Face и зеркало hf-mirror.com."""
    primary = (url or "").strip()
    if not primary:
        return []
    urls = [primary]
    if "huggingface.co" in primary:
        mirror = primary.replace("huggingface.co", "hf-mirror.com", 1)
        if mirror not in urls:
            urls.append(mirror)
    return urls


async def download_model_file(
    url: str,
    dest: Path,
    *,
    job_id: str,
    size_hint: int,
) -> None:
    """Скачать GGUF: curl с докачкой, при ошибке — зеркало или aiohttp."""
    errors: list[str] = []
    for candidate in resolve_download_urls(url):
        if shutil.which("curl"):
            try:
                await _curl_download_to_file(candidate, dest, job_id=job_id, size_hint=size_hint)
                return
            except (asyncio.TimeoutError, OSError, RuntimeError) as exc:
                errors.append(friendly_download_error(exc))

        try:
            await _http_download_to_file(candidate, dest, job_id=job_id, size_hint=size_hint)
            return
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
            errors.append(friendly_download_error(exc))

    detail = errors[-1] if errors else "Не удалось скачать модель"
    raise RuntimeError(detail)


async def download_and_import_direct(
    provider_id: str,
    job_id: str,
    *,
    prepare_pull,
) -> dict[str, Any]:
    begin_ollama_generation()
    try:
        return await _download_and_import_direct_impl(
            provider_id,
            job_id,
            prepare_pull=prepare_pull,
        )
    finally:
        end_ollama_generation()


async def _download_and_import_direct_impl(
    provider_id: str,
    job_id: str,
    *,
    prepare_pull,
) -> dict[str, Any]:
    source = get_direct_source(provider_id)
    if source is None:
        return {"success": False, "error": f"Нет прямой ссылки для {provider_id}"}

    state = get_pull_progress_state(job_id)
    if state is None:
        return {"success": False, "error": "Задача скачивания не инициализирована"}

    prep = await prepare_pull(provider_id, source.model_name)
    if not prep.get("success"):
        mark_pull_error(job_id, str(prep.get("error") or "Подготовка не удалась"))
        return get_pull_progress(job_id) or {"success": False}
    if prep.get("already_installed"):
        apply_pull_event(state, {"status": "success"})
        return {
            "success": True,
            "already_installed": True,
            "model_name": source.model_name,
            "provider_id": provider_id,
            "progress": state,
        }

    dest = resolve_gguf_path(provider_id)

    if not prep.get("file_ready"):
        partial_bytes = int(prep.get("partial_bytes") or 0)
        state["message"] = "Скачивание с Hugging Face…"
        state["status"] = "downloading"
        state["indeterminate"] = False
        state["total_label"] = format_bytes(source.size_hint)
        state["total_bytes"] = source.size_hint
        if partial_bytes > 0:
            apply_http_download_progress(
                state,
                partial_bytes,
                source.size_hint,
                resumed=True,
            )

        try:
            await download_model_file(
                source.url,
                dest,
                job_id=job_id,
                size_hint=source.size_hint,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
            mark_pull_error(job_id, friendly_download_error(exc))
            return get_pull_progress(job_id) or {"success": False}

    file_size = resolve_file_size(dest, source.size_hint)
    apply_import_progress_start(state, file_size)

    import_result = await import_gguf_with_retry(
        source.model_name,
        dest,
        job_id=job_id,
    )
    if not import_result.get("success"):
        mark_pull_error(
            job_id,
            format_ollama_import_error(
                f"{import_result.get('output') or ''}\n{import_result.get('error') or ''}"
            ),
        )
        return get_pull_progress(job_id) or {"success": False}

    apply_pull_event(state, {"status": "success"})
    final = get_pull_progress(job_id) or state
    return {
        "success": True,
        "model_name": source.model_name,
        "provider_id": provider_id,
        "job_id": job_id,
        "download_path": str(dest),
        "progress": final,
    }
