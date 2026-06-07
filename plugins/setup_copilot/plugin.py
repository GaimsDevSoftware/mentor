"""setup_copilot — onboarding guide + safe plugin builder.

Two jobs, both aimed at non-technical users:

1) GUIDE: turn the debugger's findings into a plain-language, ordered checklist —
   "from fresh install to working" — each step with why it matters and a one-click
   fix where one exists. Tool `setup_status`, route GET /api/plugins/setup/plan.

2) BUILD ("vibe coding"): the agent asks the user short probing questions until the
   intent is clear, then calls `build_plugin` — the teacher writes a small plugin,
   which is created DISABLED, compiled, and load-verified. The user reviews the code
   and explicitly enables it (`enable_plugin`). Nothing generated runs until enabled.
"""
from __future__ import annotations

import json

_api = None

# Plain-language milestones, each tied to debugger findings (area, name-prefix).
_MILESTONES = [
    ("talk", "Talk to a model",
     "You need at least one AI model reachable — local (Ollama) or a connected source.",
     [("fleet", "ollama"), ("plugin:opencode", "opencode-login")]),
    ("memory", "Turn on memory & search",
     "Memory and document search need the vector database (ChromaDB) running.",
     [("embeddings", "chromadb")]),
    ("embeddings", "Pick & index the embedding model",
     "The right (multilingual) embedding model makes search and memory accurate.",
     [("embeddings", "index-state")]),
    ("safety", "Turn on the safety firewall",
     "Aegis checks risky tool actions before they run — recommended once you use agents.",
     [("aegis", "mode")]),
]


def _setup_plan() -> dict:
    from src import debugger
    rep = debugger.run_all()
    found = {}
    for g in rep["groups"].values():
        for r in g:
            found[(r["area"], r["name"])] = r

    def _match(area, prefix):
        for (a, n), r in found.items():
            if a == area and n.startswith(prefix):
                return r
        return None

    steps = []
    done_count = 0
    for key, title, why, refs in _MILESTONES:
        ref = None
        for area, prefix in refs:
            ref = _match(area, prefix)
            if ref:
                break
        status = "done" if (ref and ref.get("status") == "ok") else "todo"
        if status == "done":
            done_count += 1
        step = {"key": key, "title": title, "why": why, "status": status,
                "detail": (ref.get("detail") if ref else "not detected yet"),
                "hint": (ref.get("hint") if ref else "")}
        if ref and ref.get("fix"):
            step["fix"] = ref["fix"]  # one-click via POST /api/cookbook/debug/fix
        steps.append(step)

    pct = round(done_count / len(_MILESTONES) * 100)
    return {"overall": rep["overall"], "progress_pct": pct,
            "done": done_count, "total": len(_MILESTONES),
            "next": next((s for s in steps if s["status"] == "todo"), None),
            "steps": steps}


# ── tools ───────────────────────────────────────────────────────────────────

async def _setup_status(content, owner):
    plan = _setup_plan()
    nxt = plan.get("next")
    msg = (f"Setup is {plan['progress_pct']}% done ({plan['done']}/{plan['total']}). "
           + (f"Next: {nxt['title']} — {nxt['why']}" if nxt else "Everything's ready! 🎉"))
    return {"response": msg, **plan, "exit_code": 0}


async def _build_plugin(content, owner):
    """content: JSON {name, intent, overwrite?}. Generates a DISABLED draft."""
    try:
        args = json.loads(content) if content and content.strip().startswith("{") else {}
    except (ValueError, TypeError):
        args = {}
    name = (args.get("name") or "").strip()
    intent = (args.get("intent") or "").strip()
    if not name or not intent:
        return {"error": "Need {name, intent}. Ask the user what the plugin should do, "
                         "then call again with a clear name and a detailed intent.", "exit_code": 1}
    from src import plugin_forge
    res = await plugin_forge.build_plugin(name, intent, overwrite=bool(args.get("overwrite")))
    if not res.get("ok"):
        return {"error": res.get("detail"), "raw": res.get("raw"), "exit_code": 1}
    return {"response": res["detail"], "slug": res["slug"], "would_load": res.get("would_load"),
            "code": res.get("code"), "manifest": res.get("manifest"), "exit_code": 0}


async def _recommend_models(content, owner):
    """content: optional JSON {scope: local|sources|both}. Recommends role→model
    across the chosen scope (honours the recommend_scope setting by default)."""
    scope = None
    try:
        if content and content.strip().startswith("{"):
            scope = (json.loads(content).get("scope") or "").strip() or None
    except (ValueError, TypeError):
        pass
    from src import recommend
    res = await recommend.recommend_roles(scope=scope)
    if not res.get("ok"):
        return {"error": res.get("detail"), "candidates": res.get("candidates"), "exit_code": 1}
    return {"response": f"Recommended roles (scope: {res['scope']})", **res, "exit_code": 0}


