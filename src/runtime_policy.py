"""Per-turn runtime policy — currently the caveman compression policy.

A turn's matched SKILLS can tune how aggressively caveman compresses, so it's
strong where that's safe (bulky web/research prose) and OFF where it would hurt
(code, exact data, precision-critical text). A skill opts in by carrying a tag:

    caveman:off          → no compression this turn (precision wins)
    caveman:minimal      → whitespace only
    caveman:structural   → + HTML / dedupe
    caveman:aggressive   → + filler phrases
    caveman:caveman      → + drop predictable grammar (max savings)
    caveman:terse        → also tell the model to REPLY tersely

The skill layer resolves the matched skills into one policy and stashes it in a
contextvar (async-safe, per request). The caveman plugin reads it via the
helpers below; if nothing set it, callers fall back to the global settings.
Kept in CORE so both the agent layer (writer) and the plugin (reader) can share
it without importing each other.
"""
from __future__ import annotations

import contextvars
from typing import Any, Dict, List, Optional

_LEVELS = ("minimal", "structural", "aggressive", "caveman")
# Strength order so the strongest explicit level among matched skills wins.
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(_LEVELS)}

# {"disabled": bool, "level": str|None, "terse": bool, "source": str} or None.
_caveman_policy: "contextvars.ContextVar[Optional[Dict[str, Any]]]" = contextvars.ContextVar(
    "caveman_policy", default=None)


def _policy_tokens(skill: Dict[str, Any]) -> List[str]:
    """Pull `caveman:<x>` / `caveman-<x>` policy tokens out of a skill's tags
    (and, defensively, an explicit `caveman` frontmatter field if present)."""
    out: List[str] = []
    raw = list(skill.get("tags") or [])
    cav = skill.get("caveman")
    if isinstance(cav, str):
        raw.append("caveman:" + cav)
    for t in raw:
        s = str(t).strip().lower().replace("-", ":")
        if s.startswith("caveman:"):
            val = s.split(":", 1)[1].strip()
            if val:
                out.append(val)
    return out


def resolve_from_skills(skills: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Fold a turn's matched skills into one caveman policy. `off` always wins
    (a precision situation must not be compressed); otherwise the strongest
    explicit level among the matches is used, and `terse` is additive. Returns
    None when no skill expressed a policy (→ caller uses the global settings)."""
    if not skills:
        return None
    disabled = False
    level: Optional[str] = None
    terse = False
    source = ""
    for sk in skills:
        for tok in _policy_tokens(sk):
            if tok in ("off", "disable", "disabled", "none", "skip"):
                disabled = True
                source = source or str(sk.get("name") or "skill")
            elif tok == "terse":
                terse = True
                source = source or str(sk.get("name") or "skill")
            elif tok in _LEVEL_RANK:
                if level is None or _LEVEL_RANK[tok] > _LEVEL_RANK[level]:
                    level = tok
                source = source or str(sk.get("name") or "skill")
    if not (disabled or level or terse):
        return None
    return {"disabled": disabled, "level": level, "terse": terse, "source": source}


# ── per-turn setters/getters (async-safe via contextvars) ──
def set_caveman_policy(policy: Optional[Dict[str, Any]]) -> None:
    _caveman_policy.set(policy)


def get_caveman_policy() -> Optional[Dict[str, Any]]:
    try:
        return _caveman_policy.get()
    except Exception:
        return None


def clear_caveman_policy() -> None:
    _caveman_policy.set(None)
