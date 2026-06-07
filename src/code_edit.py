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
                   auto_branch: bool = True, progress_cb=None) -> dict:
    """Run one Aider edit. Returns {response, diff, log, branch_created, ...}.
    progress_cb(stage:str) is called as the run advances (for live UI updates)."""
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

    branched = None
    if auto_branch:
        import subprocess
        import time
        import re as _re
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

    _stage("Aider is editing the code…")
    cmd = [_bin, "--model", model, "--yes-always", "--no-auto-commits",
           "--no-show-model-warnings", "--message", instruction] + safe_files
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=project,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        out_s = (out or b"").decode(errors="replace")
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"error": "Aider timed out (10 min).", "exit_code": 1}
    except Exception as e:
        return {"error": f"Aider run failed: {e}", "exit_code": 1}

    _stage("collecting the diff…")
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
            "log": out_s[-2000:], "diff": diff[:12000] or "(no changes)", "exit_code": 0}
