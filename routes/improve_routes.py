# routes/improve_routes.py
"""Status + control surface for the autonomous self-improvement loop.

All endpoints are admin-gated — this loop maintains global skills and house
rules (regelverk), so it is an operator concern, not a per-user one.
"""
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from core.middleware import require_admin

logger = logging.getLogger(__name__)


def _tail_jsonl(path: str, n: int = 50):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return out[-n:]


def setup_improve_routes():
    router = APIRouter(prefix="/api/improve", tags=["improve"])

    @router.get("/status")
    def status(request: Request):
        require_admin(request)
        from src.settings import get_setting
        from src.constants import DATA_DIR
        from src import regelverk
        from src import claude_budget
        from src.improvement_loop import _read_queue, _read_pending_research, _teacher_spec
        log = _tail_jsonl(os.path.join(DATA_DIR, "improvement_log.jsonl"), 50)
        return {
            "enabled": bool(get_setting("improve_loop_enabled", True)),
            "teacher_model": _teacher_spec(),
            "budget": claude_budget.status(),
            "interval_seconds": get_setting("improve_interval_seconds", 1800),
            "max_per_cycle": get_setting("improve_max_per_cycle", 3),
            "min_confidence": get_setting("improve_min_confidence",
                                          get_setting("skill_autosave_min_confidence", 0.85)),
            "sources": get_setting("improve_sources",
                                   ["reflection", "gaps", "proactive"]),
            "queue_pending": len(_read_queue()),
            "research_pending": len(_read_pending_research()),
            "rules_total": len(regelverk.load_rules()),
            "rules_active": len(regelverk.get_active_rules(max_items=10_000)),
            "recent_cycles": log,
        }

    @router.get("/regelverk")
    def list_regelverk(request: Request):
        require_admin(request)
        from src import regelverk
        return {"rules": regelverk.load_rules()}

    @router.post("/regelverk/{rule_id}/status")
    async def set_rule_status(rule_id: str, request: Request):
        require_admin(request)
        from src import regelverk
        body = await request.json()
        status_val = (body or {}).get("status", "")
        if not regelverk.set_status(rule_id, status_val):
            raise HTTPException(400, "invalid rule id or status")
        return {"ok": True}

    @router.delete("/regelverk/{rule_id}")
    def delete_rule(rule_id: str, request: Request):
        require_admin(request)
        from src import regelverk
        if not regelverk.delete_rule(rule_id):
            raise HTTPException(404, "rule not found")
        return {"ok": True}

    @router.post("/run")
    async def run_now(request: Request):
        """Trigger one improvement cycle immediately (for testing / on demand)."""
        require_admin(request)
        from src.improvement_loop import run_improvement_cycle
        try:
            body = await request.json()
        except Exception:
            body = {}
        max_items = (body or {}).get("max_items")
        summary = await run_improvement_cycle(owner=None, max_items=max_items)
        return summary

    @router.post("/toggle")
    async def toggle(request: Request):
        require_admin(request)
        from src.settings import load_settings, save_settings
        body = await request.json()
        enabled = bool((body or {}).get("enabled", True))
        s = load_settings()
        s["improve_loop_enabled"] = enabled
        save_settings(s)
        return {"ok": True, "enabled": enabled}

    return router
