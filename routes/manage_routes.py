"""Manage routes — a clickable admin UI for the plugin/diagnostics features.

Everything we built is API-first; this gives it a real interface without touching
the main SPA. Serves a self-contained page at /manage (admin) that calls the
existing JSON endpoints (debug, debug/fix, plugin login/recommend) plus three
small helpers added here: list plugins, toggle a plugin, set a whitelisted setting.

The page rides the logged-in browser session, so its same-origin fetches are
authenticated exactly like the rest of the UI.
"""
import json
import os
import re
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends
from fastapi.responses import HTMLResponse

from core.middleware import require_admin

# Settings the management UI may change (config + tokens — NOT auth/bind/secrets).
MANAGE_SETTING_KEYS = {
    "aegis_mode", "aegis_block_threshold", "aegis_warn_threshold",
    "fleet_mode", "recommend_scope", "history_rag_enabled", "plugins_enabled",
    "caveman_enabled", "caveman_level",
    "agent_continue_on_truncation", "agent_max_continuations",
    "agent_local_no_think", "agent_local_min_predict",
    "opencode_include_paid", "openrouter_tier",
    "telegram_bot_token", "telegram_allowed_user_ids", "telegram_owner", "telegram_mode",
    "ollama_flash_attention", "ollama_kv_cache_type",
    "teacher_model", "improve_teacher_model",
}
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
    async def manage_page(_admin: str = Depends(require_admin)) -> HTMLResponse:
        return HTMLResponse(_PAGE)

    return router


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Odysseus — Plugins & Diagnostics</title>
<style>
 :root{--bg:#0B0E14;--surface:#11161F;--line:#1F2733;--txt:#F2F4F8;--dim:#9AA4B2;
   --brass:#E0A95E;--cyan:#5BB6C9;--ok:#6FCF97;--warn:#E0A95E;--err:#E06C75}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);
   font:14px/1.5 ui-sans-serif,system-ui,Inter,sans-serif;padding:24px}
 h1{font-weight:300;letter-spacing:2px;font-size:20px;margin:0 0 2px}
 .sub{color:var(--dim);font-size:12px;margin-bottom:18px}
 .tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:18px;flex-wrap:wrap}
 .tab{padding:8px 14px;cursor:pointer;color:var(--dim);border-bottom:2px solid transparent}
 .tab.on{color:var(--txt);border-color:var(--cyan)}
 .panel{display:none} .panel.on{display:block}
 .card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px;margin-bottom:10px}
 .row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
 .grow{flex:1} .mono{font-family:ui-monospace,JetBrains Mono,monospace;font-size:12px}
 button{background:#1b2433;color:var(--txt);border:1px solid var(--line);border-radius:6px;
   padding:6px 12px;cursor:pointer} button:hover{border-color:var(--cyan)}
 button.go{border-color:var(--cyan);color:var(--cyan)} button.fix{border-color:var(--brass);color:var(--brass)}
 input,select{background:#0d1119;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 8px}
 input{min-width:240px}
 .pill{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line)}
 .ok{color:var(--ok)} .warn{color:var(--warn)} .err{color:var(--err)} .muted{color:var(--dim)}
 .out{white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:12px;color:var(--dim);margin-top:8px}
 label{color:var(--dim);font-size:12px;min-width:170px;display:inline-block}
</style></head><body>
<h1>PLUGINS &amp; DIAGNOSTICS</h1>
<div class="sub">Odysseus admin · everything we built, now clickable. (Routes/services need an app restart to (un)mount.)</div>
<div class="tabs">
 <div class="tab on" data-t="plugins">Plugins</div>
 <div class="tab" data-t="diag">Diagnostics</div>
 <div class="tab" data-t="sources">Model sources</div>
 <div class="tab" data-t="telegram">Telegram</div>
 <div class="tab" data-t="code">Code (Aider)</div>
 <div class="tab" data-t="selfcoder">Self-coder</div>
 <div class="tab" data-t="settings">Settings</div>
</div>
<div id="plugins" class="panel on"><div id="plugins-list" class="muted">Loading…</div></div>
<div id="diag" class="panel"><button class="go" onclick="runDiag()">Run diagnostics</button>
 <div id="diag-out"></div></div>
