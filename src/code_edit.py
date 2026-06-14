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


# ── OpenCode CLI backend ────────────────────────────────────────────────────
# The OpenCode CLI (`opencode run`) is an alternative to Aider for the coder /
# self-coder. It authenticates to the OpenCode Zen / Go subscription via its own
# credential store (~/.local/share/opencode/auth.json), so it sidesteps the
# litellm API-key dance that makes the Go subscription fail under Aider. Models
# are passed as `provider/model` (e.g. opencode-go/qwen3.7-max), output is parsed
# from `--format json` events, and it does NOT auto-commit (same as Aider's
# --no-auto-commits) so the existing git-diff snapshot logic is unchanged.

# Provider prefixes the opencode CLI resolves natively (see `opencode models`).
_OPENCODE_NATIVE_PREFIXES = (
    "opencode/", "opencode-go/", "google/", "anthropic/", "openai/",
    "openrouter/", "ollama/", "github-copilot/", "deepseek/", "xai/", "groq/",
    "mistral/", "azure/",
)


def opencode_bin():
    """Resolve the opencode binary: the official installer's path first
    (~/.opencode/bin), then PATH, then ~/.local/bin. None if not found."""
    import shutil
    cand = os.path.expanduser("~/.opencode/bin/opencode")
    if os.path.exists(cand):
        return cand
    found = shutil.which("opencode")
    if found:
        return found
    local = os.path.expanduser("~/.local/bin/opencode")
    return local if os.path.exists(local) else None


def resolve_opencode_model(model: str):
    """Map the app's model string to an opencode `provider/model` spec, or None
    if it can't be confidently mapped (caller should then fall back to Aider).

    Mirrors resolve_aider_model's endpoint lookup but emits opencode-native
    provider prefixes (opencode-go/ for the /zen/go/ subscription, opencode/ for
    pay-as-you-go Zen) instead of litellm env vars."""
    m = (model or "").strip()
    if not m:
        return None
    if any(m.lower().startswith(p) for p in _OPENCODE_NATIVE_PREFIXES):
        return m  # already a native provider/model spec
    try:
        from core.database import ModelEndpoint, SessionLocal
        import json as _json
        db = SessionLocal()
        try:
            _prefix, _, _bare = m.partition("/")
            if not _bare:
                _bare = _prefix
            eps = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all()
            # Prefer the Go subscription endpoint when the model lives on both.
            eps.sort(key=lambda e: 0 if "/zen/go/" in (e.base_url or "").lower() else 1)
            for ep in eps:
                url = (ep.base_url or "").lower()
                cached = _json.loads(ep.cached_models or "[]") if ep.cached_models else []
                pinned = _json.loads(ep.pinned_models or "[]") if ep.pinned_models else []
                allm = cached + pinned
                if not (m in allm or _bare in allm or any(_bare in x for x in allm)):
                    continue
                if "/zen/go/" in url:
                    return f"opencode-go/{_bare}"
                if "zen" in url and "opencode" in url:
                    return f"opencode/{_bare}"
                if "openrouter" in url:
                    return f"openrouter/{_bare}"
                if "anthropic" in url:
                    return f"anthropic/{_bare}"
                if "openai.com" in url:
                    return f"openai/{_bare}"
                # Generic OpenAI-compatible endpoint: opencode can't reach it
                # without provider config → signal fallback to Aider.
                return None
        finally:
            db.close()
    except Exception:
        return None
    return None


def select_coder_backend(model: str) -> dict:
    """Pick the coder backend for this run, honoring the `coder_backend` setting
    (default 'opencode') with graceful fallback to whatever is actually usable.

    Returns {backend: 'opencode'|'aider'|None, bin, model, env, error, fellback}.
    The caller builds the command via build_coder_cmd() and need not know which
    backend won."""
    from src.plugin_forge import aider_bin
    try:
        from src.settings import get_setting
        pref = (get_setting("coder_backend", "opencode") or "opencode").strip().lower()
    except Exception:
        pref = "opencode"

    oc_bin = opencode_bin()
    ai_bin = aider_bin()

    def _aider():
        am, env = resolve_aider_model(model)
        return {"backend": "aider", "bin": ai_bin, "model": am, "env": env,
                "error": None}

    def _opencode(oc_model):
        return {"backend": "opencode", "bin": oc_bin, "model": oc_model,
                "env": dict(os.environ), "error": None}

    if pref == "aider":
        if ai_bin:
            return _aider()
        ocm = resolve_opencode_model(model) if oc_bin else None
        if oc_bin and ocm:
            return {**_opencode(ocm), "fellback": True}
        return {"backend": None, "bin": None, "model": None, "env": None,
                "error": "Aider isn't installed yet — use the Install button."}

    # default: opencode preferred
    ocm = resolve_opencode_model(model) if oc_bin else None
    if oc_bin and ocm:
        return _opencode(ocm)
    if ai_bin:
        return {**_aider(), "fellback": True}
    return {"backend": None, "bin": None, "model": None, "env": None,
            "error": ("OpenCode CLI not found — install it (~/.opencode/bin) or "
                      "set coder_backend to 'aider'." if not oc_bin else
                      "This model can't be mapped to OpenCode and Aider isn't "
                      "installed.")}


