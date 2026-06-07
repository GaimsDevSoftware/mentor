"""plugin_forge — Copilot builds simple plugins for the user ("vibe coding"), safely.

The flow: the agent asks the user probing questions until the intent is clear, then
calls build_plugin(name, intent). The teacher model generates a manifest + plugin.py
against a strict scaffold; we then, WITHOUT trusting the output:

  1. write it under plugins/<slug>/ ONLY (path-guarded — never escapes the tree),
  2. force the manifest to enabled=false (a DRAFT — it does not auto-load),
  3. validate declared permissions, py_compile the code,
  4. verify it would load (briefly enable → load_all → check → back to draft),
  5. return the code for the USER to review and explicitly enable.

Nothing generated ever runs until the user enables it. Once enabled, its tool calls
still pass through Aegis and it must satisfy the debugger contract. This is the
responsible shape for letting an LLM author code that runs in-process.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from src.copilot_fix import _within  # reuse the strict plugins/ path guard

VALID_PERMISSIONS = {"tools", "hooks", "cookbook", "services", "routes"}


def _plugins_root() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return s or "plugin"


SCAFFOLD_GUIDE = """\
You are generating a SMALL Odysseus plugin for a non-technical user. Output EXACTLY
two fenced blocks and nothing else:

1) a ```json block: the manifest plugin.json with keys name, version ("0.1.0"),
   description, permissions (subset of: tools, hooks, cookbook, services, routes —
   declare ONLY what you use), entry ("plugin"), enabled (false).
2) a ```python block: plugin.py exposing `def register(api):`.

Rules:
- Keep it SIMPLE and SELF-CONTAINED. Prefer a single tool and/or a diagnostic hook.
- Use the API: api.register_tool(name, async_handler, description=..., risk_category=
  "read"|"data-write"|"external"|...), api.register_hook("diagnostic"|"build_prompt"|
  "post_tool", fn), api.register_repair(fn), api.get_setting(key, default), api.logger.
- A tool handler is `async def handler(content, owner): return {"response": "...", "exit_code": 0}`.
  `content` is the raw string the model passed (may be JSON).
- ALWAYS register a `diagnostic` hook returning {"name","status":"ok","detail","hint"}
  so the plugin is debugger-compatible.
- Do NOT import app internals beyond `api`. Do NOT touch the filesystem outside what's
  necessary. Do NOT call network/secrets unless the user explicitly asked. No infinite loops.

USER INTENT:
{intent}

