"""Agent orchestrator — Phase 2 engine for the Mentor office.

Runs a task across the user's agents, ADAPTING to how many models can run at
once (Robert's capacity ruling):
  • solo/private (one local machine, Ollama swaps one model at a time) → agents
    run SEQUENTIALLY; nothing leaves the device (privacy preserved).
  • concurrent (cloud models and/or remote nodes) → agents run in PARALLEL up to
    the budget; full team functionality, but data leaves the device.

Pattern: a lightweight orchestrator delegates the task to each selected agent
(isolated context, one bounded call each), then synthesizes — NOT free peer
chatter (which burns tokens and drifts). Hard caps throughout.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_AGENTS_PER_RUN = 6
_PER_AGENT_TOKENS = 700


def capacity(owner: Optional[str] = None) -> Dict[str, Any]:
    """How many models can run AT ONCE → drives sequential vs concurrent + the
    privacy↔functionality tradeoff shown in the office."""
    cloud = 0
    try:
        from core.database import SessionLocal, ModelEndpoint
        from src.endpoint_resolver import _is_local_base, normalize_base
        db = SessionLocal()
        try:
            q = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True)
            if owner:
                from src.auth_helpers import owner_filter
                q = owner_filter(q, ModelEndpoint, owner)
            for ep in q.all():
                if not _is_local_base(normalize_base(ep.base_url)):
                    cloud += 1
        finally:
            db.close()
    except Exception as e:
        logger.debug("capacity: cloud count failed: %s", e)
    local_slots = 1
    try:
        from src import fleet
        if not fleet.is_single():
            local_slots = 2  # a configured fleet — at least some parallelism
    except Exception:
        pass
    concurrent = cloud > 0 or local_slots > 1
    budget = min(local_slots + (cloud * 4), _MAX_AGENTS_PER_RUN)  # bounded concurrency hint
    return {
        "mode": "concurrent" if concurrent else "solo",
        "concurrent": concurrent,
        "budget": max(1, budget),
        "local_slots": local_slots,
        "cloud_endpoints": cloud,
        "privacy": "private — everything stays on this machine" if cloud == 0
                   else "cloud in use — data leaves this machine",
        "note": ("One local machine: agents take turns (private)." if not concurrent
                 else "Multiple models available: agents work in parallel."),
    }


async def _run_agent(agent: Dict[str, Any], task: str, owner: Optional[str]) -> Dict[str, Any]:
    """One bounded call for a single agent, using its own model + system prompt."""
    from src.endpoint_resolver import resolve_endpoint
    from src.ai_interaction import _resolve_model
    from src.llm_core import complete_with_continuation

    name = agent.get("name") or "agent"
    spec = (agent.get("model") or "").strip()
    try:
        if spec:
            # owner-scoped (never dispatch through another user's endpoint/key) and
            # off the event loop (_resolve_model does a blocking httpx probe).
            url, model, headers = await asyncio.to_thread(_resolve_model, spec, owner)
        else:
            url, model, headers = resolve_endpoint("default", owner=owner)
        if not url:
            return {"agent": name, "ok": False, "output": "(no model available)"}
        sysmsg = agent.get("system_prompt") or (
            f"You are {name}, the team's {agent.get('role') or 'assistant'}. "
            f"Goal: {agent.get('goal') or 'help the user'}. Be concise and useful.")
        reply = await complete_with_continuation(
            url, model,
            [{"role": "system", "content": sysmsg},
             {"role": "user", "content": task}],
            headers=headers or {}, max_tokens=_PER_AGENT_TOKENS, timeout=120)
        return {"agent": name, "role": agent.get("role", ""), "ok": True,
                "output": (reply or "").strip()}
    except Exception as e:
        return {"agent": name, "ok": False, "output": f"(failed: {e})"}


async def run_one(agent: Dict[str, Any], text: str, owner: Optional[str] = None) -> Dict[str, Any]:
    """One agent, one bounded call — used for DMs in the office room (frugal)."""
    return await _run_agent(agent, text, owner)


async def run_task(task: str, agents: List[Dict[str, Any]], owner: Optional[str] = None) -> Dict[str, Any]:
    """Delegate `task` to each agent, respecting the concurrency budget, then
    synthesize a short combined answer. Returns a transcript for the office UI."""
    task = (task or "").strip()
    if not task:
        return {"ok": False, "detail": "no task"}
    agents = [a for a in agents if a][:_MAX_AGENTS_PER_RUN]
    if not agents:
        return {"ok": False, "detail": "no agents selected"}
    cap = capacity(owner)
    budget = max(1, min(cap["budget"], len(agents)))

    # Run with parallelism capped to the capacity budget (=1 → sequential).
    sem = asyncio.Semaphore(budget)

    async def _guarded(a):
        async with sem:
            return await _run_agent(a, task, owner)

    contributions = await asyncio.gather(*[_guarded(a) for a in agents])

    # Synthesize (orchestrator) — one extra bounded call, but ONLY when >1 agent
    # actually contributed (skip it for solo/single-success runs to save a call).
    synthesis = ""
    _ok = [c for c in contributions if c.get("ok")]
    try:
        from src.endpoint_resolver import resolve_endpoint
        from src.llm_core import complete_with_continuation
        url, model, headers = resolve_endpoint("default", owner=owner) if len(_ok) > 1 else (None, None, None)
        if url:
            joined = "\n\n".join(f"### {c['agent']} ({c.get('role','')})\n{c['output']}"
                                 for c in contributions if c.get("ok"))
            prompt = (f"You are the team lead. The task was:\n{task}\n\n"
                      f"Your team reported:\n{joined}\n\n"
                      f"Give the user ONE concise combined answer. Note any disagreement.")
            synthesis = (await complete_with_continuation(
                url, model, [{"role": "user", "content": prompt}],
                headers=headers or {}, max_tokens=800, timeout=120) or "").strip()
    except Exception as e:
        logger.debug("synthesis failed: %s", e)

    return {"ok": True, "task": task, "capacity": cap,
            "contributions": contributions, "synthesis": synthesis}
