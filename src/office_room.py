"""Office room — a small persisted transcript of the user talking with the team.

Kept deliberately tiny (capped) so it never balloons context/tokens. The room is
mediated by the orchestrator (you address the Team or one agent) — NOT free
agent-to-agent chatter, which is the token-blowup failure mode we avoid.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from src.constants import DATA_DIR

_PATH = os.path.join(DATA_DIR, "office_room.json")
_LOCK = threading.Lock()
_CAP = 60  # keep only the last N messages per owner


def _load() -> Dict[str, List[Dict[str, Any]]]:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: Dict[str, List[Dict[str, Any]]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _PATH)


def get(owner: Optional[str]) -> List[Dict[str, Any]]:
    return _load().get(owner or "", [])


def append(owner: Optional[str], msg: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        d = _load()
        key = owner or ""
        lst = d.get(key, [])
        msg = {**msg, "ts": int(time.time())}
        lst.append(msg)
        d[key] = lst[-_CAP:]
        _save(d)
    return msg


def clear(owner: Optional[str]) -> None:
    with _LOCK:
        d = _load()
        d[owner or ""] = []
        _save(d)
