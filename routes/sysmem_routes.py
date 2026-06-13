"""System-memory routes — live VRAM + system-RAM status, loaded-model listing,
and a "free memory" action that unloads selected Ollama models.

Powers the Mentor sidebar memory indicator + the red near-full banner and the
"Frigjør minne" button (which opens a checklist of loaded models to unload).

Endpoints:
  GET  /api/sysmem/status  -> {vram, ram, models[], level}
  POST /api/sysmem/free    -> {ok, freed[], status}   body: {"models": ["name", ...]}
"""

import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from src.auth_helpers import require_user

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434"

# Thresholds (percent used). warn = yellow indicator + sidebar nudge,
# crit = red top banner.
WARN_PCT = 80
CRIT_PCT = 92


def _gpu_mem() -> Optional[Dict[str, float]]:
    """(used_mb, total_mb) for the first NVIDIA GPU via nvidia-smi, or None."""
    smi = shutil.which("nvidia-smi") or "/usr/bin/nvidia-smi"
    try:
        out = subprocess.run(
            [smi, "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        if out.returncode == 0 and out.stdout.strip():
            used, total = [float(x) for x in out.stdout.strip().splitlines()[0].split(",")]
            return {"used_mb": used, "total_mb": total}
    except Exception as e:
        logger.debug(f"nvidia-smi query failed: {e}")
    return None


def _sys_ram() -> Optional[Dict[str, float]]:
    """(used_mb, total_mb) for system RAM from /proc/meminfo. Used = Total - Available."""
    try:
        info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                k, _, v = line.partition(":")
                info[k.strip()] = float(v.strip().split()[0])  # kB
        total_kb = info.get("MemTotal", 0)
        avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
        if total_kb:
            return {"used_mb": (total_kb - avail_kb) / 1024.0,
                    "total_mb": total_kb / 1024.0}
    except Exception as e:
        logger.debug(f"/proc/meminfo read failed: {e}")
    return None


async def _loaded_models() -> List[Dict[str, Any]]:
    """Models currently resident in Ollama (GET /api/ps). Best-effort."""
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{OLLAMA_URL}/api/ps")
            r.raise_for_status()
            data = r.json() or {}
    except Exception as e:
        logger.debug(f"ollama /api/ps failed: {e}")
        return []
    models = []
    for m in data.get("models", []) or []:
        size = float(m.get("size", 0) or 0)
        size_vram = float(m.get("size_vram", 0) or 0)
        gpu_pct = round(100 * size_vram / size) if size else 0
        where = "GPU" if gpu_pct >= 99 else ("CPU" if gpu_pct == 0 else f"{gpu_pct}% GPU")
        models.append({
            "name": m.get("name") or m.get("model") or "?",
            "size_mb": round(size / 1048576),
            "vram_mb": round(size_vram / 1048576),
            "processor": where,
        })
    return models


def _pct(block: Optional[Dict[str, float]]) -> Optional[Dict[str, Any]]:
    if not block or not block.get("total_mb"):
        return None
    pct = round(100 * block["used_mb"] / block["total_mb"])
    return {
        "used_mb": round(block["used_mb"]),
        "total_mb": round(block["total_mb"]),
        "used_gb": round(block["used_mb"] / 1024, 1),
        "total_gb": round(block["total_mb"] / 1024, 1),
        "pct": pct,
    }


async def _status() -> Dict[str, Any]:
    vram = _pct(_gpu_mem())
    ram = _pct(_sys_ram())
    models = await _loaded_models()
    worst = max([b["pct"] for b in (vram, ram) if b] or [0])
    level = "crit" if worst >= CRIT_PCT else ("warn" if worst >= WARN_PCT else "ok")
    return {"vram": vram, "ram": ram, "models": models, "level": level,
            "worst_pct": worst, "warn_pct": WARN_PCT, "crit_pct": CRIT_PCT}


def setup_sysmem_routes() -> APIRouter:
    router = APIRouter(tags=["sysmem"])

    @router.get("/api/sysmem/status")
    async def sysmem_status(request: Request) -> Dict[str, Any]:
        require_user(request)
        return await _status()

    @router.post("/api/sysmem/free")
    async def sysmem_free(request: Request) -> Dict[str, Any]:
        require_user(request)
        try:
            body = await request.json()
        except Exception:
            body = {}
        names = [str(n).strip() for n in (body.get("models") or []) if str(n).strip()]
        if not names:
            raise HTTPException(400, "no models specified")
        freed, failed = [], []
        for name in names:
            try:
                # ollama stop <name> sets keep_alive=0 and unloads the model.
                out = subprocess.run(["ollama", "stop", name],
                                     capture_output=True, text=True, timeout=20)
                if out.returncode == 0:
                    freed.append(name)
                else:
                    failed.append({"name": name, "err": (out.stderr or "").strip()[:200]})
            except Exception as e:
                failed.append({"name": name, "err": str(e)[:200]})
        logger.info(f"[sysmem] free requested for {names}: freed={freed} failed={failed}")
        return {"ok": not failed, "freed": freed, "failed": failed,
                "status": await _status()}

    return router