<div id="sources" class="panel"></div>
<div id="telegram" class="panel"></div>
<div id="selfcoder" class="panel"><div class="card">
  <b>Autonomous self-improvement (code)</b> <span id="sc-st" class="muted">…</span>
  <div class="sub">Describe a change in plain language. The app makes it on a branch with Aider, verifies it (compile + boot + optional tests), and presents the result here. Core changes need your approval; small plugin-only changes can auto-merge. Canary deploy auto-reverts if the new build doesn't come up.</div>
  <div class="row"><input id="sc-instr" placeholder="e.g. add input validation to plugins/caveman/plugin.py" style="min-width:380px"></div>
  <div class="row"><input id="sc-files" placeholder="files (space-separated, optional)" style="min-width:380px"><button class="go" onclick="scPropose()">Propose</button><span id="sc-prog" class="muted"></span></div>
  <div id="sc-list" class="out" style="margin-top:12px"></div>
</div></div>
<div id="code" class="panel"><div class="card"><b>Vibe-coding with Aider</b> <span id="aider-st" class="muted">…</span>
  <div class="sub">Aider lets Odysseus make real, git-tracked code edits from plain language, using a local coder model. The installer detects your Python and picks the right isolated approach — never touches the app's venv.</div>
  <div id="aider-plan" class="sub" style="color:var(--cyan)"></div>
  <div class="row"><button class="go" onclick="installAider()">Install Aider</button><span id="aider-prog" class="muted"></span></div>
  <div id="aider-help"></div>
  <div id="aider-log" class="out"></div>
  <div class="sub" style="margin-top:10px">Then enable the <b>aider_code</b> plugin (Plugins tab) and set its project path + <span class="mono">aider_model</span> (e.g. <span class="mono">ollama/qwen3-coder</span>).</div></div></div>
<div id="settings" class="panel"></div>
<script>
const $=s=>document.querySelector(s); const j=(u,o)=>fetch(u,Object.assign({headers:{'Content-Type':'application/json'}},o)).then(r=>r.json());
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
  t.classList.add('on'); $('#'+t.dataset.t).classList.add('on');
  if(t.dataset.t==='plugins')loadPlugins(); if(t.dataset.t==='settings')renderSettings();
  if(t.dataset.t==='code'){aiderStatus();aiderPlan();}
  if(t.dataset.t==='selfcoder')scLoad();
});
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
        <button onclick="scToggle('${p.id}','live')">${running?'Watch live':'View progress'}</button>
        <button onclick="scToggle('${p.id}','diff')">View diff</button>
        ${p.status==='verified'?`<button class="go" onclick="scApply('${p.id}')">Apply (merge + canary)</button>`:''}
        <button class="fix" onclick="scDiscard('${p.id}')">Discard</button></div>
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
      <button id="sc-tech-btn-${id}" onclick="scToggleTech('${id}')">Show what the AI is doing (code &amp; scripting)</button>
    </div>
    <div id="sc-tech-${id}" style="display:none;margin-top:10px">
      <div class="sub">Raw timeline</div><div>${techTimeline||'<span class="muted">starting…</span>'}</div>
      <div class="sub" style="margin-top:10px">Aider output</div>
      <pre class="out" style="max-height:260px;overflow:auto;background:#0a0e16">${(log||'(waiting for output)').replace(/</g,'&lt;')}</pre>
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
async function aiderPlan(){try{const d=await j('/api/manage/install-aider/plan');
  $('#aider-plan').textContent='Detected: Python '+(d.env&&d.env.running)+' · approach: '+d.strategy+' — '+d.explanation;}catch(e){}}
function diagBtn(){$('#aider-help').innerHTML='<button class="fix" onclick="diagnoseInstall()">Ask Copilot what went wrong</button> <span id="diag-out" class="out"></span>';}
async function diagnoseInstall(){const log=$('#aider-log').textContent||'';$('#diag-out').textContent='asking the AI…';
  const r=await j('/api/manage/diagnose',{method:'POST',body:JSON.stringify({title:'Aider install',log})});
  $('#diag-out').textContent=r.ok?r.diagnosis:(r.detail||'no AI configured');}
async function aiderStatus(){try{const d=await j('/api/manage/install-aider/status');
  const el=$('#aider-st');el.textContent=d.installed?'installed ✓':(d.status==='running'?('installing… ('+(d.strategy||'')+')'):(d.status==='failed'?'install failed':'not installed'));
  el.className=d.installed?'ok':(d.status==='failed'?'err':'muted');if(d.log)$('#aider-log').textContent=d.log;
  if(d.status==='failed'&&!d.installed)diagBtn();return d;}catch(e){return {};}}
