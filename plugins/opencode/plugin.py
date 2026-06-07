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

# Per-request PAID model families on Zen (frontier proprietary) — excluded by
# default so you only use the free + Go-subscription-included open models. Flip
# `opencode_include_paid` (or edit `opencode_paid_patterns`) to use these too.
DEFAULT_PAID_PATTERNS = ["claude-", "gpt-5.5", "gpt-5.4", "gpt-4", "gemini-", "grok-"]


def _model_filter(model_id: str) -> bool:
    """Keep free + Go-included models; drop per-request paid ones unless opted in."""
    try:
        from src.settings import get_setting
        if get_setting("opencode_include_paid", False):
            return True
        pats = get_setting("opencode_paid_patterns", DEFAULT_PAID_PATTERNS) or DEFAULT_PAID_PATTERNS
    except Exception:
        pats = DEFAULT_PAID_PATTERNS
    mid = (model_id or "").lower()
    return not any(p.lower() in mid for p in pats)


_home = os.path.expanduser("~")
SOURCE = ModelSource(
    name="OpenCode Zen",
    slug="opencode",
    base_url="https://opencode.ai/zen/v1",
    env_var="OPENCODE_ZEN_API_KEY",
    auth_json_paths=[
        os.path.join(_home, ".local", "share", "opencode", "auth.json"),
        os.path.join(_home, ".config", "opencode", "auth.json"),
    ],
    auth_json_providers=["opencode", "zen"],
    model_filter=_model_filter,
    # Known Zen catalog — fallback shown if the live /v1/models probe fails.
    models=["claude-opus-4-8", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.5-pro",
            "gemini-3.5-flash", "deepseek-v4-flash", "qwen3.7-max", "glm-5.1",
            "kimi-k2.6"],
)


def register(api):
    SOURCE.mount(api)
    api.register_settings([
        {"key": "opencode_include_paid", "label": "Include per-request PAID models",
         "type": "bool", "default": False},
    ])
