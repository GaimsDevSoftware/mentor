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

# This SOURCE is the OpenCode ZEN endpoint (/zen/v1). On Zen, billing is
# per-model — subscription is its OWN separate endpoint (OpenCode Go,
# /zen/go/v1), so NO model on THIS source is "subscription". Tiers here:
#   "free"  — the promotional rotating roster ("-free" suffix or a no-suffix
#             stealth/preview model like big-pickle).
#   "paid"  — everything else: frontier proprietary (Claude/GPT-5/Gemini/Grok)
#             AND the open-source coders (GLM/Kimi/Qwen3.x/DeepSeek/…), which
#             are pay-as-you-go on Zen. Hidden by default, which steers the user
#             to the cheaper OpenCode Go subscription endpoint for those models.
# (Keep _ZEN_FREE_ROSTER in sync with routes/models_catalog_routes.py.)
DEFAULT_PAID_PATTERNS = ["claude-", "gpt-5.5", "gpt-5.4", "gpt-4", "gemini-", "grok-"]
# Open-source coder pool — pay-as-you-go on Zen, subscription on Go.
GO_PATTERNS = ["glm", "kimi", "mimo", "qwen3.7", "qwen3.6", "qwen3-coder",
               "minimax", "deepseek"]
_ZEN_FREE_ROSTER = ("big-pickle", "grok-code-fast")


def _model_tier(model_id: str) -> str:
    mid = (model_id or "").lower()
    if mid.endswith("-free") or "-free-" in mid or any(fr in mid for fr in _ZEN_FREE_ROSTER):
        return "free"
    try:
        from src.settings import get_setting
        paid_pats = get_setting("opencode_paid_patterns", DEFAULT_PAID_PATTERNS) or DEFAULT_PAID_PATTERNS
    except Exception:
        paid_pats = DEFAULT_PAID_PATTERNS
    if any(p.lower() in mid for p in paid_pats):
        return "paid"
    # Open-source coders are pay-as-you-go on the Zen endpoint → paid (hidden by
    # default; reach them cheaply via the OpenCode Go endpoint instead).
    if any(p in mid for p in GO_PATTERNS):
        return "paid"
    return "free"


def _go_endpoint_present() -> bool:
    """Does the user have an OpenCode Go subscription endpoint connected? Go is
    a SEPARATE endpoint (/zen/go/v1); its presence — not Zen model names — is
    the real signal that the user has a Go subscription."""
    try:
        from core.database import SessionLocal, ModelEndpoint
        db = SessionLocal()
        try:
            for ep in db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all():
                b = (ep.base_url or "").lower()
                n = (ep.name or "").lower()
                if "/zen/go/" in b or "opencode go" in n:
                    return True
            return False
        finally:
            db.close()
    except Exception:
        return False


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
    free = sum(1 for m in models if _model_tier(m) == "free")
    # "subscription" is no longer a Zen tier — Go is a separate endpoint, so we
    # detect it by endpoint presence rather than by Zen model names.
    has_go = _go_endpoint_present()
    # paid count won't show up here unless include_paid is on, so probe raw
    try:
        ok, raw = SOURCE.probe_models(cred)
        all_paid = sum(1 for x in (raw if ok else []) if _model_tier(x) == "paid")
    except Exception:
        all_paid = sum(1 for m in models if _model_tier(m) == "paid")
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
        {"label": "Free models", "value": str(free), "good": free > 0},
        {"label": "Go subscription", "value": "Yes" if has_go else "No", "good": has_go},
        {"label": "Paid available", "value": str(all_paid)},
        {"label": "Tokens today", "value": "~" + _h(today_tok)},
        {"label": "Tokens this month", "value": "~" + _h(month_tok)},
    ]
    if has_go:
        insight = ("OpenCode Go subscription connected — reach the GLM / Kimi / DeepSeek / Qwen3 "
                   "coder pool cheaply through the Go endpoint. " +
                   ("Per-request paid Zen models are visible." if paid_on else
                    f"{all_paid} per-request paid Zen models are hidden — toggle above to use them."))
        status = "ok"
    elif paid_on:
        insight = (f"{all_paid} per-request paid models are visible on Zen. Each request bills your "
                   "account — consider an OpenCode Go subscription for predictable costs on the coder pool.")
        status = "ok"
    else:
        insight = (f"{free} free Zen models available. The open-source coder pool (GLM, Kimi, DeepSeek, "
                   "Qwen3) is pay-as-you-go on Zen — add an OpenCode Go endpoint for a cheap subscription, "
                   "or toggle paid models above to use them per-request.")
        status = "ok" if free > 0 else "warn"
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
