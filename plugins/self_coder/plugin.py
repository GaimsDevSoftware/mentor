"""self_coder plugin — UI + routes for the autonomous code-improvement loop.

Exposes the engine in src/self_coder over HTTP and surfaces it in /manage:
  POST /api/plugins/self_coder/propose  {instruction, files[]}
  GET  /api/plugins/self_coder/proposals           — list, newest first
  GET  /api/plugins/self_coder/proposals/{id}      — one (with diff + verify log)
  POST /api/plugins/self_coder/proposals/{id}/apply    — merge + canary
  POST /api/plugins/self_coder/proposals/{id}/discard  — delete branch + record
Diagnostic shows status + the canary result of the most recent apply.
"""
from __future__ import annotations

import os
_api = None


def _enabled():
    try:
        return bool(_api.get_setting("self_coder_enabled", False))
    except Exception:
        return False


def _diagnostic():
    if not _enabled():
        return {"name": "self-coder", "status": "ok",
                "detail": "disabled (enable to let the app propose code fixes for itself)"}
    from src import self_coder as sc
    n = len(sc.list_proposals())
    # surface the most recent canary outcome, if any
    canary = ""
    try:
        results = sorted([f for f in os.listdir(sc._data_dir()) if f.endswith(".result")])
        if results:
            with open(os.path.join(sc._data_dir(), results[-1])) as f:
                canary = f" · last canary: {f.read().strip()}"
    except Exception:
        pass
    clean = sc._clean_tree()
    if not clean:
        return {"name": "self-coder", "status": "warn",
                "detail": f"working tree dirty — can't branch safely ({n} proposals on file)",
                "hint": "commit/stash your changes; self-coder needs a clean tree"}
    return {"name": "self-coder", "status": "ok",
            "detail": f"ready · {n} proposal(s){canary}"}


def register(api):
    global _api
    _api = api
    api.register_hook("diagnostic", _diagnostic)

    try:
        from fastapi import APIRouter, Body, Depends
        from core.middleware import require_admin
        router = APIRouter()

        @router.post("/api/plugins/self_coder/propose")
        async def propose(payload: dict = Body(...), admin: str = Depends(require_admin)):
            if not _enabled():
                return {"ok": False, "detail": "self_coder is disabled (enable in Plugins)"}
            from src import self_coder as sc
            import time
            return await sc.propose(
                (payload.get("instruction") or "").strip(),
                list(payload.get("files") or []),
                source=str(payload.get("source") or "manual"),
                ts=time.time())

        @router.get("/api/plugins/self_coder/proposals")
        async def list_props(admin: str = Depends(require_admin)):
            from src import self_coder as sc
            # Strip the big diff from the list view; the detail view returns it.
            items = []
            for p in sc.list_proposals():
                items.append({k: v for k, v in p.items() if k not in ("diff", "aider_log", "verify")})
            return {"proposals": items}

        @router.get("/api/plugins/self_coder/proposals/{pid}")
        async def one(pid: str, admin: str = Depends(require_admin)):
            from src import self_coder as sc
            p = sc.get_proposal(pid)
            return p or {"ok": False, "detail": "no such proposal"}

        @router.post("/api/plugins/self_coder/proposals/{pid}/apply")
        async def apply_one(pid: str, admin: str = Depends(require_admin)):
            from src import self_coder as sc
            return sc.apply_proposal(pid)

        @router.post("/api/plugins/self_coder/proposals/{pid}/discard")
        async def discard_one(pid: str, admin: str = Depends(require_admin)):
            from src import self_coder as sc
            return sc.discard_proposal(pid)

        api.register_router(router)
    except Exception as e:
        api.logger.debug("self_coder routes skipped: %s", e)
