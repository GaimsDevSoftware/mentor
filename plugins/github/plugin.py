"""GitHub plugin — git workflow from Mentor.

Integrates GitHub API for pushing, creating PRs, managing branches,
all accessible from Mentor UI or via agent tools.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_config = {
    "token": "",
    "default_repo": "robert/odysseus",
    "auto_open_pr": True,
}


# ──────────────────────────────────────────────────────────────────────────
#  GIT OPERATIONS
# ──────────────────────────────────────────────────────────────────────────

def _run_git(cmd: str, cwd: str = ".") -> tuple[int, str, str]:
    """Run a git command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


async def _tool_git_status(content: str, owner) -> dict:
    """Show git status."""
    args = json.loads(content or "{}")
    repo_path = args.get("repo", ".")

    code, out, err = _run_git("git status --porcelain", repo_path)
    if code != 0:
        return {"error": f"git status failed: {err}"}

    return {"response": f"Git status:\n{out}" if out else "Working directory clean"}


async def _tool_git_commit(content: str, owner) -> dict:
    """Stage all changes and commit with message."""
    args = json.loads(content or "{}")
    message = (args.get("message") or "").strip()
    repo_path = args.get("repo", ".")

    if not message:
        return {"error": "Missing commit message"}

    # Stage all changes
    code, _, err = _run_git("git add -A", repo_path)
    if code != 0:
        return {"error": f"git add failed: {err}"}

    # Commit
    code, out, err = _run_git(f'git commit -m "{message}"', repo_path)
    if code != 0:
        return {"error": f"git commit failed: {err}"}

    return {"response": f"Committed: {out.strip()}"}


async def _tool_git_push(content: str, owner) -> dict:
    """Push commits to remote."""
    args = json.loads(content or "{}")
    branch = (args.get("branch") or "").strip()
    remote = (args.get("remote") or "origin").strip()
    repo_path = args.get("repo", ".")

    # Get current branch if not specified
    if not branch:
        code, branch, _ = _run_git("git rev-parse --abbrev-ref HEAD", repo_path)
        if code != 0:
            return {"error": "Could not determine current branch"}
        branch = branch.strip()

    code, out, err = _run_git(f"git push {remote} {branch}", repo_path)
    if code != 0:
        return {"error": f"git push failed: {err}"}

    return {"response": f"Pushed to {remote}/{branch}:\n{out.strip()}"}


async def _tool_git_branch_list(content: str, owner) -> dict:
    """List all branches."""
    args = json.loads(content or "{}")
    repo_path = args.get("repo", ".")

    code, out, err = _run_git("git branch -a", repo_path)
    if code != 0:
        return {"error": f"git branch failed: {err}"}

    return {"response": f"Branches:\n{out}"}


async def _tool_git_branch_create(content: str, owner) -> dict:
    """Create a new branch."""
    args = json.loads(content or "{}")
    branch = (args.get("branch") or "").strip()
    repo_path = args.get("repo", ".")

    if not branch:
        return {"error": "Missing branch name"}

    code, out, err = _run_git(f"git checkout -b {branch}", repo_path)
    if code != 0:
        return {"error": f"git checkout failed: {err}"}

    return {"response": f"Created and switched to branch: {branch}"}


# ──────────────────────────────────────────────────────────────────────────
#  GITHUB API OPERATIONS
# ──────────────────────────────────────────────────────────────────────────

async def _tool_gh_pr_create(content: str, owner) -> dict:
    """Create a GitHub PR via GitHub CLI."""
    args = json.loads(content or "{}")
    title = (args.get("title") or "").strip()
    body = (args.get("body") or "").strip()
    repo = (args.get("repo") or _config["default_repo"]).strip()
    branch = (args.get("branch") or "").strip()

    if not title:
        return {"error": "Missing PR title"}

    if not branch:
        code, branch, _ = _run_git("git rev-parse --abbrev-ref HEAD")
        if code != 0:
            return {"error": "Could not determine current branch"}
        branch = branch.strip()

    cmd = f'gh pr create --repo {repo} --title "{title}" --body "{body}" --head {branch}'
    code, out, err = _run_git(cmd)
    if code != 0:
        return {"error": f"gh pr create failed: {err}"}

    return {"response": f"PR created:\n{out}"}


async def _tool_gh_pr_list(content: str, owner) -> dict:
    """List open PRs."""
    args = json.loads(content or "{}")
    repo = (args.get("repo") or _config["default_repo"]).strip()

    cmd = f"gh pr list --repo {repo} --state open"
    code, out, err = _run_git(cmd)
    if code != 0:
        return {"error": f"gh pr list failed: {err}"}

    return {"response": f"Open PRs:\n{out}" if out else "No open PRs"}


