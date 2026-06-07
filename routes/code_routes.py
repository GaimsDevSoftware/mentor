"""Code workspace API — a first-class Code pillar that does NOT depend on the
aider_code plugin being enabled. Project picker, model picker, and async edits
with live progress, all backed by src/code_edit.py.
"""
import asyncio
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from core.middleware import require_admin

_jobs: Dict[str, Dict] = {}


def _get(key, default=""):
    from src.settings import get_setting
    return get_setting(key, default)


def _set(key, value):
    from src.settings import load_settings, save_settings
    s = load_settings()
    s[key] = value
    save_settings(s)


def setup_code_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/code/status")
    async def status(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src.plugin_forge import aider_bin
        return {
            "aider_installed": bool(aider_bin()),
            "project": _get("aider_code_project", ""),
            "model": _get("aider_model", ""),
            "auto_branch": bool(_get("aider_code_auto_branch", True)),
        }

    @router.get("/api/code/projects")
    async def projects(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src.code_edit import find_git_repos
        repos = await asyncio.to_thread(find_git_repos)
        return {"projects": repos, "current": _get("aider_code_project", "")}

    @router.get("/api/code/models")
    async def models(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src.code_edit import list_local_models
        return {"models": await list_local_models(), "current": _get("aider_model", "")}

    async def _run_job(job_id, instruction, files, project, model):
        job = _jobs[job_id]
        job["status"] = "running"
        job["stage"] = "starting…"

        def _cb(stage):
            job["stage"] = stage

        try:
            from src.code_edit import run_edit
            auto_branch = bool(_get("aider_code_auto_branch", True))
            result = await run_edit(instruction, files, project, model,
                                    auto_branch=auto_branch, progress_cb=_cb)
            job["result"] = result
            job["status"] = "done" if result.get("exit_code") == 0 else "failed"
            if result.get("error"):
                job["stage"] = result["error"]
        except Exception as e:
            job["status"] = "failed"
            job["result"] = {"error": str(e), "exit_code": 1}
            job["stage"] = str(e)
        job["finished_at"] = time.time()
        # keep last 20 jobs
        if len(_jobs) > 20:
            for k in sorted(_jobs, key=lambda k: _jobs[k].get("started_at", 0))[:-20]:
                _jobs.pop(k, None)

    @router.post("/api/code/edit")
    async def edit(payload: Dict[str, Any] = Body(...), _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        instruction = (payload.get("instruction") or "").strip()
        files = payload.get("files") or []
        project = (payload.get("project") or _get("aider_code_project", "")).strip()
        model = (payload.get("model") or _get("aider_model", "")).strip()
        if not instruction:
            return {"ok": False, "error": "Describe the change first."}
        if not project:
            return {"ok": False, "error": "Pick a repository first."}
        if not model:
            return {"ok": False, "error": "Pick a coder model first."}
        # Remember the choices so chat's code_edit tool + next visit reuse them.
        if project != _get("aider_code_project", ""):
            _set("aider_code_project", project)
        if model != _get("aider_model", ""):
            _set("aider_model", model)
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "status": "queued", "stage": "queued",
                         "instruction": instruction, "started_at": time.time()}
        asyncio.create_task(_run_job(job_id, instruction, files, project, model))
        return {"ok": True, "job_id": job_id}

    @router.get("/api/code/jobs/{job_id}")
    async def job(job_id: str, _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        return _jobs.get(job_id) or {"error": "no such job"}

    return router
