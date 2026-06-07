"""openrouter — use OpenRouter models in Odysseus (free / paid as separate options).

Another thin `ModelSource` instance. Disabled by default (enabled:false in the
manifest) — enable it, then log in with your OpenRouter key (pasted or the
OPENROUTER_API_KEY env). OpenRouter marks free models with a `:free` id suffix, so
the `openrouter_tier` setting (free | paid | both, default "free") filters which
models are surfaced/used.
"""
import os

from src.model_source import ModelSource


def _tier_filter(model_id: str) -> bool:
    try:
        from src.settings import get_setting
        tier = str(get_setting("openrouter_tier", "free")).lower()
    except Exception:
        tier = "free"
    is_free = (model_id or "").lower().endswith(":free")
    if tier == "free":
        return is_free
    if tier == "paid":
        return not is_free
    return True  # both


SOURCE = ModelSource(
    name="OpenRouter",
    slug="openrouter",
    base_url="https://openrouter.ai/api/v1",
    env_var="OPENROUTER_API_KEY",
    auth_json_paths=[os.path.join(os.path.expanduser("~"), ".config", "openrouter", "auth.json")],
    auth_json_providers=["openrouter"],
    model_filter=_tier_filter,
    # Small free-tier fallback if the live /v1/models probe fails.
    models=["meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat:free",
            "qwen/qwen-2.5-72b-instruct:free"],
)


def register(api):
    SOURCE.mount(api)
    api.register_settings([
        {"key": "openrouter_tier", "label": "Model tier", "type": "select",
         "options": ["free", "paid", "both"], "default": "free"},
    ])
