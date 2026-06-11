"""Unified role→model recommendation across the chosen scope.

Copilot recommends which model to run for each role. The `recommend_scope` setting
decides the candidate pool:
  • "local"   — only our local fleet models (cookbook providers' local catalog)
  • "sources" — only models from plugins/sources (OpenCode Zen, OpenRouter, …)
  • "both"    — the union (default)

Local models carry a VRAM/node constraint; source models are remote/cloud (a
quality/escalation tier, no local VRAM cost). The teacher model is told the
difference so its picks respect each.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

ROLES = ["coder", "planner", "vision", "cheap_utility", "embeddings", "chat_generalist"]


def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def _tier_of(m: Dict[str, Any]) -> str:
    """Classify a candidate's billing tier: local/free/subscription/paid.
    Mirrors routes.models_catalog_routes.classify so the UI filter and the AI's
    candidate pool agree. OpenCode split: Zen-free → free, Go pool → subscription,
    Claude/GPT/Gemini/Grok via Zen → paid. Free-key providers (Groq/Cerebras/
    Gemini/Mistral) → free. Codex/Claude proxies → subscription."""
    if not m.get("remote"):
        return "local"
    src = str(m.get("source") or m.get("endpoint") or "").lower()
    model = str(m.get("model") or "").lower()
    if any(k in src for k in ("opencode", "zen")):
        if any(p in model for p in ("claude-", "gpt-5.5", "gpt-5.4", "gpt-4", "gemini-", "grok-")):
            return "paid"
        if any(p in model for p in ("glm", "kimi", "mimo", "qwen3.7", "qwen3.6", "qwen3-coder",
                                     "minimax", "deepseek")):
            return "subscription"
        return "free"
    if any(k in src for k in ("codex", "claude", "chatgpt")) or "ollama.com" in src:
        return "subscription"
    if any(k in src for k in ("groq", "cerebras", "mistral")) or "gemini" in src or "generativelanguage" in src:
        return "free"
    if "openrouter" in src:
        return "free" if model.endswith(":free") or ":free" in model else "paid"
    if model.endswith(":free"):
        return "free"
    return "paid"


def _candidates(scope: str):
    from src import plugin_system
    local: List[Dict[str, Any]] = []
    remote: List[Dict[str, Any]] = []
    for prov in plugin_system.get_cookbook_providers():
        try:
            cat = prov.catalog() if hasattr(prov, "catalog") else []
        except Exception:
            cat = []
        for m in cat:
            if not isinstance(m, dict) or not m.get("model"):
                continue
            m["tier"] = _tier_of(m)
            (remote if m.get("remote") else local).append(m)
    pool: List[Dict[str, Any]] = []
    if scope in ("local", "both"):
        pool += local
    if scope in ("sources", "both"):
        pool += remote
    return pool, len(local), len(remote)


async def recommend_roles(scope: Optional[str] = None,
                          tiers: Optional[List[str]] = None,
                          ready_only: bool = False) -> Dict[str, Any]:
    scope = (scope or _get("recommend_scope", "both") or "both").lower()
    if scope not in ("local", "sources", "both"):
        scope = "both"
    pool, n_local, n_remote = _candidates(scope)
    # Filter by the user's preference (which tiers they want considered) — so the
    # AI only sees candidates that match what the user actually wants to pay for.
    tier_set = {t.lower() for t in (tiers or []) if t}
    tier_pool = [m for m in pool if (not tier_set or m.get("tier") in tier_set)]
    # Ready-only = the candidate is already usable right now (local models that are
    # cached/served, or cloud endpoints that are signed in / have a key). Providers
    # mark their entries with `ready=True` when applicable; default True for safety
    # so providers without the field still surface.
    pool = [m for m in tier_pool if (not ready_only or m.get("ready", True))]
    if not pool:
        # Context-aware guidance — never tell the user to "turn off ready only"
        # when it's already off, and point local-only users at the right action.
        hints = []
        if ready_only and tier_pool:
            # There ARE tier matches, but all need setup → the toggle is the fix.
            hints.append("turn off 'Only models that work right now' — the matches need setup first")
        elif tier_set == {"local"}:
            hints.append("download a local model from the 'Fits this machine' list below")
        elif tier_set and "local" not in tier_set:
            hints.append("connect a cloud source for that tier (sign in / add a key)")
        if not hints or len(tier_set) <= 1:
            hints.append("widen the tier choice (add another tier)")
        detail = "No candidate models match your filters — " + ", or ".join(dict.fromkeys(hints)) + "."
        return {"ok": False, "scope": scope, "detail": detail,
                "counts": {"local": n_local, "remote": n_remote, "tier_matched": len(tier_pool)}}

    spec = (_get("improve_teacher_model", "") or _get("teacher_model", "") or "").strip()
    if not spec:
        return {"ok": False, "scope": scope, "detail": "no teacher model configured for recommendations",
                "candidates": [{"model": m.get("model"), "tier": m.get("tier"),
                                "source": m.get("source", m.get("endpoint", "?")),
                                "remote": bool(m.get("remote"))} for m in pool]}

    lines = []
    for m in pool:
        tier = m.get("tier", "?")
        if m.get("remote"):
            lines.append(f"- {m['model']} [REMOTE/{tier} via {m.get('source', m.get('endpoint','?'))} "
                         f"— no local VRAM]")
        else:
            extra = []
            if m.get("target_node"):
                extra.append(f"node={m['target_node']}")
            if m.get("vram_gb"):
                extra.append(f"~{m['vram_gb']}GB VRAM")
            lines.append(f"- {m['model']} [LOCAL/{tier} {' '.join(extra)}]")
    try:
        from src import fleet
        machine_note = (
            f"This is a SINGLE machine ({fleet.this_machine().get('usable_vram_gb','?')}GB usable "
            "VRAM): local models load ONE AT A TIME (swap), so each must individually fit; you "
            "may reuse one model across roles.\n" if fleet.is_single()
            else "This is a multi-machine fleet: local models may be placed on different nodes.\n")
    except Exception:
        machine_note = ""
    prompt = (
        "Assign the single best model to each role for a personal AI control center.\n"
        + machine_note +
        f"Scope: {scope}. Candidate models (only use these):\n" + "\n".join(lines) + "\n\n"
        "LOCAL models must fit their node's VRAM; REMOTE models are cloud (treat as a "
        "quality/escalation tier, no VRAM limit). Roles: coder, planner (reasoning/agentic), "
        "vision, cheap_utility, embeddings, chat_generalist. Reply with ONE fenced ```json "
        'block: {"<role>":{"model":"..","source":"local|<source>","why":".."}, ...}. Omit a '
        "role only if nothing fits.")
    try:
        from src.ai_interaction import _resolve_model
        from src.llm_core import complete_with_continuation
        url, model, headers = _resolve_model(spec)
        reply = await complete_with_continuation(
            url, model,
            [{"role": "system", "content": "You are a concise model-selection advisor."},
             {"role": "user", "content": prompt}],
            headers=headers, max_tokens=1400, timeout=60)
    except Exception as e:
        return {"ok": False, "scope": scope, "detail": f"recommendation call failed: {e}",
                "candidates": [m.get("model") for m in pool]}

    import json
    import re
    m = re.search(r"```(?:json)?\s*\n(\{.*?\})\s*\n```", reply or "", re.S) or \
        re.search(r"(\{.*\})", reply or "", re.S)
    try:
        rec = json.loads(m.group(1)) if m else {}
    except Exception:
        rec = {}
    # Enrich each recommendation with the candidate's tier + ready flag so the UI
    # can render the right action buttons (Download / Get key / Assign).
    by_model = {str(m.get("model")): m for m in pool}
    for role, info in (rec or {}).items():
        if isinstance(info, dict):
            m = by_model.get(str(info.get("model"))) or {}
            info["tier"] = m.get("tier")
            info["remote"] = bool(m.get("remote"))
            info["ready"] = bool(m.get("ready", True))
            info["endpoint"] = m.get("endpoint") or m.get("source")
    return {"ok": True, "scope": scope, "recommendations": rec,
            "counts": {"local": n_local, "remote": n_remote, "considered": len(pool)},
            "filters": {"tiers": sorted(tier_set) or None, "ready_only": ready_only},
            "raw": (reply or "")[:400] if not rec else None}
