"""Agents API — the Mentor "office" of user-created agents (employees).

CRUD over the JSON agent store, an AI "draft a system prompt" helper (so users
don't write prompts by hand), a capacity report (solo/private vs concurrent),
and a run endpoint that delegates a task across selected agents via the
capacity-aware orchestrator.
"""
from typing import Any, Dict

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

    @router.post("/api/agents/run")
    async def run(request: Request, payload: Dict[str, Any] = Body(...),
                  _u: str = Depends(require_user)) -> Dict[str, Any]:
        """Give the team (selected agents, or all) a task; capacity-aware."""
        from src import agents_store, agent_orchestrator
        owner = get_current_user(request) or ""
        task = str(payload.get("task", "")).strip()
        ids = payload.get("agent_ids") or []
        alla = agents_store.list_agents(owner)
        agents = [a for a in alla if a.get("id") in ids] if ids else alla
        return await agent_orchestrator.run_task(task, agents, owner)

    return router
