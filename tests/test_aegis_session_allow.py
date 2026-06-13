"""Aegis 'approve all like this, this session' — once a tool is session-approved,
the gate stops ASKING for it (allows + audits), while other tools still prompt
and a session reset clears the grant."""
from src import aegis_firewall as a


def _ask_mode(monkeypatch):
    # Force ask-mode with a low threshold; silence the audit log.
    monkeypatch.setattr(a, "_get", lambda k, d: {
        "aegis_mode": "ask", "aegis_block_threshold": 50, "aegis_warn_threshold": 40,
    }.get(k, d))
    monkeypatch.setattr(a, "_audit", lambda rec: None)


def test_high_risk_asks_before_session_approval(monkeypatch):
    _ask_mode(monkeypatch)
    a.clear_session_allow("s1")
    out = a.guard("bash", "rm -rf /home/robert/data", session_id="s1")
    assert out is not None and out[1].get("aegis_ask") is True


def test_session_approval_suppresses_future_asks(monkeypatch):
    _ask_mode(monkeypatch)
    a.clear_session_allow("s1")
    assert a.allow_tool_for_session("s1", "bash") is True
    # Same tool, same session → now ALLOWED (no ask).
    assert a.guard("bash", "rm -rf /home/robert/data", session_id="s1") is None
    assert "bash" in a.session_allowed_tools("s1")


def test_session_approval_is_scoped_to_tool(monkeypatch):
    _ask_mode(monkeypatch)
    a.clear_session_allow("s1")
    a.allow_tool_for_session("s1", "bash")
    # A DIFFERENT high-risk tool still prompts.
    out = a.guard("python", "import os; os.system('rm -rf x')", session_id="s1")
    assert out is not None and out[1].get("aegis_ask") is True


def test_session_approval_is_scoped_to_session(monkeypatch):
    _ask_mode(monkeypatch)
    a.clear_session_allow("s1"); a.clear_session_allow("s2")
    a.allow_tool_for_session("s1", "bash")
    # Another session is unaffected.
    out = a.guard("bash", "rm -rf /home/robert/data", session_id="s2")
    assert out is not None and out[1].get("aegis_ask") is True


def test_clear_session_allow_resets(monkeypatch):
    _ask_mode(monkeypatch)
    a.allow_tool_for_session("s1", "bash")
    a.clear_session_allow("s1")
    assert a.session_allowed_tools("s1") == []
    out = a.guard("bash", "rm -rf /home/robert/data", session_id="s1")
    assert out is not None and out[1].get("aegis_ask") is True


def test_session_allow_does_not_unblock_enforce(monkeypatch):
    # In enforce mode a hard block stays a block — session-allow only short-
    # circuits the ASK path, never a deny.
    monkeypatch.setattr(a, "_get", lambda k, d: {
        "aegis_mode": "enforce", "aegis_block_threshold": 50, "aegis_warn_threshold": 40,
    }.get(k, d))
    monkeypatch.setattr(a, "_audit", lambda rec: None)
    a.clear_session_allow("s1")
    a.allow_tool_for_session("s1", "bash")
    out = a.guard("bash", "rm -rf /home/robert/data", session_id="s1")
    assert out is not None and out[1].get("aegis_blocked") is True
