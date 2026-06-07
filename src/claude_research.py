"""Claude-powered web research that deposits into Odysseus' Deep Research library.

Runs the `claude` CLI headless (`-p`) with the WebSearch/WebFetch tools enabled,
so Claude actually browses the live web and returns a sourced report. The result
is written as a standard `data/deep_research/rp-<id>.json` so it shows up in the
Library panel exactly like a local-model research job — just higher quality.

Two callers:
  • the chat command `trigger_research engine=claude` (user-initiated),
  • the autonomous improvement loop (auto-rerun of weak local answers + proactive
    research on the user's standing interests).

Cost control: automated callers pass `enforce_budget=True`; the run is skipped if
the daily research cap (see src/claude_budget.py) is already spent. User-initiated
runs are never blocked but still counted.

Environment: the CLI must use the user's real OAuth login at $HOME/.claude. We
strip any ANTHROPIC_*/CLAUDE_CONFIG_DIR overrides (which would redirect it to an
API key or a different config) and pin HOME — the same hardening the
claude-code-proxy uses.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RESEARCH_DIR = "data/deep_research"

# Env vars that would redirect the CLI away from the real OAuth session.
_STRIP_ENV = (
    "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN",
)


def _clean_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
    home = os.environ.get("CLAUDE_PROXY_HOME") or os.path.expanduser("~")
    env["HOME"] = home
    return env


def _model_alias(name: str) -> str:
    n = (name or "").lower()
    if "opus" in n:
        return "opus"
    if "haiku" in n:
        return "haiku"
    return "sonnet"


def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def _research_owner(owner: Optional[str]) -> str:
    """Library entries are listed per-owner, so a background run must be
    attributed to a real account or it would be invisible. Falls back to the
    configured owner, then 'admin'."""
    return owner or (_get("claude_research_owner", "") or "").strip() or "admin"


# Extract sources from the report markdown: [title](url) links first, then any
# bare URLs not already captured.
_MD_LINK = re.compile(r"\[([^\]]{1,160})\]\((https?://[^\s)]+)\)")
_BARE_URL = re.compile(r"(?<![\(\]])\bhttps?://[^\s)\]]+")


def _extract_sources(text: str) -> List[Dict[str, str]]:
    seen, out = set(), []
    for m in _MD_LINK.finditer(text or ""):
        title, url = m.group(1).strip(), m.group(2).strip().rstrip(".,);")
        if url not in seen:
            seen.add(url)
            out.append({"url": url, "title": title})
    for m in _BARE_URL.finditer(text or ""):
        url = m.group(0).strip().rstrip(".,);")
        if url not in seen:
            seen.add(url)
            out.append({"url": url, "title": url})
    return out


_RESEARCH_PROMPT = """\
Research the following thoroughly using web search, and write a well-structured \
report. Use multiple searches, follow up on what you find, and cite real sources.

TOPIC
{topic}

Write the report in markdown with:
- An "## Executive Summary" (3-6 sentences).
- Detailed findings under clear headings.
- A final "## Sources" section listing each source as a markdown link \
[title](url). Only list URLs you actually consulted.

