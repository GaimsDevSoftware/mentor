"""Model catalog — the user's OWN connected models with tier/kind metadata, plus
a per-model visibility toggle (hidden_models). One source of truth so the chat
picker, role dropdowns and onboarding all show only what the user added and chose
to keep, filterable by free / paid / subscription / local / cloud.
"""
import json
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, Request

from src.auth_helpers import get_current_user, require_user

# OpenCode Zen's free tier is a PROMOTIONAL, ROTATING roster. Most free models
# carry a "-free" suffix, but some (stealth/preview models) are free with no
# suffix. This short list catches the current no-suffix free models; it WILL
# drift as opencode.ai rotates the roster, and it's only a display hint (never a
# billing guarantee). Keep in sync with plugins/opencode/plugin.py.
_ZEN_FREE_ROSTER = ("big-pickle", "grok-code-fast")


def classify(name: str, base: str, model_id: str):
    """Return (kind, tier) for a model. kind=local|cloud, tier=free|paid|subscription.

    OpenCode Zen has THREE real tiers (the plugin already enumerates them):
      * Zen free tier — most models, usage-limited but no card
      * OpenCode Go subscription — open-source coder pool (GLM, Kimi, Qwen3.x,
        DeepSeek, MiniMax, MiMo) — much cheaper than Claude Max
      * Per-request paid — Claude, GPT-5.x, Gemini, Grok, billed per call
    We mirror the plugin's heuristic so the picker reflects what each model
    actually costs the user.
    """
    n = (name or "").lower()
    b = (base or "").lower()
    m = (model_id or "").lower()
    # Subscription proxies (Codex/Claude) bind to localhost but route to a real
    # paid account — check BEFORE the local-host shortcut so we don't mislabel
    # them as a local-free model on your machine.
    if (any(k in n for k in ("chatgpt", "codex", "claude code (oauth)", "claude-code"))
            or "8750" in b or "8775" in b):
        return "cloud", "subscription"
    local = any(h in b for h in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1"))
    if local:
        return "local", "free"
    # OpenCode Zen: discriminate by model name (matches plugins/opencode/plugin.py).
    if "/zen/go/" in b or "opencode go" in n:
        return "cloud", "subscription"       # OpenCode Go — all models on this endpoint are subscription
    if "opencode" in b or "/zen" in b or any(k in n for k in ("opencode", "zen")):
        # On OpenCode Zen, billing is per-model. Subscription is its OWN
        # endpoint (OpenCode Go), handled above. The rule mirrors how
        # opencode.ai actually charges:
        #   * free roster ("-free" suffix OR a promotional no-suffix model
        #     like big-pickle) → Free (no balance needed). The roster ROTATES,
        #     so the no-suffix list will drift — it's a display hint only.
        #   * everything else on Zen → Paid (billed per request against the
        #     workspace balance). The open-source coders are pay-as-you-go
        #     HERE; the cheap way to reach them is the OpenCode Go endpoint.
        if m.endswith("-free") or "-free-" in m or any(fr in m for fr in _ZEN_FREE_ROSTER):
            return "cloud", "free"
        return "cloud", "paid"
    # Ollama Cloud is a subscription/pay-as-you-go service.
    if "ollama.com" in b:
        return "cloud", "subscription"
    # Free-key tier providers — the user mints a free key (no card), usage-limited.
    # We default these to "free" because that's how Mentor's setup wizard advertises
    # them; if a user uses a paid plan on one of these, they can hide it manually.
    if any(k in n for k in ("groq", "cerebras")):
        return "cloud", "free"
    if "openrouter" in b or "openrouter" in n:
        return "cloud", "free" if m.endswith(":free") or ":free" in m else "paid"
    if "google gemini" in n or "generativelanguage.googleapis" in b or "gemini" in n:
        return "cloud", "free"
    if "mistral" in n and "api.mistral.ai" in b:
        return "cloud", "free"
    if m.endswith(":free"):
        return "cloud", "free"
    return "cloud", "paid"


def setup_models_catalog_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/models/catalog")
    async def catalog(request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        """Every model from the endpoints YOU added, with kind+tier and whether
        it's currently hidden. Owner-scoped."""
        from core.database import SessionLocal, ModelEndpoint
        from src.auth_helpers import owner_filter
        owner = get_current_user(request) or ""
        out = []
        db = SessionLocal()
        try:
            q = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True)
            if owner:
                q = owner_filter(q, ModelEndpoint, owner)
            for ep in q.all():
                try:
                    ms = json.loads(ep.cached_models) if ep.cached_models else []
                except Exception:
                    ms = []
                try:
                    hidden = set(json.loads(ep.hidden_models)) if ep.hidden_models else set()
                except Exception:
                    hidden = set()
                for m in ms:
                    if not m:
                        continue
                    kind, tier = classify(ep.name, ep.base_url, m)
                    out.append({"spec": "%s@%s" % (m, ep.name), "model": m, "endpoint": ep.name,
                                "ep_id": str(ep.id), "kind": kind, "tier": tier, "hidden": m in hidden})
        finally:
            db.close()
        out.sort(key=lambda x: (x["hidden"], x["kind"] != "local", x["spec"].lower()))
        return {"models": out}

    @router.post("/api/models/visibility")
    async def visibility(request: Request, payload: Dict[str, Any] = Body(...),
                         _u: str = Depends(require_user)) -> Dict[str, Any]:
        """Show/hide a model everywhere by toggling its endpoint's hidden_models."""
        from core.middleware import require_admin
        require_admin(request)
        from core.database import SessionLocal, ModelEndpoint
        ep_id = str(payload.get("ep_id", ""))
        model = str(payload.get("model", ""))
        visible = bool(payload.get("visible", True))
        if not ep_id or not model:
            return {"ok": False, "error": "ep_id and model required"}
        db = SessionLocal()
        try:
            ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == ep_id).first()
            if not ep:
                return {"ok": False, "error": "endpoint not found"}
            try:
                hidden = set(json.loads(ep.hidden_models)) if ep.hidden_models else set()
            except Exception:
                hidden = set()
            if visible:
                hidden.discard(model)
            else:
                hidden.add(model)
            ep.hidden_models = json.dumps(sorted(hidden))
            db.commit()
        finally:
            db.close()
        return {"ok": True}

    return router
