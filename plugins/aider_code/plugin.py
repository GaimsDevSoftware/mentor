"""aider_code — vibe-code a real project from inside Odysseus, via Aider.

Tool `code_edit`: {instruction, files?}. Runs Aider (free, git-aware, BYO local
model) inside ONE configured project directory, applies the change, and returns
the `git diff` for you to review. So from chat / Telegram / the UI you can say
"add retries to the upload handler" and get a real, reviewable code edit — using
a local coder model, no paid API.

Safety: disabled by default (it edits real files); scoped to `aider_code_project`
only; runs with --no-auto-commits (you review the diff, nothing is committed);
the tool call still passes through Aegis. Needs `aider` on PATH (see uv install).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil

_api = None


def _cfg(k, d):
    try:
        return _api.get_setting(k, d)
    except Exception:
        return d


async def _code_edit(content, owner):
    """Chat/Telegram `code_edit` tool — delegates to the shared engine so the UI
    Code page and this tool run edits identically (one source of truth)."""
    try:
        args = json.loads(content) if content and content.strip().startswith("{") else {"instruction": content}
    except (ValueError, TypeError):
        args = {"instruction": content}
    instruction = (args.get("instruction") or "").strip()
    files = args.get("files") or []
    project = (_cfg("aider_code_project", "") or "").strip()
    model = (_cfg("aider_model", "") or "").strip()
    if not project:
        return {"error": "Set up a project in the Code page first (or set aider_code_project).", "exit_code": 1}
    if not model:
        return {"error": "Pick a coder model in the Code page first (or set aider_model).", "exit_code": 1}
    from src.code_edit import run_edit
    return await run_edit(instruction, files, project, model,
                          auto_branch=bool(_cfg("aider_code_auto_branch", True)))


def _diagnostic():
    from src.plugin_forge import aider_bin
    has_aider = bool(aider_bin())
    project = (_cfg("aider_code_project", "") or "").strip()
    model = (_cfg("aider_model", "") or "").strip()
    problems = []
    if not has_aider:
        problems.append("aider not on PATH (uv tool install --python 3.12 aider-chat)")
    if not project or not os.path.isdir(project):
        problems.append("aider_code_project not set/valid")
    if not model:
        problems.append("aider_model not set")
    if problems:
        return {"name": "aider-code", "status": "warn", "detail": "; ".join(problems),
                "hint": "fix these to enable vibe-coding via Aider"}
    return {"name": "aider-code", "status": "ok", "detail": f"ready · project={project} · model={model}"}


def _stats():
    project = (_cfg("aider_code_project", "") or "").strip()
    if not project or not os.path.isdir(project):
        return {"metrics": [{"label": "Status", "value": "Not configured"}],
                "insight": "Set aider_code_project to a git repo to start vibe-coding.",
                "status": "none"}
    import subprocess
    import time as _t
    # List aider/* branches with their last-commit unix time (committerdate).
    branches = []
    stale = []
    try:
        out = subprocess.run(
            ["git", "-C", project, "for-each-ref", "--format=%(refname:short) %(committerdate:unix)",
             "refs/heads/aider/"], capture_output=True, text=True, timeout=5)
        now = _t.time()
        for line in (out.stdout or "").strip().split("\n"):
            if not line.strip():
                continue
            parts = line.rsplit(" ", 1)
            name = parts[0]
            ts = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
            branches.append(name)
            age_days = (now - ts) / 86400 if ts else 0
            if age_days > 14:
                stale.append((name, int(age_days)))
    except Exception:
        pass
    # current branch
    try:
        cur = subprocess.run(["git", "-C", project, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        cur = "?"
    metrics = [
        {"label": "Project", "value": os.path.basename(project.rstrip("/"))},
        {"label": "Vibe branches", "value": str(len(branches)), "good": len(branches) > 0},
        {"label": "Stale (>14d)", "value": str(len(stale))},
        {"label": "Auto-branch", "value": "on" if _cfg("aider_code_auto_branch", True) else "off"},
    ]
    if stale:
        oldest = max(stale, key=lambda x: x[1])
        names = ", ".join(s[0] for s in stale[:3])
        insight = (f"{len(stale)} stale branch(es) (>14 days, oldest {oldest[1]}d): {names}. "
                   f"Prune finished ones: `git -C {project} branch -D <name>`.")
        status = "warn"
    elif len(branches) >= 8:
        insight = f"{len(branches)} aider branches in the repo. Consider merging or pruning finished ones to keep it tidy."
        status = "warn"
    elif len(branches) == 0:
        insight = "No vibe-code sessions yet. Open the Vibe-code tab to describe a change."
        status = "none"
    else:
        insight = f"{len(branches)} vibe-code branch(es). Currently on '{cur}'. Inspect with `git checkout aider/...`."
        status = "ok"
    return {"metrics": metrics, "insight": insight, "status": status}


def register(api):
    global _api
    _api = api
    api.register_tool("code_edit", _code_edit, risk_category="exec",
                      description="Make a real code change in the configured project via Aider "
                                  "(vibe-coding). JSON {instruction, files?}. Returns the git diff.")
    api.register_hook("diagnostic", _diagnostic)
    api.register_hook("stats", _stats)

    # Direct vibe-code surface for the UI. Runs ASYNCHRONOUSLY: the POST returns
    # immediately with a job_id; the UI polls /jobs/<id> for progress so a
    # 2-5 minute local-model run never trips an HTTP timeout (504).
    try:
        from fastapi import APIRouter, Body, Depends
        from core.middleware import require_admin
        import json as _json
        import asyncio as _asyncio
        import time as _time
        import uuid as _uuid
        router = APIRouter()
        _jobs = {}

        async def _run_job(job_id, instruction, files, admin):
            _jobs[job_id]["status"] = "running"
            _jobs[job_id]["stage"] = "starting Aider…"
            try:
                result = await _code_edit(_json.dumps({"instruction": instruction, "files": files}), admin)
                _jobs[job_id]["status"] = "done" if result.get("exit_code") == 0 else "failed"
                _jobs[job_id]["result"] = result
            except Exception as e:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["finished_at"] = _time.time()
            # GC old jobs (keep last 20)
            if len(_jobs) > 20:
                for k in sorted(_jobs, key=lambda k: _jobs[k].get("started_at", 0))[:-20]:
                    _jobs.pop(k, None)

        @router.post("/api/plugins/aider_code/edit")
        async def aider_edit(payload: dict = Body(...), admin: str = Depends(require_admin)):
            instruction = (payload.get("instruction") or "").strip()
            files = payload.get("files") or []
            if isinstance(files, str):
                files = [f.strip() for f in files.replace(",", " ").split() if f.strip()]
            if not instruction:
                return {"ok": False, "error": "describe the change first"}
            job_id = _uuid.uuid4().hex[:12]
            _jobs[job_id] = {"id": job_id, "status": "queued", "instruction": instruction,
                             "files": files, "started_at": _time.time(), "stage": "queued"}
            _asyncio.create_task(_run_job(job_id, instruction, files, admin))
            return {"ok": True, "job_id": job_id, "status": "running"}

        @router.get("/api/plugins/aider_code/jobs/{job_id}")
        async def aider_job(job_id: str, admin: str = Depends(require_admin)):
            j = _jobs.get(job_id)
            return j or {"error": "no such job"}

        api.register_router(router)
    except Exception as e:
        api.logger.debug("aider_code routes skipped: %s", e)