def build_coder_cmd(sel: dict, instruction: str, files, *,
                    no_git: bool = False, pretty: bool = True, cwd: str = None) -> list:
    """Build the subprocess argv for the selected backend. `no_git`/`pretty`
    only affect Aider (opencode run has no equivalents); `cwd` is used to make
    opencode's -f attachments absolute."""
    files = [f for f in (files or []) if f]
    if sel.get("backend") == "opencode":
        # --dangerously-skip-permissions is opencode's equivalent of aider's
        # --yes-always: without it, a non-interactive `run` (no TTY to prompt)
        # AUTO-REJECTS file edits as "external_directory" and changes nothing.
        # The coder/self-coder are autonomous by design and gated downstream by
        # the feature-branch + diff review + Aegis approval flow, so auto-approve
        # is correct here (mirrors the existing aider --yes-always trust model).
        # The instruction MUST come before -f: --file is a greedy array option,
        # so a positional placed after it gets swallowed as another filename.
        # -f also needs absolute paths (relative ones don't resolve against the
        # subprocess cwd), so anchor them to `cwd`.
        cmd = [sel["bin"], "run", "-m", sel["model"], "--format", "json",
               "--dangerously-skip-permissions", instruction]
        for f in files:
            af = f if (os.path.isabs(f) or not cwd) else os.path.join(cwd, f)
            cmd += ["-f", af]
        return cmd
    cmd = [sel["bin"], "--model", sel["model"], "--yes-always",
           "--no-auto-commits", "--no-show-model-warnings"]
    if no_git:
        cmd.append("--no-git")
    if not pretty:
        cmd.append("--no-pretty")
    cmd += ["--message", instruction] + files
    return cmd


def opencode_event(line: str):
    """Parse one `opencode run --format json` line into (stage, log, is_error).

    Any element may be None; a non-JSON line returns (None, raw_line, False) so
    it still shows up in the log. Used by both the Code page (stage updates) and
    the self-coder (heartbeat log)."""
    line = (line or "").strip()
    if not line:
        return None, None, False
    try:
        o = json.loads(line)
    except Exception:
        return None, line, False
    t = o.get("type")
    part = o.get("part") or {}
    if t == "tool_use":
        tool = part.get("tool") or ""
        fp = (((part.get("state") or {}).get("input")) or {}).get("filePath") or ""
        base = os.path.basename(fp) if fp else ""
        if tool in ("read", "grep", "glob", "list", "webfetch"):
            return "analyzing the repo…", f"[{tool}] {base}".strip(), False
        if tool in ("edit", "write", "patch", "multiedit"):
            return (f"writing changes{(' to ' + base) if base else ''}…",
                    f"[{tool}] {base}".strip(), False)
        if tool == "bash":
            return "running a command…", "[bash]", False
        return None, f"[{tool}] {base}".strip(), False
    if t == "step_start":
        return "model is thinking…", None, False
    if t == "text":
        txt = part.get("text") or o.get("text") or ""
        return None, (txt or None), False
    if t == "error" or part.get("error"):
        msg = o.get("error") or part.get("error") or "error"
        return None, f"ERROR: {msg}", True
    return None, None, False


# Keywords that mark a model as coder-suited (sorted/flagged first in the picker).
_CODER_HINTS = ("code", "coder", "qwen", "kimi", "deepseek", "glm", "minimax",
                "devstral", "codestral", "starcoder", "mistral", "gpt", "claude")


def _coder_suited(model_id: str) -> bool:
    return any(h in (model_id or "").lower() for h in _CODER_HINTS)


