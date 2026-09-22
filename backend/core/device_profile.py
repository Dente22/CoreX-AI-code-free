"""Профиль устройства и адаптивные лимиты нагрузки."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

Tier = Literal["low", "medium", "high"]

_LIMITS_BY_TIER: dict[Tier, dict[str, int]] = {
    "low": {
        "max_total_turns": 14,
        "max_turns_per_step": 6,
        "max_file_writes": 8,
        "delay_between_turns_ms": 900,
        "delay_between_steps_ms": 3500,
    },
    "medium": {
        "max_total_turns": 28,
        "max_turns_per_step": 10,
        "max_file_writes": 14,
        "delay_between_turns_ms": 500,
        "delay_between_steps_ms": 2000,
    },
    "high": {
        "max_total_turns": 48,
        "max_turns_per_step": 16,
        "max_file_writes": 24,
        "delay_between_turns_ms": 300,
        "delay_between_steps_ms": 1200,
    },
}


LOCAL_NUM_CTX = 4096
LOW_VRAM_GB = 4.5


@dataclass(frozen=True)
class DeviceProfile:
    tier: Tier
    cpu_cores: int
    ram_gb: float
    ram_available_gb: float
    platform: str
    machine: str
    recommended_limits: dict[str, int]
    vram_gb: float | None = None

    def summary_ru(self) -> str:
        vram = f", VRAM {self.vram_gb:.1f} ГБ" if self.vram_gb is not None else ""
        return (
            f"Устройство: {self.tier} ({self.cpu_cores} ядер, "
            f"RAM {self.ram_gb:.1f} ГБ, доступно {self.ram_available_gb:.1f} ГБ{vram})"
        )

    def limits_summary_ru(self) -> str:
        limits = self.recommended_limits
        return (
            f"Лимиты: ходы {limits['max_total_turns']}, "
            f"на этап {limits['max_turns_per_step']}, "
            f"записи {limits['max_file_writes']}"
        )

    def ollama_num_ctx(self) -> int:
        """Жёсткий потолок локального контекста (T600 4GB / qwen2.5-coder:3b)."""
        return LOCAL_NUM_CTX


def _read_ram_windows() -> tuple[float, float]:
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        return 8.0, 4.0
    total = stat.ullTotalPhys / (1024**3)
    avail = stat.ullAvailPhys / (1024**3)
    return total, avail


def _read_ram_posix() -> tuple[float, float]:
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            total = int(out) / (1024**3)
            return total, total * 0.5

        with open("/proc/meminfo", encoding="utf-8") as handle:
            total_kb = 0
            avail_kb = 0
            for line in handle:
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
            if total_kb:
                return total_kb / (1024**2), avail_kb / (1024**2) if avail_kb else total_kb / (2048**2)
    except OSError:
        pass
    return 8.0, 4.0


def _read_ram() -> tuple[float, float]:
    if sys.platform == "win32":
        return _read_ram_windows()
    return _read_ram_posix()


def _read_vram_gb() -> float | None:
    """Минимальный объём видеопамяти NVIDIA в гигабайтах, если nvidia-smi доступен."""
    kwargs: dict = {
        "timeout": 2,
        "text": True,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            **kwargs,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    values: list[float] = []
    for line in out.splitlines():
        token = (line or "").strip().split()[0] if line.strip() else ""
        try:
            values.append(float(token))
        except ValueError:
            continue
    if not values:
        return None
    return round(min(values) / 1024.0, 2)


def _read_video_adapter_names() -> tuple[str, ...]:
    if sys.platform != "win32":
        return ()
    kwargs: dict = {
        "timeout": 4,
        "text": True,
        "stderr": subprocess.DEVNULL,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    try:
        out = subprocess.check_output(
            ["wmic", "path", "win32_VideoController", "get", "Name"],
            **kwargs,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    names: list[str] = []
    for line in out.splitlines():
        token = (line or "").strip()
        if not token or token.lower() == "name":
            continue
        names.append(token)
    return tuple(names)


@lru_cache(maxsize=1)
def list_video_adapter_names() -> tuple[str, ...]:
    return _read_video_adapter_names()


def nvidia_gpu_present() -> bool:
    if _read_vram_gb() is not None:
        return True
    return any("nvidia" in name.lower() for name in list_video_adapter_names())


def intel_igpu_present() -> bool:
    return any("intel" in name.lower() for name in list_video_adapter_names())


def is_hybrid_intel_nvidia() -> bool:
    """Intel UHD/Iris + NVIDIA: Ollama Vulkan часто сажает модель на Intel."""
    return nvidia_gpu_present() and intel_igpu_present()


def _classify_tier(
    cpu_cores: int,
    ram_gb: float,
    ram_available_gb: float,
    vram_gb: float | None = None,
) -> Tier:
    if vram_gb is not None and vram_gb <= LOW_VRAM_GB:
        return "low"
    if ram_gb < 8 or cpu_cores <= 2 or ram_available_gb < 2:
        return "low"
    if ram_gb >= 16 and cpu_cores >= 8 and ram_available_gb >= 6:
        return "high"
    if ram_gb >= 12 and cpu_cores >= 4:
        return "medium"
    return "medium" if ram_gb >= 8 else "low"


@lru_cache(maxsize=1)
def detect_device_profile() -> DeviceProfile:
    cpu_cores = max(1, os.cpu_count() or 4)
    ram_gb, ram_available_gb = _read_ram()
    vram_gb = _read_vram_gb()
    tier = _classify_tier(cpu_cores, ram_gb, ram_available_gb, vram_gb)
    from core.workload_limits_service import resolve_workload_limits

    limits = resolve_workload_limits(None, tier=tier)

    return DeviceProfile(
        tier=tier,
        cpu_cores=cpu_cores,
        ram_gb=round(ram_gb, 2),
        ram_available_gb=round(ram_available_gb, 2),
        platform=platform.system(),
        machine=platform.machine(),
        recommended_limits=limits,
        vram_gb=vram_gb,
    )


def resolve_limits(custom: dict | None = None, app_root: Path | None = None) -> dict[str, int]:
    """Лимиты по железу, ползунку настроек и опциональным лимитам pipeline."""
    from core.workload_limits_service import resolve_workload_limits

    profile = detect_device_profile()
    return resolve_workload_limits(app_root, tier=profile.tier, pipeline_limits=custom)


def profile_to_dict(app_root: Path | None = None) -> dict:
    from core.workload_limits_service import get_workload_settings, workload_limits_summary_ru

    profile = detect_device_profile()
    workload = get_workload_settings(app_root, tier=profile.tier)
    payload = {
        "tier": profile.tier,
        "cpu_cores": profile.cpu_cores,
        "ram_gb": profile.ram_gb,
        "ram_available_gb": profile.ram_available_gb,
        "vram_gb": profile.vram_gb,
        "platform": profile.platform,
        "machine": profile.machine,
        "limits": workload["limits"],
        "workload": workload,
        "summary": profile.summary_ru(),
        "limits_summary": workload_limits_summary_ru(workload),
    }
    from core.gpu_preference import gpu_snapshot

    payload.update(gpu_snapshot())
    from core.ollama_lifecycle import is_using_desktop_ollama
    from core.web_access import web_access_snapshot

    payload["ollama_using_desktop"] = is_using_desktop_ollama()
    payload["web_access"] = web_access_snapshot()
    return payload