Be accurate and concrete. If sources conflict, say so. Do not fabricate URLs."""


async def run_claude_research(
    topic: str,
    *,
    owner: Optional[str] = None,
    category: Optional[str] = None,
    enforce_budget: bool = True,
    budget_kind: str = "research",
    origin: str = "claude-research",
) -> Dict[str, Any]:
    """Run one Claude web-research job and store it in the Library.

    `budget_kind` selects which windowed allowance the run draws on:
    "research" for fresh/immediate runs, "research_queue" for backlog drains
    ("free coins"). Returns {"ok": bool, "id": <rp-id>|None, "reason"?, ...}.
    """
    topic = (topic or "").strip()
    if not topic:
        return {"ok": False, "reason": "empty topic"}

    # Budget gate (automated callers only).
    try:
        from src import claude_budget
        if not claude_budget.try_consume(budget_kind, enforce=enforce_budget):
            return {"ok": False, "reason": f"{budget_kind} budget exhausted"}
    except Exception as e:
        logger.debug("budget check skipped: %s", e)

    model = _model_alias(_get("claude_research_model", "sonnet"))
    try:
        max_turns = int(_get("claude_research_max_turns", 24) or 24)
    except (TypeError, ValueError):
        max_turns = 24
    max_turns = max(4, min(60, max_turns))
    try:
        timeout = int(_get("claude_research_timeout_seconds", 900) or 900)
    except (TypeError, ValueError):
        timeout = 900
    claude_bin = os.environ.get("CLAUDE_PROXY_BIN", "claude")
    home = _clean_env()["HOME"]
    scratch = os.path.join(home, ".cache", "claude-research")
    os.makedirs(scratch, exist_ok=True)

    cmd = [
        claude_bin, "-p",
        "--model", model,
        "--allowedTools", "WebSearch", "WebFetch",
        "--max-turns", str(max_turns),
        "--output-format", "json",
        _RESEARCH_PROMPT.format(topic=topic),
    ]

    started = time.time()
    logger.info("claude-research start: %r (model=%s, max_turns=%d)", topic[:80], model, max_turns)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=scratch, env=_clean_env(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "reason": f"timed out after {timeout}s"}
    except FileNotFoundError:
        return {"ok": False, "reason": f"claude binary not found ({claude_bin})"}
    except Exception as e:
        return {"ok": False, "reason": f"subprocess error: {e}"}

    completed = time.time()
    raw = (out or b"").decode("utf-8", "replace").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("claude-research: unparseable output: %s",
                       (err or b"").decode("utf-8", "replace")[:300])
        return {"ok": False, "reason": "unparseable CLI output"}

    if data.get("is_error"):
        return {"ok": False, "reason": f"claude error: {str(data.get('result'))[:200]}"}

    report = (data.get("result") or "").strip()
    if not report:
        return {"ok": False, "reason": "empty report"}
    # Trim any conversational preamble before the actual report (the CLI
    # sometimes prefixes lines like "I have all I need. Writing the report now.").
    _m = re.search(r"(?m)^#{1,3}\s", report)
    if _m and _m.start() > 0 and _m.start() < 400:
        report = report[_m.start():].strip()

    turns = data.get("num_turns", 0)
    cost = data.get("total_cost_usd", 0)
    sources = _extract_sources(report)
    duration_s = round(completed - started, 1)
    web_reqs = (data.get("usage", {}) or {}).get("server_tool_use", {}) or {}

    stats = {
        "Duration": f"{duration_s}s",
        "Rounds": turns,
        "Queries": web_reqs.get("web_search_requests", ""),
        "URLs": len(sources),
        "Model": f"Claude {model} (web)",
        "Search": "claude-web",
        "Cost": f"${cost:.4f}" if isinstance(cost, (int, float)) else str(cost),
    }
    result_md = (
        f"---\n\n## Research Summary\n\n"
        f"**Engine:** Claude {model} (live web) | **Duration:** {duration_s}s | "
        f"**Rounds:** {turns} | **Sources:** {len(sources)}\n\n---\n\n{report}"
    )

    rid = f"rp-{uuid.uuid4().hex[:12]}"
    record = {
        "query": topic,
        "status": "done",
        "result": result_md,
        "raw_report": report,
        "sources": sources,
        "raw_findings": [{"url": s["url"], "title": s["title"], "summary": ""} for s in sources],
        "stats": stats,
        "category": category,
        "started_at": started,
        "completed_at": completed,
        "owner": _research_owner(owner),
        "engine": "claude",
        "origin": origin,
    }
    try:
        os.makedirs(_RESEARCH_DIR, exist_ok=True)
        from core.atomic_io import atomic_write_json
        atomic_write_json(os.path.join(_RESEARCH_DIR, f"{rid}.json"), record, indent=2)
    except Exception as e:
        return {"ok": False, "reason": f"failed to write library entry: {e}"}

    logger.info("claude-research done: %s (%s turns, %s, %d sources)",
                rid, turns, stats["Cost"], len(sources))
    return {"ok": True, "id": rid, "cost": cost, "turns": turns,
            "sources": len(sources), "owner": record["owner"]}
