"""Shared code-edit engine — runs Aider on ONE project directory, on a feature
branch, with --no-auto-commits, and returns the git diff for review.

Both the chat `code_edit` tool (plugins/aider_code) and the Code workspace page
(routes/code_routes) call into here, so there's one source of truth for how an
edit actually runs. Config is passed in explicitly (project, model) — this module
reads no plugin state, so the Code page works whether or not the plugin is on.
"""
from __future__ import annotations

import asyncio
import json
import os

_INDEX_EXTS = (".py", ".js", ".ts", ".html", ".css", ".json", ".md",
               ".yaml", ".yml", ".sh", ".toml")
_INDEX_SKIP = {".git", "venv", ".venv", "__pycache__", "node_modules", "data",
               "logs", "Real-ESRGAN", "tellykeys", "realesrgan-env",
               "realesrgan-ncnn", "realesrgan-weights", "designs", "dist", "build"}


def _within(path: str, root: str) -> bool:
    rp, rr = os.path.realpath(path), os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def find_git_repos(max_repos: int = 40) -> list:
    """Best-effort discovery of git repos under common roots, so the Code page
    offers a PICKER instead of asking the user to type a path."""
    home = os.path.expanduser("~")
    roots = [home, os.path.join(home, "projects"), os.path.join(home, "code"),
             os.path.join(home, "src"), os.path.join(home, "repos"),
             os.path.join(home, "git"), os.path.join(home, "dev")]
    seen, repos = set(), []
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            # depth 1: the root itself, then its immediate children.
            candidates = [root] + [os.path.join(root, d) for d in os.listdir(root)]
        except OSError:
            continue
        for path in candidates:
            try:
                if not os.path.isdir(path):
                    continue
                rp = os.path.realpath(path)
                if rp in seen:
                    continue
                if os.path.isdir(os.path.join(path, ".git")):
                    seen.add(rp)
                    repos.append(path)
                    if len(repos) >= max_repos:
                        return sorted(repos)
            except OSError:
                continue
    return sorted(repos)


def resolve_aider_model(model: str) -> tuple:
    """Resolve a model name to a litellm-compatible spec + env vars.

    Returns (aider_model_name, env_dict) where env_dict contains
    API keys and base URLs needed for Aider/litellm to authenticate.
    Handles opencode/, openrouter/, and generic endpoint models.
    """
    env = dict(os.environ)
    aider_model = model

    if model.startswith("ollama/"):
        return aider_model, env

    try:
        from core.database import ModelEndpoint, SessionLocal
        import json as _json
        db = SessionLocal()
        try:
            _prefix, _, _bare = model.partition("/")
            if not _bare:
                _bare = _prefix
                _prefix = ""

            _eps = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all()
            # Prefer an OpenCode Go subscription endpoint (/zen/go/) over the
            # pay-as-you-go Zen endpoint (/zen/v1) when the SAME model (minimax,
            # glm, kimi, qwen3-coder, deepseek…) exists on both. Otherwise the
            # request bills the empty pay-as-you-go wallet → "Insufficient balance".
            _eps.sort(key=lambda e: 0 if "/zen/go/" in (e.base_url or "").lower() else 1)
            for ep in _eps:
                url = (ep.base_url or "").lower()
                cached = _json.loads(ep.cached_models or "[]") if ep.cached_models else []
                pinned = _json.loads(ep.pinned_models or "[]") if ep.pinned_models else []
                all_models = cached + pinned
                if not (model in all_models or _bare in all_models
                        or any(_bare in m for m in all_models)):
                    continue

                if "openrouter" in url:
                    if ep.api_key:
                        env["OPENROUTER_API_KEY"] = ep.api_key
                    aider_model = f"openrouter/{_bare}"
                elif "openai.com" in url:
                    if ep.api_key:
                        env["OPENAI_API_KEY"] = ep.api_key
                    aider_model = f"openai/{_bare}"
                elif "anthropic" in url:
                    if ep.api_key:
                        env["ANTHROPIC_API_KEY"] = ep.api_key
                    aider_model = f"anthropic/{_bare}"
                else:
                    if ep.api_key:
                        env["OPENAI_API_KEY"] = ep.api_key
                    env["OPENAI_API_BASE"] = ep.base_url
                    aider_model = f"openai/{_bare}"
                break
        finally:
            db.close()
    except Exception:
        pass

    return aider_model, env


async def list_local_models() -> list:
    """Local Ollama models as aider/litellm names ('ollama/<name>'), for the
    model picker. Best-effort — empty if Ollama isn't running."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get("http://localhost:11434/api/tags")
            data = r.json() or {}
        names = [m.get("name", "") for m in (data.get("models") or [])]
        return [f"ollama/{n}" for n in names if n]
    except Exception:
        return []


async def _guess_files(instruction: str, project: str, model: str) -> list:
    """When the user names no files, ask the local coder model to pick them from a
    compact repo index — that's what makes 'just describe the change' real."""
    import httpx
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
        seen = set(files)
        return [p for p in picked if isinstance(p, str) and p in seen][:5]
    except Exception:
        return []