async function installAider(){$('#aider-prog').textContent='starting…';$('#aider-help').innerHTML='';
  await j('/api/manage/install-aider',{method:'POST'});
  const t=setInterval(async()=>{const d=await aiderStatus();$('#aider-prog').textContent=d.status||'';
    if(d.installed||d.status==='done'||d.status==='failed'){clearInterval(t);$('#aider-prog').textContent=d.installed?'done ✓':'failed — ask Copilot below';}},4000);}
async function loadPlugins(){
  const [d,s]=await Promise.all([j('/api/manage/plugins'),j('/api/manage/plugin-settings').catch(()=>({}))]);
  const sets=(s&&s.settings)||{}; const el=$('#plugins-list'); el.innerHTML='';
  (d.plugins||[]).forEach(p=>{
    const on=p.status==='loaded', err=p.status==='error';
    const c=document.createElement('div'); c.className='card';
    c.innerHTML=`<div class="row"><b class="grow">${p.name} <span class="muted mono">v${p.version||'?'}</span></b>
      <span class="pill ${on?'ok':err?'err':'muted'}">${p.status}</span></div>
      <div class="muted mono">${(p.permissions||[]).join(', ')||'—'}</div>
      ${p.error?`<div class="err mono">${p.error}</div>`:''}
      <div class="row" style="margin-top:8px">
        <button onclick="togglePl('${p.name}',${!on&&!err})">${(on)?'Disable':'Enable'}</button>
        ${err?`<button class="fix" onclick="repairPl('${p.name}')">Let Copilot fix it</button>`:''}</div>`;
    const rows=sets[p.name]||[];
    if(rows.length){const box=document.createElement('div');box.style.marginTop='10px';
      box.innerHTML='<div class="muted" style="margin-bottom:4px">Settings</div>';
      rows.forEach(r=>box.appendChild(settingRow(r)));c.appendChild(box);}
    el.appendChild(c);
  });
}
function settingRow(d){
  const wrap=document.createElement('div');wrap.className='row';wrap.style.marginTop='4px';
  const lab=document.createElement('label');lab.textContent=d.label||d.key;wrap.appendChild(lab);
  let ctrl;
  if(d.type==='select'||d.type==='bool'){ctrl=document.createElement('select');
    (d.type==='bool'?['true','false']:(d.options||[])).forEach(o=>{const op=document.createElement('option');op.textContent=o;if(String(d.current)===String(o))op.selected=true;ctrl.appendChild(op);});}
  else{ctrl=document.createElement('input');if(d.type==='int')ctrl.type='number';
    if(d.secret)ctrl.placeholder='••• (type to change)';else ctrl.value=(d.current==null?'':d.current);}
  ctrl.onchange=async()=>{await setS(d.key,ctrl.value);ctrl.style.borderColor='var(--ok)';};
  wrap.appendChild(ctrl);return wrap;
}
async function togglePl(n,en){const r=await j('/api/manage/plugins/toggle',{method:'POST',body:JSON.stringify({name:n,enabled:en})});alert(r.detail||JSON.stringify(r));loadPlugins();}
async function repairPl(n){const r=await j('/api/cookbook/debug/fix',{method:'POST',body:JSON.stringify({fix:{kind:'plugin_repair',plugin:n}})});alert(r.detail||JSON.stringify(r));loadPlugins();}
async function runDiag(){
  const d=await j('/api/cookbook/debug'); const el=$('#diag-out'); el.innerHTML='';
  el.innerHTML=`<div class="sub">overall: <b class="${d.overall==='ok'?'ok':d.overall==='error'?'err':'warn'}">${d.overall}</b></div>`;
  Object.entries(d.groups||{}).forEach(([area,items])=>{
    const c=document.createElement('div');c.className='card';c.innerHTML=`<b>${area}</b>`;
    items.forEach(r=>{const cls=r.status==='ok'?'ok':r.status==='error'?'err':'warn';
      const fix=r.fix?`<button class="fix" data-fix='${JSON.stringify(r.fix)}'>${r.fix.label||'Fix'}</button>`:'';
      c.innerHTML+=`<div class="row"><span class="pill ${cls}">${r.status}</span><span class="grow">${r.name}: ${r.detail||''}${r.hint?` <span class="muted">→ ${r.hint}</span>`:''}</span>${fix}</div>`;});
    el.appendChild(c);
  });
  el.querySelectorAll('button[data-fix]').forEach(b=>b.onclick=async()=>{const r=await j('/api/cookbook/debug/fix',{method:'POST',body:JSON.stringify({fix:JSON.parse(b.dataset.fix)})});alert(r.detail||JSON.stringify(r));runDiag();});
}
function srcCard(slug,label){return `<div class="card"><div class="row"><b class="grow">${label}</b><span id="${slug}-st" class="muted">…</span></div>
  <div class="row" style="margin-top:8px"><input id="${slug}-key" placeholder="API key (leave blank to use env/auth.json)"><button class="go" onclick="login('${slug}')">Connect</button>
  <button onclick="recommend('${slug}')">Recommend roles</button></div><div id="${slug}-out" class="out"></div></div>`;}
