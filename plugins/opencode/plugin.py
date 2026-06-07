"""opencode — log in to OpenCode Zen and use its models inside Odysseus.

A thin instance of the reusable `ModelSource` base (src/model_source.py): declare
the provider, call .mount(api), and get login/status/models/recommend routes, a
models tool, a Cookbook section, and debugger diagnostic + one-click repair — all
for free. This file is the reference for "add your own model source as a plugin"
(API key today; swap in an OAuth/CLI `resolve=` for OAuth-backed sources).

OpenCode Zen is opencode's curated, OpenAI-compatible gateway (Claude, GPT,
DeepSeek, Qwen, GLM, Kimi…). Credential order: pasted → OPENCODE_ZEN_API_KEY env
→ ~/.local/share/opencode/auth.json (from `opencode auth login`).
"""
import os

from src.model_source import ModelSource

# Tier patterns. Tiers:
#   "paid"         — frontier proprietary, ALWAYS billed per request
#                    (Claude, GPT-5.x, Gemini, Grok). Hidden by default.
#   "subscription" — open-source coder models included in the Go subscription
#                    (GLM, Kimi, MiMo, Qwen3.x, MiniMax, DeepSeek). Free with Go,
#                    pay-as-you-go on Zen without Go.
#   "free"         — everything else surfaced by Zen.
DEFAULT_PAID_PATTERNS = ["claude-", "gpt-5.5", "gpt-5.4", "gpt-4", "gemini-", "grok-"]
GO_PATTERNS = ["glm", "kimi", "mimo", "qwen3.7", "qwen3.6", "qwen3-coder",
               "minimax", "deepseek"]


def _model_tier(model_id: str) -> str:
    mid = (model_id or "").lower()
    try:
        from src.settings import get_setting
        paid_pats = get_setting("opencode_paid_patterns", DEFAULT_PAID_PATTERNS) or DEFAULT_PAID_PATTERNS
    except Exception:
        paid_pats = DEFAULT_PAID_PATTERNS
    if any(p.lower() in mid for p in paid_pats):
        return "paid"
    if any(p in mid for p in GO_PATTERNS):
        return "subscription"
    return "free"


def _model_filter(model_id: str) -> bool:
    """Keep free + subscription models; drop per-request paid ones unless the
    user has explicitly opted in (Show per-request paid models)."""
    try:
        from src.settings import get_setting
        if get_setting("opencode_include_paid", False):
            return True
    except Exception:
        pass
    return _model_tier(model_id) != "paid"


_home = os.path.expanduser("~")
SOURCE = ModelSource(
    name="OpenCode",
    slug="opencode",
    base_url="https://opencode.ai/zen/v1",
    env_var="OPENCODE_ZEN_API_KEY",
    auth_json_paths=[
        os.path.join(_home, ".local", "share", "opencode", "auth.json"),
        os.path.join(_home, ".config", "opencode", "auth.json"),
    ],
    auth_json_providers=["opencode", "zen"],
    model_filter=_model_filter,
    tier_fn=_model_tier,
    # Known Zen catalog — fallback shown if the live /v1/models probe fails.
    models=["claude-opus-4-8", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.5-pro",
            "gemini-3.5-flash", "deepseek-v4-flash", "qwen3.7-max", "glm-5.1",
            "kimi-k2.6"],
)


def _stats():
    cred, _ = SOURCE.resolve_credential()
    if not cred or not SOURCE.endpoint_exists():
        return {"metrics": [{"label": "Status", "value": "Not signed in"}],
                "insight": "Sign in (Models tab) to use OpenCode models.",
                "status": "none"}
    SOURCE._models_cache = None  # fresh count
    models = SOURCE.list_models()
    free, sub, paid = 0, 0, 0
    for m in models:
        t = _model_tier(m)
        if t == "free":
            free += 1
        elif t == "subscription":
            sub += 1
        else:
            paid += 1
    # paid count won't show up here unless include_paid is on, so probe raw
    try:
        ok, raw = SOURCE.probe_models(cred)
        all_paid = sum(1 for x in (raw if ok else []) if _model_tier(x) == "paid")
    except Exception:
        all_paid = paid
    try:
        from src.settings import get_setting
        paid_on = bool(get_setting("opencode_include_paid", False))
    except Exception:
        paid_on = False
    # usage ledger — tokens through the OpenCode endpoint
    def _h(n):
        n = int(n)
        return f"{n/1e6:.1f}M" if n >= 1e6 else (f"{n/1e3:.1f}k" if n >= 1e3 else str(n))
    usage = {}
    try:
        from src import usage_ledger
        usage = usage_ledger.summary(SOURCE.name)
    except Exception:
        pass
    today = usage.get("today", {})
    month = usage.get("month", {})
    today_tok = today.get("in", 0) + today.get("out", 0)
    month_tok = month.get("in", 0) + month.get("out", 0)
    metrics = [
        {"label": "Subscription", "value": str(sub), "good": sub > 0},
        {"label": "Paid available", "value": str(all_paid)},
        {"label": "Tokens today", "value": "~" + _h(today_tok)},
        {"label": "Tokens this month", "value": "~" + _h(month_tok)},
        {"label": "Requests (mo)", "value": str(month.get("req", 0))},
    ]
    has_go = sub > 0
    if not has_go and not paid_on:
        insight = ("No Go-subscription models detected and per-request paid models are hidden. "
                   "If you have a Go subscription, your account should expose these — try signing out and back in.")
        status = "warn"
    elif has_go:
        insight = (f"Go subscription active — {sub} subscription models available "
                   f"(GLM, Kimi, DeepSeek, etc.). " +
                   ("Per-request paid models are visible." if paid_on else
                    f"{all_paid} per-request paid models are hidden — toggle in card above to use them."))
        status = "ok"
    else:
        insight = (f"{all_paid} per-request paid models are visible. Each request bills your account; "
                   "consider switching to a Go subscription for predictable costs.")
        status = "ok"
    # append usage note when there's traffic
    if month_tok > 0:
        insight += (f"  Usage this month: ~{_h(month_tok)} tokens over {month.get('req', 0)} requests"
                    + (f" (~{_h(today_tok)} today)." if today_tok else "."))
        if paid_on and all_paid > 0:
            insight += " Paid models are ON — watch per-request costs."
    return {"metrics": metrics, "insight": insight, "status": status}


def register(api):
    SOURCE.mount(api)
    api.register_hook("stats", _stats)
    api.register_settings([
        {"key": "opencode_include_paid", "label": "Include per-request PAID models",
         "type": "bool", "default": False},
    ])
