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
# per-tool breakdown: tool -> {"calls", "orig", "comp"}
_BY_TOOL = {}
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
        bt = d.get("by_tool", {})
        if isinstance(bt, dict):
            _BY_TOOL.update(bt)
    except Exception:
        pass


def _persist_stats() -> None:
    try:
        with open(_stats_path(), "w", encoding="utf-8") as f:
            json.dump({"calls": _STATS["calls"],
                       "original_chars": _STATS["original_chars"],
                       "compressed_chars": _STATS["compressed_chars"],
                       "by_tool": _BY_TOOL}, f)
    except Exception:
        pass


def _record(orig: int, comp: int, tool: str = "system") -> None:
    with _lock:
        _STATS["calls"] += 1
        _STATS["original_chars"] += orig
        _STATS["compressed_chars"] += comp
        _STATS["session_original"] += orig
        _STATS["session_compressed"] += comp
        t = _BY_TOOL.setdefault(tool, {"calls": 0, "orig": 0, "comp": 0})
        t["calls"] += 1
        t["orig"] += orig
        t["comp"] += comp
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
                _record(o, c, tool=tool)


def _post_response(content):
    """Compress verbose AI responses before they enter the session history.

    The user sees the full original (already streamed). This only affects
    what future turns see in the context window, saving tokens on every
    subsequent round. Protected: code blocks, URLs, inline code.
    """
    if not _enabled():
        return content
    if not isinstance(content, str) or len(content) < _min_chars():
        return content
    level = _level()
    comp, o, c = cc.compress(content, level)
    if c < o:
        _record(o, c, tool="ai_response")
        return comp
    return content


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

def _human_int(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return f"{n:,}"


def _stats():
    o = _STATS["original_chars"]
    c = _STATS["compressed_chars"]
    if o == 0 and _STATS["calls"] == 0:
        return {"metrics": [{"label": "Status", "value": "Idle"}],
                "insight": "No compressions yet. Caveman runs when web_search / research tools return bulky text.",
                "status": "none"}
    saved = max(0, o - c)
    saved_tokens = cc.est_tokens(saved)
    ratio = (saved / o) if o else 0
    pct = int(ratio * 100)
    avg_per_call = saved // max(1, _STATS["calls"])
    metrics = [
        {"label": "Compressions", "value": _human_int(_STATS["calls"])},
        {"label": "Tokens saved", "value": "~" + _human_int(saved_tokens), "good": saved_tokens > 0},
        {"label": "Avg ratio", "value": f"{pct}%"},
        {"label": "Per call", "value": "~" + _human_int(cc.est_tokens(avg_per_call)) + " tok"},
    ]
    # per-tool breakdown — which tool benefits most from compression
    breakdown = ""
    if _BY_TOOL:
        ranked = sorted(_BY_TOOL.items(),
                        key=lambda kv: kv[1].get("orig", 0) - kv[1].get("comp", 0),
                        reverse=True)
        parts = []
        for name, t in ranked[:3]:
            t_saved = cc.est_tokens(t.get("orig", 0) - t.get("comp", 0))
            parts.append(f"{name}: ~{_human_int(t_saved)} tok")
        breakdown = " · ".join(parts)
    # insight + status
    if pct >= 50:
        insight = f"Strong savings — {pct}% average across {_STATS['calls']} runs."
        status = "ok"
    elif pct >= 25:
        insight = f"Moderate savings at {pct}%. Consider raising level to 'aggressive' if it's not already."
        status = "ok"
    elif pct >= 10:
        insight = f"Light savings ({pct}%). Inputs may already be terse; try lowering caveman_min_chars."
        status = "warn"
    else:
        insight = f"Low savings ({pct}%). Check caveman_level — text may be unsuitable for structural compression."
        status = "warn"
    if breakdown:
        insight += f"  By tool — {breakdown}."
    return {"metrics": metrics, "insight": insight, "status": status}


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
    api.register_hook("post_response", _post_response)
    api.register_hook("build_prompt", _prompt_hook)
    api.register_hook("diagnostic", _diagnostic)
    api.register_hook("stats", _stats)
    api.register_repair(_repair)
    api.register_settings([
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
