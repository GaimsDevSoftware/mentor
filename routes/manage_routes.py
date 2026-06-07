"""Manage routes — a clickable admin UI for the plugin/diagnostics features.

Everything we built is API-first; this gives it a real interface without touching
the main SPA. Serves a self-contained page at /manage (admin) that calls the
existing JSON endpoints (debug, debug/fix, plugin login/recommend) plus three
small helpers added here: list plugins, toggle a plugin, set a whitelisted setting.

The page rides the logged-in browser session, so its same-origin fetches are
authenticated exactly like the rest of the UI.
"""
import getpass
import json
import os
import random
import re
import time
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import HTMLResponse

from core.middleware import require_admin

# Settings the management UI may change (config + tokens — NOT auth/bind/secrets).
MANAGE_SETTING_KEYS = {
    "aegis_mode", "aegis_block_threshold", "aegis_warn_threshold",
    "fleet_mode", "recommend_scope", "history_rag_enabled", "plugins_enabled",
    "caveman_enabled", "caveman_level",
    "agent_continue_on_truncation", "agent_max_continuations",
    "agent_local_no_think", "agent_local_min_predict",
    "opencode_include_paid", "openrouter_tier", "search_model_mode", "autoheal_enabled",
    "telegram_bot_token", "telegram_allowed_user_ids", "telegram_owner", "telegram_mode",
    "ollama_flash_attention", "ollama_kv_cache_type",
    "teacher_model", "improve_teacher_model",
    # Model-role pickers — exposed as discovered-model dropdowns (no free-text).
    "default_model", "utility_model", "research_model", "task_model", "vision_model",
}

# Core (non-plugin) settings shown on the manage "Settings" tab. Each carries
# its option list and a plain-language description. The description doubles as
# context for the AI "explain" helper and as a non-AI fallback tooltip, so the
# UI can describe what every switch means for THIS install. teacher_model is
# added separately (it's a discovered-model dropdown — see core_settings()).
CORE_SETTINGS_META = [
    {"key": "aegis_mode", "label": "Aegis firewall", "type": "select",
     "options": ["off", "audit", "enforce"],
     "desc": "Aegis is the prompt-injection / unsafe-action firewall that scores risky tool calls. off = no checks; audit = scores and logs but still runs the call; enforce = blocks any call scoring at/above the block threshold."},
    {"key": "fleet_mode", "label": "Fleet mode", "type": "select",
     "options": ["auto", "single", "fleet"],
     "desc": "How model serving is spread across machines. single = only this machine; fleet = use every configured node; auto = decide from what is reachable right now."},
    {"key": "recommend_scope", "label": "Recommend scope", "type": "select",
     "options": ["both", "local", "sources"],
     "desc": "Which models the Copilot 'recommend roles' picks from: local fleet only, logged-in cloud sources only, or both."},
    {"key": "openrouter_tier", "label": "OpenRouter tier", "type": "select",
     "options": ["free", "paid", "both"],
     "desc": "Which OpenRouter models to surface: only the no-cost :free models, only paid models, or both."},
    {"key": "caveman_level", "label": "Caveman level", "type": "select",
     "options": ["minimal", "structural", "aggressive"],
     "desc": "How hard the 'caveman' compressor squeezes long tool results before they re-enter context. minimal = light touch; structural = drop boilerplate, keep structure; aggressive = maximum squeeze, may lose detail. Saves context tokens on small local models."},
    {"key": "history_rag_enabled", "label": "History RAG", "type": "select",
     "options": ["true", "false"],
     "desc": "When on, past conversations are embedded and the most relevant snippets are retrieved into context for new questions (requires the embeddings/ChromaDB service). Off = the model only sees the current thread."},
    {"key": "agent_continue_on_truncation", "label": "Continue on truncation", "type": "select",
     "options": ["true", "false"],
     "desc": "If a local model stops mid-answer because it hit its output limit, automatically send a 'continue' so the reply finishes instead of being cut off."},
    {"key": "opencode_include_paid", "label": "OpenCode include paid", "type": "select",
     "options": ["false", "true"],
     "desc": "Allow per-request paid OpenCode models (Claude, GPT, …) alongside the free/subscription ones. Off keeps you on no-extra-cost models only."},
    {"key": "search_model_mode", "label": "Search model", "type": "select",
     "options": ["app", "local", "cloud"],
     "desc": "Which model runs multi-step web search (it follows the 'multi-step-web-search' recipe: search → read → refine → re-search). app = the app's configured AI (default/research model); local = a local model (private, free, but weaker — the recipe helps it search well); cloud = one of your cloud models (stronger, costs/sends data out). Falls back to the app model if the chosen tier has no endpoint."},
    {"key": "autoheal_enabled", "label": "Auto-heal", "type": "select",
     "options": ["false", "true"],
     "desc": "When on, the app periodically checks its own health and AUTO-APPLIES only the safe, reversible setting fixes from diagnostics (the same ones behind 'Fix all safe issues') — so the health badge keeps itself green. It never auto-runs riskier fixes (starting services, reindexing, plugin repair); those stay one-click. Off by default."},
]
_PLUGINS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")
_NAME_RE = re.compile(r"^[a-z0-9_]+$")

# State for the one-click Aider installer (isolated, background, ADAPTIVE).
_install_state: Dict[str, Any] = {"status": "idle", "log": "", "code": None, "strategy": None}


