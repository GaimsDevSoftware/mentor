"""Regelverk — global operating rules the self-improvement loop maintains.

This is the third pillar of the autonomous improvement engine (alongside
*skills* and *research*). Where a SKILL.md is a task-specific procedure the
student fetches on demand, a *regel* (rule) is short, always-on guidance that
is injected into EVERY local-model agent prompt — the standing house rules the
small models should follow without being asked.

Rules are written by the teacher model (Claude, via the OAuth proxy) during a
background improvement cycle and auto-activated above a confidence threshold.
Storage is a single JSON file so it is trivial to inspect, back up, and edit by
hand.

SECURITY — rules end up in the TRUSTED system prompt, so unlike skills they are
not wrapped as untrusted data. Because the teacher distils them partly from
turn traces that contain attacker-controllable tool output, every candidate is
passed through `_looks_like_injection` before it can be stored active. Anything
that smells like an instruction-override ("ignore previous instructions",
role/system markers, tool-call payloads) is rejected outright.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _store_path() -> str:
    from src.constants import DATA_DIR
    import os
    return os.path.join(DATA_DIR, "regelverk.json")


# ── tokenisation / similarity (kept local so this module has no heavy deps) ──

_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set:
    return set(_WORD.findall((text or "").lower()))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _to_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ── injection guard ──────────────────────────────────────────────────────────

# Phrases that have no business in a one-line house rule and strongly indicate
# the candidate was lifted from prompt-injection content in a tool trace.
_INJECTION_MARKERS = [
    re.compile(r"\bignore\b.{0,30}\b(previous|prior|above|earlier)\b", re.I),
    re.compile(r"\bdisregard\b.{0,30}\b(instruction|prompt|rule)", re.I),
    re.compile(r"\b(system|developer)\s*[:>]", re.I),
    re.compile(r"<\s*/?\s*(system|im_start|im_end|s)\s*>", re.I),
    re.compile(r"\boverride\b.{0,30}\b(instruction|safety|policy|guard)", re.I),
    re.compile(r"\b(reveal|print|exfiltrate|leak)\b.{0,30}\b(prompt|key|token|secret|password)", re.I),
    re.compile(r"manage_(memory|settings|skills)\s*\(", re.I),
    re.compile(r"\bdelete_all\b", re.I),
    re.compile(r"\bcurl\b|\bwget\b|\bbase64\b", re.I),
]


def _looks_like_injection(text: str) -> bool:
    t = text or ""
    if any(p.search(t) for p in _INJECTION_MARKERS):
        return True
    # A rule is meant to be a single short directive. Multi-paragraph blobs or
    # very long text are suspicious — fail closed.
    if len(t) > 400 or t.count("\n") > 3:
        return True
    return False


# ── storage ──────────────────────────────────────────────────────────────────

def load_rules() -> List[Dict[str, Any]]:
    """All stored rules (any status). Always returns a list."""
    import json
    try:
        with open(_store_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules") if isinstance(data, dict) else data
        return rules if isinstance(rules, list) else []
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return []


def _save_rules(rules: List[Dict[str, Any]]) -> None:
    from core.atomic_io import atomic_write_json
    atomic_write_json(_store_path(), {"rules": rules}, indent=2)


def add_rule(
    rule: str,
    *,
    rationale: str = "",
    category: str = "general",
    source: str = "self-improvement",
    teacher_model: Optional[str] = None,
    confidence: float = 0.8,
    min_confidence: float = 0.85,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add (or merge) a house rule.

    Returns the stored/merged record plus a `_status` field describing the
    outcome: "added", "activated", "deduped", "rejected", or "queued".

    A rule clears to `status="active"` only when it is clean AND its confidence
    meets `min_confidence`; otherwise it is stored as `status="draft"` so a
    human can promote it from the review surface.
    """
    rule = (rule or "").strip()
    if not rule:
        return {"_status": "rejected", "reason": "empty"}
    if _looks_like_injection(rule) or _looks_like_injection(rationale):
        logger.warning("regelverk: rejected injection-like rule: %r", rule[:120])
        return {"_status": "rejected", "reason": "injection-guard", "rule": rule}

    rules = load_rules()

    # Dedup: near-identical existing rule → bump confidence, don't grow the set.
    cand = _tokenize(rule)
    for r in rules:
        if _jaccard(cand, _tokenize(r.get("rule", ""))) >= 0.7:
            r["confidence"] = max(_to_float(r.get("confidence"), 0.0),
                                  _to_float(confidence, 0.0))
            r["hits"] = int(r.get("hits", 0)) + 1
            r["updated"] = time.time()
            if r.get("status") != "active" and r["confidence"] >= min_confidence:
                r["status"] = "active"
            _save_rules(rules)
            return {**r, "_status": "deduped"}

    conf = _to_float(confidence, 0.0)
    active = conf >= min_confidence
    rec = {
        "id": uuid.uuid4().hex[:12],
        "rule": rule,
        "rationale": (rationale or "").strip()[:400],
        "category": (category or "general")[:40],
        "source": source,
        "teacher_model": teacher_model,
        "confidence": conf,
        "status": "active" if active else "draft",
        "hits": 0,
        "session_id": session_id,
        "created": time.time(),
        "updated": time.time(),
    }
    rules.append(rec)
    _save_rules(rules)
    return {**rec, "_status": "activated" if active else "queued"}


