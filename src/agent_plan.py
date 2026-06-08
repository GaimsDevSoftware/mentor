"""Session-scoped plan / todo store the agent uses to think across many rounds.

The agent calls `plan_task` (a tool) to:
  draft       — turn a multi-step user ask into a concrete plan
  revise      — replace/extend the plan when new facts make it stale
  complete    — mark step N done (with a short note)
  block       — mark step N blocked (with the reason)
  add         — append a new step
  show        — return the current plan

The plan stays in memory keyed by session_id and is RENDERED into every
subsequent assistant turn's context — so the model can re-read its own plan
and revise as facts evolve, instead of starting from scratch each round.

Tiny module on purpose: deterministic, no LLM. The intelligence is the agent
deciding WHEN to draft / revise / complete / block — this just stores it.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

# session_id -> {"goal": str, "steps": [{step, status, note}], "blockers": [...],
#                "drafted": ts, "last_revised": ts, "revisions": int}
_PLANS: Dict[str, Dict[str, Any]] = {}

STATUS = ("pending", "in_progress", "done", "blocked")


def _now() -> float:
    return time.time()


def get_plan(session_id: str) -> Optional[Dict[str, Any]]:
    return _PLANS.get(session_id) if session_id else None


def render_for_context(session_id: str) -> str:
    """Render the current plan as a compact, model-friendly block. Injected into
    each agent turn so the model always sees its own north star."""
    p = get_plan(session_id)
    if not p or not p.get("steps"):
        return ""
    lines = ["[CURRENT PLAN]  goal: " + str(p.get("goal", ""))]
    for i, s in enumerate(p["steps"], 1):
        mark = {"pending": "[ ]", "in_progress": "[*]", "done": "[x]", "blocked": "[!]"}.get(s.get("status", "pending"), "[ ]")
        note = (" — " + s["note"]) if s.get("note") else ""
        lines.append("  %d. %s %s%s" % (i, mark, s.get("step", ""), note))
    if p.get("blockers"):
        lines.append("  blockers: " + "; ".join(str(b) for b in p["blockers"]))
    rev = p.get("revisions", 0)
    if rev:
        lines.append("  (revised %d time%s)" % (rev, "" if rev == 1 else "s"))
    return "\n".join(lines)


def _coerce_steps(raw) -> List[Dict[str, Any]]:
    """Accept steps as a list of strings or list of {step, note} dicts."""
    out = []
    if not isinstance(raw, list):
        return out
    for s in raw:
        if isinstance(s, str):
            out.append({"step": s.strip(), "status": "pending"})
        elif isinstance(s, dict) and s.get("step"):
            out.append({"step": str(s["step"]).strip(),
                        "status": s.get("status", "pending") if s.get("status") in STATUS else "pending",
                        "note": str(s.get("note", "")).strip() or None})
    return out


def handle_plan_action(session_id: str, content: str) -> Dict[str, Any]:
    """The `plan_task` tool entry point. Returns {ok, action, plan, message?}.

    JSON args:
      {"action":"draft","goal":"…","steps":["...","..."]}
      {"action":"revise","goal":"…","steps":[...],"why":"...new fact..."}
      {"action":"complete","step":3,"note":"..."}      # mark done
      {"action":"block","step":3,"reason":"..."}        # mark blocked
      {"action":"add","step":"new step text"}           # append
      {"action":"show"}                                  # just return current
    """
    sid = session_id or "default"
    try:
        args = json.loads(content) if (content or "").strip().startswith("{") else {"action": "show"}
    except (ValueError, TypeError):
        args = {"action": "show"}
    act = str(args.get("action", "show")).lower().strip()

    p = _PLANS.get(sid)

    if act == "draft":
        steps = _coerce_steps(args.get("steps"))
        goal = str(args.get("goal", "")).strip()
        if not goal or not steps:
            return {"ok": False, "error": "draft needs goal + steps"}
        p = {"goal": goal, "steps": steps, "blockers": [],
             "drafted": _now(), "last_revised": _now(), "revisions": 0}
        _PLANS[sid] = p
        return {"ok": True, "action": "draft", "plan": render_for_context(sid),
                "message": "Plan drafted (%d steps)." % len(steps)}

    if act == "revise":
        new_steps = _coerce_steps(args.get("steps"))
        why = str(args.get("why", "")).strip()
        goal = str(args.get("goal", "")).strip()
        if not new_steps:
            return {"ok": False, "error": "revise needs new steps"}
        if not p:
            # treat as first draft
            p = {"goal": goal or "(no goal given)", "steps": new_steps, "blockers": [],
                 "drafted": _now(), "last_revised": _now(), "revisions": 0}
        else:
            # Preserve done/in_progress markers when the same step text is kept.
            old_status = {s["step"]: s for s in p.get("steps", [])}
            for s in new_steps:
                if s["step"] in old_status:
                    keep = old_status[s["step"]]
                    if keep.get("status") in ("done", "in_progress"):
                        s["status"] = keep["status"]
                    if keep.get("note") and not s.get("note"):
                        s["note"] = keep["note"]
            if goal:
                p["goal"] = goal
            p["steps"] = new_steps
            p["last_revised"] = _now()
            p["revisions"] = int(p.get("revisions", 0)) + 1
        _PLANS[sid] = p
        msg = "Plan revised (%d steps)" % len(new_steps)
        if why:
            msg += " — " + why
        return {"ok": True, "action": "revise", "plan": render_for_context(sid), "message": msg}

    if not p:
        return {"ok": False, "error": "no plan yet — draft one first with {\"action\":\"draft\",\"goal\":\"…\",\"steps\":[…]}"}

    if act in ("complete", "complete_step", "done"):
        idx = int(args.get("step", 0)) - 1
        if not (0 <= idx < len(p["steps"])):
            return {"ok": False, "error": "step out of range"}
        p["steps"][idx]["status"] = "done"
        if args.get("note"):
            p["steps"][idx]["note"] = str(args["note"])
        return {"ok": True, "action": "complete", "plan": render_for_context(sid),
                "message": "Marked step %d done." % (idx + 1)}

    if act in ("block", "blocked", "block_step"):
        idx = int(args.get("step", 0)) - 1
        if not (0 <= idx < len(p["steps"])):
            return {"ok": False, "error": "step out of range"}
        p["steps"][idx]["status"] = "blocked"
        reason = str(args.get("reason", "") or args.get("note", "")).strip()
        if reason:
            p["steps"][idx]["note"] = reason
            p.setdefault("blockers", []).append("step %d: %s" % (idx + 1, reason))
        return {"ok": True, "action": "block", "plan": render_for_context(sid),
                "message": "Marked step %d blocked." % (idx + 1)}

    if act == "add":
        step = str(args.get("step", "")).strip()
        if not step:
            return {"ok": False, "error": "need step text"}
        p["steps"].append({"step": step, "status": "pending"})
        return {"ok": True, "action": "add", "plan": render_for_context(sid),
                "message": "Added step %d." % len(p["steps"])}

    if act == "in_progress":
        idx = int(args.get("step", 0)) - 1
        if not (0 <= idx < len(p["steps"])):
            return {"ok": False, "error": "step out of range"}
        p["steps"][idx]["status"] = "in_progress"
        return {"ok": True, "action": "in_progress", "plan": render_for_context(sid),
                "message": "Step %d in progress." % (idx + 1)}

    # default: show
    return {"ok": True, "action": "show", "plan": render_for_context(sid) or "(no plan yet)"}


def reset_plan(session_id: str) -> None:
    _PLANS.pop(session_id or "default", None)