def _detect_python_env() -> Dict[str, Any]:
    """Inspect the host: running Python, any compatible (3.9–3.12) interpreter, uv/pipx."""
    import subprocess
    import sys
    import shutil as _sh

    def _ver(pybin):
        try:
            out = subprocess.run([pybin, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
                                 capture_output=True, text=True, timeout=5)
            return out.stdout.strip() if out.returncode == 0 else None
        except Exception:
            return None

    running = "%d.%d" % sys.version_info[:2]
    compatible = None
    for cand in ("python3.12", "python3.11", "python3.10", "python3.9", "python3"):
        p = _sh.which(cand)
        if not p:
            continue
        v = _ver(p)
        try:
            mj, mn = (int(x) for x in (v or "").split(".")[:2])
        except Exception:
            continue
        if mj == 3 and 9 <= mn <= 12:
            compatible = {"bin": p, "version": v}
            break
    return {"running": running, "compatible": compatible,
            "has_uv": bool(_sh.which("uv")), "has_pipx": bool(_sh.which("pipx"))}


def _plan_aider_install(env: Dict[str, Any]) -> Dict[str, str]:
    """Pick the install approach from the detected environment. Returns
    {strategy, script, explanation}. Everything lands in ~/.local/bin (where
    aider_bin() looks) and never touches the Odysseus venv."""
    mkbin = 'mkdir -p "$HOME/.local/bin"; '
    if env["has_uv"]:
        return {"strategy": "uv",
                "script": 'uv tool install --python 3.12 aider-chat && "$HOME/.local/bin/aider" --version',
                "explanation": "uv is installed → installs aider with Python 3.12 (isolated)."}
    if env["compatible"]:
        py, v = env["compatible"]["bin"], env["compatible"]["version"]
        script = (mkbin + f'"{py}" -m venv "$HOME/.aider-venv" && '
                  '"$HOME/.aider-venv/bin/pip" install -q -U pip setuptools wheel && '
                  '"$HOME/.aider-venv/bin/pip" install aider-chat && '
                  'ln -sf "$HOME/.aider-venv/bin/aider" "$HOME/.local/bin/aider" && '
                  '"$HOME/.local/bin/aider" --version')
        return {"strategy": "system-venv",
                "script": script,
                "explanation": f"Found Python {v} at {py} → installs aider in an isolated venv with it (no download)."}
    return {"strategy": "uv-bootstrap",
            "script": (mkbin + 'set -o pipefail; echo "[1/2] installing uv…"; '
                       'curl -LsSf https://astral.sh/uv/install.sh | sh && '
                       'export PATH="$HOME/.local/bin:$PATH" && echo "[2/2] installing aider (python 3.12)…" && '
                       'uv tool install --python 3.12 aider-chat && "$HOME/.local/bin/aider" --version'),
            "explanation": f"Running Python {env['running']} is too new and no uv / compatible Python found → "
                           "installs uv (it fetches its own Python 3.12), then aider."}


async def _run_aider_install():
    import asyncio
    plan = _plan_aider_install(_detect_python_env())
    _install_state.update(status="running", log="", code=None, strategy=plan["strategy"])
    try:
        proc = await asyncio.create_subprocess_shell(
            plan["script"], executable="/bin/bash",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=900)
        _install_state.update(status=("done" if proc.returncode == 0 else "failed"),
                              code=proc.returncode, log=(out or b"").decode(errors="replace")[-6000:])
    except Exception as e:
        _install_state.update(status="failed", code=-1, log=f"{_install_state.get('log','')}\n{e}")


_flavor_cache: Dict[str, Any] = {"name": None, "mems": None, "ts": 0.0}


def _personal_touch() -> str:
    """Occasionally (~1 in 3) return a SHORT instruction for the AI Guide to add a
    single warm sentence using the user's name or a remembered fact — just for a
    livelier vibe. Returns '' most of the time, so it stays rare and low-token."""
    if random.random() > 0.35:
        return ""
    fc = _flavor_cache
    now = time.time()
    if fc["name"] is None:
        try:
            fc["name"] = (getpass.getuser() or "").strip().capitalize()
        except Exception:
            fc["name"] = ""
    if fc["mems"] is None or (now - fc["ts"]) > 300:
        try:
            mpath = os.path.join(os.path.dirname(_PLUGINS_ROOT), "data", "memory.json")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            fc["mems"] = [m.get("text", "") for m in data
                          if isinstance(m, dict) and m.get("text")]
            fc["ts"] = now
        except Exception:
            fc["mems"] = []
    name = fc["name"] or "the user"
    snippet = random.choice(fc["mems"])[:140] if fc["mems"] else ""
    ctx = f"The user is {name}." + (f' Something known about them: "{snippet}".' if snippet else "")
    return ("\n\nPERSONAL TOUCH (optional, keep it tiny): " + ctx +
            " If — and only if — it fits naturally, add ONE short warm sentence that nods to them "
            "by name or to this, for a friendly vibe. One short sentence MAX; never force it, never "
            "pad, skip it if nothing fits.")


def _coerce(key: str, value: Any) -> Any:
    if key == "telegram_allowed_user_ids":
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [s.strip() for s in str(value).replace(";", ",").split(",") if s.strip()]
    if key in ("plugins_enabled", "history_rag_enabled", "caveman_enabled",
               "agent_continue_on_truncation", "agent_local_no_think",
               "opencode_include_paid", "ollama_flash_attention"):
        return str(value).lower() in ("1", "true", "yes", "on") if not isinstance(value, bool) else value
    if key in ("aegis_block_threshold", "aegis_warn_threshold", "agent_max_continuations",
               "agent_local_min_predict"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def setup_manage_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/manage/plugins")
    async def list_plugins(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src import plugin_system
        return {"plugins": plugin_system.list_plugins()}

    @router.post("/api/manage/plugins/toggle")
    async def toggle_plugin(payload: Dict[str, Any] = Body(...),
                            _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        enabled = bool(payload.get("enabled"))
        if not _NAME_RE.match(name):
            return {"ok": False, "detail": "invalid plugin name"}
        manifest = os.path.join(_PLUGINS_ROOT, name, "plugin.json")
        if not os.path.realpath(manifest).startswith(os.path.realpath(_PLUGINS_ROOT) + os.sep) \
                or not os.path.exists(manifest):
            return {"ok": False, "detail": f"no plugin '{name}'"}
        try:
            m = json.loads(open(manifest, encoding="utf-8").read())
            m["enabled"] = enabled
            with open(manifest, "w", encoding="utf-8") as f:
                json.dump(m, f, indent=2)
            from src import plugin_system
            plugin_system.load_all()
            return {"ok": True, "detail": f"{name} {'enabled' if enabled else 'disabled'} "
                                         f"(routes/services need an app restart to (un)mount)"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    @router.post("/api/manage/setting")
    async def set_setting(payload: Dict[str, Any] = Body(...),
                          _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        key = str(payload.get("key", ""))
        try:
            from src import plugin_system
            _plugin_keys = plugin_system.plugin_setting_keys()
        except Exception:
            _plugin_keys = set()
        if key not in MANAGE_SETTING_KEYS and key not in _plugin_keys:
            return {"ok": False, "detail": f"setting '{key}' is not manageable here"}
        try:
            from src.settings import load_settings, save_settings
            s = dict(load_settings())
            old = s.get(key)
            s[key] = _coerce(key, payload.get("value"))
            save_settings(s)
            shown = "•••" if "token" in key else s[key]
            return {"ok": True, "detail": f"{key} updated", "value": shown,
                    "changed": old != s[key]}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    @router.get("/api/manage/aider/models")
    async def aider_models(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """List models Aider can use, in its provider/model format. Pulls local
        Ollama tags + any logged-in remote source (opencode Zen, OpenRouter)."""
        out = []
        # 1) Local Ollama
        try:
            import httpx
            host = os.environ.get("LLM_HOST", "localhost")
            r = httpx.get(f"http://{host}:11434/api/tags", timeout=3)
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    if m.get("name"):
                        out.append(f"ollama/{m['name']}")
        except Exception:
            pass
        # 2) Remote sources from registered cookbook providers
        try:
            from src import plugin_system
            for prov in plugin_system.get_cookbook_providers():
                try:
                    cat = prov.catalog() if hasattr(prov, "catalog") else []
                except Exception:
                    cat = []
                for m in cat:
                    if not isinstance(m, dict) or not m.get("remote"):
                        continue
                    mid = m.get("model", "")
                    if not mid:
                        continue
                    src = (m.get("source") or m.get("endpoint") or "").lower().replace(" ", "")
                    if "openrouter" in src:
                        out.append(f"openrouter/{mid}")
                    elif "opencode" in src or "zen" in src:
                        out.append(f"opencode/{mid}")
        except Exception:
            pass
        return {"models": sorted(set(out))}

    @router.get("/api/manage/fs/git-repos")
    async def git_repos(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Find git repositories under $HOME so the user can pick one — bounded
        in depth + count so it never walks the whole filesystem."""
        home = os.path.expanduser("~")
        repos = []
        skip = {"node_modules", "venv", ".venv", "__pycache__", "target", "build",
                "dist", ".cache", ".local", "go", "Real-ESRGAN"}
        for root, dirs, _ in os.walk(home):
            depth = root[len(home):].count(os.sep)
            if depth > 3:
                dirs.clear()
                continue
            if ".git" in dirs:
                repos.append(root)
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip]
            if len(repos) >= 30:
                break
        return {"repos": sorted(repos)}

    @router.get("/api/manage/plugin-stats")
    async def plugin_stats(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Per-plugin metrics + AI insight, rendered as mini-tiles in /manage."""
        from src import plugin_system
        return {"stats": plugin_system.run_stats()}

    @router.post("/api/manage/explain")
    async def explain(payload: Dict[str, Any], _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """AI-guide for a single setting: plain-language explanation of what the
        field does, what's recommended for the user's situation, and what their
        current value implies. Uses teacher_model (free if it's a local coder)."""
        plugin = str(payload.get("plugin", ""))
        key = str(payload.get("key", ""))
        if not key:
            return {"ok": False, "detail": "no setting key"}
        try:
            from src.settings import get_setting
            current = get_setting(key, None)
        except Exception:
            current = None
        # find descriptor — first among plugin settings, then the core
        # settings catalog, then any hints the client passed alongside.
        descriptor = None
        try:
            from src import plugin_system
            for ds in plugin_system.plugin_settings().values():
                for d in ds:
                    if d.get("key") == key:
                        descriptor = d
                        break
                if descriptor:
                    break
        except Exception:
            pass
        if descriptor is None:
            for m in CORE_SETTINGS_META:
                if m["key"] == key:
                    descriptor = dict(m)
                    break
        if descriptor is None and key in ("teacher_model", "improve_teacher_model"):
            descriptor = {"label": "Teacher model", "type": "select",
                          "desc": "The capable model the app escalates to when a local model fails an "
                                  "agent task; it writes a reusable SKILL.md so the local model can do it "
                                  "next time. Format is 'model@endpoint'."}
        # Let the client enrich a thin/absent descriptor (label/type/desc/options).
        descriptor = dict(descriptor or {})
        for hk in ("label", "type", "desc", "options"):
            if not descriptor.get(hk) and payload.get(hk):
                descriptor[hk] = payload.get(hk)
        try:
            from src.settings import get_setting as _gs
            spec = (_gs("improve_teacher_model", "") or _gs("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "No AI configured. Set teacher_model (a local coder is free)."}
        prompt = (f"You are a concise UI helper. The user is looking at a setting "
                  f"in a self-hosted AI app called Odysseus (local-first, often running "
                  f"small local models on one machine).\n\n"
                  f"Setting: {key}\n"
                  f"Plugin: {plugin or '(core)'}\n"
                  f"Type: {descriptor.get('type', '?')}\n"
                  f"Label: {descriptor.get('label', key)}\n"
                  f"Possible values: {descriptor.get('options') or '(free text)'}\n"
                  f"What it does (reference): {descriptor.get('desc') or '(unknown)'}\n"
                  f"Default: {descriptor.get('default')!r}\n"
                  f"Current value: {current!r}\n\n"
                  f"In 3 short paragraphs, explain: (1) what this controls in plain language, "
                  f"(2) what value is typically recommended and why, "
                  f"(3) what the user's CURRENT value means for them. "
                  f"Be concrete and brief; avoid filler." + _personal_touch())
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You are a concise, helpful UI assistant."},
                 {"role": "user", "content": prompt}],
                headers=headers or {}, max_tokens=600, timeout=90)
            return {"ok": True, "explanation": (reply or "").strip()}
        except Exception as e:
            return {"ok": False, "detail": f"AI call failed: {e}"}

    @router.post("/api/manage/explain-finding")
    async def explain_finding(payload: Dict[str, Any], _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """AI-guide for a single diagnostics finding: what the problem means for
        THIS install, whether it actually matters, and concrete steps to fix it.
        Uses teacher_model (free if it's a local coder)."""
        area = str(payload.get("area", ""))
        name = str(payload.get("name", ""))
        status = str(payload.get("status", ""))
        detail = str(payload.get("detail", ""))
        hint = str(payload.get("hint", ""))
        if not name:
            return {"ok": False, "detail": "no finding"}
        try:
            from src.settings import get_setting as _gs
            spec = (_gs("improve_teacher_model", "") or _gs("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "No AI configured. Set teacher_model (a local coder is free)."}
        prompt = (f"You are a concise ops helper for Odysseus, a self-hosted, local-first AI app "
                  f"(often one machine, small local models, plus optional cloud sources).\n\n"
                  f"A health check reported:\n"
                  f"Area: {area}\nCheck: {name}\nStatus: {status}\n"
                  f"Detail: {detail}\nSuggested hint: {hint or '(none)'}\n\n"
                  f"In 3 short paragraphs explain: (1) what this finding means in plain language, "
                  f"(2) whether it actually matters for a local-first single-machine setup and how "
                  f"urgent it is, (3) the concrete steps to fix it (commands/settings). "
                  f"Be specific and brief; no filler." + _personal_touch())
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You are a concise, helpful operations assistant."},
                 {"role": "user", "content": prompt}],
                headers=headers or {}, max_tokens=600, timeout=90)
            return {"ok": True, "explanation": (reply or "").strip()}
        except Exception as e:
            return {"ok": False, "detail": f"AI call failed: {e}"}

    @router.get("/api/manage/trace")
    async def trace(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Recent agent activity for the trace viewer: Aegis tool-call risk log
        (what tools ran, their risk score/band) + recent self-coder proposals."""
        from src.constants import DATA_DIR
        aegis = []
        try:
            with open(os.path.join(DATA_DIR, "aegis_audit.jsonl"), "r", encoding="utf-8") as f:
                for line in f.readlines()[-80:]:
                    try:
                        e = json.loads(line)
                        aegis.append({k: e.get(k) for k in
                                      ("ts", "tool", "category", "score", "band", "mode", "session_id", "reasons")})
                    except Exception:
                        pass
        except Exception:
            pass
        aegis.reverse()
        proposals = []
        try:
            from src import plugin_system
            sc = plugin_system.run_stats() if hasattr(plugin_system, "run_stats") else {}
        except Exception:
            sc = {}
        return {"aegis": aegis, "stats": sc}

    @router.get("/api/manage/usage")
    async def usage(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Per-endpoint token usage, tier-aware — so you can watch cloud spend.
        Local = free + private; cloud counts against your usage limits."""
        from core.database import SessionLocal, ModelEndpoint
        from src.endpoint_resolver import _is_local_base, normalize_base
        from src import usage_ledger
        rows = []
        db = SessionLocal()
        try:
            for ep in db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all():
                local = _is_local_base(normalize_base(ep.base_url))
                s = usage_ledger.summary(ep.name)
                rows.append({"name": ep.name, "local": local,
                             "today": s.get("today", {}), "month": s.get("month", {})})
        finally:
            db.close()
        rows.sort(key=lambda r: (r["local"], -((r["month"].get("in", 0)) + (r["month"].get("out", 0)))))
        return {"endpoints": rows}

    @router.post("/api/manage/explain-topic")
    async def explain_topic(payload: Dict[str, Any], _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """AI-guide for any concept/section in the UI (Cookbook, etc.): plain-language
        explanation tailored to the user's actual setup. Pass {topic, context?}.
        Uses teacher_model (free if it's a local coder)."""
        topic = str(payload.get("topic", "")).strip()
        context = str(payload.get("context", "")).strip()
        if not topic:
            return {"ok": False, "detail": "no topic"}
        try:
            from src.settings import get_setting as _gs
            spec = (_gs("improve_teacher_model", "") or _gs("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "No AI configured. Set teacher_model (a local coder is free)."}
        prompt = (f"You are a concise UI helper for Odysseus, a self-hosted, local-first AI app "
                  f"(often one machine, small local models, plus optional cloud sources).\n\n"
                  f"The user is looking at this part of the interface: {topic}\n"
                  + (f"Their setup / current context: {context}\n" if context else "")
                  + f"\nIn 2-3 short paragraphs, explain in plain language: what this section is for, "
                  f"how the user would use it, and what it means for THEIR specific setup above. "
                  f"Be concrete and brief; no filler, no markdown headers." + _personal_touch())
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You are a concise, helpful UI assistant."},
                 {"role": "user", "content": prompt}],
                headers=headers or {}, max_tokens=600, timeout=90)
            return {"ok": True, "explanation": (reply or "").strip()}
        except Exception as e:
            return {"ok": False, "detail": f"AI call failed: {e}"}

    @router.get("/api/manage/teacher-model-options")
    async def teacher_model_options(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Discovered models as `model@endpoint` specs, for the teacher_model
        dropdown. Pulls every enabled endpoint's cached model list (local/Ollama,
        OpenCode, OpenRouter, …) so the admin can pick instead of typing a spec."""
        from core.database import SessionLocal, ModelEndpoint
        specs, seen = [], set()
        db = SessionLocal()
        try:
            for ep in db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all():
                try:
                    models = json.loads(ep.cached_models) if ep.cached_models else []
                except Exception:
                    models = []
                try:
                    hidden = set(json.loads(ep.hidden_models)) if ep.hidden_models else set()
                except Exception:
                    hidden = set()
                for m in models:
                    if not m or m in hidden:
                        continue
                    spec = f"{m}@{ep.name}"
                    if spec not in seen:
                        seen.add(spec)
                        specs.append(spec)
        finally:
            db.close()
        specs.sort(key=str.lower)
        return {"models": specs}

    @router.get("/api/manage/core-settings")
    async def core_settings(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """The non-plugin settings on the Settings tab, each with its current
        value — so the UI can render selects (correct option pre-selected) and
        the AI 'explain' button exactly like plugin settings. teacher_model is
        appended as a discovered-model dropdown."""
        from src.settings import get_setting
        out = []
        for meta in CORE_SETTINGS_META:
            cur = get_setting(meta["key"], None)
            if isinstance(cur, bool):
                cur = "true" if cur else "false"
            out.append({**meta, "current": cur})
        out.append({
            "key": "teacher_model", "label": "Teacher model", "type": "select",
            "suggest_url": "/api/manage/teacher-model-options",
            "desc": "The capable model the app escalates to when a local model fails an agent task; "
                    "it writes a reusable SKILL.md so the local model can do it next time. Format is "
                    "'model@endpoint'. A local coder or a free model works and costs nothing.",
            "current": get_setting("teacher_model", "") or "",
        })
        # Every model-role setting as a discovered-model dropdown (no free-text
        # typing of model names). "— choose —" / blank means auto-pick.
        _MODEL_ROLES = [
            ("default_model", "Default model",
             "The main model for chat and most agent work. Leave blank to auto-pick a running model."),
            ("utility_model", "Utility model",
             "A small, cheap/fast model for quick internal jobs (chat titles, tags, summaries). Blank = reuse the default."),
            ("research_model", "Research model",
             "Model used for Deep Research runs. Blank = reuse the default. A strong model gives better reports."),
            ("task_model", "Task model",
             "Model for scheduled / background tasks that run without you watching. Blank = reuse the default."),
            ("vision_model", "Vision model",
             "Model used to read images you send. Must be a vision-capable model. Blank = auto if the default can see."),
            ("improve_teacher_model", "Improve-loop teacher",
             "The capable model the self-improvement loop escalates to when it gets stuck. Blank = reuse Teacher model."),
        ]
        for _k, _label, _desc in _MODEL_ROLES:
            out.append({
                "key": _k, "label": _label, "type": "select",
                "suggest_url": "/api/manage/teacher-model-options",
                "desc": _desc + " Format is 'model@endpoint' — pick from the list, no typing.",
                "current": get_setting(_k, "") or "",
            })
        return {"settings": out}

    @router.post("/api/manage/plugin-forge/interview")
    async def plugin_forge_interview(payload: Dict[str, Any], _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """One step of the guided plugin interview. Given the user's idea + Q&A so
        far, the teacher model either asks ONE more clarifying question or finalizes
        a build spec (name + plain summary + detailed intent for the generator)."""
        idea = str(payload.get("idea", "")).strip()
        history = [h for h in (payload.get("history") or []) if isinstance(h, dict)]
        if not idea:
            return {"ok": False, "detail": "Describe the plugin idea first."}
        try:
            from src.settings import get_setting as _gs
            spec = (_gs("improve_teacher_model", "") or _gs("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "No AI configured. Set teacher_model (a local coder is free)."}
        qa = "\n".join(f"Q: {h.get('q','')}\nA: {h.get('a','')}" for h in history)
        finalize = len(history) >= 8
        prompt = (
            "You are a friendly, CANDID product designer running an INVESTIGATIVE INTERVIEW with a "
            "NON-TECHNICAL user to design a SMALL, self-contained plugin for Odysseus (a local-first "
            "AI app). Your job: surface every decision that matters for a GOOD plugin and let the USER "
            "decide it — never silently assume.\n\n"
            "Investigate these points (only the ones that matter for THIS idea; skip what's already "
            "clear from the answers):\n"
            " 1. The goal — concretely, what should it do?\n"
            " 2. How it's used — should the AI assistant be able to use it while chatting (a 'tool'), "
            "or is it a background health check, or a small web page? Explain the choice in plain "
            "words; don't just name the type.\n"
            " 3. Inputs — what info does it need each time (e.g. a city, a file, a number)?\n"
            " 4. Output — what should it give back, and in what form?\n"
            " 5. Connections — does it need the internet or an outside account / API key? Flag that "
            "this means extra setup and a possible privacy cost.\n"
            " 6. Settings — anything the user should be able to configure (defaults, a key)?\n"
            " 7. On failure — what should happen if it can't do the job?\n"
            " 8. A short, friendly name.\n\n"
            "RULES:\n"
            "- Ask ONE question at a time, phrased for a normal person. Use NO jargon, or explain any "
            "term in plain words. ALWAYS include a short plain-language 'why' that says what this "
            "decision means and why it matters.\n"
            "- BE HONEST, NOT FLATTERING (honesty over niceness). If the idea won't work, is a bad "
            "fit, duplicates a built-in, or is unwise (security/privacy/performance), block it with "
            "the reason and a better alternative instead of humouring the user.\n"
            "- Finalize only once the decisions that matter for THIS plugin are settled.\n\n"
            f"User's idea: {idea}\n\n"
            + (f"Interview so far:\n{qa}\n\n" if qa else "")
            + ("You have covered the essentials — finalize now (or block it if it shouldn't be built).\n"
               if finalize else "")
            + "Reply with ONLY a single JSON object and nothing else:\n"
              '  to ask:      {"question": "<plain-language question>", '
              '"why": "<one short plain line: what this decides and why it matters>"}\n'
              '  to block:    {"blocked": true, "reason": "<why this should not be built as asked, '
              'in plain language>", "alternative": "<a sounder option, or empty>"}\n'
              '  to finalize: {"ready": true, "name": "<short-kebab-name>", '
              '"summary": "<1-2 plain-language sentences of what it does>", '
              '"concerns": "<honest caveats in plain language; empty only if genuinely none>", '
              '"intent": "<a precise build instruction for a code generator: exact behavior, '
              'whether it is a tool/diagnostic/route, inputs, outputs, any settings, and edge cases>"}'
        )
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You are a candid, technically rigorous advisor. "
                  "You value honesty over niceness and never flatter. Output only JSON."},
                 {"role": "user", "content": prompt}],
                headers=headers or {}, max_tokens=700, timeout=90)
        except Exception as e:
            return {"ok": False, "detail": f"AI call failed: {e}"}
        # Lenient JSON extraction — small local models often wrap JSON in prose.
        parsed = None
        m = re.search(r"\{.*\}", reply or "", re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None
        if not isinstance(parsed, dict):
            # Treat the whole reply as a question rather than failing.
            return {"ok": True, "ready": False, "question": (reply or "Tell me more about what it should do.").strip()}
        if parsed.get("blocked"):
            return {"ok": True, "blocked": True,
                    "reason": str(parsed.get("reason", "This isn't a good fit to build as asked.")).strip(),
                    "alternative": str(parsed.get("alternative", "")).strip()}
        if parsed.get("ready"):
            return {"ok": True, "ready": True,
                    "name": str(parsed.get("name", "")).strip(),
                    "summary": str(parsed.get("summary", "")).strip(),
                    "concerns": str(parsed.get("concerns", "")).strip(),
                    "intent": str(parsed.get("intent", "")).strip()}
        return {"ok": True, "ready": False,
                "question": str(parsed.get("question", "Tell me more.")).strip(),
                "why": str(parsed.get("why", "")).strip()}

    @router.post("/api/manage/plugin-forge/build")
    async def plugin_forge_build(payload: Dict[str, Any], _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Generate a plugin from {name, intent} via plugin_forge — scaffolds
        plugins/<slug>/, verifies it compiles + loads, and leaves it as a DISABLED
        draft for review. overwrite=true replaces an existing draft."""
        from src import plugin_forge
        name = str(payload.get("name", "")).strip()
        intent = str(payload.get("intent", "")).strip()
        if not name or not intent:
            return {"ok": False, "detail": "Need both a name and a build instruction."}
        return await plugin_forge.build_plugin(name, intent, overwrite=bool(payload.get("overwrite")))

    @router.post("/api/manage/plugin-forge/enable")
    async def plugin_forge_enable(payload: Dict[str, Any], _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Enable a draft plugin (flips enabled→true and loads it). HTTP routes /
        services it declares need an app restart to mount."""
        from src import plugin_forge
        slug = str(payload.get("slug", "")).strip()
        if not slug:
            return {"ok": False, "detail": "no slug"}
        return plugin_forge.enable_plugin(slug)

    @router.get("/api/manage/plugin-settings")
    async def plugin_settings(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Per-plugin declared settings + current values, for the UI to render."""
        from src import plugin_system
        from src.settings import get_setting
        out = {}
        for name, descriptors in plugin_system.plugin_settings().items():
            rows = []
            for d in descriptors:
                cur = get_setting(d["key"], d.get("default"))
                if d.get("secret") and cur:
                    cur = "•••"
                rows.append({**d, "current": cur})
            out[name] = rows
        return {"settings": out}

    @router.post("/api/manage/install-aider")
    async def install_aider(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Install uv + aider (isolated, Python 3.12) in the background — what
        Aider vibe-coding needs. Runs `curl … | sh` then `uv tool install`; safe
        because it's isolated (~/.local) and never touches the Odysseus venv."""
        import asyncio
        from src import plugin_forge
        if plugin_forge.aider_bin():
            return {"ok": True, "detail": "aider already installed", "status": "done"}
        if _install_state["status"] == "running":
            return {"ok": True, "detail": "install already running", "status": "running"}
        asyncio.create_task(_run_aider_install())
        return {"ok": True, "detail": "Installing uv + aider in the background (a few minutes). "
                                     "Poll status; the buttons light up when it finishes.",
                "status": "running"}

    @router.get("/api/manage/install-aider/status")
    async def install_aider_status(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src import plugin_forge
        return {**_install_state, "installed": bool(plugin_forge.aider_bin())}

    @router.get("/api/manage/install-aider/plan")
    async def install_aider_plan(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Show what the installer detected + which approach it will use, before running."""
        env = _detect_python_env()
        plan = _plan_aider_install(env)
        return {"env": env, "strategy": plan["strategy"], "explanation": plan["explanation"]}

    @router.post("/api/manage/diagnose")
    async def diagnose(payload: Dict[str, Any] = Body(...),
                       _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Copilot help when something won't install/run: feed it the failure log and
        get a plain-language diagnosis + fix steps. Free if teacher_model is local/free."""
        title = str(payload.get("title", "an operation"))[:200]
        log = str(payload.get("log", ""))[:6000]
        try:
            from src.settings import get_setting
            spec = (get_setting("improve_teacher_model", "") or get_setting("teacher_model", "") or "").strip()
        except Exception:
            spec = ""
        if not spec:
            return {"ok": False, "detail": "No teacher/AI model configured — set teacher_model "
                                          "(a local coder is free) to get AI help here."}
        prompt = (f"This failed on a self-hosted Linux box: {title}\n\nOutput/log:\n{log}\n\n"
                  "Explain in plain language for a non-expert: (1) what went wrong, in one or two "
                  "sentences, and (2) the exact commands/steps to fix it. Be concise and specific.")
        try:
            from src.ai_interaction import _resolve_model
            from src.llm_core import complete_with_continuation
            url, model, headers = _resolve_model(spec)
            reply = await complete_with_continuation(
                url, model,
                [{"role": "system", "content": "You are a concise Linux/Python troubleshooting assistant."},
                 {"role": "user", "content": prompt}],
                headers=headers, max_tokens=1200, timeout=120)
            return {"ok": True, "diagnosis": (reply or "").strip()}
        except Exception as e:
            return {"ok": False, "detail": f"diagnosis call failed: {e}"}

    @router.get("/manage")
    async def manage_page(request: Request, _admin: str = Depends(require_admin)) -> HTMLResponse:
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_PAGE.replace("{{CSP_NONCE}}", nonce))

    return router


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mentor — Plugins & Diagnostics</title>
<style>
 :root, [data-theme="dark"]{
   --bg:#000; --bg-2:#0a0a0c;
   --surface:rgba(28,28,30,0.78); --surface-2:rgba(44,44,46,0.85);
   --sep:rgba(255,255,255,0.08); --sep-2:rgba(255,255,255,0.14);
   --txt:rgba(255,255,255,0.96); --dim:rgba(255,255,255,0.58); --faint:rgba(255,255,255,0.36);
   --brass:#e0a95e; --cyan:#64d2ff; --accent:#0a84ff;
   --ok:#30d158; --warn:#ffd60a; --err:#ff453a;
   --tint:rgba(255,255,255,0.04); --tint-2:rgba(255,255,255,0.06); --tint-3:rgba(255,255,255,0.10);
   --shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px rgba(0,0,0,0.5);
 }
 [data-theme="light"]{
   --bg:#fbfbfd; --bg-2:#f2f2f7;
   --surface:rgba(255,255,255,0.78); --surface-2:rgba(248,248,250,0.92);
   --sep:rgba(0,0,0,0.08); --sep-2:rgba(0,0,0,0.14);
   --txt:#1d1d1f; --dim:rgba(60,60,67,0.6); --faint:rgba(60,60,67,0.36);
   --brass:#b8843a; --cyan:#0a83af; --accent:#0071e3;
   --ok:#248a3d; --warn:#a04400; --err:#c41e3a;
   --tint:rgba(0,0,0,0.04); --tint-2:rgba(0,0,0,0.06); --tint-3:rgba(0,0,0,0.08);
   --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 10px 30px rgba(0,0,0,0.06);
 }
 [data-theme="atlas"]{
   --bg:#f4ede0; --bg-2:#ebe2cf;
   --surface:rgba(252,247,236,0.84); --surface-2:rgba(245,238,222,0.94);
   --sep:rgba(43,58,74,0.12); --sep-2:rgba(43,58,74,0.2);
   --txt:#1f2d3d; --dim:rgba(31,45,61,0.64); --faint:rgba(31,45,61,0.4);
   --brass:#9b6826; --cyan:#1f5471; --accent:#9b6826;
   --ok:#3a7f2b; --warn:#a36a00; --err:#a32d2d;
   --tint:rgba(43,58,74,0.04); --tint-2:rgba(43,58,74,0.07); --tint-3:rgba(43,58,74,0.10);
   --shadow: 0 1px 0 rgba(255,255,255,0.5) inset, 0 8px 22px rgba(43,58,74,0.08);
 }
 *{box-sizing:border-box}
 html,body{margin:0}
 body{
   background: radial-gradient(120% 80% at 50% -10%, var(--bg-2), var(--bg)) fixed;
   color: var(--txt);
   font: 15px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif;
   font-feature-settings: "kern","liga","ss01";
   -webkit-font-smoothing: antialiased;
   padding: 40px 32px 60px; max-width: 1100px; margin: 0 auto;
   letter-spacing:-0.005em;
 }
 h1{ font:600 28px/1.15 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif; letter-spacing:-0.02em; margin:0 0 6px }
 .sub{ color:var(--dim); font-size:13px; margin-bottom:24px; letter-spacing:-0.003em }
 .tabs{ display:flex; gap:4px; border-bottom:1px solid var(--sep); margin:28px 0 24px; flex-wrap:wrap }
 .tab{ padding:10px 16px; cursor:pointer; color:var(--dim); border-bottom:2px solid transparent;
   border-radius:6px 6px 0 0; font-weight:500; font-size:14px; letter-spacing:-0.003em;
   transition: color .18s ease, background .18s ease, border-color .18s ease; }
 .tab:hover{ color:var(--txt); background:var(--tint) }
 .tab.on{ color:var(--txt); border-color:var(--brass) }
 .panel{display:none} .panel.on{display:block}
 .card{ background:var(--surface); border:1px solid var(--sep); border-radius:14px;
   padding:18px 20px; margin-bottom:12px;
   backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
   box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px rgba(0,0,0,0.5); }
 .row{ display:flex; align-items:center; gap:12px; flex-wrap:wrap }
 .grow{flex:1}
 .mono{ font-family: ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace; font-size:12px }
 button{ background:var(--tint-2); color:var(--txt); border:1px solid var(--sep-2);
   border-radius:9px; padding:7px 14px; cursor:pointer; font:500 13px/1.2 inherit;
   letter-spacing:-0.003em; transition: background .15s, transform .07s, border-color .15s, box-shadow .15s; }
 button:hover{ background:var(--tint-3); border-color:var(--sep-2) }
 button:active{ transform: scale(0.97) }
 button:disabled{ opacity:.45; cursor:default; transform:none }
 button.go{ background:linear-gradient(180deg,
     color-mix(in srgb, var(--accent) 22%, transparent),
     color-mix(in srgb, var(--accent) 12%, transparent));
   border-color: color-mix(in srgb, var(--accent) 50%, transparent);
   color: var(--accent);
   box-shadow: 0 1px 0 var(--tint-3) inset, 0 6px 14px color-mix(in srgb, var(--accent) 15%, transparent); }
 button.go:hover{ background:linear-gradient(180deg,
     color-mix(in srgb, var(--accent) 30%, transparent),
     color-mix(in srgb, var(--accent) 18%, transparent));
   border-color: color-mix(in srgb, var(--accent) 70%, transparent); }
 button.fix{ background:linear-gradient(180deg,
     color-mix(in srgb, var(--brass) 18%, transparent),
     color-mix(in srgb, var(--brass) 8%, transparent));
   border-color: color-mix(in srgb, var(--brass) 50%, transparent); color:var(--brass); }
 button.fix:hover{ background:linear-gradient(180deg,
     color-mix(in srgb, var(--brass) 26%, transparent),
     color-mix(in srgb, var(--brass) 14%, transparent));
   border-color: color-mix(in srgb, var(--brass) 70%, transparent); }
 button.danger{ background:transparent; border-color:color-mix(in srgb, var(--err) 35%, transparent);
   color:var(--err); }
 button.danger:hover{ background:color-mix(in srgb, var(--err) 12%, transparent);
   border-color:color-mix(in srgb, var(--err) 55%, transparent); }
 /* Stats tiles — Apple-style mini metrics inside plugin card */
 .stats-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px }
 .stat{ background:var(--tint); border:1px solid var(--sep); border-radius:9px; padding:10px 12px }
 .stat-label{ font-size:10px; color:var(--dim); text-transform:uppercase; letter-spacing:.06em; font-weight:600; letter-spacing:0.05em }
 .stat-value{ font:600 19px/1.15 -apple-system,"SF Pro Display",system-ui,sans-serif; margin-top:4px;
   font-variant-numeric:tabular-nums; letter-spacing:-0.01em }
 .stat-value.good{ color:var(--ok) }
 .insight{ margin-top:10px; padding:10px 12px; border-radius:9px;
   background:color-mix(in srgb,var(--accent) 7%,transparent);
   border-left:3px solid var(--accent); font-size:13px; color:var(--txt); line-height:1.45 }
 .insight.ok{ background:color-mix(in srgb,var(--ok) 7%,transparent); border-left-color:var(--ok) }
 .insight.warn{ background:color-mix(in srgb,var(--warn) 9%,transparent); border-left-color:var(--warn) }
 .insight.err{ background:color-mix(in srgb,var(--err) 9%,transparent); border-left-color:var(--err) }
 /* AI help button next to each setting + the popover it opens */
 .help-btn{ width:22px; height:22px; padding:0; border-radius:99px;
   background:var(--tint); border:1px solid var(--sep); color:var(--dim);
   font:600 11px/1 -apple-system,system-ui,sans-serif; cursor:pointer;
   transition: background .15s, color .15s, border-color .15s; flex-shrink:0 }
 .help-btn:hover{ background:color-mix(in srgb,var(--accent) 14%,transparent);
   color:var(--accent); border-color:color-mix(in srgb,var(--accent) 40%,transparent) }
 .help-pop{ margin:6px 0 10px; padding:12px 14px; border-radius:10px;
   background:color-mix(in srgb,var(--accent) 5%,transparent);
   border:1px solid color-mix(in srgb,var(--accent) 25%,transparent) }
 .mdbody p{ margin:0 0 8px } .mdbody p:last-child{ margin-bottom:0 }
 .mdbody ul,.mdbody ol{ margin:6px 0; padding-left:20px } .mdbody li{ margin:2px 0 }
 .mdbody code{ font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:12px;
   background:var(--tint-2); border:1px solid var(--sep); border-radius:4px; padding:1px 5px }
 .mdbody strong{ font-weight:600 }
 /* iOS-style toggle switch */
 .toggle{ position:relative; display:inline-block; width:44px; height:26px; flex-shrink:0 }
 .toggle input{ opacity:0; width:0; height:0; position:absolute }
 .toggle .slider{ position:absolute; inset:0; background:var(--sep-2); border-radius:99px;
   transition: background .2s ease; cursor:pointer }
 .toggle .slider::before{ content:""; position:absolute; height:22px; width:22px; left:2px; top:2px;
   background:#fff; border-radius:50%; transition: transform .25s cubic-bezier(.4,.0,.2,1);
   box-shadow:0 1px 2px rgba(0,0,0,0.2), 0 2px 6px rgba(0,0,0,0.15) }
 .toggle input:checked + .slider{ background:#30d158 }
 .toggle input:checked + .slider::before{ transform: translateX(18px) }
 .toggle input:focus-visible + .slider{ box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 25%,transparent) }
 input,select,textarea{ background:var(--tint); color:var(--txt);
   border:1px solid var(--sep-2); border-radius:9px; padding:8px 12px; font:14px/1.4 inherit;
   letter-spacing:-0.003em; transition: border-color .15s, background .15s, box-shadow .15s; outline:none; }
 input:focus, select:focus, textarea:focus{
   border-color: color-mix(in srgb, var(--accent) 65%, transparent);
   background:var(--tint-2);
   box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent) }
 input{ min-width:280px }
 select{ appearance:none; -webkit-appearance:none;
   background-image:url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23a8a8a8' stroke-width='1.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
   background-repeat:no-repeat; background-position: right 12px center; padding-right:34px }
 .pill{ font:500 11px/1.2 inherit; padding:4px 10px; border-radius:99px;
   background:var(--tint-2); border:1px solid var(--sep);
   display:inline-flex; align-items:center; gap:4px; letter-spacing:0 }
 .pill.ok{ color:var(--ok); background:color-mix(in srgb, var(--ok) 12%, transparent);
   border-color:color-mix(in srgb, var(--ok) 30%, transparent) }
 .pill.warn{ color:var(--warn); background:color-mix(in srgb, var(--warn) 12%, transparent);
   border-color:color-mix(in srgb, var(--warn) 30%, transparent) }
 .pill.err{ color:var(--err); background:color-mix(in srgb, var(--err) 14%, transparent);
   border-color:color-mix(in srgb, var(--err) 35%, transparent) }
 .ok{color:var(--ok)} .warn{color:var(--warn)} .err{color:var(--err)} .muted{color:var(--dim)}
 .out{ white-space:pre-wrap; font-family:ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace;
   font-size:12px; color:var(--dim); margin-top:10px; background:var(--tint);
   border:1px solid var(--sep); border-radius:9px; padding:10px 12px; line-height:1.5 }
 label{ color:var(--dim); font-size:13px; min-width:180px; display:inline-block; letter-spacing:-0.003em }
 a{ color:var(--cyan); text-decoration:none }
 a:hover{ text-decoration:underline; text-decoration-color: rgba(100,210,255,0.5); text-underline-offset:3px }
 details summary{ cursor:pointer }
 ::-webkit-scrollbar{ width:10px; height:10px }
 ::-webkit-scrollbar-track{ background:transparent }
 ::-webkit-scrollbar-thumb{ background:var(--tint-3); border-radius:5px }
 ::-webkit-scrollbar-thumb:hover{ background:var(--sep-2) }
 /* Top bar — section nav + theme switcher, fixed in the top-right corner */
 .topbar{ position:fixed; top:14px; right:18px; display:flex; gap:8px; align-items:center; z-index:50 }
 .jump{ display:inline-flex; align-items:center; gap:6px; padding:7px 14px;
   background:var(--surface); border:1px solid var(--sep); border-radius:99px;
   color:var(--txt); text-decoration:none; font:500 12px/1 inherit; letter-spacing:-0.003em;
   backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%);
   box-shadow:var(--shadow); transition: background .15s, border-color .15s, color .15s }
 .jump:hover{ background:var(--tint-3); border-color:var(--sep-2); text-decoration:none }
 .jump .arrow{ color:var(--dim); transition: transform .15s, color .15s }
 .jump:hover .arrow{ color:var(--brass); transform: translateX(-2px) }
 .theme-switch{ display:flex; gap:2px;
   background:var(--surface); border:1px solid var(--sep); border-radius:99px; padding:3px;
   backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%);
   box-shadow:var(--shadow); font-size:11px }
 .theme-switch button{ background:transparent; border:none; color:var(--dim);
   padding:5px 11px; border-radius:99px; cursor:pointer; font-weight:500;
   transition: background .15s, color .15s; letter-spacing:-0.003em }
 .theme-switch button:hover{ color:var(--txt) }
 .theme-switch button[aria-current="true"]{ background:var(--txt); color:var(--bg) }
</style></head><body>
<nav class="topbar" aria-label="Section navigation">
  <a class="jump" href="/app" title="Back to dashboard"><span class="arrow">←</span> Home</a>
  <div class="theme-switch" aria-label="Theme">
    <button data-theme-set="dark">Dark</button>
    <button data-theme-set="light">Light</button>
    <button data-theme-set="atlas">Atlas</button>
  </div>
</nav>
<div style="display:flex;align-items:center;gap:10px;margin-bottom:28px">
  <span class="pill" style="background:color-mix(in srgb,var(--brass) 12%,transparent);border-color:color-mix(in srgb,var(--brass) 30%,transparent);color:var(--brass)">Build 2026-06-07</span>
  <span class="pill">Admin</span>
</div>
<h1>Plugins &amp; Diagnostics</h1>
<div class="sub">Everything you've built, in one place. Routes and services need an app restart to (un)mount.</div>
<div class="tabs">
 <div class="tab on" data-t="plugins">Plugins</div>
 <div class="tab" data-t="diag">Diagnostics</div>
 <div class="tab" data-t="trace">Trace</div>
 <div class="tab" data-t="usage">Usage</div>
 <div class="tab" data-t="sources">Models</div>
 <div class="tab" data-t="telegram">Telegram</div>
 <div class="tab" data-t="code">Vibe-code</div>
 <div class="tab" data-t="selfcoder">Self-coder</div>
 <div class="tab" data-t="forge">New plugin</div>
 <div class="tab" data-t="settings">Settings</div>
</div>
<div id="plugins" class="panel on"><div id="plugins-list" class="muted">Loading…</div></div>
<div id="diag" class="panel"><button class="go" data-act="runDiag">Run diagnostics</button>
 <div id="diag-out"></div></div>
<div id="trace" class="panel"><div class="card"><b>Activity trace</b><div class="sub">What the agent has been doing — every tool call the Aegis firewall scored (and whether it was allowed/warned/blocked). Newest first.</div></div>
 <div id="trace-out" class="muted">loading…</div></div>
<div id="usage" class="panel"><div class="card"><b>Usage &amp; cost</b><div class="sub">Tokens per model endpoint. <b>Local</b> = free &amp; private. <b>Cloud</b> counts against your usage limits — watch these.</div></div>
 <div id="usage-out" class="muted">loading…</div></div>
<div id="sources" class="panel"></div>
<div id="telegram" class="panel"></div>
<div id="selfcoder" class="panel"><div class="card">
  <b>Autonomous self-improvement (code)</b> <span id="sc-st" class="muted">…</span>
  <div class="sub">Describe a change in plain language. The app makes it on a branch with Aider, verifies it (compile + boot + optional tests), and presents the result here. Core changes need your approval; small plugin-only changes can auto-merge. Canary deploy auto-reverts if the new build doesn't come up.</div>
  <div class="row"><input id="sc-instr" placeholder="e.g. add input validation to plugins/caveman/plugin.py" style="min-width:380px"></div>
  <div class="row"><input id="sc-files" placeholder="files (space-separated, optional)" style="min-width:380px"><button class="go" data-act="scPropose">Propose</button><span id="sc-prog" class="muted"></span></div>
  <div id="sc-list" class="out" style="margin-top:12px"></div>
</div></div>
<div id="code" class="panel"><div class="card"><b>Vibe-coding with Aider</b> <span id="aider-st" class="muted">…</span>
  <div class="sub">Aider lets Odysseus make real, git-tracked code edits from plain language, using a local coder model. The installer detects your Python and picks the right isolated approach — never touches the app's venv.</div>
  <div id="aider-plan" class="sub" style="color:var(--cyan)"></div>
  <div class="row"><button class="go" id="aider-install-btn" data-act="installAider">Install Aider</button><span id="aider-prog" class="muted"></span></div>
  <div id="aider-help"></div>
  <div id="aider-log" class="out"></div>
  <div class="sub" style="margin-top:10px">Once installed: configure the <b>aider_code</b> plugin (Plugins tab) — set its project path + Aider model — then vibe-code below.</div></div>
<div class="card"><b>Vibe-code a change</b>
  <div class="sub">Describe a function or change to make in the configured project. Aider edits the files on a feature branch (off main) and returns the git diff — nothing is committed yet, you review first.</div>
  <textarea id="vc-instr" placeholder="e.g. add a /api/health endpoint that returns {ok:true, version: ...}" rows="3" style="width:100%;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:8px;padding:9px 11px;font-family:inherit"></textarea>
  <div class="row" style="margin-top:6px"><input id="vc-files" placeholder="files to focus on (optional — leave blank and AI picks them)" style="flex:1"><button class="go" data-act="vibeCode">Vibe-code</button><span id="vc-prog" class="muted"></span></div>
  <div id="vc-out" style="display:none;margin-top:10px">
    <div class="sub">Result</div><div id="vc-msg" class="out"></div>
    <div class="sub" style="margin-top:8px">Git diff</div>
    <pre id="vc-diff" class="out" style="max-height:340px;overflow:auto"></pre>
    <details style="margin-top:8px"><summary class="muted" style="cursor:pointer">Aider log</summary>
      <pre id="vc-log" class="out" style="max-height:200px;overflow:auto"></pre></details>
  </div></div></div>
<div id="forge" class="panel"><div class="card">
  <b>New plugin — guided</b>
  <div class="sub">Describe what you want in plain language. The AI asks a couple of questions, then generates a small plugin for your app, verifies it loads, and leaves it as a <b>disabled draft</b> for you to review and enable. Plugins can add a tool the AI can call, a health check, an HTTP route, or a model source.</div>
  <div id="forge-stage"></div>
</div></div>
<div id="settings" class="panel"></div>
<script nonce="{{CSP_NONCE}}">
// Theme: persisted in localStorage; applied to <html> via data-theme so all CSS vars switch.
(function(){
  const saved=localStorage.getItem('ody-theme')||'dark';
  document.documentElement.setAttribute('data-theme',saved);
  document.querySelectorAll('[data-theme-set]').forEach(b=>{
    if(b.dataset.themeSet===saved)b.setAttribute('aria-current','true');
    b.addEventListener('click',()=>{
      const t=b.dataset.themeSet;
      document.documentElement.setAttribute('data-theme',t);
      localStorage.setItem('ody-theme',t);
      document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current'));
      b.setAttribute('aria-current','true');
    });
  });
})();
const $=s=>document.querySelector(s); const j=(u,o)=>fetch(u,Object.assign({headers:{'Content-Type':'application/json'}},o)).then(r=>r.json());
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Tiny, XSS-safe markdown → HTML for AI guide text (escape first, then add our own tags).
function mdToHtml(md){
  const e=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const inline=s=>e(s).replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g,'$1<em>$2</em>');
  return String(md||'').replace(/\r/g,'').split(/\n{2,}/).map(b=>{
    const ls=b.split('\n').filter(x=>x.length);
    if(ls.length&&ls.every(l=>/^\s*[-*]\s+/.test(l)))
      return '<ul>'+ls.map(l=>'<li>'+inline(l.replace(/^\s*[-*]\s+/,''))+'</li>').join('')+'</ul>';
    if(ls.length&&ls.every(l=>/^\s*\d+[.)]\s+/.test(l)))
      return '<ol>'+ls.map(l=>'<li>'+inline(l.replace(/^\s*\d+[.)]\s+/,''))+'</li>').join('')+'</ol>';
    return ls.length?'<p>'+ls.map(inline).join('<br>')+'</p>':'';
  }).join('');
}
function activateTab(name){
  const t=document.querySelector('.tab[data-t="'+name+'"]'); if(!t)return false;
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
  t.classList.add('on'); $('#'+t.dataset.t).classList.add('on');
  if(t.dataset.t==='plugins')loadPlugins(); if(t.dataset.t==='settings')renderSettings();
  if(t.dataset.t==='diag')runDiag();
  if(t.dataset.t==='trace')runTrace();
  if(t.dataset.t==='usage')runUsage();
  if(t.dataset.t==='code'){aiderStatus();aiderPlan();}
  if(t.dataset.t==='selfcoder')scLoad();
  if(t.dataset.t==='forge')forgeInit();
  return true;
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>activateTab(t.dataset.t));
// Deep-link: /manage#diag (or #settings, #sources, …) opens that tab on load
// and on hashchange, so the /app health badge and other links can jump straight
// to the right section instead of the default Plugins tab.
function _tabFromHash(){const h=(location.hash||'').replace('#','');if(h)activateTab(h);}
window.addEventListener('hashchange',_tabFromHash); _tabFromHash();
let scPollTimer=null;
const SC_STEP_LABEL={branch_created:'created branch',aider_starting:'asking Aider to edit',
  aider_done:'Aider finished',no_changes:'no changes made',committed_on_branch:'committed on branch',
  verify_starting:'verifying…',verify_py_compile:'compile check',verify_import_app:'boot check (import app)',
  verify_pytest:'running tests',decided:'decision',error:'error'};
async function scLoad(){try{const d=await j('/api/plugins/self_coder/proposals');
  const el=$('#sc-list'); const props=(d.proposals||[]); $('#sc-st').textContent=props.length+' proposal(s)'; el.innerHTML='';
  let anyRunning=false;
  for(const p of props){
    const running=p.status==='building'; if(running)anyRunning=true;
    const dec=(p.decision||{}); const cls=p.status==='verified'?'ok':p.status==='failed'?'err':running?'warn':'muted';
    const c=document.createElement('div'); c.className='card'; c.style.margin='8px 0'; c.id='sc-card-'+p.id;
    c.innerHTML=`<div class="row"><span class="pill ${cls}">${p.status}${running?' …':''}</span>
      <b class="grow">${(p.instruction||'').slice(0,90)}</b>
      <span class="muted mono">${(p.changed||[]).length||(p.files||[]).length} files</span></div>
      ${dec.action?`<div class="muted">${dec.action} — ${dec.why||''}</div>`:''}
      <div class="row" style="margin-top:8px">
        <button data-act="scToggle" data-args="${p.id}|live">${running?'Watch live':'View progress'}</button>
        <button data-act="scToggle" data-args="${p.id}|diff">View diff</button>
        ${p.status==='verified'?`<button class="go" data-act="scApply" data-args="${p.id}">Apply (merge + canary)</button>`:''}
        <button class="fix" data-act="scDiscard" data-args="${p.id}">Discard</button></div>
      <div id="sc-detail-${p.id}" style="display:${running?'block':'none'};margin-top:10px"></div>`;
    el.appendChild(c);
    if(running)await scRenderDetail(p.id,'live');
  }
  if(!props.length)el.textContent='No proposals yet. Describe a change above to start one.';
  if(scPollTimer){clearInterval(scPollTimer);scPollTimer=null;}
  if(anyRunning)scPollTimer=setInterval(scPollRunning,2000);
}catch(e){$('#sc-list').textContent='self_coder is disabled — enable it in Plugins.';}}
async function scPollRunning(){
  const d=await j('/api/plugins/self_coder/proposals'); let any=false;
  for(const p of (d.proposals||[])){
    if(p.status==='building'){any=true;await scRenderDetail(p.id,'live');}
    else{const det=document.getElementById('sc-detail-'+p.id);
      const card=document.getElementById('sc-card-'+p.id);
      if(card){const pill=card.querySelector('.pill'); if(pill){
        const cls=p.status==='verified'?'ok':p.status==='failed'?'err':'muted';
        pill.className='pill '+cls; pill.textContent=p.status;}}}
  }
  if(!any){clearInterval(scPollTimer);scPollTimer=null; scLoad();}
}
function _fmtAgo(ts0,ts){if(!ts0||!ts)return''; const s=Math.max(0,Math.round(ts-ts0)); return s+'s';}
function _scIcon(s){return s==='done'?'<span class="ok" style="font-size:15px">✓</span>':
  s==='failed'?'<span class="err" style="font-size:15px">✗</span>':
  s==='active'?'<span class="warn" style="font-size:15px">⟳</span>':
  '<span class="muted" style="font-size:15px">○</span>';}
function _scPhases(progress){
  // Map the raw events to four user-friendly phases (goal → done).
  const ev={}; (progress||[]).forEach(p=>ev[p.step]=p);
  const failedV=Object.keys(ev).some(k=>k.startsWith('verify_')&&ev[k].ok===false);
  const aiderActive=ev['aider_starting']&&!ev['aider_done'];
  const verifyActive=ev['verify_starting']&&!ev['decided']&&!failedV;
  const noChanges=!!ev['no_changes'];
  const started=(progress||[]).length>0;
  return [
    {label:'Set up a safe workspace',
     desc:'Make an isolated branch so the change can be reviewed before it lands.',
     state: ev['branch_created']?'done': started?'active':'pending'},
    {label:'Make the change with AI',
     desc:'Aider edits your code based on the instruction.',
     state: noChanges?'failed': ev['aider_done']?'done': aiderActive?'active':'pending'},
    {label:'Check the change is safe',
     desc:'The new code compiles cleanly, the app still starts, and tests pass.',
     state: failedV?'failed': ev['decided']?'done': verifyActive?'active':'pending',
     sub:[{label:'Code compiles',state: ev['verify_py_compile']?(ev['verify_py_compile'].ok?'done':'failed'):'pending'},
          {label:'App still boots',state: ev['verify_import_app']?(ev['verify_import_app'].ok?'done':'failed'):'pending'},
          {label:'Tests pass',state: ev['verify_pytest']?(ev['verify_pytest'].ok?'done':'failed'):'pending', optional:true}]},
    {label:'Decide what to do',
     desc:'Auto-merge if safe + scoped + small, otherwise ask you to approve.',
     state: ev['decided']?'done':'pending', extra: ev['decided']?ev['decided'].action:''},
  ];}
async function scRenderDetail(id,kind){
  const p=await j('/api/plugins/self_coder/proposals/'+id);
  const el=document.getElementById('sc-detail-'+id); if(!el||!p)return;
  if(kind==='diff'){el.innerHTML=`<pre class="out" style="max-height:340px;overflow:auto">${(p.diff||'(no diff)').replace(/</g,'&lt;')}</pre>`;return;}
  const phases=_scPhases(p.progress);
  const phaseHTML=phases.map(ph=>{
    const sub=(ph.sub||[]).filter(s=>!s.optional||s.state!=='pending').map(s=>
      `<div class="row" style="padding-left:36px;font-size:12px;color:var(--dim)">${_scIcon(s.state)}<span>${s.label}</span></div>`).join('');
    return `<div style="padding:6px 0;border-left:2px solid var(--line);padding-left:12px;margin-left:6px">
      <div class="row" style="align-items:flex-start">
        <span style="min-width:26px">${_scIcon(ph.state)}</span>
        <div class="grow"><b>${ph.label}</b>${ph.extra?` <span class="muted">— ${ph.extra}</span>`:''}
        <div class="muted" style="font-size:12px">${ph.desc}</div></div></div>${sub}</div>`;}).join('');
  const prog=p.progress||[]; const t0=prog[0]?.ts;
  const techTimeline=prog.map(s=>{const lbl=SC_STEP_LABEL[s.step]||s.step;
    const ok=s.ok===false?' err':s.ok===true?' ok':'';
    return `<div class="row"><span class="pill${ok}" style="min-width:60px">${_fmtAgo(t0,s.ts)}</span><span class="mono" style="font-size:12px">${lbl}</span></div>`;}).join('');
  const log=(p.aider_log||'').slice(-3500);
  el.innerHTML=`
    <div class="sub" style="color:var(--cyan)">Goal</div>
    <div style="background:var(--raised);padding:10px;border-radius:6px;margin-bottom:12px;font-style:italic">${(p.instruction||'').replace(/</g,'&lt;')}</div>
    <div class="sub">Progress</div>
    <div>${phaseHTML}</div>
    <div class="row" style="margin-top:10px">
      <button id="sc-tech-btn-${id}" data-act="scToggleTech" data-args="${id}">Show what the AI is doing (code &amp; scripting)</button>
    </div>
    <div id="sc-tech-${id}" style="display:none;margin-top:10px">
      <div class="sub">Raw timeline</div><div>${techTimeline||'<span class="muted">starting…</span>'}</div>
      <div class="sub" style="margin-top:10px">Aider output</div>
      <pre class="out" style="max-height:260px;overflow:auto">${(log||'(waiting for output)').replace(/</g,'&lt;')}</pre>
    </div>`;}
function scToggleTech(id){const el=document.getElementById('sc-tech-'+id),btn=document.getElementById('sc-tech-btn-'+id);
  const open=el.style.display!=='none'; el.style.display=open?'none':'block';
  btn.textContent=open?'Show what the AI is doing (code & scripting)':'Hide technical details';}
async function scToggle(id,kind){const el=document.getElementById('sc-detail-'+id);
  if(el.style.display==='block'&&el.dataset.kind===kind){el.style.display='none';return;}
  el.style.display='block'; el.dataset.kind=kind; await scRenderDetail(id,kind);}
async function scPropose(){const i=$('#sc-instr').value.trim(),f=$('#sc-files').value.trim().split(/\s+/).filter(Boolean);
  if(!i){alert('Need an instruction');return;} $('#sc-prog').textContent='starting…';
  const r=await j('/api/plugins/self_coder/propose',{method:'POST',body:JSON.stringify({instruction:i,files:f})});
  $('#sc-prog').textContent=r.ok?'started — watch live below':('failed — '+(r.detail||'')); scLoad();}
async function scApply(id){if(!confirm('Merge + restart with canary auto-rollback?'))return;
  const r=await j('/api/plugins/self_coder/proposals/'+id+'/apply',{method:'POST'});alert(r.detail||JSON.stringify(r));scLoad();}
async function scDiscard(id){if(!confirm('Discard this proposal? (deletes the branch)'))return;
  const r=await j('/api/plugins/self_coder/proposals/'+id+'/discard',{method:'POST'});alert(r.detail);scLoad();}
async function vibeCode(){
  const instr=$('#vc-instr').value.trim(); if(!instr){alert('Describe the change first');return;}
  const files=$('#vc-files').value.trim();
  $('#vc-prog').textContent='starting…';
  $('#vc-out').style.display='block';
  $('#vc-msg').textContent='AI is picking files and editing. With a local 30B model this takes 2–5 minutes.';
  $('#vc-diff').textContent=''; $('#vc-log').textContent='';
  try{
    const r=await j('/api/plugins/aider_code/edit',{method:'POST',body:JSON.stringify({instruction:instr,files:files})});
    if(!r.ok){throw new Error(r.error||'failed to start');}
    const id=r.job_id;
    const t0=Date.now();
    const poll=setInterval(async()=>{
      try{
        const job=await j('/api/plugins/aider_code/jobs/'+id);
        const el=Math.floor((Date.now()-t0)/1000);
        if(job.status==='running'||job.status==='queued'){
          $('#vc-prog').textContent='working… '+el+'s';
          if(job.stage)$('#vc-msg').textContent=job.stage;
          return;
        }
        clearInterval(poll);
        const result=job.result||{};
        $('#vc-prog').textContent=job.status==='done'?'done ✓ ('+el+'s)':'failed ('+el+'s)';
        let msg=result.response||result.error||job.error||'(no message)';
        if(result.auto_picked&&result.auto_picked.length){msg+='\n\nAI chose these files for you: '+result.auto_picked.join(', ');}
        else if(result.files_used&&result.files_used.length){msg+='\n\nFiles edited: '+result.files_used.join(', ');}
        $('#vc-msg').textContent=msg;
        $('#vc-diff').textContent=result.diff||'(no diff)';
        $('#vc-log').textContent=result.log||'';
      }catch(e){clearInterval(poll);$('#vc-prog').textContent='lost poll: '+e;}
    },3000);
  }catch(e){$('#vc-prog').textContent='request failed: '+e;}
}
// CSP-safe event delegation: HTML data-act/data-args + a single click listener
document.addEventListener('click',function(e){const t=e.target.closest('[data-act]');if(!t)return;
  const fn=window[t.dataset.act]; if(typeof fn!=='function')return;
  const args=(t.dataset.args||'').split('|').filter(s=>s!=='').map(v=>v==='true'?true:v==='false'?false:v);
  fn.apply(null,args);});
document.addEventListener('change',function(e){const t=e.target.closest('[data-set]');if(!t)return;
  setS(t.dataset.set,t.value).then(()=>t.style.borderColor='var(--ok)');});
async function aiderPlan(){try{const d=await j('/api/manage/install-aider/plan');
  $('#aider-plan').textContent='Detected: Python '+(d.env&&d.env.running)+' · approach: '+d.strategy+' — '+d.explanation;}catch(e){}}
function diagBtn(){$('#aider-help').innerHTML='<button class="fix" data-act="diagnoseInstall">Ask Copilot what went wrong</button> <span id="diag-out" class="out"></span>';}
async function diagnoseInstall(){const log=$('#aider-log').textContent||'';$('#diag-out').textContent='asking the AI…';
  const r=await j('/api/manage/diagnose',{method:'POST',body:JSON.stringify({title:'Aider install',log})});
  $('#diag-out').textContent=r.ok?r.diagnosis:(r.detail||'no AI configured');}
async function aiderStatus(){try{const d=await j('/api/manage/install-aider/status');
  const el=$('#aider-st');el.textContent=d.installed?'installed ✓':(d.status==='running'?('installing… ('+(d.strategy||'')+')'):(d.status==='failed'?'install failed':'not installed'));
  el.className=d.installed?'ok':(d.status==='failed'?'err':'muted');if(d.log)$('#aider-log').textContent=d.log;
  // Sync the button: when installed, lock it as "Installed ✓"; while running show progress.
  const btn=$('#aider-install-btn');
  if(btn){
    if(d.installed){btn.textContent='Installed ✓';btn.disabled=true;btn.style.opacity='0.6';btn.style.cursor='default';}
    else if(d.status==='running'){btn.textContent='Installing…';btn.disabled=true;btn.style.opacity='0.6';}
    else{btn.textContent='Install Aider';btn.disabled=false;btn.style.opacity='';btn.style.cursor='';}
  }
  if(d.status==='failed'&&!d.installed)diagBtn();return d;}catch(e){return {};}}
async function installAider(){$('#aider-prog').textContent='starting…';$('#aider-help').innerHTML='';
  await j('/api/manage/install-aider',{method:'POST'});
  const t=setInterval(async()=>{const d=await aiderStatus();$('#aider-prog').textContent=d.status||'';
    if(d.installed||d.status==='done'||d.status==='failed'){clearInterval(t);$('#aider-prog').textContent=d.installed?'done ✓':'failed — ask Copilot below';}},4000);}
async function loadPlugins(){
  const [d,s,st]=await Promise.all([
    j('/api/manage/plugins'),
    j('/api/manage/plugin-settings').catch(()=>({})),
    j('/api/manage/plugin-stats').catch(()=>({})),
  ]);
  const sets=(s&&s.settings)||{}; const stats=(st&&st.stats)||{};
  const el=$('#plugins-list'); el.innerHTML='';
  (d.plugins||[]).forEach(p=>{
    const on=p.status==='loaded', err=p.status==='error';
    const c=document.createElement('div'); c.className='card';
    c.innerHTML=`<div class="row"><b class="grow">${p.name} <span class="muted mono">v${p.version||'?'}</span></b>
      <span class="pill ${on?'ok':err?'err':'muted'}">${p.status}</span></div>
      <div class="muted mono">${(p.permissions||[]).join(', ')||'—'}</div>
      ${p.error?`<div class="err mono">${p.error}</div>`:''}
      <div class="row" style="margin-top:8px">
        <button data-act="togglePl" data-args="${p.name}|${!on&&!err}">${(on)?'Disable':'Enable'}</button>
        ${err?`<button class="fix" data-act="repairPl" data-args="${p.name}">Let Copilot fix it</button>`:''}</div>`;
    // Apple-style stats tiles + insight
    const sd=stats[p.name];
    if(sd){const sb=document.createElement('div');sb.style.marginTop='14px';sb.style.paddingTop='12px';sb.style.borderTop='1px solid var(--sep)';
      const tiles=(sd.metrics||[]).map(m=>`<div class="stat"><div class="stat-label">${m.label}</div><div class="stat-value${m.good?' good':''}">${m.value}</div></div>`).join('');
      const insightCls=sd.status&&sd.status!=='none'?' '+sd.status:'';
      sb.innerHTML=`<div class="stats-grid">${tiles}</div>`+
        (sd.insight?`<div class="insight${insightCls}">${sd.insight}</div>`:'');
      c.appendChild(sb);}
    const rows=sets[p.name]||[];
    if(rows.length){const box=document.createElement('div');box.style.marginTop='14px';box.style.paddingTop='12px';box.style.borderTop='1px solid var(--sep)';
      box.innerHTML='<div class="muted" style="margin-bottom:6px;font-weight:500">Settings</div>';
      const normal=rows.filter(r=>!r.advanced), adv=rows.filter(r=>r.advanced);
      normal.forEach(r=>box.appendChild(settingRow(r,p.name)));
      if(adv.length){const det=document.createElement('details');det.style.marginTop='6px';
        det.innerHTML='<summary class="muted" style="cursor:pointer;font-size:12px">Advanced ('+adv.length+') — usually leave as-is</summary>';
        adv.forEach(r=>det.appendChild(settingRow(r,p.name)));box.appendChild(det);}
      c.appendChild(box);}
    el.appendChild(c);
  });
}
function settingRow(d, pluginName){
  const wrap=document.createElement('div');wrap.className='row';wrap.style.marginTop='4px';wrap.style.alignItems='center';
  const lab=document.createElement('label');lab.textContent=d.label||d.key;wrap.appendChild(lab);
  let ctrl;
  if(d.type==='select'||d.type==='bool'){
    ctrl=document.createElement('select');
    if(d.type==='bool'){
      ['true','false'].forEach(o=>{const op=document.createElement('option');op.textContent=o;if(String(d.current)===String(o))op.selected=true;ctrl.appendChild(op);});
    } else if(d.suggest_url){
      ctrl.innerHTML='<option>(loading…)</option>';
      fetch(d.suggest_url,{credentials:'same-origin'}).then(r=>r.json()).then(data=>{
        const opts=data.models||data.repos||data.options||[];
        if(!opts.length){ctrl.innerHTML='<option value="">(none available — check status)</option>';return;}
        ctrl.innerHTML='<option value="">— choose —</option>'+opts.map(o=>`<option value="${o}" ${String(d.current)===String(o)?'selected':''}>${o}</option>`).join('');
      }).catch(()=>{ctrl.innerHTML='<option value="">(failed to load)</option>';});
    } else {
      (d.options||[]).forEach(o=>{const op=document.createElement('option');op.textContent=o;if(String(d.current)===String(o))op.selected=true;ctrl.appendChild(op);});
    }
  } else {
    ctrl=document.createElement('input');
    if(d.type==='int')ctrl.type='number';
    if(d.secret)ctrl.placeholder='••• (type to change)';else ctrl.value=(d.current==null?'':d.current);
    if(d.suggest_url){
      const dlId='dl-'+Math.random().toString(36).slice(2,8);
      ctrl.setAttribute('list',dlId);
      ctrl.placeholder=(ctrl.placeholder||'')+' (▼ for suggestions)';
      const dl=document.createElement('datalist');dl.id=dlId;
      fetch(d.suggest_url,{credentials:'same-origin'}).then(r=>r.json()).then(data=>{
        const opts=data.repos||data.models||data.options||[];
        dl.innerHTML=opts.map(o=>`<option value="${o}">`).join('');
      }).catch(()=>{});
      wrap.appendChild(dl);
    }
  }
  ctrl.onchange=async()=>{await setS(d.key,ctrl.value);ctrl.style.borderColor='var(--ok)';};
  wrap.appendChild(ctrl);
  // "?" — AI guide. Tap once: ask AI for a plain-language explanation of this setting,
  // recommended value, and what the current value implies.
  const helpBtn=document.createElement('button');
  helpBtn.className='help-btn'; helpBtn.title='Ask AI about this setting';
  helpBtn.textContent='?';
  helpBtn.addEventListener('click', async()=>{
    let pop=wrap.querySelector('.help-pop');
    if(pop){pop.remove();return;}
    pop=document.createElement('div'); pop.className='help-pop';
    pop.innerHTML='<div class="muted" style="font-size:12px">AI is reading the docs…</div>';
    wrap.parentElement.insertBefore(pop, wrap.nextSibling);
    try{
      const r=await j('/api/manage/explain',{method:'POST',body:JSON.stringify({plugin:pluginName||'',key:d.key,label:d.label,type:d.type,options:d.options,desc:d.desc})});
      pop.innerHTML='';
      if(r.ok){
        const head=document.createElement('div'); head.style.cssText='font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);margin-bottom:6px';
        head.textContent='AI guide · ' + d.key;
        const body=document.createElement('div'); body.className='mdbody'; body.style.cssText='font-size:13px;line-height:1.5;color:var(--txt)';
        body.innerHTML=mdToHtml(r.explanation);
        pop.appendChild(head); pop.appendChild(body);
      } else {
        pop.innerHTML=`<div class="warn" style="font-size:13px">${r.detail||'(no explanation)'}</div>`;
      }
    }catch(e){pop.innerHTML=`<div class="err" style="font-size:13px">AI guide failed: ${e}</div>`;}
  });
  wrap.appendChild(helpBtn);
  return wrap;
}
async function togglePl(n,en){const r=await j('/api/manage/plugins/toggle',{method:'POST',body:JSON.stringify({name:n,enabled:en})});alert(r.detail||JSON.stringify(r));loadPlugins();}
async function repairPl(n){const r=await j('/api/cookbook/debug/fix',{method:'POST',body:JSON.stringify({fix:{kind:'plugin_repair',plugin:n}})});alert(r.detail||JSON.stringify(r));loadPlugins();}
async function runUsage(){
  const el=$('#usage-out'); el.innerHTML='<div class="muted">loading…</div>';
  let d; try{ d=await j('/api/manage/usage'); }catch(e){ el.innerHTML='<div class="card"><span class="pill err">error</span> could not load usage</div>'; return; }
  const eps=d.endpoints||[];
  if(!eps.length){ el.innerHTML='<div class="muted" style="font-size:13px">No model endpoints yet.</div>'; return; }
  const tok=o=>((o&&(o.in||0))+(o&&(o.out||0)))||0;
  el.innerHTML='<div class="card">'+eps.map(e=>{
    const cls=e.local?'ok':'warn', tier=e.local?'Local · free':'Cloud · counts vs limits';
    return `<div class="row" style="padding:8px 0;border-top:1px solid var(--sep)"><span class="pill ${cls}">${tier}</span>`
      +`<span class="grow"><b>${esc(e.name)}</b></span>`
      +`<span class="muted" style="font-size:12px">today ${tok(e.today)} tok · month ${tok(e.month)} tok</span></div>`;
  }).join('')+'</div>';
}
async function runTrace(){
  const el=$('#trace-out'); el.innerHTML='<div class="muted">loading…</div>';
  let d; try{ d=await j('/api/manage/trace'); }catch(e){ el.innerHTML='<div class="card"><span class="pill err">error</span> could not load trace</div>'; return; }
  const a=d.aegis||[];
  if(!a.length){ el.innerHTML='<div class="muted" style="font-size:13px">No tool activity logged yet — as the agent uses tools, every scored call shows here.</div>'; return; }
  const cls=b=>b==='block'?'err':b==='warn'?'warn':'ok';
  const when=ts=>{ try{ return new Date(ts*1000).toLocaleString(); }catch(_){ return ''; } };
  el.innerHTML='<div class="card">'+a.map(e=>{
    const reasons=Array.isArray(e.reasons)?e.reasons.join(', '):(e.reasons||'');
    return `<div class="row" style="padding:6px 0;border-top:1px solid var(--sep)"><span class="pill ${cls(e.band)}">${esc(e.band||'?')}</span>`
      +`<span class="grow"><b>${esc(e.tool||'?')}</b>${reasons?` <span class="muted" style="font-size:12px">${esc(reasons)}</span>`:''}</span>`
      +`<span class="muted" style="font-size:11px">score ${esc(e.score)} · ${esc(when(e.ts))}</span></div>`;
  }).join('')+'</div>';
}
async function runDiag(){
  const el=$('#diag-out'); el.innerHTML='<div class="sub">running diagnostics…</div>';
  let d; try{ d=await j('/api/cookbook/debug'); }
  catch(e){ el.innerHTML='<div class="card"><span class="pill err">error</span> diagnostics failed</div>'; return; }
  const c=d.counts||{}; el.innerHTML='';
  // summary + bulk actions
  const head=document.createElement('div'); head.className='card';
  head.innerHTML=`<div class="row"><span class="pill ${d.overall==='ok'?'ok':d.overall==='error'?'err':'warn'}">${d.overall}</span>`
    +`<span class="grow"><b>${c.ok||0}</b> ok · <b>${c.warn||0}</b> warn · <b>${c.error||0}</b> err</span>`
    +`<button class="go" id="diag-rerun">Re-run</button> <button class="fix" id="diag-fixall">Fix all safe issues</button></div>`
    +`<div class="sub" style="margin-top:6px">“Fix all safe issues” auto-applies only reversible <span class="mono">setting</span> changes. Service starts, reindexing and plugin repairs stay one-click so you stay in control. Tap <b>?</b> on any issue for an AI explanation + fix steps.</div>`;
  el.appendChild(head);
  Object.entries(d.groups||{}).forEach(([area,items])=>{
    const card=document.createElement('div');card.className='card';card.innerHTML=`<b>${area}</b>`;
    items.forEach(r=>{const cls=r.status==='ok'?'ok':r.status==='error'?'err':'warn';
      const row=document.createElement('div');row.className='row';
      const fix=r.fix?`<button class="fix" data-fix='${JSON.stringify(r.fix)}'>${r.fix.label||'Fix'}</button>`:'';
      const why=r.status!=='ok'?`<button class="help-btn" title="Ask AI what this means" data-why='${JSON.stringify({area:area,name:r.name,status:r.status,detail:r.detail||'',hint:r.hint||''})}'>?</button>`:'';
      row.innerHTML=`<span class="pill ${cls}">${r.status}</span><span class="grow">${r.name}: ${r.detail||''}${r.hint?` <span class="muted">→ ${r.hint}</span>`:''}</span>${why}${fix}`;
      card.appendChild(row);});
    el.appendChild(card);
  });
  // one-click fixes
  el.querySelectorAll('button[data-fix]').forEach(b=>b.onclick=async()=>{b.disabled=true;b.textContent='fixing…';const r=await j('/api/cookbook/debug/fix',{method:'POST',body:JSON.stringify({fix:JSON.parse(b.dataset.fix)})});alert(r.detail||JSON.stringify(r));runDiag();});
  // AI "why" popovers
  el.querySelectorAll('button[data-why]').forEach(b=>b.addEventListener('click',async()=>{
    const existing=b.parentElement.nextElementSibling;
    if(existing&&existing.classList.contains('help-pop')){existing.remove();return;}
    const pop=document.createElement('div');pop.className='help-pop';pop.innerHTML='<div class="muted" style="font-size:12px">AI is looking into it…</div>';
    b.closest('.card').insertBefore(pop,b.parentElement.nextSibling);
    try{const r=await j('/api/manage/explain-finding',{method:'POST',body:b.dataset.why});pop.innerHTML='';
      if(r.ok){const h=document.createElement('div');h.style.cssText='font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);margin-bottom:6px';h.textContent='AI guide';const bd=document.createElement('div');bd.className='mdbody';bd.style.cssText='font-size:13px;line-height:1.5';bd.innerHTML=mdToHtml(r.explanation);pop.appendChild(h);pop.appendChild(bd);}
      else pop.innerHTML=`<div class="warn" style="font-size:13px">${r.detail||'(no explanation)'}</div>`;
    }catch(e){pop.innerHTML=`<div class="err" style="font-size:13px">AI guide failed: ${e}</div>`;}
  }));
  // bulk actions
  const rerun=document.getElementById('diag-rerun'); if(rerun)rerun.onclick=runDiag;
  const fa=document.getElementById('diag-fixall'); if(fa)fa.onclick=async()=>{
    const safe=[]; Object.values(d.groups||{}).forEach(items=>items.forEach(r=>{if(r.fix&&r.fix.kind==='setting')safe.push(r.fix);}));
    if(!safe.length){alert('No auto-fixable setting issues right now.');return;}
    if(!confirm('Apply '+safe.length+' safe setting fix(es) now? These are reversible.'))return;
    fa.disabled=true;fa.textContent='fixing '+safe.length+'…';
    let done=0; for(const f of safe){try{await j('/api/cookbook/debug/fix',{method:'POST',body:JSON.stringify({fix:f})});done++;}catch(e){}}
    alert('Applied '+done+'/'+safe.length+' safe fix(es).'); runDiag();
  };
}
const SRC_INFO={
  opencode:{label:'OpenCode', getUrl:'https://opencode.ai/auth',
            note:'One key, one account. Works for both Zen (free + pay-as-you-go) and a Go subscription — we detect which models you have access to. Flip <span class="mono">opencode_include_paid</span> in the plugin to also use per-request paid models (Claude, GPT, …).'},
  openrouter:{label:'OpenRouter', getUrl:'https://openrouter.ai/keys',
              note:'Free <span class="mono">:free</span> tier by default; switch to paid in the plugin settings.'},
};
function srcCard(slug){const i=SRC_INFO[slug];return `<div class="card" id="src-${slug}">
  <div class="row"><b class="grow">${i.label}</b><span id="${slug}-st" class="pill">…</span></div>
  <div class="sub" style="margin:6px 0">${i.note} <a href="${i.getUrl}" target="_blank" rel="noopener">Get an API key →</a></div>
  <div id="${slug}-body"></div>
  <div id="${slug}-out" class="out" style="display:none"></div></div>`;}
$('#sources').innerHTML=srcCard('opencode')+srcCard('openrouter');
// Fetch the paid-models flag once so the toggle reflects current state
fetch('/api/manage/plugin-settings',{credentials:'same-origin'}).then(r=>r.json()).then(d=>{
  const oc=(d.settings||{}).opencode||[];
  const row=oc.find(x=>x.key==='opencode_include_paid');
  window.OPENCODE_INCLUDE_PAID = row ? row.current===true||row.current==='true' : false;
}).catch(()=>{}).finally(()=>['opencode','openrouter'].forEach(s=>refreshSource(s)));
async function refreshSource(s){
  let d; try{d=await j('/api/plugins/'+s+'/status');}catch(e){
    $('#'+s+'-st').textContent='plugin disabled'; $('#'+s+'-st').className='pill';
    $('#'+s+'-body').innerHTML='<div class="muted" style="font-size:13px">Enable this plugin in the Plugins tab first.</div>';
    return;}
  const pill=$('#'+s+'-st');
  if(d.logged_in&&d.endpoint_registered){
    pill.textContent='Signed in'; pill.className='pill ok';
    const sub=d.subscription?` · ${d.subscription}`:'';
    const count=d.models?`${d.models} models`:'connected';
    const paidNow = (window.OPENCODE_INCLUDE_PAID===true);
    const paidRow = s==='opencode' ? `
      <div class="row" style="margin-top:10px;padding-top:12px;border-top:1px solid var(--sep);align-items:flex-start">
        <div class="grow">
          <div style="font-size:13px;font-weight:500">Show per-request paid models</div>
          <div class="muted" style="font-size:12px;margin-top:2px;max-width:480px">Models like Claude, GPT-5.5 and Gemini that are billed per use, on top of any subscription. Hidden by default.</div>
        </div>
        <label class="toggle"><input type="checkbox" data-act="togglePaid" ${paidNow?'checked':''}><span class="slider"></span></label>
      </div>` : '';
    $('#'+s+'-body').innerHTML=`
      <div style="display:flex;align-items:center;gap:12px;padding:14px 0 12px;border-top:1px solid var(--sep);margin-top:6px">
        <div style="width:30px;height:30px;border-radius:99px;background:color-mix(in srgb,var(--ok) 18%,transparent);display:flex;align-items:center;justify-content:center;color:var(--ok);font-size:15px;flex-shrink:0">✓</div>
        <div class="grow">
          <div style="font-weight:600;font-size:14px">Signed in to ${d.name}</div>
          <div class="muted" style="font-size:12px">API key stored securely · ${count}${sub}</div>
        </div>
      </div>
      ${paidRow}
      <div class="row" style="margin-top:14px;padding-top:12px;border-top:1px solid var(--sep)">
        <button data-act="recommend" data-args="${s}">Recommend roles</button>
        <span class="grow"></span>
        <button class="danger" data-act="disconnect" data-args="${s}">Sign out</button>
      </div>`;
  } else {
    pill.textContent='Not signed in'; pill.className='pill';
    $('#'+s+'-body').innerHTML=`
      <div class="row" style="margin-top:6px">
        <input id="${s}-key" placeholder="paste API key here (or leave blank to use env/auth.json)" style="flex:1">
        <button class="go" data-act="login" data-args="${s}">Connect</button>
      </div>`;
  }
}
async function login(s){const inp=$('#'+s+'-key'); const k=inp?inp.value:'';
  const out=$('#'+s+'-out'); out.style.display='block'; out.textContent='Connecting…';
  const r=await j('/api/plugins/'+s+'/login',{method:'POST',body:JSON.stringify({api_key:k})});
  out.textContent=r.detail||JSON.stringify(r);
  if(r.ok)setTimeout(()=>{out.style.display='none'; refreshSource(s);}, 1200);}
async function disconnect(s){
  if(!confirm("Sign out of "+SRC_INFO[s].label+"?\\n\\nYour API key will be removed from this device. Any chat sessions using this source will need a different model."))return;
  const out=$('#'+s+'-out'); out.style.display='block'; out.textContent='Signing out…';
  const r=await j('/api/plugins/'+s+'/disconnect',{method:'POST'});
  out.textContent=r.detail||JSON.stringify(r);
  setTimeout(()=>{out.style.display='none'; refreshSource(s);}, 900);}
async function recommend(s){const out=$('#'+s+'-out'); out.style.display='block'; out.textContent='Asking AI for recommendations…';
  const r=await j('/api/plugins/'+s+'/recommend',{method:'POST',body:JSON.stringify({})});
  out.textContent=JSON.stringify(r.recommendations||r,null,2);}
// Paid-models toggle (delegated for checkboxes)
document.addEventListener('change',function(e){
  const t=e.target.closest('[data-act="togglePaid"]'); if(!t)return;
  const on=t.checked; window.OPENCODE_INCLUDE_PAID=on;
  setS('opencode_include_paid', on ? 'true' : 'false').then(()=>{ /* persisted */ });
});
$('#telegram').innerHTML=`<div class="card"><b>Telegram bridge</b> <span id="tg-st" class="muted">…</span>
  <div class="sub">Get a bot token from <a href="https://t.me/BotFather" target="_blank" rel="noopener" style="color:var(--cyan)">@BotFather</a> · find your numeric Telegram id at <a href="https://t.me/userinfobot" target="_blank" rel="noopener" style="color:var(--cyan)">@userinfobot</a> · empty allowlist answers nobody.</div>
  <div class="row"><label>Bot token</label><input id="tg-tok" placeholder="123:ABC…"></div>
  <div class="row"><label>Allowed user ids</label><input id="tg-ids" placeholder="111111, 222222"></div>
  <div class="row" style="margin-top:8px"><button class="go" data-act="saveTg">Save</button>
  <span class="muted">then enable the <b>telegram</b> plugin + restart.</span></div><div id="tg-out" class="out"></div></div>`;
(async()=>{try{const d=await j('/api/plugins/telegram/status');$('#tg-st').textContent=d.configured?('bot @'+(d.bot||'?')):'not configured';}catch(e){$('#tg-st').textContent='plugin disabled';}})();
async function setS(k,v){return j('/api/manage/setting',{method:'POST',body:JSON.stringify({key:k,value:v})});}
async function saveTg(){await setS('telegram_bot_token',$('#tg-tok').value);const r=await setS('telegram_allowed_user_ids',$('#tg-ids').value);$('#tg-out').textContent='Saved. '+(r.detail||'');}
// Settings tab: server hands us each setting with its current value + metadata;
// we render every row through settingRow() so each gets the "?" AI-explain button
// (what it does for YOUR setup) and the right control — including teacher_model
// as a dropdown of discovered models instead of a free-text box.
async function renderSettings(){
  const host=$('#settings');
  host.innerHTML='<div class="card"><b>Settings</b><div class="sub">Tap <b>?</b> on any setting for a plain-language explanation of what it does for <i>your</i> setup. Teacher tip: pick a local coder or a free model for <span class="mono">teacher_model</span> — no paid API needed.</div></div>';
  let data;
  try{ data=await j('/api/manage/core-settings'); }
  catch(e){ host.innerHTML+='<div class="card"><span class="pill err">error</span> Could not load settings.</div>'; return; }
  (data.settings||[]).forEach(d=>{
    const card=document.createElement('div'); card.className='card';
    card.appendChild(settingRow(d,''));
    host.appendChild(card);
  });
}
// ── Guided plugin builder ───────────────────────────────────────────────────
const FORGE_FLD='width:100%;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:8px;padding:9px 11px;font-family:inherit';
let forgeIdea='', forgeHistory=[], forgeSpec=null;
function forgeInit(){
  forgeIdea=''; forgeHistory=[]; forgeSpec=null;
  const s=$('#forge-stage'); if(!s) return;
  s.innerHTML=`<div style="margin-top:10px"><textarea id="forge-idea" rows="3" style="${FORGE_FLD}" placeholder="e.g. a tool that returns today's weather for a city · or a health check that warns when disk space is low"></textarea></div>`
    +`<div class="row" style="margin-top:8px"><button class="go" id="forge-start">Start</button></div>`
    +`<div id="forge-talk" style="margin-top:14px"></div>`;
  $('#forge-start').onclick=forgeStart;
}
async function forgeStart(){
  const v=($('#forge-idea').value||'').trim(); if(!v){alert('Describe the plugin first.');return;}
  forgeIdea=v; forgeHistory=[]; forgeSpec=null;
  $('#forge-talk').innerHTML='<div class="muted">Thinking…</div>'; forgeNext();
}
async function forgeNext(){
  try{
    const r=await j('/api/manage/plugin-forge/interview',{method:'POST',body:JSON.stringify({idea:forgeIdea,history:forgeHistory})});
    if(!r.ok){ $('#forge-talk').innerHTML=`<div class="card"><span class="pill warn">note</span> ${esc(r.detail||'failed')}</div>`; return; }
    if(r.blocked){
      $('#forge-talk').innerHTML=`<div class="card"><span class="pill err">not recommended</span>`
        +`<div style="margin-top:8px">${esc(r.reason||'This is not a good fit to build as asked.')}</div>`
        +(r.alternative?`<div class="sub" style="margin-top:8px"><b>Suggested instead:</b> ${esc(r.alternative)}</div>`:'')
        +`<div class="row" style="margin-top:10px"><button id="forge-anyway" class="go">Build it anyway</button> <button id="forge-restart2">Start over</button></div></div>`;
      $('#forge-restart2').onclick=forgeInit;
      $('#forge-anyway').onclick=()=>{ forgeSpec={name:'',summary:r.reason||'',concerns:r.reason||'',intent:forgeIdea+(r.alternative?(' — note: '+r.alternative):'')}; forgeRenderSpec(); };
      return;
    }
    if(r.ready){ forgeSpec={name:r.name||'',summary:r.summary||'',concerns:r.concerns||'',intent:r.intent||''}; forgeRenderSpec(); }
    else forgeRenderQuestion(r.question||'Anything else it should do?', r.why||'');
  }catch(e){ $('#forge-talk').innerHTML=`<div class="card"><span class="pill err">error</span> interview failed: ${esc(e)}</div>`; }
}
function forgeRenderQuestion(q, why){
  const prior=forgeHistory.map(h=>`<div style="padding:6px 0;border-left:2px solid var(--sep);padding-left:12px;margin:6px 0"><div class="muted" style="font-size:12px">${esc(h.q)}</div><div>${esc(h.a)}</div></div>`).join('');
  $('#forge-talk').innerHTML=prior
    +`<div class="card"><div class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Question ${forgeHistory.length+1}</div>`
    +`<b>${esc(q)}</b>`
    +(why?`<div class="sub" style="margin-top:6px">${esc(why)}</div>`:'')
    +`<div class="row" style="margin-top:10px"><input id="forge-ans" style="flex:1" placeholder="your answer — or 'skip' / 'you decide'"><button class="go" id="forge-answer">Answer</button></div></div>`;
  const send=()=>{ const a=($('#forge-ans').value||'').trim(); if(!a)return; forgeHistory.push({q:q,a:a}); $('#forge-talk').innerHTML='<div class="muted">Thinking…</div>'; forgeNext(); };
  $('#forge-answer').onclick=send;
  $('#forge-ans').addEventListener('keydown',e=>{ if(e.key==='Enter')send(); });
  $('#forge-ans').focus();
}
function forgeRenderSpec(){
  $('#forge-talk').innerHTML=
    `<div class="card"><b>Proposed plugin</b>`
    +`<div class="row" style="margin-top:8px"><label style="min-width:60px">Name</label><input id="forge-name" style="flex:1" value="${esc(forgeSpec.name)}"></div>`
    +`<div class="sub" style="margin-top:8px">${esc(forgeSpec.summary)}</div>`
    +(forgeSpec.concerns?`<div class="out" style="margin-top:10px;border-color:color-mix(in srgb,var(--warn) 35%,transparent)"><b style="color:var(--warn)">Honest assessment:</b> ${esc(forgeSpec.concerns)}</div>`:'')
    +`<div class="sub" style="margin-top:8px">Build instruction (edit to refine):</div>`
    +`<textarea id="forge-intent" rows="5" style="${FORGE_FLD};margin-top:4px">${esc(forgeSpec.intent)}</textarea>`
    +`<div class="row" style="margin-top:10px"><button class="go" id="forge-build">Build plugin</button> <button id="forge-restart">Start over</button> <span id="forge-bmsg" class="muted"></span></div></div>`
    +`<div id="forge-result" style="margin-top:14px"></div>`;
  $('#forge-build').onclick=()=>forgeBuild(false);
  $('#forge-restart').onclick=forgeInit;
}
async function forgeBuild(overwrite){
  const name=($('#forge-name').value||'').trim(), intent=($('#forge-intent').value||'').trim();
  if(!name||!intent){alert('Need a name and a build instruction.');return;}
  const msg=$('#forge-bmsg'); msg.textContent='Generating + verifying… (this can take a moment)';
  try{
    const r=await j('/api/manage/plugin-forge/build',{method:'POST',body:JSON.stringify({name,intent,overwrite:!!overwrite})});
    msg.textContent=''; forgeRenderResult(r);
  }catch(e){ msg.textContent='build failed: '+e; }
}
function forgeRenderResult(r){
  const el=$('#forge-result');
  if(!r.ok){
    const exists=(r.detail||'').indexOf('already exists')>=0;
    el.innerHTML=`<div class="card"><span class="pill err">failed</span> ${esc(r.detail||'build failed')}`
      +(exists?` <button id="forge-ow">Rebuild (overwrite)</button>`:'')
      +(r.code?`<div class="sub" style="margin-top:8px">Generated code (did not pass):</div><pre class="out" style="max-height:300px;overflow:auto">${esc(r.code)}</pre>`:'')
      +`</div>`;
    const ow=$('#forge-ow'); if(ow) ow.onclick=()=>{ el.innerHTML='<div class="muted">Rebuilding…</div>'; forgeBuild(true); };
    return;
  }
  const loads=r.would_load!==false;
  el.innerHTML=`<div class="card"><span class="pill ${loads?'ok':'warn'}">${esc(r.status||'draft')}</span> ${esc(r.detail||'')}`
    +`<div class="sub" style="margin-top:10px">plugin.json</div><pre class="out" style="max-height:200px;overflow:auto">${esc(JSON.stringify(r.manifest||{},null,2))}</pre>`
    +`<div class="sub" style="margin-top:8px">plugin.py</div><pre class="out" style="max-height:380px;overflow:auto">${esc(r.code||'')}</pre>`
    +(loads
        ? `<div class="row" style="margin-top:10px"><button class="go" id="forge-enable" data-slug="${esc(r.slug)}">Enable plugin</button> <button id="forge-ow2">Rebuild (overwrite)</button> <span id="forge-emsg" class="muted"></span></div>`
        : `<div class="sub" style="color:var(--warn);margin-top:8px">${esc(r.load_error||'Draft does not load yet — refine the instruction and rebuild.')}</div><div class="row" style="margin-top:8px"><button id="forge-ow2">Rebuild (overwrite)</button></div>`)
    +`</div>`;
  const en=$('#forge-enable'); if(en) en.onclick=forgeEnable;
  const ow2=$('#forge-ow2'); if(ow2) ow2.onclick=()=>{ el.innerHTML='<div class="muted">Rebuilding…</div>'; forgeBuild(true); };
}
async function forgeEnable(e){
  const slug=e.target.dataset.slug; const msg=$('#forge-emsg'); msg.textContent='Enabling…';
  try{ const r=await j('/api/manage/plugin-forge/enable',{method:'POST',body:JSON.stringify({slug:slug})});
    msg.textContent=r.detail||(r.ok?'enabled':'failed'); if(r.ok) loadPlugins();
  }catch(e2){ msg.textContent='enable failed: '+e2; }
}
// Kick off the loaders for whichever tab is active on first paint, so the user
// doesn't have to click the already-active tab to see its content.
loadPlugins();
</script></body></html>"""