async def _tool_gh_status(content: str, owner) -> dict:
    """Show GitHub repo status (commits ahead/behind, PR status)."""
    args = json.loads(content or "{}")
    repo = (args.get("repo") or _config["default_repo"]).strip()
    repo_path = args.get("repo_path", ".")

    # Get current branch
    code, branch, _ = _run_git("git rev-parse --abbrev-ref HEAD", repo_path)
    if code != 0:
        return {"error": "Could not determine current branch"}
    branch = branch.strip()

    # Check for PRs on this branch
    cmd = f'gh pr list --repo {repo} --head {branch}'
    code, prs, _ = _run_git(cmd)

    status = f"Repository: {repo}\nBranch: {branch}\n"
    if code == 0 and prs.strip():
        status += f"Associated PRs:\n{prs}"
    else:
        status += "No associated PRs"

    return {"response": status}


def _diagnostic():
    """Debugger-compatible self-check. MUST stay cheap and must NOT call
    debugger.run_all() — this hook runs INSIDE the debugger."""
    # git availability (no network, fast)
    code, out, _ = _run_git("git --version")
    if code != 0:
        return {"name": "github", "status": "error",
                "detail": "git executable not found on PATH",
                "hint": "install git so the github plugin's tools can run"}
    if _config.get("token"):
        detail = f"git ready ({out.strip()}); GitHub token set, gh_* tools active"
    else:
        detail = f"git ready ({out.strip()}); no GitHub token — gh_* tools disabled"
    return {"name": "github", "status": "ok", "detail": detail, "hint": ""}


def register(api):
    """Register GitHub tools with the agent."""
    logger.info("github plugin loaded")

    # Get settings
    token = api.get_setting("github_token", _config["token"])
    if token:
        _config["token"] = token

    default_repo = api.get_setting("github_default_repo", _config["default_repo"])
    if default_repo:
        _config["default_repo"] = default_repo

    auto_open = api.get_setting("github_auto_open_pr", str(_config["auto_open_pr"]))
    _config["auto_open_pr"] = auto_open.lower() == "true"

    # Register git tools
    api.register_tool(
        "git_status",
        _tool_git_status,
        description="Show git status of a repository",
        risk_category="read",
        schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository path (default: current directory)"},
            },
        },
    )

    api.register_tool(
        "git_commit",
        _tool_git_commit,
        description="Stage all changes and create a commit",
        risk_category="write",
        schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
                "repo": {"type": "string", "description": "Repository path (default: current directory)"},
            },
            "required": ["message"],
        },
    )

    api.register_tool(
        "git_push",
        _tool_git_push,
        description="Push commits to remote repository",
        risk_category="external",
        schema={
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Branch to push (default: current branch)"},
                "remote": {"type": "string", "description": "Remote name (default: origin)"},
                "repo": {"type": "string", "description": "Repository path (default: current directory)"},
            },
        },
    )

    api.register_tool(
        "git_branch_list",
        _tool_git_branch_list,
        description="List all branches in the repository",
        risk_category="read",
        schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository path (default: current directory)"},
            },
        },
    )

    api.register_tool(
        "git_branch_create",
        _tool_git_branch_create,
        description="Create a new git branch and switch to it",
        risk_category="write",
        schema={
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Name of the new branch"},
                "repo": {"type": "string", "description": "Repository path (default: current directory)"},
            },
            "required": ["branch"],
        },
    )

    # Register GitHub CLI tools (if token is set)
    if token:
        api.register_tool(
            "gh_pr_create",
            _tool_gh_pr_create,
            description="Create a GitHub pull request",
            risk_category="external",
            schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description"},
                    "repo": {"type": "string", "description": "Repository (owner/repo)"},
                    "branch": {"type": "string", "description": "Source branch (default: current)"},
                },
                "required": ["title"],
            },
        )

        api.register_tool(
            "gh_pr_list",
            _tool_gh_pr_list,
            description="List open pull requests",
            risk_category="read",
            schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo)"},
                },
            },
        )

        api.register_tool(
            "gh_status",
            _tool_gh_status,
            description="Show GitHub repository status and associated PRs",
            risk_category="read",
            schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo)"},
                    "repo_path": {"type": "string", "description": "Local repository path"},
                },
            },
        )

    # Debugger/cookbook contract: expose a self-check so this plugin is
    # debugger-compatible (clears the "no diagnostic() hook" warning).
    api.register_hook("diagnostic", _diagnostic)
