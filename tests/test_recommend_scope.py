"""recommend_roles: the explicit tier chips must drive the candidate SCOPE,
so picking 'Local' can't be silently dropped by a recommend_scope='sources'
setting (the "no candidates even though I picked Local" bug)."""
import asyncio

import src.recommend as rec


def _run(**kw):
    return asyncio.run(rec.recommend_roles(**kw))


def _patch(monkeypatch, setting_scope="sources"):
    seen = {}

    def fake_candidates(scope):
        seen["scope"] = scope
        return [], 0, 0            # empty → returns before any LLM call

    monkeypatch.setattr(rec, "_candidates", fake_candidates)
    monkeypatch.setattr(rec, "_get",
                        lambda k, d=None: setting_scope if k == "recommend_scope" else d)
    return seen


def test_local_tier_forces_local_scope(monkeypatch):
    seen = _patch(monkeypatch, "sources")
    _run(tiers=["local"], cloud_teacher=False)
    assert seen["scope"] == "local"          # NOT 'sources' from the setting


def test_cloud_tiers_force_sources(monkeypatch):
    seen = _patch(monkeypatch, "local")
    _run(tiers=["free", "subscription"], cloud_teacher=False)
    assert seen["scope"] == "sources"


def test_mixed_tiers_force_both(monkeypatch):
    seen = _patch(monkeypatch, "sources")
    _run(tiers=["local", "free"], cloud_teacher=False)
    assert seen["scope"] == "both"


def test_no_tiers_falls_back_to_setting(monkeypatch):
    seen = _patch(monkeypatch, "sources")
    _run(tiers=None, cloud_teacher=False)
    assert seen["scope"] == "sources"        # honor the setting when nothing explicit


def test_is_local_spec():
    assert rec._is_local_spec("qwen2.5:7b@Local (Ollama)") is True
    assert rec._is_local_spec("model@localhost:11434") is True
    assert rec._is_local_spec("claude-opus@OpenCode Go") is False
