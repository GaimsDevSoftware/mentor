"""usage_ledger — lightweight, windowed token-usage accounting per model endpoint.

A tiny append-friendly ledger so plugins (and the UI) can show "tokens used today
/ this month" per source. Fully defensive: any failure is swallowed — usage
accounting must NEVER break a chat call.

Storage: data/usage_ledger.json
  { "<endpoint name>": { "YYYY-MM-DD": {"in": N, "out": N, "req": N}, ... }, ... }

We bucket by local date string (no Date.now in workflows, but this is the live
app, so time.time() is fine here). Old days beyond ~70 are pruned on write.
"""
from __future__ import annotations

import json
import os
import threading
import time

_LOCK = threading.Lock()
_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "usage_ledger.json")


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _load() -> dict:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        tmp = _PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _PATH)
    except Exception:
        pass


def record(endpoint: str, in_tokens: int = 0, out_tokens: int = 0) -> None:
    """Add a request's token counts to today's bucket for `endpoint`. No-op on
    any error."""
    if not endpoint:
        return
    try:
        with _LOCK:
            d = _load()
            ep = d.setdefault(endpoint, {})
            day = ep.setdefault(_today(), {"in": 0, "out": 0, "req": 0})
            day["in"] += int(in_tokens or 0)
            day["out"] += int(out_tokens or 0)
            day["req"] += 1
            # prune to ~70 most recent days per endpoint
            if len(ep) > 70:
                for k in sorted(ep.keys())[:-70]:
                    ep.pop(k, None)
            _save(d)
    except Exception:
        pass


def summary(endpoint: str) -> dict:
    """Return {today:{in,out,req}, month:{...}, total:{...}, days:[(date,total_tok)...]}
    for `endpoint`. Empty-safe."""
    out = {"today": {"in": 0, "out": 0, "req": 0},
           "month": {"in": 0, "out": 0, "req": 0},
           "total": {"in": 0, "out": 0, "req": 0},
           "days": []}
    try:
        ep = _load().get(endpoint, {})
        today = _today()
        month = today[:7]
        for date, v in sorted(ep.items()):
            for k in ("in", "out", "req"):
                out["total"][k] += v.get(k, 0)
            if date.startswith(month):
                for k in ("in", "out", "req"):
                    out["month"][k] += v.get(k, 0)
            if date == today:
                out["today"] = {k: v.get(k, 0) for k in ("in", "out", "req")}
        # last 7 days totals for a sparkline
        recent = sorted(ep.items())[-7:]
        out["days"] = [(d, v.get("in", 0) + v.get("out", 0)) for d, v in recent]
    except Exception:
        pass
    return out
