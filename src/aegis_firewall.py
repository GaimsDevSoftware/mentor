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
  • "audit"   — score + log every call, never block. Use first to see what it
                would do against YOUR real traffic before enforcing.
  • "enforce" — block calls at/above `aegis_block_threshold`; allow the rest
                (still audited). Warn-band calls are logged as "warn".

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


# ── audit log ────────────────────────────────────────────────────────────────

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
    that the caller should return verbatim to BLOCK the call — matching the
    shape `execute_tool_block` already uses for its other gates.
    """
    mode = str(_get("aegis_mode", "off") or "off").lower()
    if mode == "off":
        return None

    try:
        block_thr = int(_get("aegis_block_threshold", 80) or 80)
        warn_thr = int(_get("aegis_warn_threshold", 60) or 60)
    except (TypeError, ValueError):
        block_thr, warn_thr = 80, 60

    score, reasons, category = score_tool_call(tool, content)
    will_block = (mode == "enforce" and score >= block_thr)
    band = "block" if will_block else ("warn" if score >= warn_thr else "allow")

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

    if will_block:
        desc = f"{tool}: BLOCKED by Aegis (risk {score})"
        result = {
            "error": (
                f"Aegis firewall blocked this {tool} call (risk score {score} ≥ "
                f"{block_thr}). Flagged: {', '.join(r for r in reasons if r.startswith('+')) or 'high-risk surface'}. "
                "If this is legitimate, lower aegis_block_threshold, switch "
                "aegis_mode to 'audit', or perform the action manually."
            ),
            "exit_code": 1,
            "aegis_blocked": True,
            "aegis_score": score,
        }
        return desc, result

    return None
