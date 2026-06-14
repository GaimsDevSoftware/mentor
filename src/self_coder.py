"""self_coder — the app proposes, verifies, and (optionally) applies code changes
to ITSELF, safely.

The autonomous self-improvement loop for CODE (the skills loop already does this
for skills). Pieces, all here:

  1. HARNESS: each change is made on an isolated git BRANCH by Aider, then verified
     (py_compile changed files + `import app` boot check + optional pytest) BEFORE
     it can land. A change that doesn't compile/boot never reaches the working tree.
  2. AUTONOMY POLICY: a risk tier (scope: plugins-only vs core; diff size; tests
     pass?) decides auto-merge eligibility — reusing the Aegis idea. Core changes
     ALWAYS need human approval; only scoped+small+passing changes can auto-merge.
  3. CANARY DEPLOY + ROLLBACK: applying = merge the branch, then launch a DETACHED
     watchdog (scripts/canary_deploy.sh) that restarts the service, health-checks,
     and `git reset --hard`'s back to the previous commit if it doesn't come up —
     because a bad self-edit must never brick the app (a bricked app can't fix
     itself).

Hard preconditions: a CLEAN, committed working tree (refuses otherwise — a dirty
tree can't be branched/merged safely), and `aider` installed. Disabled by default.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional

_HEALTH_DEFAULT = "http://127.0.0.1:7000/app"
_SERVICE_DEFAULT = "odysseus-ui.service"


def _repo() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_dir() -> str:
    d = os.path.join(_repo(), "data", "self_coder")
    os.makedirs(d, exist_ok=True)
    return d


def _git(*args, check: bool = True, timeout: int = 60, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", cwd or _repo(), *args],
                          capture_output=True, text=True, timeout=timeout, check=check)


# ── isolated worktree (builds never touch the live checkout) ──────────────────

def _worktree_dir(pid: str) -> str:
    """Per-proposal worktree under the gitignored data dir, so a build never
    disturbs the user's active branch or working tree, and a mid-build app
    restart can't break the running app."""
    return os.path.join(_data_dir(), "wt", pid)


def _add_worktree(pid: str, branch: str, base: str) -> str:
    wt = _worktree_dir(pid)
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    # Clear any stale worktree/branch left from a previous aborted run.
    _git("worktree", "remove", "--force", wt, check=False)
    _git("worktree", "prune", check=False)
    _git("branch", "-D", branch, check=False)
    _git("worktree", "add", "-b", branch, wt, base, check=True)
    return wt


def _remove_worktree(pid: str) -> None:
    wt = _worktree_dir(pid)
    _git("worktree", "remove", "--force", wt, check=False)
    _git("worktree", "prune", check=False)


def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def _clean_tree() -> bool:
    try:
        return _git("status", "--porcelain").stdout.strip() == ""
    except Exception:
        return False


def _stash_push(label: str) -> bool:
    """Stash dirty working tree (including untracked) so self-coder can branch
    safely. Returns True if something was stashed."""
    if _clean_tree():
        return False
    try:
        r = _git("stash", "push", "--include-untracked", "-m", f"self-coder/{label}",
                 check=False)
        return r.returncode == 0 and "No local changes" not in (r.stdout or "")
    except Exception:
        return False


def _stash_pop() -> bool:
    """Restore the most recent self-coder stash. Best-effort; conflicts leave
    the stash intact so the user can resolve manually."""
    try:
        # Find the topmost self-coder stash.
        r = _git("stash", "list", check=False)
        if not r.stdout or "self-coder/" not in r.stdout:
            return False
        for line in r.stdout.splitlines():
            if "self-coder/" in line:
                ref = line.split(":", 1)[0]  # e.g. "stash@{0}"
                pop = _git("stash", "pop", ref, check=False)
                return pop.returncode == 0
        return False
    except Exception:
        return False


def _current_commit() -> str:
    try:
        return _git("rev-parse", "HEAD").stdout.strip()
    except Exception:
        return ""


def _current_branch() -> str:
    try:
        return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    except Exception:
        return ""


# ── autonomy policy (risk tiering) ───────────────────────────────────────────

