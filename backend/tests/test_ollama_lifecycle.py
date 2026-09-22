"""TDD: спячка Ollama и обнаружение моделей без запуска сервера."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ollama_lifecycle import (
    IDLE_SLEEP_SEC,
    begin_ollama_generation,
    detect_installed_models_from_disk,
    end_ollama_generation,
    merge_ollama_runtime_env,
    note_ollama_activity,
    reset_ollama_lifecycle_state,
    seconds_until_idle_sleep,
    should_sleep_ollama,
)


@pytest.fixture(autouse=True)
def _reset_lifecycle(monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.should_skip_desktop_ollama", lambda: False)
    reset_ollama_lifecycle_state()
    yield
    reset_ollama_lifecycle_state()


def test_merge_ollama_runtime_env_sets_low_memory_flags(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.gpu_preference.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.gpu_preference._nvidia_gpus", lambda: [])
    monkeypatch.setattr("core.device_profile.list_video_adapter_names", lambda: ())
    monkeypatch.setattr("core.gpu_preference.get_saved_gpu_id", lambda: "")
    env = merge_ollama_runtime_env({"PATH": "/bin"})
    assert env["PATH"] == "/bin"
    assert env["OLLAMA_KEEP_ALIVE"] == "10m"
    assert env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert "11435" in env["OLLAMA_HOST"]
    assert env["OLLAMA_VULKAN"] == "0"
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"


def test_merge_ollama_runtime_env_disables_vulkan_on_nvidia(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.gpu_preference.COREX_ROOT", tmp_path)
    monkeypatch.setattr(
        "core.gpu_preference._nvidia_gpus",
        lambda: [
            {
                "id": "nvidia:0",
                "name": "NVIDIA T600",
                "kind": "nvidia",
                "index": 0,
                "vram_gb": 4.0,
            }
        ],
    )
    monkeypatch.setattr(
        "core.device_profile.list_video_adapter_names",
        lambda: ("NVIDIA T600",),
    )
    monkeypatch.setattr("core.gpu_preference.get_saved_gpu_id", lambda: "")
    monkeypatch.setattr("core.gpu_preference.detect_ollama_cuda_library", lambda: "cuda_v12")
    monkeypatch.setattr("core.gpu_preference.pin_windows_high_performance_gpu", lambda: None)
    env = merge_ollama_runtime_env({"PATH": "/bin"})
    assert env["OLLAMA_VULKAN"] == "0"
    assert "CUDA_VISIBLE_DEVICES" not in env
    assert "GGML_VK_VISIBLE_DEVICES" not in env


def test_detect_installed_models_from_disk_reads_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.COREX_ROOT", tmp_path)
    manifests = (
        tmp_path
        / "ollama_models"
        / "manifests"
        / "registry.ollama.ai"
        / "library"
        / "llama3.1"
    )
    manifests.mkdir(parents=True)
    (manifests / "8b").write_text("{}", encoding="utf-8")
    (manifests / "latest").write_text("{}", encoding="utf-8")

    models = detect_installed_models_from_disk()
    names = {m["name"] for m in models}
    assert "llama3.1:8b" in names
    assert "llama3.1:latest" in names


def test_should_sleep_ollama_after_idle_without_pull():
    note_ollama_activity()
    with patch("core.ollama_lifecycle.is_any_pull_active", return_value=False):
        assert should_sleep_ollama(now=time.monotonic() + IDLE_SLEEP_SEC + 1) is True


def test_should_not_sleep_ollama_while_generation_active():
    note_ollama_activity()
    begin_ollama_generation()
    with patch("core.ollama_lifecycle.is_any_pull_active", return_value=False):
        assert should_sleep_ollama(now=time.monotonic() + IDLE_SLEEP_SEC + 60) is False
    end_ollama_generation()


def test_should_not_sleep_ollama_while_pull_active():
    note_ollama_activity()
    with patch("core.ollama_lifecycle.is_any_pull_active", return_value=True):
        assert should_sleep_ollama(now=time.monotonic() + IDLE_SLEEP_SEC + 60) is False


def test_seconds_until_idle_sleep_counts_down():
    now = time.monotonic()
    note_ollama_activity()
    remaining = seconds_until_idle_sleep(now=now + 10)
    assert IDLE_SLEEP_SEC - 11 <= remaining <= IDLE_SLEEP_SEC - 9


@pytest.mark.asyncio
async def test_list_installed_models_does_not_start_ollama_when_sleeping(monkeypatch):
    monkeypatch.setattr("core.ollama_model_service.COREX_ROOT", MagicMock())
    monkeypatch.setattr(
        "core.ollama_lifecycle.attach_if_already_running",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "core.ollama_model_service._is_server_running",
        AsyncMock(return_value=False),
    )
    ensure = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_model_service.ensure_corex_ollama_running", ensure)
    monkeypatch.setattr(
        "core.ollama_model_service.detect_installed_models_from_disk",
        lambda: [{"name": "phi3:mini"}],
    )

    from core.ollama_model_service import list_installed_models

    result = await list_installed_models(start_if_down=False)
    ensure.assert_not_called()
    assert result["models"] == [{"name": "phi3:mini"}]
    assert result.get("ollama_state") == "sleeping"


@pytest.mark.asyncio
async def test_stop_ollama_serve_terminates_tracked_process(monkeypatch):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 4242

    from core import ollama_lifecycle

    ollama_lifecycle._serve_process = proc
    ollama_lifecycle._we_started_process = True

    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(return_value=False),
    )

    from core.ollama_lifecycle import stop_ollama_serve

    stopped = await stop_ollama_serve()
    assert stopped is True
    proc.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_stop_ollama_idle_does_not_kill_unmanaged_listener(monkeypatch):
    from core import ollama_lifecycle
    from core.ollama_lifecycle import stop_ollama_serve

    ollama_lifecycle._serve_process = None
    ollama_lifecycle._we_started_process = False

    monkeypatch.setattr("core.ollama_lifecycle._is_server_running", AsyncMock(return_value=True))
    monkeypatch.setattr("core.ollama_lifecycle._find_listener_pid", lambda _port: 9999)
    terminate = MagicMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle._terminate_pid", terminate)
    monkeypatch.setattr("core.ollama_lifecycle.cleanup_zombie_llama_workers", AsyncMock(return_value=False))

    stopped = await stop_ollama_serve(reason="idle")

    assert stopped is False
    terminate.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_ollama_serve_starts_watchdog(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_desktop_ollama_running",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(side_effect=[False, True]),
    )
    popen = MagicMock()
    popen.poll.return_value = None
    monkeypatch.setattr("core.ollama_lifecycle.subprocess.Popen", MagicMock(return_value=popen))

    import core.ollama_lifecycle as lifecycle

    ok = await lifecycle.ensure_ollama_serve_running()
    assert ok is True
    assert lifecycle._watchdog_task is not None


@pytest.mark.asyncio
async def test_ensure_uses_desktop_ollama_when_11434_is_up(monkeypatch):
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_desktop_ollama_running",
        AsyncMock(return_value=True),
    )
    popen = MagicMock()
    monkeypatch.setattr("core.ollama_lifecycle.subprocess.Popen", popen)
    monkeypatch.setattr("core.ollama_lifecycle._find_listener_pid", lambda _port: None)

    import core.ollama_lifecycle as lifecycle

    ok = await lifecycle.ensure_ollama_serve_running()
    assert ok is True
    assert lifecycle.is_using_desktop_ollama() is True
    assert "11434" in lifecycle.resolve_ollama_base_url()
    assert lifecycle.get_ollama_state() == "running"
    popen.assert_not_called()


@pytest.mark.asyncio
async def test_attach_skips_desktop_on_hybrid(monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.should_skip_desktop_ollama", lambda: True)
    desktop = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle._is_desktop_ollama_running", desktop)
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(return_value=False),
    )

    from core.ollama_lifecycle import attach_if_already_running

    ok = await attach_if_already_running()
    assert ok is False
    desktop.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_starts_managed_cuda_on_hybrid_even_if_desktop_up(monkeypatch):
    monkeypatch.setattr("core.ollama_lifecycle.should_skip_desktop_ollama", lambda: True)
    monkeypatch.setattr("core.device_profile.nvidia_gpu_present", lambda: True)

    def fake_apply(env, gpu_id=None):
        env["OLLAMA_VULKAN"] = "0"
        env["GGML_VK_VISIBLE_DEVICES"] = "-1"
        env["CUDA_VISIBLE_DEVICES"] = "0"
        return env

    monkeypatch.setattr("core.gpu_preference.apply_gpu_env", fake_apply)
    evict = AsyncMock()
    monkeypatch.setattr("core.ollama_lifecycle._evict_desktop_ollama", evict)
    monkeypatch.setattr(
        "core.ollama_lifecycle.cleanup_zombie_llama_workers",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "core.ollama_lifecycle._is_server_running",
        AsyncMock(side_effect=[False, False, True]),
    )
    popen_proc = MagicMock()
    popen_proc.poll.return_value = None
    popen = MagicMock(return_value=popen_proc)
    monkeypatch.setattr("core.ollama_lifecycle.subprocess.Popen", popen)
    monkeypatch.setattr("core.ollama_lifecycle.STARTUP_WAIT_SEC", 0)
    monkeypatch.setattr("core.ollama_lifecycle.STARTUP_WAIT_ROUNDS", 1)

    from core.ollama_lifecycle import ensure_ollama_serve_running, is_using_desktop_ollama

    ok = await ensure_ollama_serve_running()
    assert ok is True
    assert is_using_desktop_ollama() is False
    evict.assert_awaited_once()
    popen.assert_called_once()
    env = popen.call_args.kwargs["env"]
    assert env["OLLAMA_VULKAN"] == "0"
    assert "11435" in env["OLLAMA_HOST"]


@pytest.mark.asyncio
async def test_restart_managed_clears_desktop_flag_then_starts(monkeypatch):
    import core.ollama_lifecycle as lifecycle

    lifecycle._using_desktop = True
    stop = AsyncMock(return_value=True)
    ensure = AsyncMock(return_value=True)
    monkeypatch.setattr("core.ollama_lifecycle.stop_ollama_serve", stop)
    monkeypatch.setattr("core.ollama_lifecycle.ensure_ollama_serve_running", ensure)

    ok = await lifecycle.restart_managed_ollama_serve()
    assert ok is True
    assert lifecycle._using_desktop is False
    stop.assert_awaited_once()
    ensure.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_installed_models_attaches_to_desktop_before_listing(monkeypatch):
    async def fake_attach():
        import core.ollama_lifecycle as lifecycle

        lifecycle._attach_endpoint(lifecycle.DESKTOP_OLLAMA_BASE_URL, desktop=True)
        return True

    attach = AsyncMock(side_effect=fake_attach)
    monkeypatch.setattr("core.ollama_lifecycle.attach_if_already_running", attach)
    monkeypatch.setattr(
        "core.ollama_model_service._is_server_running",
        AsyncMock(return_value=True),
    )

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self):
            return {"models": [{"name": "qwen2.5-coder:3b"}]}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url):
            assert url.startswith("http://127.0.0.1:11434")
            return FakeResponse()

    monkeypatch.setattr("core.ollama_model_service.aiohttp.ClientSession", FakeSession)

    from core.ollama_model_service import list_installed_models

    result = await list_installed_models(start_if_down=False)
    attach.assert_awaited_once()
    assert result["success"] is True
    assert result["models"] == [{"name": "qwen2.5-coder:3b"}]
    assert "11434" in result["base_url"]
    assert result["ollama_state"] == "running"


def test_bind_client_retargets_stale_11435():
    import core.ollama_lifecycle as lifecycle

    lifecycle._attach_endpoint(lifecycle.DESKTOP_OLLAMA_BASE_URL, desktop=True)
    client = MagicMock()
    live = lifecycle.bind_client_to_live_endpoint(client)
    assert live == "http://127.0.0.1:11434"
    assert client.root_url == "http://127.0.0.1:11434"
    assert client.chat_url == "http://127.0.0.1:11434/api/chat"


@pytest.mark.asyncio
async def test_stop_ollama_does_not_kill_desktop_app(monkeypatch):
    import core.ollama_lifecycle as lifecycle
    from core.ollama_lifecycle import stop_ollama_serve

    lifecycle._attach_endpoint(lifecycle.DESKTOP_OLLAMA_BASE_URL, desktop=True)
    terminate = MagicMock()
    monkeypatch.setattr("core.ollama_lifecycle._terminate_pid", terminate)

    stopped = await stop_ollama_serve(reason="manual")
    assert stopped is False
    terminate.assert_not_called()
