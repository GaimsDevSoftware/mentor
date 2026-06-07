"""Windowed usage budget for Claude (subscription) calls.

The autonomous improvement system talks to the user's Claude *subscription* via
the OAuth proxy / CLI. Two kinds of calls draw on it:

  • "coach"    — teacher coaching/reflection calls (cheap-ish, text-only).
  • "research" — headless web-research runs (multi-turn, browses; expensive).

To protect the Max-plan usage limit AND keep capacity available all day long, we
cap each kind PER FIXED TIME WINDOW rather than per day. A window is a block of
`*_window_hours` hours aligned to the epoch; each window gets a fresh allowance
of `*_per_window` calls. So with research = 1 per 2h, at most one research runs
every two hours — it can never all be spent in the morning, and there is always
a fresh slot a couple of hours later. Unused allowance does NOT roll over, which
also keeps total usage bounded and predictable.

Settings (tunable without code):
  claude_research_per_window    (default 1)
  claude_research_window_hours  (default 2)
  improve_coach_per_window      (default 3)
  improve_coach_window_hours    (default 2)

User-initiated calls (e.g. the chat command "research X with Claude") pass
enforce=False: they still increment the counter for visibility, but are never
blocked — the user explicitly asked for them.

State lives in data/claude_usage.json and is keyed by the current window index.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# kind -> (per_window_setting, per_window_default, window_hours_setting, window_hours_default)
#
# "research"       — fresh/immediate web-research (auto-rerun of weak answers,
#                    proactive runs, on-command chat). The "normal" budget.
# "research_queue" — draining the backlog (research_pending.jsonl). A SEPARATE
#                    allowance — "free coins" — so clearing the queue never eats
#                    into the normal research budget. Both refill per window.
_CFG = {
    "coach": ("improve_coach_per_window", 3, "improve_coach_window_hours", 2),
    "research": ("claude_research_per_window", 2, "claude_research_window_hours", 2),
    "research_queue": ("claude_research_queue_per_window", 2, "claude_research_queue_window_hours", 2),
}


def _path() -> str:
    import os
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "claude_usage.json")


def _get_int(key: str, default: int) -> int:
    try:
        from src.settings import get_setting
        return int(get_setting(key, default) or default)
    except Exception:
        return default


def _cfg(kind: str) -> Tuple[int, float]:
    """Return (per_window_cap, window_seconds) for a kind."""
    pk, pd, hk, hd = _CFG.get(kind, (None, 0, None, 2))
    cap = _get_int(pk, pd) if pk else 0
    hours = _get_int(hk, hd) if hk else hd
    return cap, max(1, hours) * 3600.0


def _window_index(window_seconds: float, now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // window_seconds)


def _load() -> Dict[str, Any]:
    import json
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        d = {}
    return d


def _save(d: Dict[str, Any]) -> None:
    from core.atomic_io import atomic_write_json
    atomic_write_json(_path(), d, indent=2)


def _entry(d: Dict[str, Any], kind: str, win: int) -> Dict[str, Any]:
    """Get/reset the per-kind counter, resetting when the window rolls over."""
    e = d.get(kind)
    if not isinstance(e, dict) or e.get("window") != win:
        e = {"window": win, "count": 0}
        d[kind] = e
    return e


def remaining(kind: str) -> int:
    cap, wsec = _cfg(kind)
    with _lock:
        d = _load()
        e = _entry(d, kind, _window_index(wsec))
        return max(0, cap - e.get("count", 0))


def try_consume(kind: str, n: int = 1, *, enforce: bool = True) -> bool:
    """Reserve `n` calls of `kind` in the current window.

    enforce=True  → returns False (consumes nothing) if the window cap would be
                    exceeded. Gate for AUTOMATED calls.
    enforce=False → always consumes and returns True (user-initiated calls).
    """
    cap, wsec = _cfg(kind)
    win = _window_index(wsec)
    with _lock:
        d = _load()
        e = _entry(d, kind, win)
        if enforce and e.get("count", 0) + n > cap:
            return False
        e["count"] = e.get("count", 0) + n
        _save(d)
        return True


def _seconds_to_window_reset(wsec: float) -> int:
    return int(wsec - (time.time() % wsec))


def status() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    with _lock:
        d = _load()
        for kind in _CFG:
            cap, wsec = _cfg(kind)
            e = _entry(d, kind, _window_index(wsec))
            out[kind] = {
                "used_this_window": e.get("count", 0),
                "per_window": cap,
                "remaining": max(0, cap - e.get("count", 0)),
                "window_hours": round(wsec / 3600, 2),
                "resets_in_min": round(_seconds_to_window_reset(wsec) / 60),
            }
    return out