def assess_risk(files: List[str], diff: str) -> Dict[str, Any]:
    files = [f for f in files if f]
    core = any(f == "app.py" or f.startswith(("src/", "core/", "routes/", "services/"))
               for f in files)
    plugins_only = bool(files) and all(f.startswith("plugins/") for f in files)
    lines = (diff or "").count("\n")
    return {"tier": "core" if core else ("plugin" if plugins_only else "mixed"),
            "core": core, "plugins_only": plugins_only,
            "diff_lines": lines, "big": lines > 200, "files": files}


def decide(risk: Dict[str, Any], verified: bool, autonomy: int) -> Dict[str, str]:
    """autonomy: 0=manual(propose only) 1=propose+1-click 2=scoped-auto-merge."""
    if not verified:
        return {"action": "rejected", "why": "verification failed — change discarded"}
    if autonomy >= 2 and risk["plugins_only"] and not risk["big"] and not risk["core"]:
        return {"action": "auto-merge", "why": "scoped to plugins, small, and verified"}
    if risk["core"]:
        return {"action": "needs-approval", "why": "touches core — human approval required"}
    return {"action": "needs-approval", "why": "verified — one-click merge"}


# ── proposal storage ─────────────────────────────────────────────────────────

def _save(p: Dict[str, Any]) -> None:
    from core.atomic_io import atomic_write_json
    atomic_write_json(os.path.join(_data_dir(), f"{p['id']}.json"), p, indent=2)


def list_proposals() -> List[Dict[str, Any]]:
    out = []
    for fn in sorted(os.listdir(_data_dir())):
        if fn.endswith(".json"):
            try:
                out.append(json.loads(open(os.path.join(_data_dir(), fn)).read()))
            except Exception:
                pass
    return sorted(out, key=lambda p: p.get("ts", 0), reverse=True)