async def run_edit(instruction: str, files, project: str, model: str,
                   auto_branch: bool = True, progress_cb=None, line_cb=None) -> dict:
    """Run one Aider edit. Returns {response, diff, log, branch_created, ...}.
    progress_cb(stage:str) is called as the run advances (for live UI updates).
    line_cb(line:str) is called for every raw stdout line from Aider."""
    def _stage(s):
        if progress_cb:
            try:
                progress_cb(s)
            except Exception:
                pass

    instruction = (instruction or "").strip()
    if not instruction:
        return {"error": "Need an instruction describing the change.", "exit_code": 1}
    if not project or not os.path.isdir(project):
        return {"error": "Pick an existing repository first.", "exit_code": 1}
    if not os.path.isdir(os.path.join(project, ".git")):
        return {"error": "That folder isn't a git repository (no .git).", "exit_code": 1}
    model = (model or "").strip()
    if not model:
        return {"error": "Pick a coder model first.", "exit_code": 1}

    from src.plugin_forge import aider_bin
    _bin = aider_bin()
    if not _bin:
        return {"error": "Aider isn't installed yet — use the Install button.", "exit_code": 1}

    files = files or []
    if isinstance(files, str):
        files = [f.strip() for f in files.replace(",", " ").split() if f.strip()]
    safe_files = [f for f in files if isinstance(f, str) and _within(os.path.join(project, f), project)]

    auto_picked = []
    if not safe_files:
        _stage("choosing which files to edit…")
        auto_picked = await _guess_files(instruction, project, model)
        safe_files = [f for f in auto_picked if _within(os.path.join(project, f), project)]

    import subprocess
    import time
    import re as _re
    branched = None
    if auto_branch:
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
                    _stage(f"working on a safe branch: {new_branch}")
        except Exception:
            pass

    # Snapshot the working tree BEFORE Aider runs — `git stash create` writes a
    # commit-ish without touching the index or worktree, so we can diff exactly
    # this run's changes later, excluding any pre-existing dirty files from
    # other work. Falls back to HEAD if the tree is clean (stash create returns
    # empty in that case).
    snapshot = None
    try:
        r = subprocess.run(["git", "-C", project, "stash", "create"],
                           capture_output=True, text=True, timeout=10)
        snapshot = (r.stdout or "").strip() or None
        if not snapshot:
            snapshot = subprocess.run(["git", "-C", project, "rev-parse", "HEAD"],
                                      capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        snapshot = None

    _stage("Aider is editing the code…")
    aider_model, env = resolve_aider_model(model)

    cmd = [_bin, "--model", aider_model, "--yes-always", "--no-auto-commits",
           "--no-show-model-warnings", "--message", instruction] + safe_files

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=project, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        lines = []
        try:
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=600)
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                lines.append(text)
                if line_cb and text:
                    try: line_cb(text)
                    except Exception: pass
                _lwr = text.lower()
                if "searching" in _lwr or "repo map" in _lwr:
                    _stage("analyzing the repo…")
                elif "sending" in _lwr or "request" in _lwr:
                    _stage("sending to model…")
                elif "writing" in _lwr or "applied" in _lwr or "wrote" in _lwr:
                    fname = text.split()[-1] if text.split() else ""
                    _stage(f"writing changes{(' to ' + fname) if fname else ''}…")
                elif "tokens" in _lwr and ("/" in text or "cost" in _lwr):
                    _stage("model is thinking…")
                elif "edit" in _lwr and ("file" in _lwr or ".py" in _lwr or ".js" in _lwr):
                    _stage(f"editing: {text[:60]}…")
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {"error": "Aider timed out (10 min).", "exit_code": 1}
        await proc.wait()
        out_s = "\n".join(lines)
    except Exception as e:
        return {"error": f"Aider run failed: {e}", "exit_code": 1}

    _stage("collecting the diff…")
    diff = ""
    try:
        diff_cmd = ["git", "-C", project, "diff"]
        if snapshot:
            # Scoped diff: only show this run's edits, not unrelated dirty files.
            diff_cmd.append(snapshot)
        dp = await asyncio.create_subprocess_exec(
            *diff_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        d, _ = await dp.communicate()
        diff = (d or b"").decode(errors="replace")
    except Exception:
        pass

    # Honest exit code: trust Aider's returncode, AND scan the output for the
    # known failure markers Aider prints without crashing (auth errors come
    # out as text on stdout in many providers — litellm wraps the exception
    # then Aider just keeps the chat going with zero edits).
    rc = proc.returncode if proc.returncode is not None else 1
    out_lc = out_s.lower()
    error_markers = (
        "authenticationerror", "insufficient balance", "invalid api key",
        "rate limit", "ratelimiterror", "could not connect",
        "litellm.apiconnectionerror", "litellm.authenticationerror",
        "litellm.notfounderror",
    )
    failed_marker = next((m for m in error_markers if m in out_lc), None)
    if failed_marker and rc == 0:
        rc = 1

    branch_note = f" on branch '{branched}'" if branched else ""
    if rc != 0:
        why = failed_marker or f"aider exited with code {rc}"
        return {"error": f"Aider failed: {why}. See log for details.",
                "instruction": instruction, "branch_created": branched,
                "files_used": safe_files, "auto_picked": auto_picked,
                "log": out_s[-2000:], "diff": diff[:12000] or "(no changes)",
                "exit_code": rc}

    response_msg = (f"Aider applied the change in {project}{branch_note} "
                    "(not committed — review the diff).")
    if not diff.strip():
        # Honest: zero exit code AND no diff = nothing actually happened.
        response_msg = (f"Aider exited cleanly in {project}{branch_note} but "
                        "made no changes. Re-check the instruction or the model.")
    return {"response": response_msg,
            "instruction": instruction, "branch_created": branched,
            "files_used": safe_files, "auto_picked": auto_picked,
            "log": out_s[-2000:], "diff": diff[:12000] or "(no changes)", "exit_code": rc}
