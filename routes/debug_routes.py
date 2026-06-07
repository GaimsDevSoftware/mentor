"""Cookbook debugger route — one endpoint that explains what is wrong.

Surfaces the unified diagnostics engine (src/debugger.py) under the cookbook
namespace. Admin-only: it reveals serving/endpoint/plugin internals. Read-only
and safe (no heavy work), so it's cheap to poll from the UI.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from core.middleware import require_admin


def setup_debug_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/cookbook/debug")
    async def cookbook_debug(
        only_failures: bool = Query(False, description="return only warn/error findings"),
        _admin: str = Depends(require_admin),
    ) -> Dict[str, Any]:
        """Run all diagnostics (serving, embeddings/Chroma, plugins + their
        self-checks, Aegis, autonomous loop, fleet) and return a grouped report
        with plain-language problems[] and actionable hints."""
        from src import debugger
        return debugger.run_all(only_failures=only_failures)

    @router.post("/api/cookbook/debug/fix")
    async def cookbook_debug_fix(
        payload: Dict[str, Any],
        _admin: str = Depends(require_admin),
    ) -> Dict[str, Any]:
        """One-click remediation. Pass the `fix` object from a debug finding:
          • setting  → flips a whitelisted setting instantly
          • command  → launches a vetted background command (e.g. reindex)
          • plugin_repair → plugin self-heals, else Copilot rewrites the plugin's
            code (scoped to plugins/<name>/ — never the core app), verified by reload
        Returns {ok, detail, ...}."""
        from src import copilot_fix
        fix = payload.get("fix", payload)
        result = await copilot_fix.apply_fix(fix, owner=_admin)
        return result

    @router.get("/api/cookbook/sources")
    async def cookbook_sources(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Models grouped by registered source — one section per cookbook provider
        (local fleet catalog, plus each logged-in model source like OpenCode Zen).
        The Cookbook renders these as separate sections; Copilot recommendations
        come from each source's /api/plugins/<slug>/recommend."""
        from src import plugin_system
        sections = []
        for prov in plugin_system.get_cookbook_providers():
            try:
                catalog = prov.catalog() if hasattr(prov, "catalog") else []
            except Exception:
                catalog = []
            sections.append({
                "name": getattr(prov, "name", "source"),
                "remote": any(isinstance(m, dict) and m.get("remote") for m in catalog),
                "count": len(catalog),
                "models": catalog,
            })
        return {"sections": sections}

    @router.post("/api/cookbook/recommend")
    async def cookbook_recommend(scope: str = Query(None, description="local|sources|both"),
                                 _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Copilot recommends role→model. Optional ?scope=local|sources|both
        overrides the recommend_scope setting for this call."""
        from src import recommend
        return await recommend.recommend_roles(scope=scope)

    @router.get("/api/cookbook/route")
    async def cookbook_route(q: str = Query(..., description="the task/request text"),
                             scope: str = Query(None),
                             _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Smart escalation routing: which model tier to START at for this task,
        plus the available escalation ladder (availability + budget aware)."""
        from src import router as rt
        return rt.route(q, scope=scope)

    return router
