"""Agents API — the Mentor "office" of user-created agents (employees).

CRUD over the JSON agent store, an AI "draft a system prompt" helper (so users
don't write prompts by hand), a capacity report (solo/private vs concurrent),
and a run endpoint that delegates a task across selected agents via the
capacity-aware orchestrator.
"""
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, Request

from src.auth_helpers import get_current_user, require_user


def setup_agents_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/agents")
    async def list_agents(request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import agents_store
        owner = get_current_user(request) or ""
        return {"agents": agents_store.list_agents(owner)}

    @router.post("/api/agents")
    async def create_agent(request: Request, payload: Dict[str, Any] = Body(...),
                           _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import agents_store
        owner = get_current_user(request) or ""
        try:
            return {"ok": True, "agent": agents_store.create_agent(payload, owner)}
        except ValueError as e:
            return {"ok": False, "detail": str(e)}

    @router.put("/api/agents/{aid}")
    async def update_agent(aid: str, request: Request, payload: Dict[str, Any] = Body(...),
                           _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import agents_store
        owner = get_current_user(request) or ""
        a = agents_store.update_agent(aid, payload, owner)
        return {"ok": bool(a), "agent": a}

    @router.delete("/api/agents/{aid}")
    async def delete_agent(aid: str, request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import agents_store
        owner = get_current_user(request) or ""
        return {"ok": agents_store.delete_agent(aid, owner)}

    @router.get("/api/agents/capacity")
    async def capacity(request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import agent_orchestrator
        return agent_orchestrator.capacity(get_current_user(request) or "")

    @router.get("/api/agents/models")
    async def models(request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        """Discovered models as `model@endpoint` specs, scoped to the caller — so
        the Office model dropdown works for non-admins (unlike the admin-only
        teacher-model-options)."""
        from core.database import SessionLocal, ModelEndpoint
        from src.auth_helpers import owner_filter
        try:
            from src.endpoint_resolver import normalize_base, _is_local_base
        except Exception:
            normalize_base = None
            _is_local_base = None
        owner = get_current_user(request) or ""
        out: List[Dict[str, Any]] = []
        seen = set()
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
                # local = private + free + on your hardware; cloud = capable but
                # costs money and sends data out. This is the signal that lets a
                # user pick a helper's model by cost / privacy.
                kind = "cloud"
                try:
                    if normalize_base and _is_local_base and _is_local_base(normalize_base(ep.base_url)):
                        kind = "local"
                except Exception:
                    pass
                for m in ms:
                    if not m:
                        continue
                    spec = f"{m}@{ep.name}"
                    if spec not in seen:
                        seen.add(spec)
                        out.append({"spec": spec, "model": m, "endpoint": ep.name, "kind": kind})
        finally:
            db.close()
        # Local first (private/free), then alphabetical — the safe default.
        out.sort(key=lambda x: (x["kind"] != "local", x["spec"].lower()))
        return {"models": [o["spec"] for o in out], "details": out}

    @router.post("/api/agents/draft")
    async def draft(request: Request, payload: Dict[str, Any] = Body(...),
                    _u: str = Depends(require_user)) -> Dict[str, Any]:
        """Draft a system prompt from role + goal + personality + backstory, so a
        non-technical user never writes one by hand."""
        role = str(payload.get("role", "")).strip()
        goal = str(payload.get("goal", "")).strip()
        personality = str(payload.get("personality", "")).strip()
        backstory = str(payload.get("backstory", "")).strip()
        name = str(payload.get("name", "")).strip() or "the agent"
        if not role and not goal:
            return {"ok": False, "detail": "give at least a role or a goal first"}
        try:
            from src.settings import get_setting as _gs
            spec = (_gs("improve_teacher_model", "") or _gs("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "No AI configured. Set teacher_model (a local coder is free)."}
        prompt = (
            f"Write a tight system prompt for an AI agent named '{name}' that works as a "
            f"team member in a personal AI 'office'.\n"
            f"Role/title: {role or '(unspecified)'}\n"
            f"Goal (the outcome it optimizes for): {goal or '(unspecified)'}\n"
            f"Personality: {personality or 'professional, concise'}\n"
            f"Backstory/working style: {backstory or '(none given)'}\n\n"
            f"Output ONLY the system prompt text (no preamble). 4-8 sentences. Make the role "
            f"SPECIFIC and competence-first; let personality flavor the tone, not dominate. "
            f"Tell it to use its tools when useful and to say when it's unsure.")
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You write crisp, effective agent system prompts."},
                 {"role": "user", "content": prompt}],
                headers=headers or {}, max_tokens=600, timeout=90)
            return {"ok": True, "system_prompt": (reply or "").strip()}
        except Exception as e:
            return {"ok": False, "detail": f"AI call failed: {e}"}

    @router.get("/api/agents/room")
    async def room(request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import office_room
        return {"messages": office_room.get(get_current_user(request) or "")}

    @router.delete("/api/agents/room")
    async def clear_room(request: Request, _u: str = Depends(require_user)) -> Dict[str, Any]:
        from src import office_room
        office_room.clear(get_current_user(request) or "")
        return {"ok": True}

    @router.post("/api/agents/say")
    async def say(request: Request, payload: Dict[str, Any] = Body(...),
                  _u: str = Depends(require_user)) -> Dict[str, Any]:
        """Send a message to one agent (DM) or the whole team. Frugal by design:
        a DM = 1 model call; a team message is capped (orchestrator caps to the
        capacity budget AND office_max_agents) and mediated by a synthesis — no
        free agent-to-agent chatter."""
        from src import agents_store, agent_orchestrator, office_room
        from src.settings import get_setting
        owner = get_current_user(request) or ""
        text = str(payload.get("text", "")).strip()
        target = str(payload.get("target", "team")).strip() or "team"
        if not text:
            return {"ok": False, "detail": "empty message"}
        out: List[Dict[str, Any]] = []
        out.append(office_room.append(owner, {"role": "user", "text": text}))

        if target != "team":
            agent = agents_store.get_agent(target, owner)
            if not agent:
                return {"ok": False, "detail": "no such agent"}
            r = await agent_orchestrator.run_one(agent, text, owner)
            out.append(office_room.append(owner, {
                "role": "agent", "agent_id": agent["id"], "agent_name": agent.get("name", ""),
                "color": agent.get("color", ""), "text": r.get("output", "")}))
            return {"ok": True, "messages": out}

        # Team: cap how many agents actually get called (token frugality).
        try:
            cap = int(get_setting("office_max_agents", 3) or 3)
        except Exception:
            cap = 3
        agents = agents_store.list_agents(owner)[:max(1, cap)]
        if not agents:
            return {"ok": False, "detail": "hire an agent first"}
        result = await agent_orchestrator.run_task(text, agents, owner)
        for c in result.get("contributions", []):
            if c.get("ok"):
                out.append(office_room.append(owner, {
                    "role": "agent", "agent_name": c.get("agent", ""),
                    "text": c.get("output", "")}))
        if result.get("synthesis"):
            out.append(office_room.append(owner, {
                "role": "team", "agent_name": "Team", "text": result["synthesis"]}))
        return {"ok": True, "messages": out, "capacity": result.get("capacity")}

    return router
