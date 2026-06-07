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
            (remote if m.get("remote") else local).append(m)
    pool: List[Dict[str, Any]] = []
    if scope in ("local", "both"):
        pool += local
    if scope in ("sources", "both"):
        pool += remote
    return pool, len(local), len(remote)


async def recommend_roles(scope: Optional[str] = None) -> Dict[str, Any]:
    scope = (scope or _get("recommend_scope", "both") or "both").lower()
    if scope not in ("local", "sources", "both"):
        scope = "both"
    pool, n_local, n_remote = _candidates(scope)
    if not pool:
        return {"ok": False, "scope": scope,
                "detail": f"no candidate models for scope '{scope}' — download local models "
                          f"and/or log in to a source (e.g. OpenCode Zen) first."}

    spec = (_get("improve_teacher_model", "") or _get("teacher_model", "") or "").strip()
    if not spec:
        return {"ok": False, "scope": scope, "detail": "no teacher model configured for recommendations",
                "candidates": [m.get("model") for m in pool]}

    lines = []
    for m in pool:
        if m.get("remote"):
            lines.append(f"- {m['model']} [REMOTE/cloud via {m.get('source', m.get('endpoint','?'))} "
                         f"— quality/escalation tier, no local VRAM]")
        else:
            extra = []
            if m.get("target_node"):
                extra.append(f"node={m['target_node']}")
            if m.get("vram_gb"):
                extra.append(f"~{m['vram_gb']}GB VRAM")
            lines.append(f"- {m['model']} [LOCAL {' '.join(extra)}]")
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
            headers=headers, max_tokens=1400, timeout=150)
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
    return {"ok": True, "scope": scope, "recommendations": rec,
            "counts": {"local": n_local, "remote": n_remote, "considered": len(pool)},
            "raw": (reply or "")[:400] if not rec else None}
