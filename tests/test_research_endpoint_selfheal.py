"""Self-heal for the research model<->endpoint mismatch (the recurring OpenCode
Go case): a Go-subscription model configured against the Zen endpoint should be
re-pointed to the Go endpoint that actually serves it."""
import json
from types import SimpleNamespace
from routes.research_routes import _select_serving_endpoint, _ep_models, _base_matches


def _ep(name, base, models):
    return SimpleNamespace(name=name, base_url=base, api_key="k",
                           cached_models=json.dumps(models))


ZEN = _ep("OpenCode", "https://opencode.ai/zen/v1", ["qwen3.6-plus-free", "glm-5.1"])
GO  = _ep("OpenCode Go", "https://opencode.ai/zen/go/v1", ["qwen3.6-plus", "deepseek-v4-pro"])
ZEN_URL = "https://opencode.ai/zen/v1/chat/completions"
GO_URL  = "https://opencode.ai/zen/go/v1/chat/completions"


def test_go_model_on_zen_endpoint_repoints_to_go():
    # research configured: qwen3.6-plus @ Zen endpoint -> should re-point to Go.
    target = _select_serving_endpoint([ZEN, GO], "qwen3.6-plus", ZEN_URL)
    assert target is GO


def test_correct_pairing_is_left_alone():
    # qwen3.6-plus already resolved at the Go endpoint -> no change.
    assert _select_serving_endpoint([ZEN, GO], "qwen3.6-plus", GO_URL) is None
    # qwen3.6-plus-free at Zen -> Zen serves it -> no change.
    assert _select_serving_endpoint([ZEN, GO], "qwen3.6-plus-free", ZEN_URL) is None


def test_unknown_catalog_is_trusted():
    blank = _ep("Custom", "https://x.local/v1", [])
    assert _select_serving_endpoint([blank], "anything", "https://x.local/v1/chat/completions") is None


def test_model_served_nowhere_keeps_resolved():
    assert _select_serving_endpoint([ZEN, GO], "no-such-model", ZEN_URL) is None


def test_base_matches_distinguishes_zen_from_go():
    assert _base_matches("https://opencode.ai/zen/v1", ZEN_URL) is True
    assert _base_matches("https://opencode.ai/zen/v1", GO_URL) is False   # not a prefix
    assert _base_matches("https://opencode.ai/zen/go/v1", GO_URL) is True


def test_ep_models_parsing():
    assert _ep_models(ZEN) == ["qwen3.6-plus-free", "glm-5.1"]
    assert _ep_models(SimpleNamespace(cached_models=None)) == []
    assert _ep_models(SimpleNamespace(cached_models="not-json")) == []