def get_proposal(pid: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(_data_dir(), f"{pid}.json")
    if not os.path.exists(path):
        return None
    try:
        return json.loads(open(path).read())
    except Exception:
        return None


# ── verification ─────────────────────────────────────────────────────────────

def _verify(changed_py: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """py_compile changed files + boot-check (`import app`). Ruthless: any failure
    means the change is rejected. (pytest can be added via self_coder_run_tests.)
    Runs in ``cwd`` (the proposal's isolated worktree) so it checks the edited
    code, not the live tree."""
    import sys
    py = sys.executable or "python3"
    root = cwd or _repo()
    steps = []
    ok = True
    if changed_py:
        r = subprocess.run([py, "-m", "py_compile", *changed_py],
                           cwd=root, capture_output=True, text=True, timeout=120)
        steps.append({"step": "py_compile", "ok": r.returncode == 0, "out": (r.stderr or r.stdout)[-1500:]})
        ok = ok and r.returncode == 0
    # boot/import check — catches the most common breakage (bad imports/wiring)
    r2 = subprocess.run([py, "-c", "import app"], cwd=root,
                        capture_output=True, text=True, timeout=180,
                        env={**os.environ, "PYTHONPATH": root})
    steps.append({"step": "import app", "ok": r2.returncode == 0, "out": (r2.stderr or r2.stdout)[-2000:]})
    ok = ok and r2.returncode == 0
    if ok and _get("self_coder_run_tests", False):
        r3 = subprocess.run([py, "-m", "pytest", "-q", "--timeout=120"], cwd=root,
                            capture_output=True, text=True, timeout=600,
                            env={**os.environ, "PYTHONPATH": root})
        steps.append({"step": "pytest", "ok": r3.returncode == 0, "out": (r3.stdout or r3.stderr)[-2000:]})
        ok = ok and r3.returncode == 0
    return {"verified": ok, "steps": steps}


# ── propose a change ─────────────────────────────────────────────────────────

def _progress(p: Dict[str, Any], step: str, **kw) -> None:
    """Append a timestamped step to the proposal so the UI can show progress live."""
    p.setdefault("progress", []).append({"step": step, "ts": time.time(), **kw})
    _save(p)


async def propose(instruction: str, files: List[str], *, source: str = "manual",
                  ts: Optional[float] = None) -> Dict[str, Any]:
    """Kick off a self-coder proposal. Validates preconditions, creates the proposal
    record with status="building", and runs the actual work IN THE BACKGROUND so the
    HTTP caller returns immediately. The UI polls the proposal to watch progress
    (`progress` timeline + live `aider_log`) while it runs."""
    instruction = (instruction or "").strip()
    if not instruction:
        return {"ok": False, "detail": "no instruction"}
    from src.plugin_forge import aider_bin
    if not aider_bin():
        return {"ok": False, "detail": "aider not installed (use the Install Aider button)"}
    if not (_get("aider_model", "") or "").strip():
        return {"ok": False, "detail": "set aider_model (a free local coder)"}

    pid = uuid.uuid4().hex[:12]
    proposal = {"id": pid, "ts": ts or time.time(), "source": source,
                "instruction": instruction, "files": list(files or []),
                "status": "building", "progress": [], "aider_log": ""}
    _save(proposal)
    import asyncio
    asyncio.create_task(_do_propose(pid))
    return {"ok": True, "id": pid, "status": "building",
            "detail": "Working — Aider is editing on a branch. Watch progress live."}


async def _run_aider(p: Dict[str, Any], instruction: str, safe_files: List[str],
                     wt: str) -> bool:
    """Spawn aider once with ``instruction`` inside the isolated worktree ``wt``,
    STREAM its output into ``p['aider_log']`` (so the model's tokens give a real
    heartbeat), and supervise it. If no output arrives for ``stall_seconds`` the
    state flips to ``'stalled'`` (yellow) while it keeps waiting; if the silence
    reaches ``hard_timeout`` the process is killed and ``status`` flips to
    ``'failed'`` (red). ``p['last_activity_ts']`` is kept fresh throughout so the
    UI can show "last activity Ns ago" and a traffic-light state."""
    import asyncio
    from src.settings import get_setting
    from src.code_edit import select_coder_backend, build_coder_cmd, opencode_event

    stall_s = int(_get("self_coder_stall_seconds", 90) or 90)
    hard_s = int(_get("self_coder_hard_timeout", 300) or 300)

    model = (get_setting("aider_model", "") or "").strip()
    sel = select_coder_backend(model)
    if sel.get("error"):
        p.update(status="failed", state="failed", detail=sel["error"])
        _save(p)
        return False
    backend = sel["backend"]
    # --no-pretty (aider) keeps the log parse-friendly; opencode uses --format
    # json which build_coder_cmd already sets.
    cmd = build_coder_cmd(sel, instruction, safe_files, pretty=False, cwd=wt)
    try:
        # NOTE: streaming is intentionally ON so silence is a genuine signal
        # that the model is stuck, not just mid-generation.
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=wt, env=sel["env"],
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except Exception as e:
        p.update(status="failed", state="failed", detail=f"could not start {backend}: {e}")
        _save(p)
        return False

    now = time.time()
    last_output = now
    last_save = 0.0
    stalled = False
    p["last_activity_ts"] = now
    p.update(state="working")
    _save(p)

    if proc.stdout is not None:
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
            except asyncio.TimeoutError:
                idle = time.time() - last_output
                if idle >= hard_s:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    p.update(status="failed", state="failed",
                             detail=f"aider stuck — no output for {int(idle)}s "
                                    f"(hard limit {hard_s}s). The model may be too "
                                    f"slow or Ollama is hung.")
                    p["last_activity_ts"] = last_output
                    _progress(p, "killed_stalled", idle=int(idle))
                    _save(p)
                    return False
                if idle >= stall_s and not stalled:
                    stalled = True
                    p.update(state="stalled")
                    _progress(p, "stalled", idle=int(idle))
                    _save(p)
                elif time.time() - last_save > 3:
                    # heartbeat save so the UI's "last activity" age keeps ticking
                    _save(p)
                    last_save = time.time()
                continue
            if not line:
                break
            last_output = time.time()
            p["last_activity_ts"] = last_output
            if stalled:
                stalled = False
                p.update(state="working")
                _progress(p, "resumed")
            txt = line.decode(errors="replace")
            if backend == "opencode":
                # Distill the JSON event stream into a readable heartbeat line.
                _stage, _log, _err = opencode_event(txt)
                txt = ((_log + "\n") if _log else "") if (_log or _err) else ""
            if txt:
                p["aider_log"] = ((p.get("aider_log") or "") + txt)[-20000:]
            if time.time() - last_save > 2:
                _save(p)
                last_save = time.time()
    await proc.wait()
    p["aider_log"] = (p.get("aider_log") or "")[-20000:]
    p["last_activity_ts"] = time.time()
    _save(p)
    return True


def _verify_summary(vr: Dict[str, Any]) -> str:
    """Compact failure summary suitable for feeding back to aider as a fix
    instruction. Only includes the failing step's output, capped tight."""
    for step in vr.get("steps", []):
        if not step.get("ok"):
            out = (step.get("out") or "").strip()
            return f"{step['step']}: {out[-800:]}"
    return "verification failed (no per-step output)"


async def _do_propose(pid: str) -> None:
    """The real work — runs in the background. Streams Aider stdout into the
    proposal's aider_log so the UI sees what the AI is doing, and records each
    verify step on the progress timeline. Auto-stashes dirty state, retries on
    verify failure with the error fed back to aider, and only auto-merges when
    the policy allows it."""
    p = get_proposal(pid)
    if not p:
        return
    instruction = p["instruction"]
    base_branch = _current_branch()
    base_commit = _current_commit()
    branch = f"selfimprove/{pid}"
    p.update(branch=branch, base_branch=base_branch, base_commit=base_commit,
             state="building", last_activity_ts=time.time())

    # filter file list to real files inside the repo
    safe_files = [f for f in p.get("files", []) if isinstance(f, str)
                  and os.path.realpath(os.path.join(_repo(), f)).startswith(_repo() + os.sep)
                  and os.path.exists(os.path.join(_repo(), f))]
    p["files"] = safe_files
    _save(p)

    # Build in an ISOLATED worktree off the base commit. The live checkout and
    # the user's working tree are never touched — no stash, no branch switch —
    # so a mid-build app restart can't break the running app.
    try:
        wt = _add_worktree(pid, branch, base_commit)
    except Exception as e:
        p.update(status="failed", state="failed", detail=f"could not create worktree: {e}")
        _progress(p, "worktree_failed", detail=str(e))
        _save(p)
        return
    p["worktree"] = wt
    _progress(p, "worktree_created", branch=branch, base=base_commit[:8])

    # All git ops during the build target the worktree, not the live repo.
    def g(*args, **kw):
        return _git(*args, cwd=wt, **kw)

    from src.settings import get_setting
    model = (get_setting("aider_model", "") or "").strip()
    max_retries = int(_get("self_coder_max_retries", 2) or 0)
    _progress(p, "aider_starting", model=model, files=safe_files, max_retries=max_retries)

    try:
        current_instruction = instruction
        attempt = 0
        vr: Dict[str, Any] = {"verified": False, "steps": []}
        decision: Dict[str, str] = {}
        risk: Dict[str, Any] = {}
        changed: List[str] = []
        diff = ""

        while attempt <= max_retries:
            attempt += 1
            _progress(p, "aider_attempt", n=attempt)

            ok = await _run_aider(p, current_instruction, safe_files, wt)
            if not ok or p.get("status") == "failed":
                return
            _progress(p, "aider_done", attempt=attempt)

            changed = g("diff", "--name-only").stdout.split() or \
                      g("diff", "HEAD", "--name-only").stdout.split()
            # If the previous attempt committed, the diff is empty — pull from HEAD
            if not changed:
                # walk back to base to see cumulative changes from this branch
                changed = g("diff", f"{base_commit}..HEAD", "--name-only").stdout.split()
            diff = g("diff", f"{base_commit}..HEAD").stdout
            p["changed"] = changed
            p["diff"] = diff[:30000]

            if not changed:
                p.update(status="empty", state="empty", verified=False,
                         decision={"action": "rejected", "why": "no changes made"})
                _progress(p, "no_changes")
                return

            # commit pending worktree edits from this attempt
            if g("diff", "--name-only").stdout.strip():
                g("add", "-A")
                g("commit", "-m",
                  f"self-improve attempt {attempt}: {instruction[:50]}", check=False)
                _progress(p, "committed_on_branch", files=len(changed), attempt=attempt)

            _progress(p, "verify_starting",
                      run_tests=bool(_get("self_coder_run_tests", False)),
                      attempt=attempt)
            p.update(state="verifying")
            _save(p)
            vr = _verify([f for f in changed if f.endswith(".py")], cwd=wt)
            for s in vr.get("steps", []):
                _progress(p, "verify_" + s["step"].replace(" ", "_"),
                          ok=s["ok"], out=(s["out"] or "")[-400:], attempt=attempt)

            if vr["verified"]:
                break

            # verification failed — if retries left, ask aider to fix with the
            # exact error context. This is the "smarter at fixing itself" bit:
            # the model now SEES what broke and can target the fix.
            if attempt > max_retries:
                _progress(p, "out_of_retries")
                break

            err = _verify_summary(vr)
            current_instruction = (
                f"Your previous edit broke verification. Read the error below and "
                f"fix the code that caused it. Do not revert; keep the intent of "
                f"the original task: {instruction!r}\n\n"
                f"Error:\n{err}"
            )
            p["retry_reason"] = err[:1500]
            _progress(p, "retry_planned", error=err[:300], next_attempt=attempt + 1)

        risk = assess_risk(changed, diff)
        autonomy = int(_get("self_coder_autonomy", 1) or 1)
        decision = decide(risk, vr["verified"], autonomy)
        _ok = vr["verified"]
        p.update(status="verified" if _ok else "failed",
                 state="verified" if _ok else "failed",
                 verify=vr, risk=risk, decision=decision, attempts=attempt)
        _progress(p, "decided", action=decision["action"], why=decision["why"],
                  attempts=attempt)
    except Exception as e:
        p.update(status="failed", state="failed", verified=False, detail=str(e))
        _progress(p, "error", detail=str(e))
    finally:
        # Tear down the isolated worktree. The branch is KEPT so apply_proposal
        # can still merge it; the live checkout was never touched.
        try:
            _remove_worktree(pid)
        except Exception:
            pass
        p.pop("worktree", None)
        if p.get("state") not in ("verified", "failed", "empty"):
            p["state"] = p.get("status") or "failed"
        p["last_activity_ts"] = time.time()
        _save(p)

    # autonomous apply only when policy explicitly says so
    if p.get("decision", {}).get("action") == "auto-merge":
        p["auto_applied"] = apply_proposal(pid)
        _save(p)


# ── apply (merge) + canary deploy ────────────────────────────────────────────

def apply_proposal(pid: str) -> Dict[str, Any]:
    """Merge the proposal's branch into the working branch, then launch the
    detached canary watchdog (restart → health-check → rollback on failure)."""
    p = get_proposal(pid)
    if not p:
        return {"ok": False, "detail": "no such proposal"}
    if p.get("status") != "verified":
        return {"ok": False, "detail": f"proposal not verified (status={p.get('status')})"}
    stashed = _stash_push(f"apply-{pid}")
    prev = _current_commit()
    try:
        _git("merge", "--no-ff", "-m", f"merge self-improve {pid}", p["branch"])
    except Exception as e:
        if stashed:
            _stash_pop()
        return {"ok": False, "detail": f"merge failed: {e}"}
    if stashed:
        popped = _stash_pop()
        if not popped:
            # merge succeeded but stash didn't pop cleanly — keep stash for user
            p["stash_kept_after_apply"] = True

    # Launch the detached canary watchdog (survives the app restart it triggers).
    watchdog = os.path.join(_repo(), "scripts", "canary_deploy.sh")
    health = _get("self_coder_health_url", _HEALTH_DEFAULT)
    service = _get("self_coder_service", _SERVICE_DEFAULT)
    launched = False
    if os.path.exists(watchdog):
        try:
            subprocess.Popen(["/bin/bash", watchdog, _repo(), prev, str(health), str(service), pid],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            launched = True
        except Exception:
            launched = False
    p.update(status="applied", applied_over=prev, canary=launched)
    _save(p)
    return {"ok": True, "detail": f"merged {pid}; canary {'launched' if launched else 'NOT launched (restart manually)'}",
            "rollback_to": prev}


def discard_proposal(pid: str) -> Dict[str, Any]:
    p = get_proposal(pid)
    if not p:
        return {"ok": False, "detail": "no such proposal"}
    try:
        _remove_worktree(pid)
    except Exception:
        pass
    try:
        _git("branch", "-D", p.get("branch", ""), check=False)
    except Exception:
        pass
    try:
        os.remove(os.path.join(_data_dir(), f"{pid}.json"))
    except Exception:
        pass
    return {"ok": True, "detail": f"discarded {pid}"}
