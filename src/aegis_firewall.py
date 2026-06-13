"""Aegis — runtime tool-call firewall for the agent loop.

Inspired by the community `aegis-odysseus` fork: every tool call is risk-scored
*before* execution at the single chokepoint (`tool_execution.execute_tool_block`),
then Allowed, flagged (Warn), or Blocked, and always written to an audit log.

This is the enforcement complement to the existing prompt-injection guards
(`regelverk._looks_like_injection`, the untrusted-trace wrappers): those stop bad
*instructions* from being learned; Aegis stops bad *actions* from running — the
dangerous-shell / secret-exfil / destructive-write class that survives a clean
prompt. It also directly serves the "tool calls compound downhill" point: long
autonomous runs need a gate, not blind trust.

Modes (setting `aegis_mode`):
  • "off"     — no-op (default; zero behaviour change until you opt in).
  • "audit"   — score + log every call, never block, SILENT. Use first to see
                what it would do against YOUR real traffic before enforcing.
  • "warn"    — Cowork-style "run it anyway, but tell me": risky calls at/above
                `aegis_warn_threshold` still execute, but a prominent non-blocking
                red banner is surfaced in the UI and the call is audited. This is
                the "carry out warned-against actions regardless" mode.
  • "ask"     — prompt user with prominent UI notification (blinking borders)
                before executing risky calls at/above threshold. User can approve/deny.
  • "enforce" — block calls at/above `aegis_block_threshold`; allow the rest
                (still audited). Warn-band calls are logged as "warn".

The "warn" and "ask" modes are the two halves of the Cowork permission model:
"ask" stops and prompts; "warn" proceeds but flags. They share the same risk
scorer and audit log — only the return signal differs.

All thresholds are settings-tunable and the whole thing is reversible by setting
aegis_mode=off. No external deps. The audit log is data/aegis_audit.jsonl.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── settings helpers ────────────────────────────────────────────────────────

def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def _data_dir() -> str:
    try:
        from src.constants import DATA_DIR
        return DATA_DIR
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


# ── risk model ───────────────────────────────────────────────────────────────

# Base risk by tool surface. Tool names are the `tool_type` strings the agent
# emits. Unknown tools get a low-moderate default so new surfaces aren't free.
_EXEC_TOOLS = {"bash", "python"}
_SYSTEM_WRITE_TOOLS = {
    "manage_settings", "manage_endpoints", "manage_tokens",
    "manage_mcp", "manage_webhooks",
}
_EXTERNAL_TOOLS = {
    "app_api", "api_call", "send_email", "bulk_email", "reply_to_email",
    "trigger_research",
}
_DATA_WRITE_TOOLS = {
    "write_file", "edit_file", "create_document", "update_document",
    "edit_document", "manage_documents", "manage_notes", "manage_calendar",
    "manage_tasks", "manage_skills", "manage_memory", "manage_contact",
    "edit_image", "download_model", "serve_model", "stop_served_model",
}
# Read-only surfaces — cheap, low base risk.
_READ_TOOLS = {
    "web_search", "read_file", "search_chats", "list_emails", "list_served_models",
    "list_downloads", "search_hf_models", "list_cached_models", "vault_search",
    "vault_get", "resolve_contact", "manage_research",
}


_CATEGORY_SCORE = {"exec": 55, "system-write": 45, "external": 35,
                   "data-write": 25, "read": 5, "unknown": 20}


def _base_score(tool: str) -> Tuple[int, str]:
    if tool in _EXEC_TOOLS:
        return 55, "exec"
    if tool in _SYSTEM_WRITE_TOOLS:
        return 45, "system-write"
    if tool in _EXTERNAL_TOOLS:
        return 35, "external"
    if tool in _DATA_WRITE_TOOLS:
        return 25, "data-write"
    if tool in _READ_TOOLS:
        return 5, "read"
    # Plugin-registered tools can declare a risk_category in their manifest;
    # honour it so a plugin's "exec"-class tool is scored like bash, not as a
    # cheap unknown.
    try:
        from src import plugin_system
        cat = plugin_system.tool_risk_category(tool)
        if cat in _CATEGORY_SCORE:
            return _CATEGORY_SCORE[cat], cat
    except Exception:
        pass
    return 20, "unknown"


# Content patterns that raise the score. (regex, delta, reason). Kept readable;
# this is heuristic defence-in-depth, not a sandbox — pair with OS-level limits.
_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
    # Catastrophic / destructive filesystem + disk
    (re.compile(r"\brm\s+-[rf]{1,2}\b"), 45, "recursive/forced delete"),
    (re.compile(r"\b(mkfs|fdisk|parted)\b"), 45, "disk format/partition"),
    (re.compile(r"\bdd\s+if=|\bof=/dev/"), 45, "raw disk write (dd)"),
    (re.compile(r">\s*/dev/(sd|nvme|disk)"), 45, "write to block device"),
    (re.compile(r":\(\)\s*\{.*\};\s*:"), 50, "fork bomb"),
    (re.compile(r"\bchmod\s+-R?\s*0?777\b"), 25, "world-writable chmod"),
    (re.compile(r"\bchown\s+-R\b"), 20, "recursive chown"),
    # Privilege + remote code execution
    (re.compile(r"\b(sudo|doas|su)\b"), 20, "privilege escalation"),
    (re.compile(r"(curl|wget)[^|]*\|\s*(sudo\s+)?(bash|sh|zsh|python3?)"), 40, "pipe-to-shell (RCE)"),
    (re.compile(r"\bbase64\s+-d.*\|\s*(bash|sh)"), 40, "obfuscated pipe-to-shell"),
    (re.compile(r"\beval\s*\("), 15, "eval()"),
    # Secret / credential access + exfiltration
    (re.compile(r"(\.ssh/|id_rsa|id_ed25519|/etc/shadow|/etc/passwd)"), 35, "credential file access"),
    (re.compile(r"(\.env\b|secrets?|credentials?|private[_-]?key|api[_-]?key|token)", re.I), 25, "secret-bearing path/term"),
    (re.compile(r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"), 40, "literal secret/key"),
    # Destructive data ops
    (re.compile(r"\b(DROP\s+TABLE|TRUNCATE\s+TABLE|DELETE\s+FROM)\b", re.I), 30, "destructive SQL"),
    (re.compile(r"\bdelete_all\b|\bpurge\b|\bwipe\b", re.I), 25, "bulk delete/purge"),
    # Network egress beyond localhost (in shell/api content)
    (re.compile(r"https?://(?!(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|100\.))[A-Za-z0-9.-]+"), 15, "external network egress"),
    (re.compile(r"\b(nc|ncat|netcat|socat)\b"), 25, "raw network tool"),
]


def score_tool_call(tool: str, content: str) -> Tuple[int, List[str], str]:
    """Return (score 0..100, reasons, category) for a proposed tool call."""
    score, category = _base_score(tool or "")
    reasons: List[str] = [f"base:{category}({score})"]
    text = content or ""
    for pat, delta, why in _PATTERNS:
        if pat.search(text):
            score += delta
            reasons.append(f"+{delta} {why}")
    return min(100, score), reasons, category


# ── context-specific explanations ────────────────────────────────────────────
# The score tells the user *how* risky; these tell them *why this call, right
# now* — in plain language, quoting the exact text matched in THIS call. The
# `{snippet}` slot is filled with that text so the approval dialog explains the
# action on screen instead of a generic "this could harm your system".
_EXPLAIN: Dict[str, str] = {
    "recursive/forced delete":
        "Recursively force-deletes files (`{snippet}`). Everything under the "
        "target path is removed at once — no recycle bin, no undo.",
    "disk format/partition":
        "Formats or repartitions a disk (`{snippet}`). This erases all data on "
        "the target device.",
    "raw disk write (dd)":
        "Writes raw bytes to a device with dd (`{snippet}`). A wrong target "
        "overwrites your filesystem irreversibly.",
    "write to block device":
        "Redirects output straight to a block device (`{snippet}`), bypassing "
        "the filesystem — can corrupt the disk.",
    "fork bomb":
        "Matches a fork-bomb shape (`{snippet}`) that spawns processes until the "
        "machine becomes unresponsive.",
    "world-writable chmod":
        "Makes files world-writable (`{snippet}`) — any local user or process "
        "can then read and modify them.",
    "recursive chown":
        "Recursively changes ownership (`{snippet}`) — can lock you out of files "
        "or hand them to another account.",
    "privilege escalation":
        "Runs with elevated privileges (`{snippet}`). The action can affect the "
        "whole system, not just your own files.",
    "pipe-to-shell (RCE)":
        "Downloads code from the network and pipes it straight into a shell "
        "(`{snippet}`). The remote server decides what runs on your machine.",
    "obfuscated pipe-to-shell":
        "Decodes data and pipes it into a shell (`{snippet}`), hiding what "
        "actually executes.",
    "eval()":
        "Executes a constructed string with eval() (`{snippet}`); what runs "
        "depends on runtime data and is hard to audit.",
    "credential file access":
        "Touches a credential / SSH / system file (`{snippet}`) — could read or "
        "leak private keys or password hashes.",
    "secret-bearing path/term":
        "References a secret-bearing path or term (`{snippet}`) — may expose API "
        "keys, tokens, or passwords.",
    "literal secret/key":
        "Contains what looks like a real key or token in plaintext (`{snippet}`) "
        "— risks leaking a live credential.",
    "destructive SQL":
        "Runs destructive SQL (`{snippet}`) — can drop or empty database tables.",
    "bulk delete/purge":
        "Performs a bulk delete / purge (`{snippet}`) — removes many records at "
        "once and is hard to undo.",
    "external network egress":
        "Sends data to an external host (`{snippet}`) — information leaves your "
        "machine.",
    "raw network tool":
        "Uses a raw networking tool (`{snippet}`) that can open arbitrary "
        "connections or move data off the box.",
}


def _excerpt_around(text: str, m: "re.Match[str]", trail: int = 56) -> str:
    """The exact text a pattern matched, plus a little trailing context.

    The patterns match the *verb* (e.g. ``rm -rf``); the dangerous *object*
    (the path, URL, or device) usually follows, so we extend a few chars past
    the match — trimmed at the next newline — to show what is actually targeted.
    """
    start = m.start()
    end = min(len(text), m.end() + trail)
    frag = text[start:end]
    nl = frag.find("\n")
    if nl != -1:
        frag = frag[:nl]
    frag = frag.strip()
    if len(frag) > 140:
        frag = frag[:140].rstrip() + "…"
    return frag


def _content_excerpt(content: str, limit: int = 1800) -> str:
    """Trimmed copy of the raw tool content for display in the approval UI."""
    text = (content or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n…(+{len(text) - limit} more chars)"


def explain_tool_call(tool: str, content: str) -> List[Dict[str, str]]:
    """Per-match, context-specific explanations for a proposed tool call.

    Re-runs the risk patterns and, for each one that fires, returns the exact
    text it matched in THIS call plus a plain-language description of the
    concrete harm — so the approval dialog can explain the action on screen,
    not risk in the abstract.
    """
    text = content or ""
    out: List[Dict[str, str]] = []
    seen: set = set()
    for pat, _delta, why in _PATTERNS:
        m = pat.search(text)
        if not m or why in seen:
            continue
        seen.add(why)
        snippet = _excerpt_around(text, m)
        tmpl = _EXPLAIN.get(why)
        detail = tmpl.format(snippet=snippet) if tmpl else f"Flagged as {why}: `{snippet}`."
        out.append({"label": why, "snippet": snippet, "detail": detail})
    return out


# ── audit log ────────────────────────────────────────────────────────────────

# ── pending warn notices (for "warn" mode) ──────────────────────────────────
# In "warn" mode the call is ALLOWED (guard returns None so the tool runs), but
# we stash a non-blocking notice keyed by session so the streaming layer can
# attach it to the tool_output event and the UI can show a banner. guard()
# clears any stale notice at the start of every call, so a slot can never leak
# from one tool call into the next.
_PENDING_WARN: Dict[str, Dict[str, Any]] = {}


def _set_warn(session_id: Optional[str], meta: Dict[str, Any]) -> None:
    _PENDING_WARN[session_id or ""] = meta


def _clear_warn(session_id: Optional[str]) -> None:
    _PENDING_WARN.pop(session_id or "", None)


def pop_warn(session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return and clear the pending warn notice for a session (or None)."""
    return _PENDING_WARN.pop(session_id or "", None)


