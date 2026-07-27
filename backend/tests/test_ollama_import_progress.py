"""TDD: прогресс импорта GGUF в Ollama (ollama create)."""

from __future__ import annotations

import pytest

from core.model_direct_download import (
    parse_ollama_create_progress,
    resolve_file_size,
    run_ollama_create_with_progress,
)
from core.ollama_pull_progress import (
    apply_import_progress_start,
    apply_ollama_import_progress,
    format_bytes,
)

def test_parse_ollama_create_progress_extracts_percent():
  text = (
      "gathering model components\n"
      "copying file sha256:abc123def456 37%\n"
      "copying file sha256:abc123def456 38%"
  )
  assert parse_ollama_create_progress(text) == 38


def test_parse_ollama_create_progress_returns_none_without_copy_line():
  assert parse_ollama_create_progress("gathering model components") is None


def test_apply_import_progress_start_sets_importing_state():
  state: dict = {}
  apply_import_progress_start(state, 4_400_000_000)
  assert state["status"] == "importing"
  assert state["indeterminate"] is True
  assert state["completed_bytes"] == 0
  assert state["total_bytes"] == 4_400_000_000
  assert state["percent"] == 0.0
  assert state["percent_label"] == "0%"
  assert state["total_label"] == format_bytes(4_400_000_000)
  assert "Регистрация" in state["message"]


def test_apply_ollama_import_progress_updates_copy_percent():
  state: dict = {}
  apply_import_progress_start(state, 1_000_000)
  apply_ollama_import_progress(state, 450_000, 1_000_000, percent=45.0)
  assert state["status"] == "importing"
  assert state["indeterminate"] is False
  assert state["completed_bytes"] == 450_000
  assert state["percent"] == 45.0
  assert state["percent_label"] == "45%"
  assert "45%" in state["message"]


def test_resolve_file_size_reads_existing_file(tmp_path):
  gguf = tmp_path / "model.gguf"
  gguf.write_bytes(b"x" * 2048)
  assert resolve_file_size(gguf) == 2048
  assert resolve_file_size(tmp_path / "missing.gguf", fallback=100) == 100


def test_run_ollama_create_with_progress_parses_stderr(monkeypatch):
  state: dict = {}
  apply_import_progress_start(state, 1_000)

  class FakeStream:
    def __init__(self, chunks):
      self._chunks = list(chunks)

    def readline(self):
      if self._chunks:
        return self._chunks.pop(0)
      return ""

  class FakeProcess:
    def __init__(self):
      self.returncode = 0
      self.stderr = FakeStream(
          [
              "gathering model components\n",
              "copying file sha256:abc123 50%\n",
          ]
      )
      self.stdout = FakeStream(["created\n"])

    def wait(self, timeout=None):
      return 0

  monkeypatch.setattr(
      "core.model_direct_download.subprocess.Popen",
      lambda *args, **kwargs: FakeProcess(),
  )

  result = run_ollama_create_with_progress(
      ["ollama", "create", "qwen2.5-coder:7b", "-f", "Modelfile"],
      env={},
      cwd=".",
      timeout=60,
      file_size=1_000,
      state=state,
  )

  assert result["success"] is True
  assert state["percent"] == 50.0
  assert "50%" in state["message"]


@pytest.mark.asyncio
async def test_import_gguf_to_ollama_uses_thread_not_async_subprocess(monkeypatch, tmp_path):
  gguf = tmp_path / "model.gguf"
  gguf.write_bytes(b"g" * 128)

  async def fail_async_subprocess(*args, **kwargs):
    raise NotImplementedError()

  monkeypatch.setattr(
      "core.model_direct_download.asyncio.create_subprocess_exec",
      fail_async_subprocess,
  )
  monkeypatch.setattr(
      "core.model_direct_download.run_ollama_create_with_progress",
      lambda *args, **kwargs: {"success": True, "exit_code": 0, "output": "ok", "error": ""},
  )

  from core.model_direct_download import import_gguf_to_ollama

  result = await import_gguf_to_ollama("qwen2.5-coder:7b", gguf, job_id="")
  assert result["success"] is True
