"""model_autoheal — automatic model failover when a provider hits its limits.

When an LLM call fails with a 401 / 403 / balance / quota error, this module
finds a replacement model in the same pricing tier from a DIFFERENT provider
and silently switches. A calm notification is stored so the UI can surface
"Switched from X to Y — the original provider hit its limit."

The switch persists in settings (the role's model is actually updated), so the
user doesn't hit the same wall on the next request. The original model is
recorded so the user can switch back when the provider recovers.
"""
import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# In-memory log of recent auto-heals — the UI polls this to show notifications.
_heal_log = []  # [{ts, role, old_model, new_model, reason}]
_MAX_LOG = 20


def is_quota_error(error: Exception) -> bool:
    msg = str(error).lower()
    return any(k in msg for k in (
        "401", "403", "insufficient", "balance", "quota", "rate limit",
        "rejected", "unauthorized", "exceeded", "limit reached",
        "empty response", "billing",
    ))


def find_replacement(current_spec: str, role: str = "",
                     owner: str = "") -> Optional[str]:
    """Find a model in the same tier from a different provider.
    Returns 'model@endpoint' spec or None."""
    try:
        import json
        from core.database import SessionLocal, ModelEndpoint
        from routes.models_catalog_routes import classify

        current_model = current_spec.split("@")[0] if "@" in current_spec else current_spec
        current_ep = current_spec.split("@")[1] if "@" in current_spec else ""

        # Classify current model's tier
        db = SessionLocal()
        try:
            current_tier = None
            candidates = []
            for ep in db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all():
                ms = json.loads(ep.cached_models) if ep.cached_models else []
                for m in ms:
                    _, tier = classify(ep.name, ep.base_url or "", m)
                    spec = f"{m}@{ep.name}"
                    if m == current_model and (not current_ep or ep.name == current_ep):
                        current_tier = tier
                    else:
                        candidates.append({"spec": spec, "model": m, "ep": ep.name,
                                           "tier": tier, "base_url": ep.base_url or ""})
            if not current_tier:
                return None

            # Filter: same tier, different provider
            same_tier = [c for c in candidates
                         if c["tier"] == current_tier and c["ep"] != current_ep]
            if not same_tier:
                # Broaden: any tier that's equal or cheaper
                tier_rank = {"free": 0, "subscription": 1, "paid": 2}
                cur_rank = tier_rank.get(current_tier, 1)
                same_tier = [c for c in candidates
                             if tier_rank.get(c["tier"], 1) <= cur_rank
                             and c["ep"] != current_ep]
            if not same_tier:
                return None

            # Prefer models with similar names/capabilities
            return same_tier[0]["spec"]
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"autoheal find_replacement failed: {e}")
        return None


def heal_role(role_key: str, old_spec: str, reason: str,
              owner: str = "") -> Optional[str]:
    """Switch a settings role to a replacement model. Returns new spec or None."""
    replacement = find_replacement(old_spec, role=role_key, owner=owner)
    if not replacement:
        logger.info(f"[autoheal] no replacement found for {role_key}={old_spec}")
        _heal_log.append({
            "ts": time.time(),
            "role": role_key,
            "old": old_spec,
            "new": None,
            "reason": "No replacement available",
            "suggestion": (
                "All connected models in this tier are from the same provider. "
                "Add a free backup source — OpenRouter (free tier, no card needed) "
                "is the quickest: get a key at openrouter.ai/keys, then paste it "
                "in Admin → Connect. Or add Groq / Cerebras / Google Gemini for "
                "another free pool. Atlas can help: say 'add a free backup source'."
            ),
        })
        if len(_heal_log) > _MAX_LOG:
            del _heal_log[:-_MAX_LOG]
        return None

    try:
        from src.settings import load_settings, save_settings
        s = load_settings()
        s[role_key] = replacement
        # Store the original so the user can see what was replaced
        s[f"_autoheal_{role_key}_original"] = old_spec
        s[f"_autoheal_{role_key}_reason"] = reason
        s[f"_autoheal_{role_key}_ts"] = time.time()
        save_settings(s)
    except Exception as e:
        logger.warning(f"[autoheal] could not save: {e}")
        return None

    _heal_log.append({
        "ts": time.time(),
        "role": role_key,
        "old": old_spec,
        "new": replacement,
        "reason": reason,
    })
    if len(_heal_log) > _MAX_LOG:
        del _heal_log[:-_MAX_LOG]

    logger.info(f"[autoheal] {role_key}: {old_spec} → {replacement} ({reason})")
    return replacement


def recent_heals() -> list:
    """Return recent auto-heal events for the UI notification system."""
    return list(_heal_log)


def check_and_heal_all(owner: str = "") -> list:
    """Quick probe of all configured role models — heal any that are dead.
    Returns list of heals performed."""
    import asyncio
    from src.settings import get_setting

    roles = ["default_model", "utility_model", "research_model",
             "vision_model", "teacher_model"]
    heals = []
    for role in roles:
        spec = (get_setting(role, "") or "").strip()
        if not spec:
            continue
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import llm_call_async
            url, model, headers = _resolve_model(spec)

            async def _probe():
                return await llm_call_async(
                    url, model,
                    [{"role": "user", "content": "Say OK"}],
                    max_tokens=4, headers=headers, timeout=15,
                )
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return heals
                asyncio.run(_probe())
            except Exception as e:
                if is_quota_error(e):
                    new = heal_role(role, spec, str(e)[:100], owner=owner)
                    if new:
                        heals.append({"role": role, "old": spec, "new": new})
        except Exception:
            pass
    return heals