def _audit(record: Dict[str, Any]) -> None:
    try:
        path = os.path.join(_data_dir(), "aegis_audit.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover — never break execution on audit
        logger.debug("aegis audit write skipped: %s", e)


# ── the gate ─────────────────────────────────────────────────────────────────

def guard(tool: str, content: str, *, owner: Optional[str] = None,
          session_id: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Risk-score a tool call at the chokepoint.

    Returns None to ALLOW (caller proceeds), or a (description, result) tuple
    that the caller should return verbatim to BLOCK/ASK the call — matching the
    shape `execute_tool_block` already uses for its other gates.
    """
    # Drop any stale warn notice for this session before assessing this call, so
    # a previous call's banner can never bleed onto an unrelated tool result.
    _clear_warn(session_id)

    mode = str(_get("aegis_mode", "off") or "off").lower()
    if mode == "off":
        return None

    try:
        block_thr = int(_get("aegis_block_threshold", 80) or 80)
        warn_thr = int(_get("aegis_warn_threshold", 60) or 60)
    except (TypeError, ValueError):
        block_thr, warn_thr = 80, 60

    score, reasons, category = score_tool_call(tool, content)
    will_ask = (mode == "ask" and score >= block_thr)
    will_block = (mode == "enforce" and score >= block_thr)
    will_warn = (mode == "warn" and score >= warn_thr)
    band = ("ask" if will_ask else "block" if will_block
            else ("warn" if score >= warn_thr else "allow"))

    _audit({
        "ts": time.time(), "tool": tool, "category": category,
        "score": score, "band": band, "mode": mode,
        "owner": owner, "session_id": session_id,
        "reasons": reasons,
        "content_preview": (content or "")[:200],
    })

    if band != "allow":
        logger.warning("aegis %s tool=%s score=%d reasons=%s",
                       band.upper(), tool, score, "; ".join(reasons))

    if will_ask:
        desc = f"{tool}: ASKING user approval (risk {score})"
        explanations = explain_tool_call(tool, content)
        if explanations:
            why_lines = "\n".join(f"• {e['detail']}" for e in explanations)
            message = (
                f"⚠️ HIGH-RISK ACTION — {tool} (risk {score}/100)\n\n"
                f"Flagged before running, because of what this specific call does:\n\n"
                f"{why_lines}\n\n"
                f"Review the exact command shown above and approve only if you "
                f"intend precisely this."
            )
        else:
            message = (
                f"⚠️ HIGH-RISK ACTION — {tool} (risk {score}/100)\n\n"
                f"This is a high-risk tool surface ({category}). No single dangerous "
                f"pattern matched, but the action can have wide effects. Review the "
                f"command shown above and approve only if you intend it."
            )
        result = {
            "aegis_ask": True,
            "aegis_score": score,
            "tool": tool,
            "reasons": reasons,
            "category": category,
            # Context-specific payload so the UI can explain the action on screen.
            "aegis_explanations": explanations,
            "aegis_content": _content_excerpt(content),
            "message": message,
            "exit_code": 0,  # Don't fail immediately; let UI handle approval
        }
        return desc, result

    if will_block:
        desc = f"{tool}: BLOCKED by Aegis (risk {score})"
        explanations = explain_tool_call(tool, content)
        why = explanations[0]["detail"] if explanations else "high-risk tool surface"
        result = {
            "error": (
                f"Aegis firewall blocked this {tool} call (risk score {score} ≥ "
                f"{block_thr}). {why} "
                "If this is legitimate, lower aegis_block_threshold, switch "
                "aegis_mode to 'audit', or perform the action manually."
            ),
            "exit_code": 1,
            "aegis_blocked": True,
            "aegis_score": score,
            "aegis_explanations": explanations,
        }
        return desc, result

    if will_warn:
        # Cowork-style "run it anyway, but tell me": ALLOW the call (return None
        # so the caller executes it), but stash a non-blocking notice the agent
        # loop attaches to the tool_output event for a prominent UI banner.
        flagged = [r for r in reasons if r.startswith("+")]
        explanations = explain_tool_call(tool, content)
        if explanations:
            wmsg = (
                f"⚠️ Aegis ran this {tool} call (risk {score}/100) but flagged it: "
                + "; ".join(e["detail"] for e in explanations)
            )
        else:
            wmsg = (
                f"⚠️ Aegis flagged this {tool} call (risk {score}/100) "
                f"but ran it anyway — 'warn' mode is on."
            )
        _set_warn(session_id, {
            "aegis_warn": True,
            "aegis_score": score,
            "aegis_reasons": flagged or [f"base:{category}({score})"],
            "aegis_category": category,
            "aegis_explanations": explanations,
            "aegis_content": _content_excerpt(content),
            "aegis_message": wmsg,
        })
        return None

    return None
