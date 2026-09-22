from pathlib import Path

from core.gpu_preference import (
    apply_gpu_env,
    list_gpus,
    physical_gpu_count,
    recommended_gpu_id,
    set_selected_gpu_id,
    should_isolate_ollama_serve,
)


def _nvidia_t600():
    return [
        {
            "id": "nvidia:0",
            "name": "NVIDIA T600",
            "kind": "nvidia",
            "index": 0,
            "vram_gb": 4.0,
        }
    ]


def _patch_hybrid(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.gpu_preference.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.gpu_preference._nvidia_gpus", _nvidia_t600)
    monkeypatch.setattr(
        "core.device_profile.list_video_adapter_names",
        lambda: ("Intel(R) UHD Graphics 630", "NVIDIA T600"),
    )
    monkeypatch.setattr("core.device_profile.nvidia_gpu_present", lambda: True)
    monkeypatch.setattr("core.device_profile.intel_igpu_present", lambda: True)
    monkeypatch.setattr("core.device_profile.is_hybrid_intel_nvidia", lambda: True)
    monkeypatch.setattr("core.gpu_preference.detect_ollama_cuda_library", lambda: "cuda_v12")
    monkeypatch.setattr("core.gpu_preference.pin_windows_high_performance_gpu", lambda: None)


def test_hybrid_recommends_nvidia_and_isolates(monkeypatch, tmp_path: Path):
    _patch_hybrid(monkeypatch, tmp_path)
    devices = list_gpus()
    assert recommended_gpu_id(devices) == "nvidia:0"
    assert physical_gpu_count(devices) == 2
    assert should_isolate_ollama_serve() is True
    nvidia = next(item for item in devices if item["id"] == "nvidia:0")
    assert nvidia["selected"] is True
    assert nvidia["recommended"] is True
    env = apply_gpu_env({"PATH": "/bin", "CUDA_VISIBLE_DEVICES": "0", "HIP_VISIBLE_DEVICES": "-1"})
    assert env["OLLAMA_VULKAN"] == "0"
    assert "CUDA_VISIBLE_DEVICES" not in env
    assert "HIP_VISIBLE_DEVICES" not in env
    assert "GGML_VK_VISIBLE_DEVICES" not in env
    assert "OLLAMA_LLM_LIBRARY" not in env


def test_persist_intel_choice_enables_vulkan(monkeypatch, tmp_path: Path):
    _patch_hybrid(monkeypatch, tmp_path)
    result = set_selected_gpu_id("intel:0")
    assert result["gpu_id"] == "intel:0"
    env = apply_gpu_env({})
    assert env["OLLAMA_VULKAN"] == "1"
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"
    assert env["GGML_VK_VISIBLE_DEVICES"] == "0"


def test_cpu_choice_hides_gpus(monkeypatch, tmp_path: Path):
    _patch_hybrid(monkeypatch, tmp_path)
    set_selected_gpu_id("cpu")
    env = apply_gpu_env({})
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"
    assert env["OLLAMA_VULKAN"] == "0"


def test_invalid_id_falls_back_to_nvidia(monkeypatch, tmp_path: Path):
    _patch_hybrid(monkeypatch, tmp_path)
    result = set_selected_gpu_id("nope")
    assert result["gpu_id"] == "nvidia:0"


def test_persist_recommended_gpu_on_hybrid(monkeypatch, tmp_path: Path):
    _patch_hybrid(monkeypatch, tmp_path)
    from core.gpu_preference import get_saved_gpu_id, persist_recommended_gpu_if_needed

    persist_recommended_gpu_if_needed()
    assert get_saved_gpu_id() == "nvidia:0"


def test_single_nvidia_does_not_isolate(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("core.gpu_preference.COREX_ROOT", tmp_path)
    monkeypatch.setattr("core.gpu_preference._nvidia_gpus", _nvidia_t600)
    monkeypatch.setattr(
        "core.device_profile.list_video_adapter_names",
        lambda: ("NVIDIA GeForce RTX 3050",),
    )
    monkeypatch.setattr("core.device_profile.is_hybrid_intel_nvidia", lambda: False)
    devices = list_gpus()
    assert physical_gpu_count(devices) == 1
    assert should_isolate_ollama_serve() is False
