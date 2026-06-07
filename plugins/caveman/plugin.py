"""caveman — token-compression plugin.

Hooks:
  • post_tool    — compress bulky output of allowlisted prose tools (web/search)
                   IN PLACE before it enters the context window.
  • build_prompt — optionally minimal-compress the system prompt (opt-in, safe).
  • diagnostic   — report cumulative token savings to the Cookbook debugger.
Route:
  • GET /api/plugins/caveman/stats — live savings.

Why allowlist tools instead of compressing everything? Whitespace/structure
collapse would corrupt code or data returned by read_file/bash/mcp. Web & search
results are bulky PROSE/HTML — the safe, high-value target. Add tools via the
`caveman_compress_tools` setting.
"""
from __future__ import annotations

import json
import os
import threading

import caveman_compress as cc

_STATS = {"calls": 0, "original_chars": 0, "compressed_chars": 0,
          "session_original": 0, "session_compressed": 0}
_lock = threading.Lock()
_api = None  # set in register(); used for settings + data_dir


def _stats_path() -> str:
    return os.path.join(_api.data_dir(), "caveman_stats.json")


def _load_stats() -> None:
    try:
        with open(_stats_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        _STATS["calls"] = int(d.get("calls", 0))
        _STATS["original_chars"] = int(d.get("original_chars", 0))
        _STATS["compressed_chars"] = int(d.get("compressed_chars", 0))
    except Exception:
        pass


def _persist_stats() -> None:
    try:
        with open(_stats_path(), "w", encoding="utf-8") as f:
            json.dump({"calls": _STATS["calls"],
                       "original_chars": _STATS["original_chars"],
                       "compressed_chars": _STATS["compressed_chars"]}, f)
    except Exception:
        pass


def _record(orig: int, comp: int) -> None:
    with _lock:
        _STATS["calls"] += 1
        _STATS["original_chars"] += orig
        _STATS["compressed_chars"] += comp
        _STATS["session_original"] += orig
        _STATS["session_compressed"] += comp
        # Persist occasionally to avoid disk churn under load.
        if _STATS["calls"] % 10 == 0:
            _persist_stats()


def _enabled() -> bool:
    return bool(_api.get_setting("caveman_enabled", True))


def _level() -> str:
    lvl = str(_api.get_setting("caveman_level", "aggressive")).lower()
    return lvl if lvl in ("minimal", "structural", "aggressive") else "aggressive"


def _min_chars() -> int:
    try:
        return int(_api.get_setting("caveman_min_chars", 600))
    except (TypeError, ValueError):
        return 600


def _compress_tools() -> set:
    tools = _api.get_setting("caveman_compress_tools",
                             ["web_search", "trigger_research", "manage_research"])
    return set(tools or [])


# ── hooks ─────────────────────────────────────────────────────────────────────

def _post_tool(tool, content, result):
    """Compress bulky text fields of an allowlisted tool result, in place."""
    if not _enabled() or not isinstance(result, dict):
        return
    if tool not in _compress_tools():
        return
    level = _level()
    floor = _min_chars()
    # Keys aligned with what agent_loop reads into history (output/results/stdout)
    # + response — so the compression PERSISTS in the session history and saves
    # tokens on every subsequent turn, not just once.
    for key in ("output", "results", "stdout", "response"):
        v = result.get(key)
        if isinstance(v, str) and len(v) >= floor:
            comp, o, c = cc.compress(v, level)
            if c < o:
                result[key] = comp
                _record(o, c)


def _prompt_hook(prompt, context):
    """Opt-in, SAFE minimal compression of the system prompt (whitespace only)."""
    if not _enabled() or not _api.get_setting("caveman_compress_system_prompt", False):
        return prompt
    comp, o, c = cc.compress(prompt, "minimal")
    if c < o:
        _record(o, c)
        return comp
    return prompt


def _diagnostic():
    o = _STATS["original_chars"]
    c = _STATS["compressed_chars"]
    saved = o - c
    pct = (saved / o * 100) if o else 0
    detail = (f"{_STATS['calls']} compressions, ~{cc.est_tokens(saved):,} tokens saved "
              f"({pct:.0f}% on {o:,} chars), level={_level()}")
    status = "ok" if _enabled() else "warn"
    hint = "" if _enabled() else "caveman_enabled is false — no compression happening"
    return {"name": "savings", "status": status, "detail": detail, "hint": hint}


# ── registration ──────────────────────────────────────────────────────────────

def _repair(finding):
    """One-click self-heal: re-enable compression and reset stale stats."""
    try:
        s = dict(__import__("src.settings", fromlist=["load_settings"]).load_settings())
        s["caveman_enabled"] = True
        __import__("src.settings", fromlist=["save_settings"]).save_settings(s)
    except Exception:
        pass
    with _lock:
        _STATS["session_original"] = _STATS["session_compressed"] = 0
    return {"ok": True, "detail": "caveman re-enabled; session stats reset"}


def register(api):
    global _api
    _api = api
    _load_stats()

    api.register_hook("post_tool", _post_tool)
    api.register_hook("build_prompt", _prompt_hook)
    api.register_hook("diagnostic", _diagnostic)
    api.register_repair(_repair)
    api.register_settings([
        {"key": "caveman_enabled", "label": "Enabled", "type": "bool", "default": True},
        {"key": "caveman_level", "label": "Compression level", "type": "select",
         "options": ["minimal", "structural", "aggressive"], "default": "aggressive"},
        {"key": "caveman_min_chars", "label": "Min chars to compress", "type": "int", "default": 600},
    ])

    try:
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/api/plugins/caveman/stats")
        async def caveman_stats():
            o = _STATS["original_chars"]
            c = _STATS["compressed_chars"]
            return {
                "enabled": _enabled(), "level": _level(),
                "calls": _STATS["calls"],
                "chars_in": o, "chars_out": c, "chars_saved": o - c,
                "tokens_saved_est": cc.est_tokens(o - c),
                "ratio": round(c / o, 3) if o else 1.0,
                "session_tokens_saved_est": cc.est_tokens(
                    _STATS["session_original"] - _STATS["session_compressed"]),
            }

        api.register_router(router)
    except Exception as e:
        api.logger.debug("caveman router registration skipped: %s", e)
