"""Тесты прогресса скачивания Ollama."""

from core.ollama_pull_progress import (
    apply_pull_event,
    format_bytes,
    init_pull_progress,
)


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(5 * 1024 * 1024 * 1024) == "5.0 GB"


def test_apply_pull_event_downloading_updates_totals():
    state = init_pull_progress("job", "phi3:mini", "ollama-lite")
    apply_pull_event(
        state,
        {
            "status": "downloading",
            "digest": "sha256:abc",
            "total": 1000,
            "completed": 250,
        },
    )
    assert state["completed_bytes"] == 250
    assert state["total_bytes"] == 1000
    assert state["percent"] == 25.0
    assert state["percent_label"] == "25%"
    assert state["indeterminate"] is False


def test_apply_pull_event_aggregates_layers():
    state = init_pull_progress("job", "phi3:mini")
    apply_pull_event(
        state,
        {"status": "downloading", "digest": "a", "total": 100, "completed": 100},
    )
    apply_pull_event(
        state,
        {"status": "downloading", "digest": "b", "total": 100, "completed": 50},
    )
    assert state["completed_bytes"] == 150
    assert state["total_bytes"] == 200
    assert state["percent"] == 75.0


def test_apply_pull_event_success_marks_done():
    state = init_pull_progress("job", "phi3:mini")
    state["total_bytes"] = 500
    apply_pull_event(state, {"status": "success"})
    assert state["done"] is True
    assert state["success"] is True
    assert state["percent"] == 100.0


def test_get_pull_job_progress_keeps_found_while_running():
    from core.ollama_model_service import get_pull_job_progress

    state = init_pull_progress("ollama-lite", "phi3:mini", "ollama-lite")
    state["success"] = False
    state["done"] = False
    result = get_pull_job_progress("ollama-lite")
    assert result["found"] is True
    assert result["done"] is False
    assert result["success"] is False


def test_mark_pull_error_network_message_is_friendly():
    from core.ollama_pull_progress import mark_pull_error

    state = mark_pull_error("job", "wsarecv: connection forcibly closed")
    assert "интернет" in state["error"].lower() or "vpn" in state["error"].lower()


def test_friendly_pull_error_manifest():
    from core.ollama_pull_progress import friendly_pull_error

    msg = friendly_pull_error('pull model manifest: Get "https://registry.ollama.ai/..."')
    assert "ollama" in msg.lower() or "интернет" in msg.lower()


def test_format_eta():
    from core.ollama_pull_progress import format_eta

    assert "30" in format_eta(30)
    assert "мин" in format_eta(125)
