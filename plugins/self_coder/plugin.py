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


def _diagnostic():
    from src import self_coder as sc
    n = len(sc.list_proposals())
    canary = ""
    try:
        results = sorted([f for f in os.listdir(sc._data_dir()) if f.endswith(".result")])
        if results:
            with open(os.path.join(sc._data_dir(), results[-1])) as f:
                canary = f" · last canary: {f.read().strip()}"
    except Exception:
        pass
    # Dirty tree is no longer blocking — self-coder auto-stashes. Just inform.
    tree_note = "" if sc._clean_tree() else " · dirty tree (will auto-stash)"
    return {"name": "self-coder", "status": "ok",
            "detail": f"ready · {n} proposal(s){canary}{tree_note}"}


def _stats():
    from src import self_coder as sc
    props = sc.list_proposals()
    if not props:
        return {"metrics": [{"label": "Status", "value": "Quiet"}],
                "insight": "No proposals yet — the loop hasn't suggested any code changes.",
                "status": "none"}
    n = len(props)
    verified = sum(1 for p in props if p.get("status") == "verified")
    failed = sum(1 for p in props if p.get("status") == "failed")
    applied = sum(1 for p in props if p.get("status") == "applied")
    # canary results
    import os as _os
    rollbacks = 0
    passed = 0
    try:
        for fn in _os.listdir(sc._data_dir()):
            if fn.endswith(".result"):
                with open(_os.path.join(sc._data_dir(), fn)) as f:
                    r = f.read().strip()
                    if r == "rollback":
                        rollbacks += 1
                    elif r == "pass":
                        passed += 1
    except Exception:
        pass
    # 7-day activity timeline (proposals per day, oldest→newest) as a sparkline
    import time as _t
    now = _t.time()
    buckets = [0] * 7
    for p in props:
        ts = p.get("ts", 0)
        if not ts:
            continue
        age_days = int((now - ts) // 86400)
        if 0 <= age_days < 7:
            buckets[6 - age_days] += 1
    spark_chars = " ▁▂▃▄▅▆▇█"
    mx = max(buckets) or 1
    spark = "".join(spark_chars[min(8, int(v / mx * 8))] for v in buckets)
    last7 = sum(buckets)
    metrics = [
        {"label": "Proposals", "value": str(n)},
        {"label": "Verified", "value": str(verified), "good": verified > 0},
        {"label": "Applied", "value": str(applied)},
        {"label": "Rollbacks", "value": str(rollbacks)},
        {"label": "Last 7 days", "value": f"{spark}  {last7}"},
    ]
    if rollbacks > 0 and rollbacks >= applied / 2:
        insight = f"{rollbacks} rollback(s) out of {applied} apply(es). Verify gate may be letting unstable changes through — consider enabling self_coder_run_tests."
        status = "warn"
    elif failed > verified * 2 and n > 5:
        insight = f"{failed} failed proposals vs {verified} verified. The model may be struggling — try a stronger aider_model."
        status = "warn"
    elif applied > 0:
        insight = f"{applied} change(s) applied successfully{f' with {passed} healthy canary deploy(s)' if passed else ''}. The loop is contributing."
        status = "ok"
    else:
        insight = f"{verified} verified proposals waiting for your review (one-click merge in Self-coder tab)."
        status = "ok"
    return {"metrics": metrics, "insight": insight, "status": status}


def register(api):
    global _api
    _api = api
    api.register_hook("diagnostic", _diagnostic)
    api.register_hook("stats", _stats)

    try:
        from fastapi import APIRouter, Body, Depends
        from core.middleware import require_admin
        router = APIRouter()

        @router.post("/api/plugins/self_coder/propose")
        async def propose(payload: dict = Body(...), admin: str = Depends(require_admin)):
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

        @router.get("/api/plugins/self_coder/status")
        async def status(admin: str = Depends(require_admin)):
            """Compact global status for the sidebar traffic-light. Derives a
            green/amber/red/blue/idle light from the newest proposal's live
            state and how long since it last did anything."""
            from src import self_coder as sc
            import time
            props = sc.list_proposals()
            if not props:
                return {"light": "idle", "state": "none", "active": False}
            p = props[0]
            state = p.get("state") or p.get("status") or "none"
            active = state in ("building", "working", "verifying", "stalled")
            last = p.get("last_activity_ts") or p.get("ts")
            age = (time.time() - last) if last else None
            light = ("amber" if state == "stalled"
                     else "red" if state == "failed"
                     else "green" if state in ("verified", "applied")
                     else "blue" if active
                     else "idle")
            return {"light": light, "state": state, "status": p.get("status"),
                    "active": active, "pid": p.get("id"),
                    "instruction": (p.get("instruction") or "")[:120],
                    "last_activity_ts": last,
                    "age_seconds": round(age) if age is not None else None,
                    "detail": (p.get("detail") or "")[:200]}

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
