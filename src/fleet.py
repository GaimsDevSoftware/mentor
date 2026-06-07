"""Fleet mode — single-machine vs multi-machine awareness.

The app must work EXCELLENTLY on one machine, not as a degraded fleet. This
resolves the deployment mode and, in single mode, describes THIS machine (detected
from hardware) so topology, recommendations and onboarding adapt instead of
assuming a second node.

  fleet_mode setting: "auto" (default) | "single" | "fleet"
    auto → "fleet" if LLM_HOSTS lists extra hosts, else "single".
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

_machine_cache: Optional[Dict[str, Any]] = None


def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def mode() -> str:
    m = str(_get("fleet_mode", "auto") or "auto").lower()
    if m in ("single", "fleet"):
        return m
    hosts = (os.getenv("LLM_HOSTS", "") or _get("llm_hosts", "") or "").strip()
    return "fleet" if hosts else "single"


def is_single() -> bool:
    return mode() == "single"


def this_machine(refresh: bool = False) -> Dict[str, Any]:
    """Describe the machine the app runs on, detected from hardware. Cached."""
    global _machine_cache
    if _machine_cache is not None and not refresh:
        return _machine_cache
    vram = ram = 0.0
    unified = False
    backend = ""
    try:
        from services.hwfit.hardware import detect_system
        info = detect_system()
        vram = float(info.get("gpu_vram_gb", 0) or 0)
        ram = float(info.get("total_ram_gb", 0) or 0)
        unified = bool(info.get("unified_memory", False))
        backend = str(info.get("backend", "") or "")
    except Exception:
        try:
            import psutil
            ram = psutil.virtual_memory().total / 1e9
        except Exception:
            ram = 0.0

    b = backend.lower()
    if unified:
        kind = "apple-unified" if "metal" in b or "mps" in b else "unified"
    elif "cuda" in b or "nvidia" in b:
        kind = "nvidia-gpu"
    elif "rocm" in b or "amd" in b:
        kind = "amd-gpu"
    elif vram < 2:
        kind = "cpu-only"
    else:
        kind = "gpu"

    reserved = min(8 if unified else 6, max(1, int(vram // 4))) if vram >= 4 else 0
    _machine_cache = {
        "id": "this-machine", "kind": kind,
        "vram_gb": round(vram, 1), "reserved_vram_gb": reserved,
        "usable_vram_gb": max(0, round(vram - reserved, 1)),
        "ram_gb": round(ram, 1),
        "role": "all-in-one", "always_on": True, "daily_driver": True,
        "serving": "ollama-native", "detected": True,
    }
    return _machine_cache


def nodes(curated_fleet: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """In single mode: just THIS machine. In fleet mode: the curated topology."""
    return [this_machine()] if is_single() else curated_fleet


def summary() -> str:
    if is_single():
        m = this_machine()
        return (f"single machine ({m['kind']}, {m['usable_vram_gb']}GB usable VRAM of "
                f"{m['vram_gb']}, {m['ram_gb']}GB RAM)")
    return "multi-machine fleet"
