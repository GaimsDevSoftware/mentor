"""Unit tests for the turn sentinel's pure classify() + should_auto_resume()."""
from src import turn_sentinel as ts


# ── classify ──────────────────────────────────────────────────────────────────

def test_clean_answer_is_not_resumable():
    c = ts.classify(status="done", saw_content=True, finish_reason="stop")
    assert c["end_reason"] == ts.CLEAN
    assert c["resumable"] is False
    assert c["ambiguous"] is False


def test_user_stopped_never_resumes():
    # A cancelled run = a newer user action superseded it (Stop / run-now).
    c = ts.classify(status="stopped", saw_content=True, finish_reason="length")
    assert c["end_reason"] == ts.USER_STOPPED
    assert c["resumable"] is False


def test_truncated_by_finish_reason():
    c = ts.classify(status="done", saw_content=True, finish_reason="length")
    assert c["end_reason"] == ts.TRUNCATED
    assert c["resumable"] is True


def test_empty_completion_is_truncated():
    # Done but produced nothing — local reasoning model burned budget in <think>.
    c = ts.classify(status="done", saw_content=False, finish_reason="stop")
    assert c["end_reason"] == ts.TRUNCATED
    assert c["resumable"] is True


def test_idle_timeout_is_stalled():
    c = ts.classify(status="error", saw_content=True, idle_timeout=True)
    assert c["end_reason"] == ts.STALLED
    assert c["resumable"] is True


def test_awaiting_approval():
    c = ts.classify(status="done", saw_content=True, awaiting_approval=True)
    assert c["end_reason"] == ts.AWAITING_USER
    assert c["resumable"] is False


def test_question_end_is_awaiting_user_but_ambiguous():
    c = ts.classify(status="done", saw_content=True, finish_reason="stop",
                    ends_with_question=True)
    assert c["end_reason"] == ts.AWAITING_USER
    assert c["resumable"] is False
    assert c["ambiguous"] is True          # judge may reclassify in resume mode


def test_4xx_error_is_deterministic():
    c = ts.classify(status="error", saw_content=False, saw_error=True,
                    error_status=422, error_msg="unprocessable")
    assert c["end_reason"] == ts.ERRORED_DETERMINISTIC
    assert c["resumable"] is False


def test_5xx_error_is_transient():
    c = ts.classify(status="error", saw_content=False, saw_error=True,
                    error_status=503, error_msg="bad gateway")
    assert c["end_reason"] == ts.ERRORED_TRANSIENT
    assert c["resumable"] is True


def test_connection_error_message_is_transient():
    c = ts.classify(status="error", saw_content=True,
                    error_msg="connection reset by peer")
    assert c["end_reason"] == ts.ERRORED_TRANSIENT


def test_tool_error_message_is_deterministic():
    c = ts.classify(status="error", saw_content=False,
                    error_msg="unsupported tool: frobnicate")
    assert c["end_reason"] == ts.ERRORED_DETERMINISTIC


def test_unknown_error_defaults_deterministic():
    # Never loop on a mystery error.
    c = ts.classify(status="error", saw_content=False, error_msg="???")
    assert c["end_reason"] == ts.ERRORED_DETERMINISTIC


# ── should_auto_resume guardrails ───────────────────────────────────────────

_TRUNC = {"end_reason": ts.TRUNCATED, "resumable": True, "ambiguous": False, "label": "Cut off"}


def test_resume_blocked_off_and_detect_modes():
    for mode in ("off", "detect", ""):
        d = ts.should_auto_resume(_TRUNC, mode=mode, attempts=0, cap=2)
        assert d["resume"] is False


def test_resume_allowed_in_resume_mode():
    d = ts.should_auto_resume(_TRUNC, mode="resume", attempts=0, cap=2)
    assert d["resume"] is True
    assert "1/2" in d["reason"]


def test_cap_blocks_runaway():
    d = ts.should_auto_resume(_TRUNC, mode="resume", attempts=2, cap=2)
    assert d["resume"] is False
    assert "cap" in d["reason"].lower()


def test_queued_user_message_wins():
    d = ts.should_auto_resume(_TRUNC, mode="resume", attempts=0, cap=2,
                              queue_has_user_msg=True)
    assert d["resume"] is False
    assert "queued" in d["reason"].lower()


def test_pending_approval_blocks_resume():
    d = ts.should_auto_resume(_TRUNC, mode="resume", attempts=0, cap=2,
                              approval_pending=True)
    assert d["resume"] is False
    assert "approval" in d["reason"].lower()


def test_budget_exhausted_blocks_resume():
    d = ts.should_auto_resume(_TRUNC, mode="resume", attempts=0, cap=2,
                              budget_ok=False)
    assert d["resume"] is False


def test_clean_end_never_resumes_even_in_resume_mode():
    clean = {"end_reason": ts.CLEAN, "resumable": False, "ambiguous": False, "label": "Done"}
    d = ts.should_auto_resume(clean, mode="resume", attempts=0, cap=2)
    assert d["resume"] is False
