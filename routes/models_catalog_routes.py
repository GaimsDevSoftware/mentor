"""Model catalog — the user's OWN connected models with tier/kind metadata, plus
a per-model visibility toggle (hidden_models). One source of truth so the chat
picker, role dropdowns and onboarding all show only what the user added and chose
to keep, filterable by free / paid / subscription / local / cloud.
"""
import json
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, Request

from src.auth_helpers import get_current_user, require_user


def classify(name: str, base: str, model_id: str):
    """Return (kind, tier) for a model. kind=local|cloud, tier=free|paid|subscription."""
    n = (name or "").lower()
    b = (base or "").lower()
    m = (model_id or "").lower()
    sub = (any(k in n for k in ("chatgpt", "codex", "claude", "opencode", "zen"))
           or any(k in b for k in ("opencode", "/zen", "ollama.com")))
    local = any(h in b for h in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1"))
    if sub:
        return "cloud", "subscription"
    if local:
        return "local", "free"
    if m.endswith(":free") or ("openrouter" in b and ":free" in m):
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
