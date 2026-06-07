"""Smart escalation routing.

Pick the RIGHT model tier for a task and escalate only when needed. The ladder,
cheap → capable:

  0 local-cheap   small local utility model        (trivial: classify/tag/title)
  1 local-default the everyday local MoE            (normal work)
  2 capable       a bigger local model OR a FREE    (hard: reasoning/coding)
                  source model (OpenCode Zen / OpenRouter free)
  3 escalation    Claude / a paid source            (expert OR repeated failure)

"Smart" = (a) ENTER at the rung matching task difficulty (don't burn Claude on
"what's 2+2", don't send an architecture refactor to a 4B); (b) only ESCALATE on
detected failure/low-confidence; (c) never offer a rung that isn't AVAILABLE
(model not served, source not logged in) or that the BUDGET can't afford (the
escalation rung is gated on claude_budget); (d) respect the recommend scope and
single-vs-fleet mode. The agent loop / teacher-escalation consults this to decide
where to start and where to go next.
"""
from __future__ import annotations

import re
import socket
from typing import Any, Dict, List, Optional

_DIFF = ["trivial", "normal", "hard", "expert"]
_DIFF_ENTRY = {"trivial": 0, "normal": 1, "hard": 2, "expert": 3}

_HARD = ("refactor", "architect", "prove", "debug", "optimize", "migrate", "design ",
         "across the", "whole codebase", "step by step", "plan ", "why does", "trace ",
         "root cause", "concurren", "race condition")
_EASY = ("just ", "quick", "simple", "what is", "define ", "translate", "summar",
         "rename", "list ", "tldr", "yes or no")


def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def classify(request: str) -> str:
    t = (request or "").lower()
    n = len(t)
    score = 1  # default normal
    if n > 1200:
        score += 1
    if n > 4500:
        score += 1
    if any(k in t for k in _HARD):
        score += 1
    # actual code present (not the English noun "function")
    if "```" in (request or "") or re.search(r"\bdef \w|\bclass \w|=>|\);|\bimport \w|\bawait \w", request or ""):
        score += 1
    if any(k in t for k in _EASY):
        score -= 1
    return _DIFF[max(0, min(3, score))]


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _local_available() -> bool:
    import os
    return _port_open(os.getenv("LLM_HOST", "localhost"), 11434)


def _source_connected() -> bool:
    """A logged-in remote source with at least one model in its catalog."""
    try:
        from src import plugin_system
        for prov in plugin_system.get_cookbook_providers():
            try:
                cat = prov.catalog() if hasattr(prov, "catalog") else []
            except Exception:
                cat = []
            if any(isinstance(m, dict) and m.get("remote") for m in cat):
                return True
    except Exception:
        pass
    return False


def _escalation_available() -> tuple:
    """(available, reason). Escalation = teacher/Claude/paid, gated on budget."""
    spec = (_get("improve_teacher_model", "") or _get("teacher_model", "") or "").strip()
    if not spec:
        return False, "no teacher/escalation model configured"
    try:
        from src import claude_budget
        if claude_budget.remaining("coach") <= 0:
            return False, "escalation budget window exhausted (refills next window)"
    except Exception:
        pass
    return True, "available"


def build_ladder(scope: Optional[str] = None) -> List[Dict[str, Any]]:
    """The available rungs in order, each annotated with availability + reason."""
    scope = (scope or _get("recommend_scope", "both") or "both").lower()
    local = _local_available()
    src = _source_connected()
    esc_ok, esc_reason = _escalation_available()
    allow_local = scope in ("local", "both")
    allow_src = scope in ("sources", "both")

    rungs = [
        {"tier": "local-cheap", "level": 0,
         "available": local and allow_local,
         "reason": "local utility model" if local else "local server not reachable"},
        {"tier": "local-default", "level": 1,
         "available": local and allow_local,
         "reason": "everyday local MoE" if local else "local server not reachable"},
        {"tier": "capable", "level": 2,
         "available": (local and allow_local) or (src and allow_src),
         "reason": "bigger local model or free source"
                   if ((local and allow_local) or (src and allow_src)) else "no capable tier available"},
        {"tier": "escalation", "level": 3,
         "available": esc_ok and allow_src if scope != "local" else esc_ok,
         "reason": esc_reason},
    ]
    return rungs


def route(request: str, scope: Optional[str] = None) -> Dict[str, Any]:
    """Decide where to START. Returns difficulty, the entry rung (best available at
    or below the difficulty target), and the full ladder for later escalation."""
    diff = classify(request)
    target = _DIFF_ENTRY[diff]
    ladder = build_ladder(scope)
    avail = [r for r in ladder if r["available"]]
    if not avail:
        return {"difficulty": diff, "entry": None, "ladder": ladder,
                "reason": "no model tier available — connect a local model or a source"}
    # entry = highest available rung not above the target; else the lowest available.
    at_or_below = [r for r in avail if r["level"] <= target]
    entry = (max(at_or_below, key=lambda r: r["level"]) if at_or_below
             else min(avail, key=lambda r: r["level"]))
    try:
        from src import fleet
        mode = fleet.mode()
    except Exception:
        mode = "?"
    return {"difficulty": diff, "mode": mode, "scope": scope or _get("recommend_scope", "both"),
            "entry": entry["tier"], "entry_level": entry["level"], "ladder": ladder,
            "reason": f"{diff} task → enter at '{entry['tier']}' ({entry['reason']})"}


def should_escalate(tool_results=None, agent_reply: str = "") -> bool:
    """True if the last turn looks like a failure worth escalating."""
    try:
        from src.teacher_escalation import evaluate_turn_regex
        verdict, _ = evaluate_turn_regex(tool_results or [], agent_reply or "")
        return verdict == "failure"
    except Exception:
        return False


def next_rung(current_level: int, scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The next AVAILABLE rung above current_level (bounded; escalation budget-gated)."""
    for r in build_ladder(scope):
        if r["level"] > current_level and r["available"]:
            return r
    return None
