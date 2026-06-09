"""Agentic Code-edit engine — drives `stream_agent_loop` against ONE project,
with a tight tool allowlist and hard cost-safety guards.

Why a separate motor from `code_edit.run_edit` (Aider, one-shot):
- Code-as-an-agent: explore → plan → edit → verify, over multiple rounds.
- Hard cost ceiling: only {read_file, write_file, bash, plan_task} are exposed,
  and any tool that could escalate to a paid teacher model is hard-blocked.
- Default model is pinned to a subscription-covered endpoint
  (`minimax-m2.7@OpenCode Go`) so there is no path to a pay-as-you-go wallet.

Public entry point: `run_agentic_edit(...)` returns the same dict shape as
`run_edit` so the route only needs a toggle to swap engines.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# Allowed tools — tight on purpose. Everything else is implicitly disabled
# because `stream_agent_loop` treats `relevant_tools` as an allowlist.
CODE_AGENT_ALLOWED_TOOLS: frozenset = frozenset({
    "read_file", "write_file", "bash", "plan_task",
})

# Defence in depth: even if RAG ever overrode the allowlist, these tools
# can never be called by the Code agent. They are the ones that could
# escalate to a paid Claude / teacher model, kick off a research run, or
# pull another model into the loop.
CODE_AGENT_DISABLED_TOOLS: frozenset = frozenset({
    "ask_teacher", "chat_with_model", "pipeline", "trigger_research",
    "self_coder", "create_session", "send_to_session", "manage_research",
})

# Hard ceiling on agent rounds. The global default is 60; Code needs less.
CODE_AGENT_MAX_ROUNDS = 25

# Default model spec: model@endpoint syntax pins resolution to the Go
# subscription endpoint, sidestepping the Zen (pay-as-you-go) wallet.
CODE_AGENT_DEFAULT_MODEL = "minimax-m2.7@OpenCode Go"


def _system_prompt(project: str, files_hint: list[str]) -> str:
    files_line = ""
    if files_hint:
        files_line = (
            "\nThe user named these files as the most likely edit targets — "
            "start by reading them: " + ", ".join(files_hint) + "."
        )
    return (
        "You are an autonomous coding agent working on ONE git repository.\n"
        f"REPOSITORY ROOT (absolute): {project}\n"
        "WORKFLOW:\n"
        "  1. Plan with plan_task before any edits if the change touches more than one file.\n"
        "  2. Explore with read_file / bash to understand the code before editing.\n"
        "  3. Edit with write_file. Make the smallest change that solves the request.\n"
        "  4. Verify: run a syntax check, the test suite, or a smoke command via bash.\n"
        "  5. Stop when the change is done. Do NOT commit — the user reviews the diff.\n\n"
        "BASH CONTEXT — IMPORTANT:\n"
        "  The bash tool does NOT start in the repository directory. Prefix every command\n"
        f"  with `cd {project} && ...` or pass absolute paths. Never assume cwd.\n\n"
        "FILE PATHS:\n"
        "  Use absolute paths under the repository root for read_file and write_file.\n"
        "  Do not touch files outside the repository.\n\n"
        "BOUNDARIES:\n"
        "  - Do not ask the user clarifying questions; make a reasonable decision and proceed.\n"
        "  - Do not delegate to other models — only the four tools above are available.\n"
        "  - Keep tool output focused. Don't dump huge files; read targeted ranges.\n"
        + files_line
    )


def _safe_branch_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower())[:32].strip("-") or "edit"


def _git(project: str, *args: str, timeout: float = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", project, *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def _maybe_branch(project: str, instruction: str) -> Optional[str]:
    """If on main/master, switch to a throwaway branch so the agent can never
    dirty the user's primary branch. Mirrors `code_edit.run_edit`."""
    try:
        cur = _git(project, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if cur in ("main", "master"):
            branch = f"agent/{int(time.time())}-{_safe_branch_slug(instruction)}"
            r = _git(project, "checkout", "-b", branch)
            if r.returncode == 0:
                return branch
    except Exception as e:
        logger.warning(f"[code_agent] branch creation failed: {e}")
    return None


def _snapshot(project: str) -> Optional[str]:
    """Snapshot the current working tree as a commit-ish, WITHOUT touching the
    tree or the index. `git stash create` returns a SHA we can diff against
    later — so the agent's edits show up in the diff even if the working tree
    already had unrelated dirty changes from other work."""
    try:
        # `git stash create` succeeds even on a clean tree (returns empty); in
        # that case HEAD is the right baseline.
        r = _git(project, "stash", "create")
        sha = (r.stdout or "").strip()
        if sha:
            return sha
        head = _git(project, "rev-parse", "HEAD").stdout.strip()
        return head or None
    except Exception as e:
        logger.warning(f"[code_agent] snapshot failed: {e}")
        return None


def _scoped_diff(project: str, snapshot: Optional[str], limit: int = 12000) -> str:
    """Diff the working tree against the pre-run snapshot — so the result shows
    ONLY the agent's edits, not unrelated dirty files that were already there."""
    if not snapshot:
        # Fall back to whole-repo diff if snapshot failed. Better than nothing.
        try:
            r = _git(project, "diff")
            return (r.stdout or "")[:limit] or "(no changes)"
        except Exception:
            return "(no changes)"
    try:
        r = _git(project, "diff", snapshot)
        text = r.stdout or ""
        return text[:limit] if text else "(no changes)"
    except Exception as e:
        logger.warning(f"[code_agent] diff failed: {e}")
        return "(no changes)"


def _resolve_safely(model_spec: str, owner: Optional[str]):
    """Resolve the user-supplied model spec, with one forgiving retry that
    strips a litellm-style prefix (`openrouter/foo` → `foo`) when the literal
    spec doesn't resolve. Raises ValueError if neither shape works."""
    from src.ai_interaction import _resolve_model

    try:
        return _resolve_model(model_spec, owner=owner)
    except ValueError:
        if "/" in model_spec and "@" not in model_spec:
            bare = model_spec.split("/", 1)[1]
            return _resolve_model(bare, owner=owner)
        raise


async def run_agentic_edit(
    instruction: str,
    files,
    project: str,
    model: str,
    auto_branch: bool = True,
    progress_cb=None,
    line_cb=None,
    owner: Optional[str] = None,
    max_rounds: int = CODE_AGENT_MAX_ROUNDS,
) -> dict:
    """Run one agentic code-edit. Returns the same dict shape as run_edit:
    {response, diff, log, branch_created, files_used, instruction, exit_code, error?}

    progress_cb(stage:str)   — called as the run advances (drives UI stage text).
    line_cb(line:str)        — called for every notable line (drives live_log).
    """
    def _stage(s: str) -> None:
        if progress_cb:
            try: progress_cb(s)
            except Exception: pass

    def _line(s: str) -> None:
        if line_cb and s:
            try: line_cb(s)
            except Exception: pass

    instruction = (instruction or "").strip()
    if not instruction:
        return {"error": "Need an instruction describing the change.", "exit_code": 1}
    if not project or not os.path.isdir(project):
        return {"error": "Pick an existing repository first.", "exit_code": 1}
    if not os.path.isdir(os.path.join(project, ".git")):
        return {"error": "That folder isn't a git repository (no .git).", "exit_code": 1}

    model_spec = (model or CODE_AGENT_DEFAULT_MODEL).strip() or CODE_AGENT_DEFAULT_MODEL

    if isinstance(files, str):
        files = [f.strip() for f in files.replace(",", " ").split() if f.strip()]
    files = files or []
    files_hint = [f for f in files if isinstance(f, str)][:5]

    _stage("resolving model…")
    try:
        endpoint_url, model_id, headers = await asyncio.to_thread(
            _resolve_safely, model_spec, owner
        )
    except ValueError as e:
        msg = (f"Couldn't route model '{model_spec}': {e}. "
               "Pick a coder model from the picker.")
        return {"error": msg, "exit_code": 1}
    except Exception as e:
        return {"error": f"Model routing failed: {e}", "exit_code": 1}

    _line(f"[model] routed '{model_spec}' → {model_id} @ {endpoint_url}")

    branched = None
    if auto_branch:
        branched = _maybe_branch(project, instruction)
        if branched:
            _stage(f"working on a safe branch: {branched}")
            _line(f"[git] checked out {branched}")

    snapshot = _snapshot(project)
    if snapshot:
        _line(f"[git] snapshot {snapshot[:10]} — diff will be scoped to this run")

    messages = [
        {"role": "system", "content": _system_prompt(project, files_hint)},
        {"role": "user", "content": instruction},
    ]

    _stage("agent is thinking…")
    from src.agent_loop import stream_agent_loop

    full_response = ""
    last_round = 0
    final_metrics = None
    final_exit_code = 0
    tool_failures = 0

    try:
        async for raw in stream_agent_loop(
            endpoint_url=endpoint_url,
            model=model_id,
            messages=messages,
            headers=headers,
            temperature=0.2,
            max_rounds=max_rounds,
            owner=owner,
            relevant_tools=set(CODE_AGENT_ALLOWED_TOOLS),
            disabled_tools=set(CODE_AGENT_DISABLED_TOOLS),
        ):
            if not raw or not raw.startswith("data: "):
                continue
            payload = raw[6:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                ev = json.loads(payload)
            except Exception:
                continue

            if "delta" in ev:
                full_response += ev["delta"]
                continue

            t = ev.get("type")
            if t == "tool_start":
                tool = ev.get("tool", "?")
                cmd = (ev.get("command") or "").strip()
                _stage(f"{tool}: {cmd[:80]}" if cmd else f"running {tool}…")
                if cmd:
                    _line(f"[{tool}] {cmd[:200]}")
            elif t == "tool_output":
                tool = ev.get("tool", "?")
                out = (ev.get("output") or "").strip()
                rc = ev.get("exit_code")
                if rc not in (None, 0):
                    tool_failures += 1
                if out:
                    head = out.splitlines()[0][:200] if out else ""
                    _line(f"[{tool} → exit={rc}] {head}")
            elif t == "agent_step":
                rnd = ev.get("round") or 0
                if rnd and rnd != last_round:
                    last_round = rnd
                    _stage(f"round {rnd}…")
            elif t == "metrics":
                final_metrics = ev.get("data") or {}
            elif t == "approval_required":
                _stage("waiting for approval…")
    except asyncio.CancelledError:
        _stage("cancelled")
        return {
            "error": "Agent run cancelled.",
            "exit_code": 1,
            "branch_created": branched,
            "instruction": instruction,
            "log": full_response[-2000:],
            "diff": _scoped_diff(project, snapshot),
        }
    except Exception as e:
        logger.exception("[code_agent] stream_agent_loop crashed")
        return {
            "error": f"Agent run failed: {e}",
            "exit_code": 1,
            "branch_created": branched,
            "instruction": instruction,
            "log": full_response[-2000:],
            "diff": _scoped_diff(project, snapshot),
        }

    _stage("collecting the diff…")
    diff = _scoped_diff(project, snapshot)

    # Honest exit-code semantics: success only if the model produced a final
    # response AND nothing crashed. We deliberately don't fail on tool exit
    # codes alone — a non-zero `bash` is often diagnostic information the
    # agent then handled (e.g. a failing test it went on to fix). The diff
    # is the ground truth the user reviews.
    summary = full_response.strip() or "(agent finished without writing a summary)"
    if not full_response.strip() and diff == "(no changes)":
        final_exit_code = 1
        summary = "Agent finished without making any changes."

    branch_note = f" on branch '{branched}'" if branched else ""
    response_text = f"{summary}\n\n_Edits in {project}{branch_note} — not committed._"

    result = {
        "response": response_text,
        "instruction": instruction,
        "branch_created": branched,
        "files_used": files_hint,
        "auto_picked": [],
        "log": full_response[-2000:],
        "diff": diff,
        "exit_code": final_exit_code,
        "engine": "agentic",
        "rounds": last_round,
        "tool_failures": tool_failures,
    }
    if final_metrics:
        # Trim metrics to a few fields useful in the UI; full metrics are
        # large (raw round texts, tool events).
        result["metrics"] = {
            k: final_metrics.get(k) for k in (
                "input_tokens", "output_tokens", "total_tokens",
                "ttft", "prefill_tps", "decode_tps", "agent_rounds",
            ) if k in final_metrics
        }
    return result
