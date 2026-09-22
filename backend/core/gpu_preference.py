"""Выбор GPU для локальной Ollama, если карт несколько."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.core_x_library import COREX_ROOT

CONFIG_FILENAME = "gpu_preference.json"
CPU_GPU_ID = "cpu"


def _config_path() -> Path:
    return Path(COREX_ROOT) / "chat" / CONFIG_FILENAME


def _run_hidden(argv: list[str], *, timeout: int = 6) -> str:
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "text": True,
        "capture_output": True,
        "check": False,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(argv, **kwargs)
    except (OSError, subprocess.SubprocessError, ValueError, TimeoutError):
        return ""
    return completed.stdout or ""


def _nvidia_gpus() -> list[dict[str, Any]]:
    out = _run_hidden(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total",
            "--format=csv,noheader,nounits",
        ],
        timeout=4,
    )
    if not out.strip():
        return []
    devices: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = [part.strip() for part in (line or "").split(",")]
        if len(parts) < 2:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        name = parts[1] or f"NVIDIA GPU {index}"
        vram_gb = None
        if len(parts) >= 3:
            token = parts[2].split()[0] if parts[2] else ""
            try:
                vram_gb = round(float(token) / 1024.0, 2)
            except ValueError:
                vram_gb = None
        devices.append(
            {
                "id": f"nvidia:{index}",
                "name": name,
                "kind": "nvidia",
                "index": index,
                "vram_gb": vram_gb,
            }
        )
    return devices


def _short_label(name: str, kind: str) -> str:
    cleaned = (
        name.replace("(R)", "")
        .replace("(TM)", "")
        .replace("  ", " ")
        .strip()
    )
    if kind == "cpu":
        return "CPU"
    if kind == "nvidia":
        stripped = cleaned.replace("NVIDIA", "", 1).strip()
        return stripped or cleaned
    return cleaned


def _adapter_gpus(skip_names: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from core.device_profile import list_video_adapter_names

    nvidia_fallback: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for index, name in enumerate(list_video_adapter_names()):
        lowered = name.lower()
        if "basic display" in lowered or "basic render" in lowered:
            continue
        if any(skip and skip in lowered for skip in skip_names):
            continue
        if "nvidia" in lowered:
            nvidia_index = len(nvidia_fallback)
            nvidia_fallback.append(
                {
                    "id": f"nvidia:{nvidia_index}",
                    "name": name,
                    "kind": "nvidia",
                    "index": nvidia_index,
                    "vram_gb": None,
                }
            )
            continue
        kind = "intel" if "intel" in lowered else "other"
        others.append(
            {
                "id": f"{kind}:{index}",
                "name": name,
                "kind": kind,
                "index": index,
                "vram_gb": None,
            }
        )
    return nvidia_fallback, others


def list_gpus() -> list[dict[str, Any]]:
    nvidia = _nvidia_gpus()
    skip = {item["name"].lower() for item in nvidia}
    nvidia_fallback, adapters = _adapter_gpus(skip)
    if not nvidia:
        nvidia = nvidia_fallback
    cpu = [
        {
            "id": CPU_GPU_ID,
            "name": "Только процессор (CPU)",
            "kind": "cpu",
            "index": None,
            "vram_gb": None,
        }
    ]
    devices = nvidia + adapters + cpu
    recommended = recommended_gpu_id(devices)
    selected = resolve_selected_gpu_id(devices)
    for item in devices:
        item["label"] = _short_label(str(item["name"]), str(item["kind"]))
        item["recommended"] = item["id"] == recommended
        item["selected"] = item["id"] == selected
    return devices


def physical_gpu_count(devices: list[dict[str, Any]] | None = None) -> int:
    rows = devices if devices is not None else list_gpus()
    return sum(1 for item in rows if item.get("kind") != "cpu")


def recommended_gpu_id(devices: list[dict[str, Any]] | None = None) -> str:
    rows = devices if devices is not None else list_gpus()
    for item in rows:
        if item.get("kind") == "nvidia":
            return str(item["id"])
    for item in rows:
        if item.get("kind") != "cpu":
            return str(item["id"])
    return CPU_GPU_ID


def get_saved_gpu_id() -> str:
    path = _config_path()
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("gpu_id") or "").strip()


def resolve_selected_gpu_id(devices: list[dict[str, Any]] | None = None) -> str:
    rows = devices if devices is not None else list_gpus()
    allowed = {str(item["id"]) for item in rows}
    saved = get_saved_gpu_id()
    if saved in allowed:
        return saved
    return recommended_gpu_id(rows)


def set_selected_gpu_id(gpu_id: str) -> dict[str, Any]:
    devices = list_gpus()
    allowed = {str(item["id"]) for item in devices}
    chosen = (gpu_id or "").strip()
    if chosen not in allowed:
        chosen = recommended_gpu_id(devices)
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"gpu_id": chosen}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    snapshot = gpu_snapshot()
    snapshot["success"] = True
    snapshot["gpu_id"] = chosen
    return snapshot


def should_isolate_ollama_serve() -> bool:
    """Свой serve на 11435, если карт несколько — desktop Ollama на 11434 не видит CUDA_VISIBLE_DEVICES."""
    from core.device_profile import is_hybrid_intel_nvidia

    return physical_gpu_count() >= 2 or is_hybrid_intel_nvidia()


def persist_recommended_gpu_if_needed() -> None:
    """На гибриде сразу запомнить NVIDIA, чтобы следующий запуск не шёл в Intel."""
    if get_saved_gpu_id():
        return
    nvidia = _nvidia_gpus()
    skip = {item["name"].lower() for item in nvidia}
    fallback, adapters = _adapter_gpus(skip)
    physical = (nvidia or fallback) + adapters
    if len(physical) < 2:
        from core.device_profile import is_hybrid_intel_nvidia

        if not is_hybrid_intel_nvidia():
            return
    rec = recommended_gpu_id(physical + [{"id": CPU_GPU_ID, "kind": "cpu", "name": "CPU"}])
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"gpu_id": rec}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def detect_ollama_cuda_library() -> str:
    """T600 (Turing) стабильнее на cuda_v12; v13 тоже есть в Ollama 0.33."""
    from core.ollama_lifecycle import resolve_ollama_executable

    exe = Path(resolve_ollama_executable())
    roots = [exe.parent / "lib" / "ollama", exe.parent / "lib"]
    found: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and child.name.lower().startswith("cuda_v"):
                found.append(child.name)
    lowered = {name.lower(): name for name in found}
    for preferred in ("cuda_v12", "cuda_v13", "cuda_v11"):
        if preferred in lowered:
            return lowered[preferred]
    return found[0] if found else ""


def pin_windows_high_performance_gpu() -> None:
    """Windows Graphics: ollama.exe → высокопроизводительный GPU (NVIDIA)."""
    if sys.platform != "win32":
        return
    from core.ollama_lifecycle import resolve_ollama_executable

    exe = Path(resolve_ollama_executable())
    paths = [str(exe)]
    app = exe.with_name("ollama app.exe")
    if app.is_file():
        paths.append(str(app))
    try:
        import winreg
    except ImportError:
        return
    try:
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\DirectX\UserGpuPreferences",
        )
        for path in paths:
            winreg.SetValueEx(key, path, 0, winreg.REG_SZ, "GpuPreference=2;")
        winreg.CloseKey(key)
    except OSError:
        return


def apply_gpu_env(env: dict[str, str], gpu_id: str | None = None) -> dict[str, str]:
    """Флаги CUDA/Vulkan для выбранной карты."""
    devices = list_gpus()
    chosen = gpu_id or resolve_selected_gpu_id(devices)
    match = next((item for item in devices if item["id"] == chosen), None)
    if match is None:
        chosen = recommended_gpu_id(devices)
        match = next((item for item in devices if item["id"] == chosen), None)
    kind = str((match or {}).get("kind") or "")
    index = (match or {}).get("index")

    if kind == "nvidia":
        # Ollama 0.33: любой CUDA/HIP/VK_VISIBLE_DEVICES срывает discovery
        # («user overrode visible devices» → только CPU). Vulkan выключаем отдельно.
        for key in (
            "CUDA_VISIBLE_DEVICES",
            "HIP_VISIBLE_DEVICES",
            "GGML_VK_VISIBLE_DEVICES",
            "ROCR_VISIBLE_DEVICES",
            "GPU_DEVICE_ORDINAL",
            "OLLAMA_LLM_LIBRARY",
        ):
            env.pop(key, None)
        env["OLLAMA_VULKAN"] = "0"
        persist_recommended_gpu_if_needed()
        pin_windows_high_performance_gpu()
        return env
    if kind == "cpu":
        env["OLLAMA_VULKAN"] = "0"
        env["GGML_VK_VISIBLE_DEVICES"] = "-1"
        env["CUDA_VISIBLE_DEVICES"] = "-1"
        env["HIP_VISIBLE_DEVICES"] = "-1"
        return env
    if kind == "intel":
        env["OLLAMA_VULKAN"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = "-1"
        env["GGML_VK_VISIBLE_DEVICES"] = "0"
        return env
    return env


def gpu_snapshot() -> dict[str, Any]:
    devices = list_gpus()
    selected = resolve_selected_gpu_id(devices)
    match = next((item for item in devices if item["id"] == selected), None)
    return {
        "gpus": devices,
        "gpu_id": selected,
        "gpu_name": (match or {}).get("name") or selected,
        "gpu_choice_needed": physical_gpu_count(devices) >= 2,
    }
