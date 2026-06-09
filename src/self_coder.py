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


def _git(*args, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", _repo(), *args],
                          capture_output=True, text=True, timeout=timeout, check=check)


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

def _verify(changed_py: List[str]) -> Dict[str, Any]:
    """py_compile changed files + boot-check (`import app`). Ruthless: any failure
    means the change is rejected. (pytest can be added via self_coder_run_tests.)"""
    import sys
    py = sys.executable or "python3"
    steps = []
    ok = True
    if changed_py:
        r = subprocess.run([py, "-m", "py_compile", *changed_py],
                           cwd=_repo(), capture_output=True, text=True, timeout=120)
        steps.append({"step": "py_compile", "ok": r.returncode == 0, "out": (r.stderr or r.stdout)[-1500:]})
        ok = ok and r.returncode == 0
    # boot/import check — catches the most common breakage (bad imports/wiring)
    r2 = subprocess.run([py, "-c", "import app"], cwd=_repo(),
                        capture_output=True, text=True, timeout=180,
                        env={**os.environ, "PYTHONPATH": _repo()})
    steps.append({"step": "import app", "ok": r2.returncode == 0, "out": (r2.stderr or r2.stdout)[-2000:]})
    ok = ok and r2.returncode == 0
    if ok and _get("self_coder_run_tests", False):
        r3 = subprocess.run([py, "-m", "pytest", "-q", "--timeout=120"], cwd=_repo(),
                            capture_output=True, text=True, timeout=600,
                            env={**os.environ, "PYTHONPATH": _repo()})
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
    if not _clean_tree():
        return {"ok": False, "detail": "working tree is dirty — commit/stash your changes first "
                                       "(self-coder needs a clean tree to branch safely)"}
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


async def _do_propose(pid: str) -> None:
    """The real work — runs in the background. Streams Aider stdout into the
    proposal's aider_log so the UI sees what the AI is doing, and records each
    verify step on the progress timeline. Always returns to the base branch and
    auto-merges only when the policy allows it."""
    p = get_proposal(pid)
    if not p:
        return
    instruction = p["instruction"]
    base_branch = _current_branch()
    base_commit = _current_commit()
    branch = f"selfimprove/{pid}"
    p.update(branch=branch, base_branch=base_branch, base_commit=base_commit)

    # filter file list to real files inside the repo
    safe_files = [f for f in p.get("files", []) if isinstance(f, str)
                  and os.path.realpath(os.path.join(_repo(), f)).startswith(_repo() + os.sep)
                  and os.path.exists(os.path.join(_repo(), f))]
    p["files"] = safe_files
    _save(p)

    try:
        _git("checkout", "-b", branch)
    except Exception as e:
        p.update(status="failed", detail=f"could not create branch: {e}")
        _save(p)
        return
    _progress(p, "branch_created", branch=branch, base=base_commit[:8])

    from src.plugin_forge import aider_bin
    from src.settings import get_setting
    model = (get_setting("aider_model", "") or "").strip()
    _progress(p, "aider_starting", model=model, files=safe_files)

    import asyncio
    from src.code_edit import resolve_aider_model
    aider_model, aider_env = resolve_aider_model(model)
    try:
        proc = await asyncio.create_subprocess_exec(
            aider_bin(), "--model", aider_model, "--yes-always", "--no-auto-commits",
            "--no-show-model-warnings",
            "--no-pretty", "--no-stream", "--message", instruction, *safe_files,
            cwd=_repo(), env=aider_env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        # stream stdout line-by-line into the proposal so the UI shows it live
        last_save = time.time()
        log_chars = 0
        if proc.stdout is not None:
            while True:
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=600)
                except asyncio.TimeoutError:
                    proc.kill()
                    p.update(status="failed", detail="aider timed out")
                    _save(p)
                    break
                if not line:
                    break
                txt = line.decode(errors="replace")
                p["aider_log"] += txt
                log_chars += len(txt)
                # save every ~2s OR every 800 chars so the UI sees live progress
                if time.time() - last_save > 2 or log_chars > 800:
                    _save(p)
                    last_save = time.time()
                    log_chars = 0
        await proc.wait()
        if p.get("status") == "failed":
            return
        # cap log + record finish
        p["aider_log"] = (p["aider_log"] or "")[-12000:]
        _progress(p, "aider_done", exit_code=proc.returncode)

        # what changed
        changed = _git("diff", "--name-only").stdout.split()
        diff = _git("diff").stdout
        p["changed"] = changed
        p["diff"] = diff[:30000]
        if not changed:
            p.update(status="empty", verified=False,
                     decision={"action": "rejected", "why": "no changes made"})
            _progress(p, "no_changes")
        else:
            _git("add", "-A")
            _git("commit", "-m", f"self-improve: {instruction[:60]}", check=False)
            _progress(p, "committed_on_branch", files=len(changed))

            _progress(p, "verify_starting", run_tests=bool(_get("self_coder_run_tests", False)))
            vr = _verify([f for f in changed if f.endswith(".py")])
            for s in vr.get("steps", []):
                _progress(p, "verify_" + s["step"].replace(" ", "_"),
                          ok=s["ok"], out=(s["out"] or "")[-400:])

            risk = assess_risk(changed, diff)
            autonomy = int(_get("self_coder_autonomy", 1) or 1)
            decision = decide(risk, vr["verified"], autonomy)
            p.update(status="verified" if vr["verified"] else "failed",
                     verify=vr, risk=risk, decision=decision)
            _progress(p, "decided", action=decision["action"], why=decision["why"])
    except Exception as e:
        p.update(status="failed", verified=False, detail=str(e))
        _progress(p, "error", detail=str(e))
    finally:
        try:
            _git("checkout", base_branch, check=False)
        except Exception:
            pass
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
    if not _clean_tree():
        return {"ok": False, "detail": "working tree is dirty — commit/stash first"}
    prev = _current_commit()
    try:
        _git("merge", "--no-ff", "-m", f"merge self-improve {pid}", p["branch"])
    except Exception as e:
        return {"ok": False, "detail": f"merge failed: {e}"}

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
        _git("branch", "-D", p.get("branch", ""), check=False)
    except Exception:
        pass
    try:
        os.remove(os.path.join(_data_dir(), f"{pid}.json"))
    except Exception:
        pass
    return {"ok": True, "detail": f"discarded {pid}"}