def set_status(rule_id: str, status: str) -> bool:
    """Promote/retire a rule. status in {active, draft, retired}."""
    if status not in ("active", "draft", "retired"):
        return False
    rules = load_rules()
    for r in rules:
        if r.get("id") == rule_id:
            r["status"] = status
            r["updated"] = time.time()
            _save_rules(rules)
            return True
    return False


def delete_rule(rule_id: str) -> bool:
    rules = load_rules()
    new = [r for r in rules if r.get("id") != rule_id]
    if len(new) == len(rules):
        return False
    _save_rules(new)
    return True


def bump_hits(rule_ids: List[str]) -> None:
    """Increment the `hits` counter for each rule id that was actually injected
    into a prompt. This makes `hits` a real usage signal (previously it only
    counted dedup collisions), so low-value rules can be pruned by the janitor."""
    if not rule_ids:
        return
    ids = set(rule_ids)
    rules = load_rules()
    changed = False
    for r in rules:
        if r.get("id") in ids:
            r["hits"] = int(r.get("hits", 0) or 0) + 1
            changed = True
    if changed:
        _save_rules(rules)


def get_active_rules(max_items: int = 12, min_confidence: float = 0.0) -> List[Dict[str, Any]]:
    """Active rules, highest-confidence first, capped at `max_items`."""
    rules = [r for r in load_rules()
             if r.get("status") == "active"
             and _to_float(r.get("confidence"), 0.0) >= min_confidence]
    rules.sort(key=lambda r: _to_float(r.get("confidence"), 0.0), reverse=True)
    return rules[:max(0, max_items)]


def render_rules_block(max_items: int = 12, record: bool = True) -> str:
    """A compact markdown block for the agent system prompt. Empty string if
    there are no active rules (so callers can concatenate unconditionally).

    When `record` is True (the live injection path), bumps each rendered rule's
    `hits` so usage is tracked. Pass record=False for previews/admin views."""
    active = get_active_rules(max_items=max_items)
    if not active:
        return ""
    if record:
        try:
            bump_hits([r["id"] for r in active if r.get("id")])
        except Exception:  # pragma: no cover - never break prompt build
            pass
    lines = [
        "## Driftsregelverk (house rules)",
        "Standing rules learned for this assistant. Follow them on every turn "
        "unless the user explicitly overrides one for the current request.",
    ]
    for r in active:
        lines.append(f"- {r['rule'].rstrip('.')}")
    return "\n".join(lines)
