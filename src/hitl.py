"""Human-in-the-loop (HITL) approval gate for tool execution.

When ``hitl_mode`` is ``risky`` or ``all``, the streaming agent loop pauses
before executing a gated tool and waits for the user to approve or deny it via
``POST /api/approvals/{id}``. Pending approvals live in-process, keyed by id, and
are resolved by setting an :class:`asyncio.Event` the loop is awaiting.

This is deliberately tiny and dependency-free so it can sit at the single
execute chokepoint without touching the rest of the loop. Default mode is
``off`` — existing chats are unaffected until the user opts in.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, Optional

# Tools that can change the machine or run code — gated in 'risky' mode.
RISKY_TOOLS = {
    "bash", "python", "shell", "execute", "run", "computer", "browser",
    "apply_patch", "write_file", "edit_file", "delete_file",
}

# id -> {"event": asyncio.Event, "decision": str|None, "tool": str}
_PENDING: Dict[str, Dict] = {}

# Seconds to wait for a human before auto-denying, so a walked-away user never
# wedges the stream forever.
TIMEOUT = 300


def _mode(owner: Optional[str]) -> str:
    """Resolve hitl_mode for this owner (per-user overrides global). off|risky|all."""
    try:
        from src.settings import get_setting, get_user_setting
        if owner:
            v = get_user_setting(owner, "hitl_mode", None)
            if v:
                return str(v)
        return str(get_setting("hitl_mode", "off") or "off")
    except Exception:
        return "off"


def needs_approval(tool_type: str, owner: Optional[str] = None) -> bool:
    """True if this tool must be approved by a human before it runs."""
    m = _mode(owner)
    if m == "all":
        return True
    if m == "risky":
        return tool_type in RISKY_TOOLS
    return False


def create(tool_type: str, command: str) -> str:
    """Register a pending approval and return its id (cheap, synchronous)."""
    aid = uuid.uuid4().hex[:12]
    _PENDING[aid] = {"event": asyncio.Event(), "decision": None, "tool": tool_type}
    return aid


async def wait_for_decision(aid: str) -> str:
    """Block until the user resolves ``aid`` (or TIMEOUT). Returns
    'approve' | 'deny' | 'timeout'. Always cleans up the registry entry."""
    rec = _PENDING.get(aid)
    if not rec:
        return "deny"
    try:
        await asyncio.wait_for(rec["event"].wait(), timeout=TIMEOUT)
        return rec.get("decision") or "deny"
    except asyncio.TimeoutError:
        return "timeout"
    finally:
        _PENDING.pop(aid, None)


def resolve(aid: str, decision: str) -> bool:
    """Record the user's decision and wake the waiting loop. Returns False if the
    approval is unknown (already resolved / timed out)."""
    rec = _PENDING.get(aid)
    if not rec:
        return False
    rec["decision"] = "approve" if decision == "approve" else "deny"
    rec["event"].set()
    return True
