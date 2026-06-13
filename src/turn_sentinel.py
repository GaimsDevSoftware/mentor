"""Turn sentinel — the "etterretning" pass over every agent turn.

After a turn ends — by clean completion, accident, or error — this module
classifies HOW it ended and decides whether an *unexpected* end should be
auto-resumed. It is the safety net over the whole class of "the turn stopped
when it shouldn't have" (truncation, stall, dropped connection), without ever
overriding an *intended* end (a clean answer, a question to the user, or a stop
the user triggered).

Design (mirrors the Aegis rollout: off → detect → resume):
  • `autocontinue_mode = "off"`     — no classification, no resume (zero change).
  • `autocontinue_mode = "detect"`  — classify + emit a `turn_end` event + log,
                                      but NEVER auto-resume. Audit-first: watch
                                      what really happens against real traffic.
  • `autocontinue_mode = "resume"`  — additionally auto-resume the safe,
                                      unambiguous unexpected ends, behind hard
                                      guardrails (cap, budget, queue/approval).

This module is PURE (no I/O, no model calls) so the decision logic is unit
-testable in isolation. `agent_runs._drain` feeds it the signals it observed on
the stream; the optional LLM judge for ambiguous ends lives behind an explicit
endpoint (turn_judge), called only in "resume" mode for the ambiguous cases.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

# ── End reasons ──────────────────────────────────────────────────────────────
CLEAN = "clean"                              # finished as intended
AWAITING_USER = "awaiting_user"              # paused for the user (question / approval)
USER_STOPPED = "user_stopped"                # a newer user action superseded it
TRUNCATED = "truncated"                      # cut off (output-limit / empty completion)
STALLED = "stalled"                          # went silent (idle timeout, dropped socket)
ERRORED_TRANSIENT = "errored_transient"      # network/connection-class error
ERRORED_DETERMINISTIC = "errored_deterministic"  # 4xx / tool / parse — fails identically on retry

# Only these are EVER auto-resumable. Everything else is either intended
# (clean / awaiting_user / user_stopped) or pointless to retry (deterministic).
_RESUMABLE = frozenset({TRUNCATED, STALLED, ERRORED_TRANSIENT})

_LABELS = {
    CLEAN: "Completed normally",
    AWAITING_USER: "Waiting for you",
    USER_STOPPED: "Stopped by you",
    TRUNCATED: "Cut off before finishing",
    STALLED: "Stalled — no response",
    ERRORED_TRANSIENT: "Transient error",
    ERRORED_DETERMINISTIC: "Error",
}

# finish_reason values that mean the model hit its output ceiling mid-thought.
_TRUNCATING_FINISH = frozenset({"length", "max_tokens", "max_output_tokens", "max_completion_tokens"})


def label_for(end_reason: str) -> str:
    return _LABELS.get(end_reason, end_reason)


def is_resumable(end_reason: str) -> bool:
    return end_reason in _RESUMABLE


# Deterministic errors will fail identically on retry — surface, don't loop.
_DETERMINISTIC_ERR = re.compile(r"\btool\b|unsupported|json|parse|\b4\d\d\b", re.I)
# Connection-class errors are the genuine "silently died" case worth resuming.
_TRANSIENT_ERR = re.compile(
    r"network|fetch|connection|reset|closed|aborted|stream|tim(?:e|ed)\s?out|econn|eof|\b5\d\d\b",
    re.I,
)


def _classify_error(error_msg: str, error_status: Optional[int]) -> str:
    if error_status is not None:
        if 400 <= error_status < 500:
            return ERRORED_DETERMINISTIC
        if error_status >= 500:           # 5xx incl. our 504 idle
            return ERRORED_TRANSIENT
    msg = error_msg or ""
    if _DETERMINISTIC_ERR.search(msg):
        return ERRORED_DETERMINISTIC
    if _TRANSIENT_ERR.search(msg):
        return ERRORED_TRANSIENT
    # Unknown error: default to deterministic so we never loop on a mystery.
    return ERRORED_DETERMINISTIC


def classify(
    *,
    status: str,
    saw_content: bool,
    finish_reason: Optional[str] = None,
    saw_error: bool = False,
    error_msg: str = "",
    error_status: Optional[int] = None,
    idle_timeout: bool = False,
    awaiting_approval: bool = False,
    ends_with_question: bool = False,
) -> Dict[str, Any]:
    """Classify how a turn ended from the signals the drain layer observed.

    `status` is the agent_runs run status: "done" | "stopped" | "error".
    Returns {end_reason, resumable, ambiguous, label}.
    """
    fr = (finish_reason or "").strip().lower()

    if status == "stopped":
        # The run's task was cancelled — which only happens when a NEWER user
        # action (explicit Stop, or run-now / re-send starting a fresh turn)
        # superseded it. Never auto-resume a turn the user replaced.
        reason = USER_STOPPED
        ambiguous = False
    elif idle_timeout:
        reason = STALLED
        ambiguous = False
    elif status == "error" or saw_error:
        reason = _classify_error(error_msg, error_status)
        ambiguous = False
    elif fr in _TRUNCATING_FINISH:
        reason = TRUNCATED
        ambiguous = False
    elif not saw_content:
        # Ended "cleanly" yet produced no answer — an empty completion. The
        # classic local-reasoning case: the model burned its budget inside the
        # <think> block and never emitted the reply. Treat as truncated.
        reason = TRUNCATED
        ambiguous = False
    elif awaiting_approval:
        reason = AWAITING_USER
        ambiguous = False
    elif ends_with_question:
        # A complete-looking answer that ends on a question is USUALLY the model
        # intentionally asking you something (don't resume). But it can also be
        # a model that trailed off mid-thought. Default to the safe reading and
        # flag it so the judge can reclassify in resume mode.
        reason = AWAITING_USER
        ambiguous = True
    else:
        reason = CLEAN
        ambiguous = False

    return {
        "end_reason": reason,
        "resumable": reason in _RESUMABLE,
        "ambiguous": ambiguous,
        "label": _LABELS[reason],
    }


def should_auto_resume(
    classification: Dict[str, Any],
    *,
    mode: str,
    attempts: int,
    cap: int,
    queue_has_user_msg: bool = False,
    approval_pending: bool = False,
    budget_ok: bool = True,
) -> Dict[str, Any]:
    """Decide whether to auto-resume, applying every guardrail.

    Returns {resume: bool, reason: str}. `reason` is human-readable for the
    visible banner / audit log. The guardrails are checked before the
    resumability of the end reason so the *most important* veto wins the message
    (e.g. "a user message is queued" reads better than "not resumable").
    """
    if (mode or "off") != "resume":
        return {"resume": False, "reason": "auto-continue is not in 'resume' mode"}
    if approval_pending:
        return {"resume": False, "reason": "an approval is pending — leaving it to you"}
    if queue_has_user_msg:
        return {"resume": False, "reason": "a queued message takes priority"}
    if not budget_ok:
        return {"resume": False, "reason": "auto-continue budget exhausted"}
    if attempts >= cap:
        return {"resume": False, "reason": f"auto-continue cap reached ({attempts}/{cap})"}
    if not classification.get("resumable"):
        return {"resume": False,
                "reason": f"ended '{classification.get('end_reason')}' — not an unexpected stop"}
    return {"resume": True,
            "reason": f"{classification.get('label')} — continuing automatically ({attempts + 1}/{cap})"}