$('#sources').innerHTML=srcCard('opencode','OpenCode Zen')+srcCard('openrouter','OpenRouter');
['opencode','openrouter'].forEach(async s=>{try{const d=await j('/api/plugins/'+s+'/status');$('#'+s+'-st').textContent=d.logged_in?'connected':'not connected';$('#'+s+'-st').className=d.logged_in?'ok':'muted';}catch(e){$('#'+s+'-st').textContent='plugin disabled';}});
async function login(s){const k=$('#'+s+'-key').value;const r=await j('/api/plugins/'+s+'/login',{method:'POST',body:JSON.stringify({api_key:k})});$('#'+s+'-out').textContent=r.detail||JSON.stringify(r);}
async function recommend(s){const r=await j('/api/plugins/'+s+'/recommend',{method:'POST',body:JSON.stringify({})});$('#'+s+'-out').textContent=JSON.stringify(r.recommendations||r,null,2);}
$('#telegram').innerHTML=`<div class="card"><b>Telegram bridge</b> <span id="tg-st" class="muted">…</span>
  <div class="sub">Bot from @BotFather · your numeric id from @userinfobot · empty allowlist answers nobody.</div>
  <div class="row"><label>Bot token</label><input id="tg-tok" placeholder="123:ABC…"></div>
  <div class="row"><label>Allowed user ids</label><input id="tg-ids" placeholder="111111, 222222"></div>
  <div class="row" style="margin-top:8px"><button class="go" onclick="saveTg()">Save</button>
  <span class="muted">then enable the <b>telegram</b> plugin + restart.</span></div><div id="tg-out" class="out"></div></div>`;
(async()=>{try{const d=await j('/api/plugins/telegram/status');$('#tg-st').textContent=d.configured?('bot @'+(d.bot||'?')):'not configured';}catch(e){$('#tg-st').textContent='plugin disabled';}})();
async function setS(k,v){return j('/api/manage/setting',{method:'POST',body:JSON.stringify({key:k,value:v})});}
async function saveTg(){await setS('telegram_bot_token',$('#tg-tok').value);const r=await setS('telegram_allowed_user_ids',$('#tg-ids').value);$('#tg-out').textContent='Saved. '+(r.detail||'');}
const SETTINGS=[['aegis_mode','Aegis firewall',['off','audit','enforce']],['fleet_mode','Fleet mode',['auto','single','fleet']],
 ['recommend_scope','Recommend scope',['both','local','sources']],['openrouter_tier','OpenRouter tier',['free','paid','both']],
 ['caveman_level','Caveman level',['minimal','structural','aggressive']],
 ['history_rag_enabled','History RAG',['true','false']],['agent_continue_on_truncation','Continue on truncation',['true','false']],
 ['opencode_include_paid','OpenCode include paid',['false','true']]];
function renderSettings(){$('#settings').innerHTML='<div class="card"><b>Settings</b><div class="sub">Free teacher tip: set teacher_model to a local coder or a free Zen/OpenRouter model — no paid API needed.</div></div>'+
 SETTINGS.map(([k,l,opts])=>`<div class="card row"><label>${l}</label><select id="set-${k}" onchange="setS('${k}',this.value).then(()=>this.style.borderColor='var(--ok)')">${opts.map(o=>`<option>${o}</option>`).join('')}</select></div>`).join('')+
 `<div class="card row"><label>teacher_model</label><input id="set-tm" placeholder="qwen3-coder@local  (or leave blank)"><button onclick="setS('teacher_model',$('#set-tm').value).then(r=>alert(r.detail))">Save</button></div>`;}
</script></body></html>"""
