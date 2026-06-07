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


def _within(path: str, root: str) -> bool:
    rp, rr = os.path.realpath(path), os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


_INDEX_EXTS = (".py", ".js", ".ts", ".html", ".css", ".json", ".md",
               ".yaml", ".yml", ".sh", ".toml")
_INDEX_SKIP = {".git", "venv", ".venv", "__pycache__", "node_modules", "data",
               "logs", "Real-ESRGAN", "tellykeys", "realesrgan-env",
               "realesrgan-ncnn", "realesrgan-weights", "designs"}


async def _guess_files(instruction: str, project: str, model: str) -> list:
    """When the user doesn't specify files, ask the local coder model to pick
    them from a compact index of the repo. Returns up to 5 relative paths. The
    whole point of vibe-coding is that the user shouldn't need to know the
    layout — this is what makes that real."""
    import httpx
    # 1) build a compact, deduped index of source files
    files = []
    for root, dirs, fs in os.walk(project):
        rel_root = os.path.relpath(root, project)
        if rel_root != "." and any(p in rel_root.split(os.sep) for p in _INDEX_SKIP):
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d not in _INDEX_SKIP and not d.startswith(".")]
        for f in fs:
            if f.endswith(_INDEX_EXTS):
                files.append(os.path.relpath(os.path.join(root, f), project))
        if len(files) > 1200:
            break
    if not files:
        return []
    # 2) ask the local model to pick the most relevant
    prompt = (
        "You're choosing which files in a project to edit for a code change.\n"
        f"USER WANTS:\n{instruction}\n\n"
        "FILES AVAILABLE (one per line):\n" + "\n".join(sorted(files)[:900]) +
        "\n\nReturn ONLY a JSON array of 1-5 file paths (relative, exactly as "
        'listed) that most likely need editing. No prose. Example: '
        '["routes/foo.py","plugins/bar/plugin.py"]')
    try:
        ollama_model = model[len("ollama/"):] if model.startswith("ollama/") else model
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.1}})
            text = (r.json() or {}).get("response", "")
        import re as _re
        m = _re.search(r"\[\s*(?:\".*?\"\s*,?\s*)+\]", text, _re.DOTALL)
        if not m:
            return []
        picked = json.loads(m.group(0))
        # keep only entries that actually exist in our index
        seen = set(files)
        return [p for p in picked if isinstance(p, str) and p in seen][:5]
    except Exception:
        return []


async def _code_edit(content, owner):
    try:
        args = json.loads(content) if content and content.strip().startswith("{") else {"instruction": content}
    except (ValueError, TypeError):
        args = {"instruction": content}
    instruction = (args.get("instruction") or "").strip()
    files = args.get("files") or []
    if not instruction:
        return {"error": "Need an 'instruction' describing the change.", "exit_code": 1}

    project = (_cfg("aider_code_project", "") or "").strip()
    if not project or not os.path.isdir(project):
        return {"error": "Set aider_code_project to an existing repository path.", "exit_code": 1}
    model = (_cfg("aider_model", "") or "").strip()
    if not model:
        return {"error": "Set aider_model (e.g. ollama/qwen3-coder).", "exit_code": 1}
    from src.plugin_forge import aider_bin
    _bin = aider_bin()
    if not _bin:
        return {"error": "aider is not installed. Use the 'Install Aider' button in /manage "
                         "(or `uv tool install --python 3.12 aider-chat`).", "exit_code": 1}

    # Only let Aider touch files INSIDE the configured project.
    safe_files = [f for f in files if isinstance(f, str) and _within(os.path.join(project, f), project)]

    # Vibe-coding: when the user didn't specify files, let the local model pick
    # them for us from a compact index of the repo. That's what makes "describe
    # what you want" actually work — the user shouldn't need to know the layout.
    auto_picked = []
    if not safe_files:
        auto_picked = await _guess_files(instruction, project, model)
        safe_files = [f for f in auto_picked if _within(os.path.join(project, f), project)]

    # Safety: if on main/master and auto-branch is on, create a feature branch
    # FIRST so a bad edit never lands on main. Aider runs --no-auto-commits, so
    # files change on the branch but the user reviews + commits explicitly.
    branched = None
    if _cfg("aider_code_auto_branch", True):
        import subprocess, time, re as _re
        try:
            cur = subprocess.run(["git", "-C", project, "rev-parse", "--abbrev-ref", "HEAD"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            if cur in ("main", "master"):
                slug = _re.sub(r"[^a-z0-9]+", "-", instruction.lower())[:32].strip("-") or "edit"
                new_branch = f"aider/{int(time.time())}-{slug}"
                r = subprocess.run(["git", "-C", project, "checkout", "-b", new_branch],
                                   capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    branched = new_branch
        except Exception:
            pass

    # --no-show-model-warnings: skips Aider's "Continue anyway? [y/N]" prompt for
    # unknown models (the warnings.html page) — without it, Aider HANGS waiting
    # for input, since --yes-always doesn't cover that specific check.
    cmd = [_bin, "--model", model, "--yes-always", "--no-auto-commits",
           "--no-show-model-warnings",
           "--message", instruction] + safe_files
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=project,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=420)
        out_s = (out or b"").decode(errors="replace")
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"error": "Aider timed out (420s).", "exit_code": 1}
    except Exception as e:
        return {"error": f"Aider run failed: {e}", "exit_code": 1}

    diff = ""
    try:
        dp = await asyncio.create_subprocess_exec(
            "git", "-C", project, "diff",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        d, _ = await dp.communicate()
        diff = (d or b"").decode(errors="replace")
    except Exception:
        pass

    branch_note = f" on branch '{branched}'" if branched else ""
    return {"response": f"Aider applied the change in {project}{branch_note} (not committed — review the diff).",
            "instruction": instruction, "branch_created": branched,
            "files_used": safe_files, "auto_picked": auto_picked,
            "log": out_s[-1500:], "diff": diff[:8000] or "(no changes)", "exit_code": 0}


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