def list_coder_models() -> dict:
    """Curated, source-grouped coder models for the picker. Three sources:
    OpenCode Go (subscription, via opencode CLI), OpenCode Zen FREE-only (the
    `-free` tier), and local Ollama. The returned model id encodes the backend
    route (opencode-go/…, opencode/…, ollama/…), so picking a model is all the
    coder/self-coder need — select_coder_backend() routes from the id.

    Returns {groups: [{source, label, backend, note?, models: [{id, label,
    suited}]}], current}."""
    groups = []
    go_models, zen_free, local = [], [], []
    try:
        from core.database import ModelEndpoint, SessionLocal
        import json as _json
        db = SessionLocal()
        try:
            for ep in db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all():
                url = (ep.base_url or "").lower()
                cached = _json.loads(ep.cached_models or "[]") if ep.cached_models else []
                pinned = _json.loads(ep.pinned_models or "[]") if ep.pinned_models else []
                ids = [m for m in (cached + pinned) if m]
                if "/zen/go/" in url:
                    for m in ids:
                        bare = m.split("/", 1)[-1]
                        go_models.append(f"opencode-go/{bare}")
                elif "zen" in url and "opencode" in url:
                    for m in ids:
                        bare = m.split("/", 1)[-1]
                        if bare.endswith("-free"):   # user: only the fully-free tier
                            zen_free.append(f"opencode/{bare}")
        finally:
            db.close()
    except Exception:
        pass

    # Local Ollama models — prefer tool-capable ones (proper tool calls are what
    # make the agentic editor actually write code, not just talk about it).
    try:
        import httpx
        with httpx.Client(timeout=4) as client:
            data = client.get("http://localhost:11434/api/tags").json() or {}
        for m in (data.get("models") or []):
            name = m.get("name", "")
            if name:
                local.append(f"ollama/{name}")
    except Exception:
        pass

    def _mk(ids):
        seen, items = set(), []
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            items.append({"id": mid, "label": mid.split("/", 1)[-1],
                          "suited": _coder_suited(mid)})
        # coder-suited first, then alphabetical
        items.sort(key=lambda x: (not x["suited"], x["label"].lower()))
        return items

    if go_models:
        groups.append({"source": "go", "label": "OpenCode Go (subscription)",
                       "backend": "opencode", "models": _mk(go_models)})
    if zen_free:
        groups.append({"source": "zen-free", "label": "OpenCode Zen (free)",
                       "backend": "opencode", "models": _mk(zen_free)})
    if local:
        groups.append({"source": "local", "label": "Local (Ollama)",
                       "backend": "opencode/aider",
                       "note": "Local models vary in tool-calling — if a run only "
                               "prints text and makes no edits, the model isn't "
                               "emitting proper tool calls; try a Go/Zen model.",
                       "models": _mk(local)})

    cur = ""
    try:
        from src.settings import get_setting
        cur = (get_setting("aider_model", "") or "").strip()
    except Exception:
        pass
    return {"groups": groups, "current": cur}


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

    sel = select_coder_backend(model)
    if sel.get("error"):
        return {"error": sel["error"], "exit_code": 1}
    backend = sel["backend"]
    backend_label = "OpenCode" if backend == "opencode" else "Aider"

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
                new_branch = f"{backend}/{int(time.time())}-{slug}"
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

    _stage(f"{backend_label} is editing the code…")
    cmd = build_coder_cmd(sel, instruction, safe_files, cwd=project)
    env = sel["env"]

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
                if backend == "opencode":
                    # Parse the JSON event stream → readable log + stage updates.
                    stage, log_txt, _is_err = opencode_event(text)
                    if log_txt:
                        lines.append(log_txt)
                        if line_cb:
                            try: line_cb(log_txt)
                            except Exception: pass
                    if stage:
                        _stage(stage)
                    continue
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
            return {"error": f"{backend_label} timed out (10 min).", "exit_code": 1}
        await proc.wait()
        out_s = "\n".join(lines)
    except Exception as e:
        return {"error": f"{backend_label} run failed: {e}", "exit_code": 1}

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

    # Honest exit code: trust the backend's returncode, AND scan the output for
    # known failure markers it prints without crashing (auth errors come out as
    # text on stdout in many providers — litellm/opencode wrap the exception
    # then keep the chat going with zero edits).
    rc = proc.returncode if proc.returncode is not None else 1
    out_lc = out_s.lower()
    error_markers = (
        "authenticationerror", "insufficient balance", "invalid api key",
        "rate limit", "ratelimiterror", "could not connect",
        "litellm.apiconnectionerror", "litellm.authenticationerror",
        "litellm.notfounderror", "requires an api key", "unauthorized",
    )
    failed_marker = next((m for m in error_markers if m in out_lc), None)
    if failed_marker and rc == 0:
        rc = 1

    branch_note = f" on branch '{branched}'" if branched else ""
    if rc != 0:
        why = failed_marker or f"{backend} exited with code {rc}"
        return {"error": f"{backend_label} failed: {why}. See log for details.",
                "instruction": instruction, "branch_created": branched,
                "files_used": safe_files, "auto_picked": auto_picked,
                "backend": backend,
                "log": out_s[-2000:], "diff": diff[:12000] or "(no changes)",
                "exit_code": rc}

    response_msg = (f"{backend_label} applied the change in {project}{branch_note} "
                    "(not committed — review the diff).")
    if not diff.strip():
        # Honest: zero exit code AND no diff = nothing actually happened.
        response_msg = (f"{backend_label} exited cleanly in {project}{branch_note} but "
                        "made no changes. Re-check the instruction or the model.")
    return {"response": response_msg,
            "instruction": instruction, "branch_created": branched,
            "files_used": safe_files, "auto_picked": auto_picked, "backend": backend,
            "log": out_s[-2000:], "diff": diff[:12000] or "(no changes)", "exit_code": rc}
