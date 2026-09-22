"""Профиль устройства: VRAM и жёсткий контекст 4096."""

from core.device_profile import LOCAL_NUM_CTX, DeviceProfile, _classify_tier


def test_ollama_num_ctx_is_always_4096():
    profile = DeviceProfile(
        tier="high",
        cpu_cores=8,
        ram_gb=32,
        ram_available_gb=16,
        platform="Windows",
        machine="AMD64",
        recommended_limits={},
        vram_gb=4.0,
    )
    assert profile.ollama_num_ctx() == LOCAL_NUM_CTX == 4096


def test_four_gb_vram_is_low_tier():
    assert _classify_tier(8, 16, 8, vram_gb=4.0) == "low"
    assert _classify_tier(8, 16, 8, vram_gb=8.0) == "high"


def test_hybrid_intel_nvidia_detected_from_adapters(monkeypatch):
    monkeypatch.setattr("core.device_profile._read_vram_gb", lambda: 4.0)
    monkeypatch.setattr(
        "core.device_profile.list_video_adapter_names",
        lambda: ("Intel(R) UHD Graphics 630", "NVIDIA T600"),
    )
    from core.device_profile import is_hybrid_intel_nvidia, intel_igpu_present, nvidia_gpu_present

    assert nvidia_gpu_present() is True
    assert intel_igpu_present() is True
    assert is_hybrid_intel_nvidia() is True


def test_desktop_nvidia_only_is_not_hybrid(monkeypatch):
    monkeypatch.setattr("core.device_profile._read_vram_gb", lambda: 8.0)
    monkeypatch.setattr(
        "core.device_profile.list_video_adapter_names",
        lambda: ("NVIDIA GeForce RTX 3050",),
    )
    from core.device_profile import is_hybrid_intel_nvidia

    assert is_hybrid_intel_nvidia() is False
