"""Agent store — user-created agents ("employees") for the Mentor office.

A tiny JSON-backed store (data/agents.json) so we don't need a DB migration.
Each agent: id, name, role, goal, personality, backstory, system_prompt, model
(spec "model@endpoint"), tools (list), autonomy ("approve"|"auto"), color, owner,
status, created.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.constants import DATA_DIR

_PATH = os.path.join(DATA_DIR, "agents.json")
_LOCK = threading.Lock()

# A small palette so each employee gets a distinct avatar colour.
_PALETTE = ["#e0a95e", "#64d2ff", "#30d158", "#ff9f0a", "#bf5af2", "#ff453a", "#5e5ce6", "#ffd60a"]


def _load() -> List[Dict[str, Any]]:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items: List[Dict[str, Any]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=1, ensure_ascii=False)
    os.replace(tmp, _PATH)


def _visible(a: Dict[str, Any], owner: Optional[str]) -> bool:
    if not owner:
        return True
    return a.get("owner") in (owner, None, "")


def list_agents(owner: Optional[str] = None) -> List[Dict[str, Any]]:
    return [a for a in _load() if _visible(a, owner)]


def get_agent(aid: str, owner: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for a in _load():
        if a.get("id") == aid and _visible(a, owner):
            return a
    return None


_ALLOWED_TOOLS = {
    "web_search", "web_fetch", "bash", "python", "read_file",
    "manage_notes", "manage_calendar", "manage_research", "manage_memory",
    "create_document", "edit_image", "trigger_research",
}


def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
    name = str(data.get("name", "")).strip()[:60]
    tools = [t for t in (data.get("tools") or []) if t in _ALLOWED_TOOLS]
    autonomy = "auto" if str(data.get("autonomy", "")).lower() == "auto" else "approve"
    return {
        "name": name,
        "role": str(data.get("role", "")).strip()[:120],
        "goal": str(data.get("goal", "")).strip()[:400],
        "personality": str(data.get("personality", "")).strip()[:60],
        "backstory": str(data.get("backstory", "")).strip()[:2000],
        "system_prompt": str(data.get("system_prompt", "")).strip()[:4000],
        "model": str(data.get("model", "")).strip()[:160],
        "tools": tools,
        "autonomy": autonomy,
    }


def create_agent(data: Dict[str, Any], owner: Optional[str] = None) -> Dict[str, Any]:
    fields = _clean(data)
    if not fields["name"]:
        raise ValueError("name required")
    with _LOCK:
        items = _load()
        agent = {
            "id": uuid.uuid4().hex[:12],
            **fields,
            "color": _PALETTE[len(items) % len(_PALETTE)],
            "owner": owner or "",
            "status": "idle",
            "created": int(time.time()),
        }
        items.append(agent)
        _save(items)
    return agent


def update_agent(aid: str, updates: Dict[str, Any], owner: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _LOCK:
        items = _load()
        for a in items:
            if a.get("id") == aid and _visible(a, owner):
                a.update({k: v for k, v in _clean(updates).items() if v != "" or k in ("backstory", "system_prompt", "goal")})
                if "status" in updates:
                    a["status"] = str(updates["status"])[:24]
                _save(items)
                return a
    return None


def delete_agent(aid: str, owner: Optional[str] = None) -> bool:
    with _LOCK:
        items = _load()
        keep = [a for a in items if not (a.get("id") == aid and _visible(a, owner))]
        if len(keep) == len(items):
            return False
        _save(keep)
    return True
