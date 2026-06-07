"""ModelSource — reusable base for "add your own model source" plugins.

A plugin that wires up a model provider (an OpenAI-compatible API key source like
OpenCode Zen / OpenRouter / Together, or an OAuth / CLI-backed source) shouldn't
re-implement credential resolution, endpoint registration, discovery, status,
diagnostics and repair every time. Declare a ModelSource and call `.mount(api)`;
the framework gives you, for free:

  • login/status routes  → /api/plugins/<slug>/login (POST), /status (GET)
  • a `<slug>_models` tool that lists the provider's models
  • a debugger diagnostic + one-click repair (reconnect)
  • registration of an Odysseus ModelEndpoint so the models are usable as
    `model@<Name>` and auto-discovered via /v1/models.

Credential kinds:
  • api_key (default): resolved pasted → env_var → auth.json (paths × providers)
  • custom/oauth:       pass `resolve=fn(pasted)->(credential, source)` — e.g. read
                        an OAuth token file, or shell out to a CLI. `auth_header`
                        lets non-Bearer schemes set their own header.

Minimal example (an API-key source in a plugin's register()):

    from src.model_source import ModelSource
    SRC = ModelSource(name="OpenRouter", slug="openrouter",
                      base_url="https://openrouter.ai/api/v1",
                      env_var="OPENROUTER_API_KEY")
    def register(api):
        SRC.mount(api)
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, List, Optional, Tuple


class ModelSource:
    def __init__(self, *, name: str, base_url: str, slug: Optional[str] = None,
                 auth_kind: str = "api_key",
                 env_var: Optional[str] = None,
                 auth_json_paths: Optional[List[str]] = None,
                 auth_json_providers: Optional[List[str]] = None,
                 resolve: Optional[Callable[[Optional[str]], Tuple[Optional[str], str]]] = None,
                 auth_header: Optional[Callable[[str], dict]] = None,
                 model_filter: Optional[Callable[[str], bool]] = None,
                 tier_fn: Optional[Callable[[str], str]] = None,
                 models: Optional[List[str]] = None):
        self.name = name
        self.slug = slug or "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
        self.base_url = base_url.rstrip("/")
        self.auth_kind = auth_kind
        self.env_var = env_var
        self.auth_json_paths = auth_json_paths or []
        self.auth_json_providers = auth_json_providers or []
        self._resolve = resolve
        self._auth_header = auth_header or (lambda c: {"Authorization": f"Bearer {c}"})
        self.model_filter = model_filter  # (model_id)->bool; None = keep all
        self.tier_fn = tier_fn  # (model_id)->"free"|"subscription"|"paid"; None = unknown
        self.static_models = models or []
        self._logger = None
        self._models_cache: Optional[List[str]] = None

    # ── credential resolution ────────────────────────────────────────────────
    def _from_auth_json(self) -> Optional[str]:
        for p in self.auth_json_paths:
            if not p or not os.path.exists(p):
                continue
            try:
                data = json.loads(open(p, encoding="utf-8").read())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for prov in self.auth_json_providers:
                entry = data.get(prov)
                if isinstance(entry, dict) and entry.get("key"):
                    return entry["key"]
                if isinstance(entry, str) and entry:
                    return entry
            for k, v in data.items():
                if any(pr in k.lower() for pr in self.auth_json_providers):
                    if isinstance(v, dict) and v.get("key"):
                        return v["key"]
        return None

    def resolve_credential(self, pasted: Optional[str] = None) -> Tuple[Optional[str], str]:
        if self._resolve:
            return self._resolve(pasted)
        if pasted and pasted.strip():
            return pasted.strip(), "pasted"
        if self.env_var:
            env = os.environ.get(self.env_var, "").strip()
            if env:
                return env, "env"
        k = self._from_auth_json()
        if k:
            return k, "auth.json"
        return None, "none"

    # ── endpoint registration ────────────────────────────────────────────────
    def register_endpoint(self, credential: str, owner: Optional[str] = None) -> str:
        from core.database import SessionLocal, ModelEndpoint
        from datetime import datetime
        import uuid
        db = SessionLocal()
        try:
            ep = db.query(ModelEndpoint).filter(ModelEndpoint.name == self.name).first()
            if ep:
                ep.base_url = self.base_url
                ep.api_key = credential
                ep.is_enabled = True
                ep.updated_at = datetime.utcnow()
                action = "updated"
            else:
                kw = dict(id=uuid.uuid4().hex[:12], name=self.name, base_url=self.base_url,
                          api_key=credential, is_enabled=True,
                          created_at=datetime.utcnow(), updated_at=datetime.utcnow())
                if hasattr(ModelEndpoint, "owner") and owner:
                    kw["owner"] = owner
                db.add(ModelEndpoint(**kw))
                action = "created"
            db.commit()
            return action
        finally:
            db.close()

    def endpoint_exists(self) -> bool:
        from core.database import SessionLocal, ModelEndpoint
        db = SessionLocal()
        try:
            return db.query(ModelEndpoint).filter(
                ModelEndpoint.name == self.name,
                ModelEndpoint.is_enabled == True).first() is not None  # noqa: E712
        finally:
            db.close()

    def probe_models(self, credential: str, timeout: int = 8) -> Tuple[bool, Any]:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/models",
                          headers=self._auth_header(credential), timeout=timeout)
            if r.status_code == 401:
                return False, "unauthorized (bad/expired credential)"
            r.raise_for_status()
            data = r.json()
            items = data.get("data", data) if isinstance(data, dict) else data
            ids = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
            return True, ids or self.static_models
        except Exception as e:
            if self.static_models:
                return True, self.static_models
            return False, str(e)

    # ── diagnostic + repair ──────────────────────────────────────────────────
    def diagnostic(self) -> dict:
        cred, src = self.resolve_credential()
        if not cred:
            return {"name": f"{self.slug}-login", "status": "warn",
                    "detail": f"not connected to {self.name}",
                    "hint": f"POST /api/plugins/{self.slug}/login with your key"
                            + (f" (or set {self.env_var})" if self.env_var else "")}
        if not self.endpoint_exists():
            return {"name": f"{self.slug}-login", "status": "warn",
                    "detail": f"credential found ({src}) but endpoint not registered",
                    "hint": "click reconnect or POST the login route"}
        return {"name": f"{self.slug}-login", "status": "ok",
                "detail": f"connected via {src}; endpoint '{self.name}' registered"}

    def repair(self, finding: dict) -> dict:
        cred, src = self.resolve_credential()
        if not cred:
            return {"ok": False, "detail": f"no credential found for {self.name} — log in to provide one"}
        action = self.register_endpoint(cred)
        return {"ok": True, "detail": f"reconnected {self.name} from {src}; endpoint {action}"}

    # ── cookbook section: this source's models as a catalog ──────────────────
    def list_models(self, refresh: bool = False) -> List[str]:
        # Cache the RAW id list; apply the (settings-driven) filter on each call so
        # toggling e.g. include-paid re-filters without re-probing the network.
        if self._models_cache is None or refresh:
            cred, _ = self.resolve_credential()
            if not cred:
                self._models_cache = list(self.static_models)
            else:
                ok, res = self.probe_models(cred)
                self._models_cache = list(res) if ok else list(self.static_models)
        ids = self._models_cache
        if self.model_filter:
            try:
                ids = [i for i in ids if self.model_filter(i)]
            except Exception:
                pass
        return ids

    def cookbook_provider(self):
        src = self

        class _Provider:
            name = self.name

            def catalog(self_inner):
                # Empty until logged in — the section appears once a credential
                # is registered. Remote/cloud models (no local VRAM fit). Each
                # entry carries a `tier` (free / subscription / paid) so the UI
                # can label / colour them accordingly.
                cred, _ = src.resolve_credential()
                if not cred:
                    return []
                out = []
                for m in src.list_models():
                    d = {"model": m, "source": src.name, "remote": True,
                         "endpoint": src.name}
                    if src.tier_fn:
                        try:
                            d["tier"] = src.tier_fn(m)
                        except Exception:
                            pass
                    out.append(d)
                return out

            def profiles(self_inner):
                return []

        return _Provider()

    # ── Copilot role recommendation over the source's models ─────────────────
    async def recommend(self, fleet_context: str = "") -> dict:
        """Ask the teacher model which model to use for each role. These are
        remote models, so it's a role/quality judgement, not a VRAM-fit one."""
        models = self.list_models()
        if not models:
            return {"ok": False, "detail": f"no models available from {self.name} (log in first)"}
        try:
            from src.settings import get_setting
            spec = (get_setting("improve_teacher_model", "") or get_setting("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "no teacher model configured for recommendations",
                    "models": models}
        prompt = (
            f"You advise on model selection for a personal AI control center.\n"
            f"Available REMOTE models from {self.name} (cloud — no local VRAM needed; "
            f"treat as an escalation/quality tier):\n{', '.join(models)}\n\n"
            f"{fleet_context}\n\n"
            "Recommend the single best model for each role. Roles: coder, planner "
            "(reasoning/agentic), vision, cheap-utility, chat-generalist. Only use "
            "models from the list. Reply with ONE fenced ```json block: "
            '{"coder":{"model":"..","why":".."}, "planner":{...}, "vision":{...}, '
            '"cheap_utility":{...}, "chat_generalist":{...}}.')
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You are a concise model-selection advisor."},
                 {"role": "user", "content": prompt}],
                headers=headers, max_tokens=1200, timeout=120)
        except Exception as e:
            return {"ok": False, "detail": f"recommendation call failed: {e}", "models": models}
        import json as _json
        import re as _re
        m = _re.search(r"```(?:json)?\s*\n(\{.*?\})\s*\n```", reply or "", _re.S) or \
            _re.search(r"(\{.*\})", reply or "", _re.S)
        try:
            rec = _json.loads(m.group(1)) if m else {}
        except Exception:
            rec = {}
        return {"ok": True, "source": self.name, "recommendations": rec,
                "models": models, "raw": (reply or "")[:400] if not rec else None}

    # ── one call wires everything into a plugin ──────────────────────────────
    def mount(self, api) -> None:
        self._logger = api.logger
        api.register_hook("diagnostic", self.diagnostic)
        api.register_repair(self.repair)
        # Expose the source's models as a Cookbook section (needs "cookbook" perm).
        try:
            api.register_cookbook_provider(self.cookbook_provider())
        except Exception as e:
            if self._logger:
                self._logger.debug("%s cookbook provider skipped: %s", self.name, e)

        async def _models_tool(content, owner):
            cred, src = self.resolve_credential()
            if not cred:
                return {"error": f"Not connected to {self.name}. Log in via "
                                 f"/api/plugins/{self.slug}/login.", "exit_code": 1}
            ok, res = self.probe_models(cred)
            if not ok:
                return {"error": f"{self.name} model probe failed: {res}", "exit_code": 1}
            return {"response": f"{len(res)} {self.name} models available",
                    "models": res, "endpoint": self.name, "exit_code": 0}

        api.register_tool(f"{self.slug}_models", _models_tool,
                          description=f"List the {self.name} models available after login.",
                          risk_category="read")

        try:
            from fastapi import APIRouter, Body, Depends
            from core.middleware import require_admin
            router = APIRouter()

            @router.post(f"/api/plugins/{self.slug}/login")
            async def _login(payload: dict = Body(default={}), admin: str = Depends(require_admin)):
                cred, src = self.resolve_credential(payload.get("api_key") or payload.get("credential"))
                if not cred:
                    return {"ok": False, "detail": f"no credential provided and none found for {self.name}"}
                ok, res = self.probe_models(cred)
                if not ok:
                    return {"ok": False, "detail": f"credential rejected by {self.name}: {res}"}
                action = self.register_endpoint(cred, owner=admin)
                # Subscription hint: surface what was actually returned so the user
                # sees "Go" when Go-family models are present, not a hardcoded label.
                hint = ""
                if self.slug == "opencode":
                    GO = ("glm", "kimi", "mimo", "qwen3.7", "qwen3.6", "minimax", "deepseek")
                    if any(any(g in str(m).lower() for g in GO) for m in res):
                        hint = " · Go subscription models detected"
                return {"ok": True, "source": src, "endpoint": self.name, "action": action,
                        "models": len(res), "subscription_hint": hint.strip(" ·"),
                        "detail": f"Connected to {self.name} ({len(res)} models){hint}. "
                                  f"Use them as 'model@{self.name}'."}

            @router.get(f"/api/plugins/{self.slug}/status")
            async def _status(admin: str = Depends(require_admin)):
                cred, src = self.resolve_credential()
                registered = self.endpoint_exists() if cred else False
                info = {"name": self.name, "logged_in": bool(cred), "credential_source": src,
                        "endpoint_registered": registered, "base_url": self.base_url}
                if cred and registered:
                    models = self.list_models()
                    info["models"] = len(models)
                    if self.slug == "opencode":
                        GO = ("glm", "kimi", "mimo", "qwen3.7", "qwen3.6", "minimax", "deepseek")
                        if any(any(g in str(m).lower() for g in GO) for m in models):
                            info["subscription"] = "Go subscription"
                        else:
                            info["subscription"] = "Zen pay-as-you-go"
                return info

            @router.post(f"/api/plugins/{self.slug}/disconnect")
            async def _disconnect(admin: str = Depends(require_admin)):
                """Delete the stored credential + endpoint. Like Apple's 'Sign Out'
                — drops the key, leaves the plugin installed for later reconnect."""
                from core.database import SessionLocal, ModelEndpoint
                db = SessionLocal()
                try:
                    ep = db.query(ModelEndpoint).filter(ModelEndpoint.name == self.name).first()
                    if not ep:
                        return {"ok": False, "detail": "not connected"}
                    db.delete(ep)
                    db.commit()
                    # also drop the in-memory model cache so a re-login re-probes
                    self._models_cache = None
                    return {"ok": True, "detail": f"Signed out of {self.name}. The API key was removed."}
                finally:
                    db.close()

            @router.get(f"/api/plugins/{self.slug}/models")
            async def _models(admin: str = Depends(require_admin)):
                # The cookbook "section" data for this source.
                return {"name": self.name, "endpoint": self.name,
                        "remote": True, "models": self.list_models(refresh=True)}

            @router.post(f"/api/plugins/{self.slug}/recommend")
            async def _recommend(payload: dict = Body(default={}),
                                 admin: str = Depends(require_admin)):
                # Copilot recommends role→model over this source's models.
                return await self.recommend(fleet_context=payload.get("fleet_context", ""))

            api.register_router(router)
        except Exception as e:
            if self._logger:
                self._logger.debug("%s route mount skipped: %s", self.name, e)
