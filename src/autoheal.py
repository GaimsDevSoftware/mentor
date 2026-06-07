"""Auto-heal — opt-in self-healing for the app's own health.

When enabled, periodically runs the diagnostics engine and auto-applies ONLY the
safe, reversible **setting** fixes (via copilot_fix, which whitelists them). It
never auto-runs command/plugin-repair fixes — those stay one-click so the user
keeps control. Default OFF. This turns the health badge from a passive indicator
into something that quietly keeps the app healthy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


async def tick(owner: Optional[str] = None) -> Dict[str, Any]:
    """One pass: diagnose, then apply safe setting-fixes. Returns what changed."""
    try:
        from src import debugger, copilot_fix
    except Exception as e:
        return {"ok": False, "detail": f"unavailable: {e}", "fixed": []}
    try:
        data = await asyncio.to_thread(debugger.run_all, only_failures=True)
    except Exception as e:
        return {"ok": False, "detail": f"diagnostics failed: {e}", "fixed": []}

    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for _area, items in (data.get("groups") or {}).items():
        for f in items:
            fx = f.get("fix")
            if isinstance(fx, dict) and fx.get("kind") == "setting":
                candidates.append((f.get("name", "?"), fx))

    applied: List[Dict[str, Any]] = []
    for name, fx in candidates:
        try:
            r = await copilot_fix.apply_fix(fx, owner=owner)
            if r.get("ok"):
                applied.append({"name": name, "detail": r.get("detail", "")})
                logger.info("autoheal applied %s: %s", name, r.get("detail", ""))
        except Exception as e:
            logger.debug("autoheal fix %s failed: %s", name, e)
    return {"ok": True, "fixed": applied, "counts": data.get("counts", {})}
