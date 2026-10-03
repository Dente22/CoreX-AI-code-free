"""OmniRoute gateway: detection, auto-start and setup guide (no real OmniRoute)."""

import socket

from core import omniroute_service as omni
from core import online_api_client
from core.online_api_client import OnlineApiClient
from core.omniroute_service import (
    ensure_omniroute,
    is_omniroute_url,
    omniroute_root,
    omniroute_setup_guide,
    probe_omniroute,
)

LOCAL = "http://127.0.0.1:20128/v1"


def _probe_sequence(monkeypatch, results):
    calls = iter(results)

    async def fake_probe(base_url, timeout_sec=2.0):
        return next(calls, results[-1])

    monkeypatch.setattr(omni, "probe_omniroute", fake_probe)


def test_detects_omniroute_by_port_host_or_name():
    assert is_omniroute_url(LOCAL)
    assert is_omniroute_url("https://omniroute.example.com/v1")
    assert is_omniroute_url("http://10.0.0.5:9000/v1", "OmniRoute (локальный шлюз)")
    assert not is_omniroute_url("https://openrouter.ai/api/v1", "OpenRouter")


def test_root_and_guide_follow_custom_port():
    assert omniroute_root("http://127.0.0.1:20200/v1") == "http://127.0.0.1:20200"
    guide = omniroute_setup_guide("http://127.0.0.1:20200/v1")
    assert "omniroute serve --daemon --no-open --port 20200" in guide
    assert "npm install -g omniroute" in guide
    assert "http://127.0.0.1:20200/v1" in guide


async def test_probe_reports_closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert await probe_omniroute(f"http://127.0.0.1:{port}/v1", timeout_sec=1.0) is False


async def test_running_gateway_is_not_restarted(monkeypatch):
    _probe_sequence(monkeypatch, [True])
    monkeypatch.setattr(omni, "start_omniroute", lambda *a: (_ for _ in ()).throw(AssertionError))
    status = await ensure_omniroute(LOCAL)
    assert status.ok and not status.started


async def test_remote_gateway_is_never_autostarted(monkeypatch):
    _probe_sequence(monkeypatch, [False])
    monkeypatch.setattr(omni, "start_omniroute", lambda *a: (_ for _ in ()).throw(AssertionError))
    status = await ensure_omniroute("https://omniroute.example.com/v1")
    assert not status.ok
    assert "Как подключить" in status.message


async def test_missing_command_returns_install_guide(monkeypatch):
    _probe_sequence(monkeypatch, [False])
    monkeypatch.setattr(omni, "find_omniroute_command", lambda: None)
    status = await ensure_omniroute(LOCAL)
    assert not status.ok
    assert "не найдена" in status.message
    assert "npm install -g omniroute" in status.message


async def test_autostart_waits_until_gateway_answers(monkeypatch):
    _probe_sequence(monkeypatch, [False, False, False, True])
    started = []
    monkeypatch.setattr(omni, "find_omniroute_command", lambda: ["omniroute"])
    monkeypatch.setattr(omni, "start_omniroute", lambda cmd, port: started.append((cmd, port)))
    monkeypatch.setattr(omni.asyncio, "sleep", _no_sleep)
    status = await ensure_omniroute(LOCAL, wait_sec=30)
    assert status.ok and status.started
    assert started == [(["omniroute"], 20128)]
    assert "запущен автоматически" in status.message


async def test_autostart_timeout_returns_guide(monkeypatch):
    _probe_sequence(monkeypatch, [False])
    monkeypatch.setattr(omni, "find_omniroute_command", lambda: ["omniroute"])
    monkeypatch.setattr(omni, "start_omniroute", lambda cmd, port: None)
    status = await ensure_omniroute(LOCAL, wait_sec=0)
    assert not status.ok
    assert "не ответил" in status.message


async def test_online_client_blocks_generation_when_gateway_down(monkeypatch):
    async def fake_ensure(base_url, **kwargs):
        return omni.OmniRouteStatus(ok=False, message="guide")

    monkeypatch.setattr(online_api_client, "ensure_omniroute", fake_ensure)
    client = OnlineApiClient(model_name="claude-free", base_url=LOCAL, api_key="sk-x")
    assert await client.ensure_ready() is False
    assert client.last_error == "guide"

    other = OnlineApiClient(model_name="m", base_url="https://api.groq.com/openai/v1", api_key="k")
    assert await other.ensure_ready() is True


async def _no_sleep(_seconds):
    return None
