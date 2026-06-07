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


async def _code_edit(content, owner):
    if not _cfg("aider_code_enabled", False):
        return {"error": "aider_code is disabled. Enable it + set aider_code_project + aider_model.",
                "exit_code": 1}
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

    cmd = [_bin, "--model", model, "--yes-always", "--no-auto-commits",
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

    return {"response": f"Aider applied the change in {project} (not committed — review the diff).",
            "instruction": instruction, "log": out_s[-1500:], "diff": diff[:8000] or "(no changes)",
            "exit_code": 0}


def _diagnostic():
    from src.plugin_forge import aider_bin
    has_aider = bool(aider_bin())
    enabled = bool(_cfg("aider_code_enabled", False))
    project = (_cfg("aider_code_project", "") or "").strip()
    model = (_cfg("aider_model", "") or "").strip()
    if not enabled:
        return {"name": "aider-code", "status": "ok", "detail": "disabled (enable to vibe-code a project)"}
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


def register(api):
    global _api
    _api = api
    api.register_tool("code_edit", _code_edit, risk_category="exec",
                      description="Make a real code change in the configured project via Aider "
                                  "(vibe-coding). JSON {instruction, files?}. Returns the git diff.")
    api.register_hook("diagnostic", _diagnostic)
