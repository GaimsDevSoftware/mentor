"""Copilot one-click remediation for Cookbook debugger findings.

Each fixable debugger finding carries a `fix` descriptor; this engine applies it.
Three kinds, escalating in power and care:

  • setting       — flip a whitelisted setting (instant, safe). e.g. aegis_mode→audit.
  • command       — launch a vetted background command (e.g. reindex embeddings).
  • plugin_repair — heal a plugin: call its own `repair()` if it has one, else have
                    Copilot (the teacher model) rewrite the plugin's code — SCOPED
                    STRICTLY to plugins/<name>/, verified by reloading. It can never
                    touch core app files ("fix the plugin, not the app").

The hard guarantee: a code-fix only ever writes inside the plugins/ tree. Any path
that resolves outside it is refused. Settings fixes only touch a safe whitelist.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Settings the one-click fixer is allowed to change. Anything security-relevant
# (auth_enabled, passwords, bind addresses, allowed_origins…) is deliberately NOT
# here — a fix payload can never flip those.
SAFE_SETTING_KEYS = {
    "aegis_mode", "aegis_block_threshold", "aegis_warn_threshold",
    "agent_local_no_think", "agent_local_min_predict",
    "improve_loop_enabled", "plugins_enabled",
    "caveman_enabled", "caveman_level", "caveman_min_chars",
    "caveman_compress_system_prompt",
    "regelverk_max_injected", "skill_max_injected",
    "improve_success_sample_rate",
}

# Vetted background commands the fixer may launch (argv built at call time).
_COMMANDS = {
    "reindex_embeddings": ["scripts/reindex_embeddings.py", "--apply"],
}


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _plugins_root() -> str:
    return os.path.join(_repo_root(), "plugins")


def _within(path: str, root: str) -> bool:
    rp = os.path.realpath(path)
    rr = os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


# ── setting fix ──────────────────────────────────────────────────────────────

def _apply_setting(fix: Dict[str, Any]) -> Dict[str, Any]:
    key = fix.get("key")
    if key not in SAFE_SETTING_KEYS:
        return {"ok": False, "detail": f"setting {key!r} is not one the fixer may change"}
    val = fix.get("value")
    try:
        from src.settings import load_settings, save_settings
        s = dict(load_settings())
        old = s.get(key)
        s[key] = val
        save_settings(s)
        return {"ok": True, "detail": f"{key}: {old!r} → {val!r}"}
    except Exception as e:
        return {"ok": False, "detail": f"failed to set {key}: {e}"}


# ── command fix ──────────────────────────────────────────────────────────────

def _apply_command(fix: Dict[str, Any]) -> Dict[str, Any]:
    cmd_id = fix.get("command")
    argv = _COMMANDS.get(cmd_id)
    if not argv:
        return {"ok": False, "detail": f"unknown command {cmd_id!r}"}
    import subprocess
    import sys
    py = sys.executable or "python3"
    full = [py] + [os.path.join(_repo_root(), argv[0])] + argv[1:]
    try:
        # Detached background run; the debugger will reflect the result next run.
        subprocess.Popen(full, cwd=_repo_root(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return {"ok": True, "detail": f"launched: {' '.join(argv)} (runs in background)"}
    except Exception as e:
        return {"ok": False, "detail": f"failed to launch {cmd_id}: {e}"}


# ── plugin repair (self-heal, then Copilot code-fix) ─────────────────────────

_TEACHER_FIX_PROMPT = """\
A plugin for our app failed to load. Return ONLY the corrected, COMPLETE contents \
of the file, in one ```python fenced block, nothing else. Fix the error without \
changing the plugin's intended behaviour. Do not add imports of app internals \
beyond what's already used.

FILE: {relpath}
ERROR:
{error}

CURRENT CONTENTS:
```python
{source}
```"""


def _teacher_spec() -> str:
    from src.settings import get_setting
    return (get_setting("improve_teacher_model", "") or get_setting("teacher_model", "") or "").strip()


async def copilot_repair_plugin(name: str) -> Dict[str, Any]:
    """Heal a broken plugin. Tries the plugin's own repair() first; otherwise asks
    the teacher model to rewrite plugins/<name>/plugin.py. Writes ONLY inside the
    plugins tree, backs up first, reloads, and verifies the plugin now loads."""
    from src import plugin_system

    # 1) Plugin's own repair handler wins (no code generation needed).
    if plugin_system.has_repair(name):
        res = plugin_system.run_repair(name, {"name": name})
        plugin_system.load_all()
        return {"ok": bool(res.get("ok")), "via": "plugin.repair", "detail": res.get("detail", "")}

    # 2) Copilot code-fix, scoped to the plugin directory.
    pdir = os.path.join(_plugins_root(), name)
    target = os.path.join(pdir, "plugin.py")
    if not _within(target, _plugins_root()) or not os.path.isdir(pdir):
        return {"ok": False, "detail": f"refused: {name!r} is not a plugin directory under plugins/"}
    if not os.path.exists(target):
        return {"ok": False, "detail": f"no plugin.py in plugins/{name}/"}

    spec = _teacher_spec()
    if not spec:
        return {"ok": False, "detail": "no teacher model configured — set teacher_model to enable Copilot code-fix"}

    # Find the recorded load error.
    error = next((p.get("error") for p in plugin_system.list_plugins()
                  if p.get("name") == name), None) or "plugin failed to load"
    try:
        source = open(target, "r", encoding="utf-8").read()
    except Exception as e:
        return {"ok": False, "detail": f"could not read plugin.py: {e}"}
    if len(source) > 24000:
        return {"ok": False, "detail": "plugin.py too large for automatic Copilot fix"}

    prompt = _TEACHER_FIX_PROMPT.format(relpath=f"plugins/{name}/plugin.py",
                                        error=str(error)[:1500], source=source)
    try:
        from src.ai_interaction import _resolve_model
        from src.llm_core import complete_with_continuation
        url, model, headers = _resolve_model(spec)
        reply = await complete_with_continuation(
            url, model,
            [{"role": "system", "content": "You are a careful Python repair assistant."},
             {"role": "user", "content": prompt}],
            headers=headers, max_tokens=8000, timeout=180)
    except Exception as e:
        return {"ok": False, "detail": f"Copilot call failed: {e}"}

    m = re.search(r"```(?:python)?\s*\n(.*?)\n```", reply or "", re.S)
    new_src = (m.group(1) if m else (reply or "")).strip()
    if not new_src or "def register" not in new_src:
        return {"ok": False, "detail": "Copilot did not return a usable plugin.py (no register())"}

    # Re-assert the path guard right before writing — never escape plugins/.
    if not _within(target, _plugins_root()):
        return {"ok": False, "detail": "refused: write target escaped the plugins tree"}
    backup = target + ".copilot-bak"
    try:
        os.replace(target, backup) if os.path.exists(target) else None
        with open(target, "w", encoding="utf-8") as f:
            f.write(new_src + ("\n" if not new_src.endswith("\n") else ""))
    except Exception as e:
        return {"ok": False, "detail": f"failed to write fix: {e}"}

    # Verify by reloading; revert on failure.
    plugin_system.load_all()
    now = next((p for p in plugin_system.list_plugins() if p.get("name") == name), None)
    if now and now.get("status") == "loaded":
        return {"ok": True, "via": "copilot", "detail": f"plugins/{name}/plugin.py repaired and now loads "
                                                        f"(backup: plugin.py.copilot-bak)"}
    # Revert.
    try:
        if os.path.exists(backup):
            os.replace(backup, target)
            plugin_system.load_all()
    except Exception:
        pass
    return {"ok": False, "via": "copilot",
            "detail": f"Copilot fix did not load (reverted): {now.get('error') if now else 'unknown'}"}


# ── dispatch ─────────────────────────────────────────────────────────────────

async def apply_fix(fix: Dict[str, Any], owner: Optional[str] = None) -> Dict[str, Any]:
    """Apply a single fix descriptor from a debugger finding."""
    if not isinstance(fix, dict):
        return {"ok": False, "detail": "no fix descriptor"}
    kind = fix.get("kind")
    if kind == "setting":
        return _apply_setting(fix)
    if kind == "command":
        return _apply_command(fix)
    if kind == "plugin_repair":
        name = fix.get("plugin")
        if not name:
            return {"ok": False, "detail": "plugin_repair fix missing 'plugin'"}
        return await copilot_repair_plugin(name)
    return {"ok": False, "detail": f"unknown fix kind {kind!r}"}
