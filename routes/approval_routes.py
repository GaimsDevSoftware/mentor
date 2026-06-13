"""HITL approval endpoint — the chat UI calls this to approve/deny a gated tool
the streaming agent loop is waiting on. See src/hitl.py."""
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from src.auth_helpers import require_user


def setup_approval_routes() -> APIRouter:
    router = APIRouter()

    @router.post("/api/approvals/{approval_id}")
    async def resolve_approval(
        approval_id: str,
        payload: Dict[str, Any] = Body(default={}),
        _u: str = Depends(require_user),
    ) -> Dict[str, Any]:
        """Record approve/deny for a pending tool approval and wake the loop."""
        from src import hitl
        decision = "approve" if str(payload.get("decision", "")).lower() == "approve" else "deny"
        ok = hitl.resolve(approval_id, decision)
        # ok=False means it already resolved or timed out — not an error for the UI.
        return {"ok": ok, "decision": decision}

    @router.post("/api/aegis/allow-session")
    async def aegis_allow_session(
        payload: Dict[str, Any] = Body(default={}),
        _u: str = Depends(require_user),
    ) -> Dict[str, Any]:
        """Auto-approve all future high-risk calls of a given tool for the rest
        of this session (the 'approve all like this' button on the Aegis
        dialog). In-memory + per-session — resets on a new session/restart."""
        from src import aegis_firewall
        session_id = str(payload.get("session_id", "") or "")
        tool = str(payload.get("tool", "") or "")
        ok = aegis_firewall.allow_tool_for_session(session_id, tool)
        return {"ok": ok, "tool": tool,
                "session_allowed": aegis_firewall.session_allowed_tools(session_id)}

    return router