EXISTING PLUGINS (avoid duplicating): {existing}
"""


def _extract_blocks(text: str) -> Tuple[Optional[dict], Optional[str], str]:
    """Pull the json manifest + python code from the teacher reply."""
    jm = re.search(r"```json\s*\n(\{.*?\})\s*\n```", text or "", re.S)
    pm = re.search(r"```python\s*\n(.*?)\n```", text or "", re.S)
    manifest = None
    if jm:
        try:
            manifest = json.loads(jm.group(1))
        except Exception:
            manifest = None
    code = pm.group(1).strip() if pm else None
    note = "" if (manifest and code) else "missing json or python block"
    return manifest, code, note


def _sanitize_manifest(manifest: dict, slug: str) -> Tuple[Optional[dict], str]:
    if not isinstance(manifest, dict):
        return None, "manifest is not an object"
    perms = manifest.get("permissions", []) or []
    bad = [p for p in perms if p not in VALID_PERMISSIONS]
    if bad:
        return None, f"manifest declares unknown permissions {bad}"
    clean = {
        "name": str(manifest.get("name") or slug),
        "version": str(manifest.get("version") or "0.1.0"),
        "description": str(manifest.get("description") or "")[:500],
        "permissions": [p for p in perms if p in VALID_PERMISSIONS],
        "entry": "plugin",
        "enabled": False,  # ALWAYS a draft — user must enable after review
    }
    return clean, ""


def build_from_code(slug: str, manifest: dict, code: str,
                    overwrite: bool = False) -> Dict[str, Any]:
    """The verification pipeline (no LLM): write → compile → load-verify. Returns
    a result with the code and whether it would load. Always leaves it DISABLED."""
    slug = _slugify(slug)
    pdir = os.path.join(_plugins_root(), slug)
    if not _within(pdir, _plugins_root()):
        return {"ok": False, "detail": "refused: target escaped the plugins tree"}
    if os.path.isdir(pdir) and not overwrite:
        return {"ok": False, "detail": f"plugins/{slug}/ already exists (pass overwrite=true to replace)"}

    clean, err = _sanitize_manifest(manifest, slug)
    if not clean:
        return {"ok": False, "detail": err}
    if not code or "def register" not in code:
        return {"ok": False, "detail": "generated code has no register(api) function"}

    os.makedirs(pdir, exist_ok=True)
    mpath = os.path.join(pdir, "plugin.json")
    cpath = os.path.join(pdir, "plugin.py")
    # final path re-assertion before writing
    for p in (mpath, cpath):
        if not _within(p, _plugins_root()):
            return {"ok": False, "detail": "refused: write target escaped the plugins tree"}
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    with open(cpath, "w", encoding="utf-8") as f:
        f.write(code + ("\n" if not code.endswith("\n") else ""))

    # 1) syntax
    import py_compile
    try:
        py_compile.compile(cpath, doraise=True)
    except Exception as e:
        return {"ok": False, "detail": f"draft written but does NOT compile: {e}",
                "slug": slug, "status": "draft-broken", "manifest": clean, "code": code}

    # 2) would-it-load: briefly enable → load_all → check → back to draft
    loaded_ok, load_err = _verify_loads(slug, mpath, clean)

    return {"ok": True, "slug": slug, "status": "draft" + ("" if loaded_ok else "-broken"),
            "would_load": loaded_ok, "load_error": load_err,
            "manifest": clean, "code": code,
            "detail": (f"Draft created at plugins/{slug}/ (DISABLED). "
                       + ("Verified it loads. Review the code, then enable it."
                          if loaded_ok else f"It does not load yet: {load_err}"))}


def _verify_loads(slug: str, mpath: str, manifest: dict) -> Tuple[bool, str]:
    from src import plugin_system
    try:
        m = dict(manifest)
        m["enabled"] = True
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        plugin_system.load_all()
        rec = next((p for p in plugin_system.list_plugins() if p.get("name") == manifest["name"]
                    or os.path.basename(p.get("dir", "")) == slug), None)
        ok = bool(rec and rec.get("status") == "loaded")
        err = "" if ok else (rec.get("error") if rec else "not discovered")
        return ok, err or ""
    except Exception as e:
        return False, str(e)
    finally:
        # always revert to draft
        try:
            m = dict(manifest)
            m["enabled"] = False
            with open(mpath, "w", encoding="utf-8") as f:
                json.dump(m, f, indent=2)
            plugin_system.load_all()
        except Exception:
            pass


def enable_plugin(slug: str) -> Dict[str, Any]:
    """User-confirmed enable: flip the manifest to enabled and load it."""
    slug = _slugify(slug)
    mpath = os.path.join(_plugins_root(), slug, "plugin.json")
    if not _within(mpath, _plugins_root()) or not os.path.exists(mpath):
        return {"ok": False, "detail": f"no plugin draft at plugins/{slug}/"}
    try:
        m = json.loads(open(mpath, encoding="utf-8").read())
        m["enabled"] = True
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        from src import plugin_system
        plugin_system.load_all()
        rec = next((p for p in plugin_system.list_plugins()
                    if p.get("name") == m.get("name")), None)
        if rec and rec.get("status") == "loaded":
            return {"ok": True, "detail": f"Enabled plugins/{slug}/. (Note: any HTTP routes "
                                          f"or background services it adds take effect after an app restart.)"}
        return {"ok": False, "detail": f"enabled but failed to load: {rec.get('error') if rec else '?'}"}
    except Exception as e:
        return {"ok": False, "detail": f"enable failed: {e}"}


def _teacher_spec() -> str:
    from src.settings import get_setting
    return (get_setting("improve_teacher_model", "") or get_setting("teacher_model", "") or "").strip()


def aider_bin() -> Optional[str]:
    """Resolve the aider binary: PATH first, then ~/.local/bin (where
    `uv tool install` / the install button puts it, which the systemd service's
    PATH may not include)."""
    import shutil
    found = shutil.which("aider")
    if found:
        return found
    local = os.path.expanduser("~/.local/bin/aider")
    return local if os.path.exists(local) else None


def _aider_available() -> bool:
    return aider_bin() is not None


async def build_with_aider(slug: str, intent: str, overwrite: bool = False) -> Dict[str, Any]:
    """Build a plugin with Aider (free, git-aware code editor, BYO local model — see
    research-cache:free-ai-coding-assistants-2026). Scaffolds the files, lets Aider
    edit them per the intent, then runs the SAME safe verify pipeline (forced draft,
    compile, load-check). Aider runs scoped to the plugin dir with --no-git, only the
    two plugin files in its chat — it can't touch the rest of the app."""
    from src.settings import get_setting
    model = (get_setting("aider_model", "") or "").strip()
    if not model:
        return {"ok": False, "detail": "set aider_model (e.g. ollama/qwen3-coder) to use the Aider builder"}
    pdir = os.path.join(_plugins_root(), slug)
    if not _within(pdir, _plugins_root()):
        return {"ok": False, "detail": "refused: escaped plugins tree"}
    if os.path.isdir(pdir) and not overwrite:
        return {"ok": False, "detail": f"plugins/{slug}/ already exists (pass overwrite=true)"}
    os.makedirs(pdir, exist_ok=True)
    # Scaffold so Aider has files to edit (manifest stays a DRAFT).
    with open(os.path.join(pdir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump({"name": slug, "version": "0.1.0", "description": "",
                   "permissions": [], "entry": "plugin", "enabled": False}, f, indent=2)
    with open(os.path.join(pdir, "plugin.py"), "w", encoding="utf-8") as f:
        f.write("def register(api):\n    pass\n")

    msg = ("Implement this Odysseus plugin by editing plugin.py and plugin.json.\n"
           + SCAFFOLD_GUIDE.format(intent=intent.strip()[:2000], existing="(see other plugins)")
           + "\nKeep manifest enabled=false. Edit ONLY these two files.")
    import asyncio
    _bin = aider_bin()
    if not _bin:
        return {"ok": False, "detail": "aider not installed (use the Install Aider button in /manage)"}
    try:
        proc = await asyncio.create_subprocess_exec(
            _bin, "--model", model, "--no-git", "--yes-always",
            "--message", msg, "plugin.py", "plugin.json",
            cwd=pdir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            await asyncio.wait_for(proc.wait(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "detail": "Aider timed out (300s)"}
    except FileNotFoundError:
        return {"ok": False, "detail": "aider not installed (pip install aider-chat)"}
    except Exception as e:
        return {"ok": False, "detail": f"Aider run failed: {e}"}

    try:
        manifest = json.loads(open(os.path.join(pdir, "plugin.json"), encoding="utf-8").read())
        code = open(os.path.join(pdir, "plugin.py"), encoding="utf-8").read()
    except Exception as e:
        return {"ok": False, "detail": f"could not read Aider output: {e}"}
    res = build_from_code(slug, manifest, code, overwrite=True)
    res["via"] = "aider"
    return res


async def build_plugin(name: str, intent: str, overwrite: bool = False) -> Dict[str, Any]:
    """Generate a plugin from a natural-language intent, then run it through the
    safe verification pipeline. Backend (setting `plugin_builder_backend`):
    "aider" (free git-aware editor), "teacher" (the teacher model), or "auto"
    (Aider if installed + aider_model set, else teacher). Returns the draft + code."""
    slug = _slugify(name)
    if not (intent or "").strip():
        return {"ok": False, "detail": "no intent provided — ask the user what the plugin should do first"}

    from src.settings import get_setting
    backend = str(get_setting("plugin_builder_backend", "auto") or "auto").lower()
    use_aider = backend == "aider" or (
        backend == "auto" and _aider_available() and (get_setting("aider_model", "") or "").strip())
    if use_aider:
        return await build_with_aider(slug, intent, overwrite=overwrite)

    spec = _teacher_spec()
    if not spec:
        return {"ok": False, "detail": "no teacher model configured — set teacher_model to use the plugin builder"}
    if not (intent or "").strip():
        return {"ok": False, "detail": "no intent provided — ask the user what the plugin should do first"}

    try:
        from src import plugin_system
        existing = ", ".join(p.get("name", "?") for p in plugin_system.list_plugins()) or "(none)"
    except Exception:
        existing = "(none)"
    prompt = SCAFFOLD_GUIDE.format(intent=intent.strip()[:2000], existing=existing)

    try:
        from src.ai_interaction import _resolve_model
        from src.llm_core import complete_with_continuation
        url, model, headers = _resolve_model(spec)
        reply = await complete_with_continuation(
            url, model,
            [{"role": "system", "content": "You write small, safe Odysseus plugins."},
             {"role": "user", "content": prompt}],
            headers=headers, max_tokens=4000, timeout=180)
    except Exception as e:
        return {"ok": False, "detail": f"plugin generation call failed: {e}"}

    manifest, code, note = _extract_blocks(reply)
    if not manifest or not code:
        return {"ok": False, "detail": f"teacher did not return a usable plugin ({note})",
                "raw": (reply or "")[:600]}
    return build_from_code(slug, manifest, code, overwrite=overwrite)