async def _route_task(content, owner):
    """content: JSON {request, scope?}. Smart escalation routing — which tier to
    start at for this task + the available ladder."""
    req, scope = "", None
    try:
        if content and content.strip().startswith("{"):
            d = json.loads(content)
            req = (d.get("request") or "").strip()
            scope = (d.get("scope") or "").strip() or None
        else:
            req = (content or "").strip()
    except (ValueError, TypeError):
        req = (content or "").strip()
    if not req:
        return {"error": "Need the task text (request) to route.", "exit_code": 1}
    from src import router as rt
    return {"response": "Routing decision", **rt.route(req, scope=scope), "exit_code": 0}


async def _enable_plugin(content, owner):
    try:
        args = json.loads(content) if content and content.strip().startswith("{") else {"slug": content.strip()}
    except (ValueError, TypeError):
        args = {"slug": (content or "").strip()}
    slug = (args.get("slug") or "").strip()
    if not slug:
        return {"error": "Need {slug} of the draft to enable.", "exit_code": 1}
    from src import plugin_forge
    res = plugin_forge.enable_plugin(slug)
    return ({"response": res["detail"], "exit_code": 0} if res.get("ok")
            else {"error": res["detail"], "exit_code": 1})


# ── hooks ───────────────────────────────────────────────────────────────────

def _prompt_hook(prompt, context):
    return prompt + (
        "\n\n## Setup & extend (be a patient guide)\n"
        "Help the user go from fresh install to a working setup. If anything isn't working, "
        "call `setup_status` for a plain-language checklist and offer the one-click fixes. "
        "You can also BUILD a simple plugin when the user wants a new capability: ask SHORT "
        "probing questions until you clearly understand what they want, then call `build_plugin` "
        "with a clear name and a detailed intent. Generated plugins are created DISABLED — show "
        "the user what it does, then call `enable_plugin` only after they confirm. Assume no "
        "technical background; speak simply.")


def _diagnostic():
    # MUST stay cheap and must NOT call debugger.run_all() — this hook runs INSIDE
    # the debugger, so calling run_all() here would recurse. The full plan is
    # available via the setup_status tool / GET /api/plugins/setup/plan.
    return {"name": "setup-guide", "status": "ok",
            "detail": "setup guide ready — call setup_status for the checklist",
            "hint": ""}


def register(api):
    global _api
    _api = api
    api.register_tool("setup_status", _setup_status,
                      description="Plain-language setup checklist: what's done and the next step "
                                  "to reach a working install.", risk_category="read")
    api.register_tool("build_plugin", _build_plugin,
                      description="Build a simple plugin for the user from a clear intent. Ask "
                                  "probing questions first. Creates a DISABLED draft to review.",
                      risk_category="data-write")
    api.register_tool("enable_plugin", _enable_plugin,
                      description="Enable a plugin draft after the user has reviewed it.",
                      risk_category="data-write")
    api.register_tool("recommend_models", _recommend_models,
                      description="Recommend which model to run for each role. Optional JSON "
                                  "{scope:'local'|'sources'|'both'}.", risk_category="read")
    api.register_tool("route_task", _route_task,
                      description="Smart escalation routing: which model tier to start at for a "
                                  "task + the escalation ladder. JSON {request, scope?}.",
                      risk_category="read")
    api.register_hook("build_prompt", _prompt_hook)
    api.register_hook("diagnostic", _diagnostic)
    api.register_settings([
        {"key": "plugin_builder_backend", "label": "Plugin builder backend", "type": "select",
         "options": ["auto", "aider", "teacher"], "default": "auto"},
        {"key": "aider_model", "label": "Aider model (free coder)", "type": "select",
         "suggest_url": "/api/manage/aider/models", "default": "",
         "desc": "The local/free coder model Aider uses to edit code. Pick a discovered model "
                 "from the list — a local Ollama coder (e.g. qwen3-coder) is free and private."},
        {"key": "recommend_scope", "label": "Recommend scope", "type": "select",
         "options": ["both", "local", "sources"], "default": "both"},
    ])

    try:
        from fastapi import APIRouter, Body, Depends
        from core.middleware import require_admin
        router = APIRouter()

        @router.get("/api/plugins/setup/plan")
        async def setup_plan(admin: str = Depends(require_admin)):
            return _setup_plan()

        @router.post("/api/plugins/forge/build")
        async def forge_build(payload: dict = Body(default={}), admin: str = Depends(require_admin)):
            from src import plugin_forge
            return await plugin_forge.build_plugin(payload.get("name", ""), payload.get("intent", ""),
                                                   overwrite=bool(payload.get("overwrite")))

        @router.post("/api/plugins/forge/enable")
        async def forge_enable(payload: dict = Body(default={}), admin: str = Depends(require_admin)):
            from src import plugin_forge
            return plugin_forge.enable_plugin(payload.get("slug", ""))

        api.register_router(router)
    except Exception as e:
        api.logger.debug("setup_copilot routes skipped: %s", e)
