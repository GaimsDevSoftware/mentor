"""app_routes — the start of our own front-end ("Celestial Terminal").

A modern, calm dashboard served at /app: your private AI fleet as a constellation,
system health at a glance, model sources, and big clear entry points. It consumes
the JSON APIs we already built; it's the foundation we grow the wrapper app from.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.auth_helpers import require_user


def setup_app_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/app")
    async def app_home(request: Request, _user: str = Depends(require_user)) -> HTMLResponse:
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_HOME.replace("{{CSP_NONCE}}", nonce))

    @router.get("/app/cookbook")
    async def app_cookbook(request: Request, _user: str = Depends(require_user)) -> HTMLResponse:
        """The Cookbook — scan & serve models — in our own design (not the old SPA)."""
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_COOKBOOK.replace("{{CSP_NONCE}}", nonce))

    @router.get("/app/office")
    async def app_office(request: Request, _user: str = Depends(require_user)) -> HTMLResponse:
        """The Office — your team of AI agents (employees) — in the Mentor design."""
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_OFFICE.replace("{{CSP_NONCE}}", nonce))

    @router.get("/app/setup")
    async def app_setup(request: Request, _user: str = Depends(require_user)) -> HTMLResponse:
        """Guided 'Set up your AI system' wizard — hardware → model → agent → done."""
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_SETUP.replace("{{CSP_NONCE}}", nonce))

    @router.get("/app/code")
    async def app_code(request: Request, _user: str = Depends(require_user)) -> HTMLResponse:
        """The Code workspace — vibe-code a real repo (the Code pillar)."""
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_CODE.replace("{{CSP_NONCE}}", nonce))

    @router.get("/app/workspace")
    async def app_workspace(request: Request, _user: str = Depends(require_user)) -> HTMLResponse:
        """The Workspace — tile multiple Mentor surfaces (chat, admin, office…) as
        resizable sub-windows in one screen. The app window as a desk."""
        nonce = getattr(request.state, "csp_nonce", "")
        return HTMLResponse(_WORKSPACE.replace("{{CSP_NONCE}}", nonce))

    return router


_HOME = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/static/mentor-icon.png">
<title>Mentor</title>
<style>
 :root, [data-theme="dark"]{
   --bg:#000; --bg-2:#0a0a0c;
   --surface:rgba(28,28,30,0.78); --surface-2:rgba(44,44,46,0.85);
   --sep:rgba(255,255,255,0.08); --sep-2:rgba(255,255,255,0.14);
   --txt:rgba(255,255,255,0.96); --dim:rgba(255,255,255,0.58); --faint:rgba(255,255,255,0.36);
   --brass:#e0a95e; --cyan:#64d2ff; --accent:#0a84ff;
   --ok:#30d158; --warn:#ffd60a; --err:#ff453a;
   --tint:rgba(255,255,255,0.04); --tint-2:rgba(255,255,255,0.06);
   --shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px rgba(0,0,0,0.5);
 }
 [data-theme="light"]{
   --bg:#fbfbfd; --bg-2:#f2f2f7;
   --surface:rgba(255,255,255,0.78); --surface-2:rgba(248,248,250,0.92);
   --sep:rgba(0,0,0,0.08); --sep-2:rgba(0,0,0,0.14);
   --txt:#1d1d1f; --dim:rgba(60,60,67,0.6); --faint:rgba(60,60,67,0.36);
   --brass:#b8843a; --cyan:#0a83af; --accent:#0071e3;
   --ok:#248a3d; --warn:#a04400; --err:#c41e3a;
   --tint:rgba(0,0,0,0.04); --tint-2:rgba(0,0,0,0.06);
   --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 10px 30px rgba(0,0,0,0.06);
 }
 [data-theme="atlas"]{
   --bg:#f4ede0; --bg-2:#ebe2cf;
   --surface:rgba(252,247,236,0.84); --surface-2:rgba(245,238,222,0.94);
   --sep:rgba(43,58,74,0.12); --sep-2:rgba(43,58,74,0.2);
   --txt:#1f2d3d; --dim:rgba(31,45,61,0.64); --faint:rgba(31,45,61,0.4);
   --brass:#9b6826; --cyan:#1f5471; --accent:#9b6826;
   --ok:#3a7f2b; --warn:#a36a00; --err:#a32d2d;
   --tint:rgba(43,58,74,0.04); --tint-2:rgba(43,58,74,0.07);
   --shadow: 0 1px 0 rgba(255,255,255,0.5) inset, 0 8px 22px rgba(43,58,74,0.08);
 }
 *{box-sizing:border-box} option{background:var(--bg-2);color:var(--txt)} html,body{margin:0;height:100%}
 body{
   background: radial-gradient(120% 80% at 50% -10%, var(--bg-2), var(--bg)) fixed;
   color: var(--txt);
   font: 15px/1.6 -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif;
   font-feature-settings:"kern","liga","ss01";
   -webkit-font-smoothing: antialiased;
   padding: 56px 32px 64px; max-width: 1100px; margin: 0 auto;
   letter-spacing:-0.005em;
 }
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:16px;margin-bottom:6px}
 .mark{ font:300 42px/1.05 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif; letter-spacing:-0.04em }
 .pill{ font:500 11px/1.2 inherit; padding:4px 10px; border-radius:99px;
   background:var(--tint-2); border:1px solid var(--sep); color:var(--dim);
   display:inline-flex; align-items:center; gap:4px }
 .pill.ok{ color:var(--ok); background:color-mix(in srgb,var(--ok) 12%,transparent); border-color:color-mix(in srgb,var(--ok) 30%,transparent) }
 .pill.warn{ color:var(--warn); background:color-mix(in srgb,var(--warn) 12%,transparent); border-color:color-mix(in srgb,var(--warn) 30%,transparent) }
 .pill.err{ color:var(--err); background:color-mix(in srgb,var(--err) 14%,transparent); border-color:color-mix(in srgb,var(--err) 35%,transparent) }
 .tag{ color:var(--faint); font-size:13px; margin-bottom:36px; letter-spacing:-0.003em }
 .grid{display:grid;gap:14px} .g3{grid-template-columns:repeat(3,1fr)} .g2{grid-template-columns:repeat(2,1fr)}
 @media(max-width:760px){.g3,.g2{grid-template-columns:1fr}}
 .card{ background:var(--surface); border:1px solid var(--sep); border-radius:14px; padding:20px;
   backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
   box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px rgba(0,0,0,0.5); }
 .card h3{ margin:0 0 4px; font-weight:600; font-size:15px; letter-spacing:-0.01em }
 .card .d{ color:var(--dim); font-size:13px; letter-spacing:-0.003em }
 .act{ display:flex; align-items:center; gap:14px; transition: transform .12s ease, border-color .18s ease, background .18s ease }
 .act:hover{ border-color:rgba(255,255,255,0.18); background:var(--surface-2); transform: translateY(-1px) }
 .act .ic{ font-size:22px; width:32px; text-align:center; flex-shrink:0 }
 .sky{ position:relative; height:170px; border:1px solid var(--sep); border-radius:14px;
   background: radial-gradient(80% 100% at 50% 110%, color-mix(in srgb,var(--brass) 8%,transparent), transparent 60%), linear-gradient(180deg,var(--bg-2),var(--bg));
   overflow:hidden; margin-bottom:32px;
   backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
 .node{ position:absolute; text-align:center; transform:translate(-50%,-50%) }
 .star{ width:12px; height:12px; border-radius:50%; margin:0 auto 6px; box-shadow:0 0 18px 4px currentColor }
 .node b{ font-weight:600; font-size:13px; letter-spacing:-0.003em }
 .node small{ color:var(--dim); font-size:11px; white-space:nowrap; letter-spacing:-0.003em }
 .sec-title{ color:var(--faint); font-size:11px; letter-spacing:1.5px; margin:32px 0 14px; text-transform:uppercase; font-weight:600 }
 .chip{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--dim);
   border:1px solid var(--sep); border-radius:7px; padding:4px 10px; margin:0 6px 6px 0;
   font-family: ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace; background:var(--tint) }
 .chip.rem{ border-color:color-mix(in srgb,var(--cyan) 30%,transparent); color:var(--cyan); background:color-mix(in srgb,var(--cyan) 8%,transparent) }
 .chip .tag{ font:600 9px/1 -apple-system,system-ui,sans-serif; letter-spacing:.04em; text-transform:uppercase;
   padding:2px 5px; border-radius:4px; opacity:.85 }
 .chip.subscription{ border-color:color-mix(in srgb,var(--accent) 30%,transparent); color:var(--accent); background:color-mix(in srgb,var(--accent) 6%,transparent) }
 .chip.subscription .tag{ background:color-mix(in srgb,var(--accent) 20%,transparent); color:var(--accent) }
 .chip.paid{ border-color:color-mix(in srgb,var(--brass) 35%,transparent); color:var(--brass); background:color-mix(in srgb,var(--brass) 8%,transparent) }
 .chip.paid .tag{ background:color-mix(in srgb,var(--brass) 22%,transparent); color:var(--brass) }
 .chip.free .tag{ background:color-mix(in srgb,var(--ok) 16%,transparent); color:var(--ok) }
 svg line{ stroke:var(--brass); stroke-opacity:.45 } svg circle{ fill:var(--faint) }
 ::-webkit-scrollbar{ width:10px; height:10px }
 ::-webkit-scrollbar-track{ background:transparent }
 ::-webkit-scrollbar-thumb{ background:var(--sep-2); border-radius:5px }
 ::-webkit-scrollbar-thumb:hover{ background:var(--dim) }
 /* Top bar — section nav + theme switcher */
 .topbar{ position:fixed; top:14px; right:18px; display:flex; gap:8px; align-items:center; z-index:50 }
 .jump{ display:inline-flex; align-items:center; gap:6px; padding:7px 14px;
   background:var(--surface); border:1px solid var(--sep); border-radius:99px;
   color:var(--txt); text-decoration:none; font:500 12px/1 inherit; letter-spacing:-0.003em;
   backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%);
   box-shadow:var(--shadow); transition: background .15s, border-color .15s, color .15s }
 .jump:hover{ background:var(--tint-2); border-color:var(--sep-2); text-decoration:none }
 .jump .arrow{ color:var(--dim); transition: transform .15s, color .15s }
 .jump:hover .arrow{ color:var(--brass); transform: translateX(2px) }
 .theme-switch{ display:flex; gap:2px;
   background:var(--surface); border:1px solid var(--sep); border-radius:99px; padding:3px;
   backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%);
   box-shadow:var(--shadow); font-size:11px }
 .theme-switch button{ background:transparent; border:none; color:var(--dim);
   padding:5px 11px; border-radius:99px; cursor:pointer; font:500 11px/1 inherit;
   transition: background .15s, color .15s; letter-spacing:-0.003em }
 .theme-switch button:hover{ color:var(--txt) }
 .theme-switch button[aria-current="true"]{ background:var(--txt); color:var(--bg) }
</style></head><body>
<nav class="topbar" aria-label="Section navigation">
  <a class="jump" href="/app">Home</a><a class="jump" href="/">Chat</a><a class="jump" href="/app/office">Office</a><a class="jump" href="/app/code">Code</a><a class="jump" href="/app/cookbook">Cookbook</a><a class="jump" href="/manage">Admin</a>
  <div class="theme-switch" aria-label="Theme">
    <button data-theme-set="dark">Dark</button>
    <button data-theme-set="light">Light</button>
    <button data-theme-set="atlas">Atlas</button>
  </div>
</nav>
<div class="top"><div class="mark">Mentor</div><a id="health" class="pill" href="/manage#diag" title="Open diagnostics — see and fix each issue">checking…</a></div>
<div class="tag">Your private AI · Local-first · By the stars, toward home</div>

<!-- First-run nudge — shown only when no model endpoint is connected yet. -->
<div id="setup-banner" style="display:none;margin:6px 0 18px;padding:16px 18px;border:1px solid color-mix(in srgb,var(--brass) 45%,transparent);border-radius:14px;background:color-mix(in srgb,var(--brass) 9%,transparent)">
  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
    <div style="flex:1;min-width:220px">
      <div style="font-weight:600;font-size:15px;margin-bottom:3px">Welcome — let's give Mentor a brain ✦</div>
      <div style="color:var(--dim);font-size:13px;line-height:1.5">No AI model is connected yet. The guided setup walks you from nothing to a working assistant in a couple of minutes — local (private &amp; free) or a cloud API.</div>
    </div>
    <a href="/app/setup" style="white-space:nowrap;padding:10px 18px;border-radius:10px;background:color-mix(in srgb,var(--accent,#0a84ff) 16%,transparent);border:1px solid color-mix(in srgb,var(--accent,#0a84ff) 45%,transparent);color:var(--accent,#0a84ff);font-weight:600;font-size:13px">Start setup →</a>
  </div>
</div>

<div class="sky" id="sky"><svg width="100%" height="100%" id="lines"></svg></div>

<div class="sec-title">Quick actions</div>
<div class="grid g3">
 <a class="card act" href="/app/setup"><span class="ic" style="color:var(--cyan)">🧭</span><div><h3>Set up</h3><div class="d">Guided AI setup.</div></div></a>
 <a class="card act" href="/app/workspace"><span class="ic" style="color:var(--brass)">▦</span><div><h3>Workspace</h3><div class="d">Many screens at once.</div></div></a>
 <a class="card act" href="/"><span class="ic" style="color:var(--cyan)">✦</span><div><h3>Chat &amp; Agents</h3><div class="d">Talk, and let it act.</div></div></a>
 <a class="card act" href="/manage"><span class="ic" style="color:var(--brass)">⌘</span><div><h3>Plugins &amp; Diagnostics</h3><div class="d">Manage, fix, configure.</div></div></a>
 <a class="card act" href="/#research"><span class="ic" style="color:var(--cyan)">◎</span><div><h3>Deep Research</h3><div class="d">Gather &amp; synthesize.</div></div></a>
 <a class="card act" href="/#memory"><span class="ic" style="color:var(--brass)">✶</span><div><h3>Memory</h3><div class="d">What it remembers.</div></div></a>
 <a class="card act" href="/app/cookbook"><span class="ic" style="color:var(--cyan)">▦</span><div><h3>Cookbook</h3><div class="d">Scan &amp; serve models.</div></div></a>
 <a class="card act" href="/app/office"><span class="ic" style="color:var(--brass)">👥</span><div><h3>Office</h3><div class="d">Your team of agents.</div></div></a>
 <a class="card act" href="/app/code"><span class="ic" style="color:var(--cyan)">⌨</span><div><h3>Code</h3><div class="d">Vibe-code a repo.</div></div></a>
 <a class="card act" href="/manage"><span class="ic" style="color:var(--brass)">⚙</span><div><h3>Settings</h3><div class="d">Tune the system.</div></div></a>
</div>

<div class="sec-title">Models available</div>
<div class="sub" style="color:var(--dim);font-size:13px;margin:-6px 0 14px"></div>
<div id="models" class="d" style="color:var(--dim)">loading…</div>

<script nonce="{{CSP_NONCE}}">
// Theme — persisted in localStorage, shared across /app and /manage
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
const j=u=>fetch(u,{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(r.status));
// health
j('/api/cookbook/debug').then(d=>{const h=document.getElementById('health');
  const c=d.counts||{};h.textContent=`${d.overall} · ${c.ok||0} ok / ${c.warn||0} warn / ${c.error||0} err`;
  h.className='pill '+(d.overall==='ok'?'ok':d.overall==='error'?'err':'warn');}).catch(()=>{});
// fleet constellation (nodes from the local plugin)
j('/api/plugins/local/catalog').then(d=>{
  const sky=document.getElementById('sky'),svg=document.getElementById('lines');
  const nodes=(d.nodes||[]).slice(0,4); const W=sky.clientWidth||900,H=150;
  const pts=nodes.map((n,i)=>({n,x:W*(0.22+0.56*(i/Math.max(1,nodes.length-1||1))),y:H*(i%2?0.62:0.38)}));
  pts.forEach((p,i)=>{if(i){const a=pts[i-1];svg.innerHTML+=`<line x1="${a.x}" y1="${a.y}" x2="${p.x}" y2="${p.y}"/>`;}});
  pts.forEach(p=>{const warm=p.n.always_on; const col=warm?'var(--brass)':'var(--cyan)';
    const el=document.createElement('div');el.className='node';el.style.left=p.x+'px';el.style.top=p.y+'px';
    const usable=p.n.usable_vram_gb!=null?p.n.usable_vram_gb:(p.n.vram_gb-(p.n.reserved_vram_gb||0));
    el.innerHTML=`<div class="star" style="color:${col}"></div><b style="font-size:12px">${p.n.id}</b><br><small>${p.n.role||''} · ${usable}GB</small>`;
    sky.appendChild(el);});
  if(!nodes.length)sky.innerHTML+='<div style="position:absolute;inset:0;display:grid;place-items:center;color:var(--faint)">No fleet configured — single machine mode.</div>';
}).catch(()=>{document.getElementById('sky').innerHTML='<div style="position:absolute;inset:0;display:grid;place-items:center;color:var(--faint)">Fleet view needs the odysseus_local plugin.</div>';});
// model sources — chips coloured + tagged by tier (free / subscription / paid)
const TIER_LABEL={subscription:'Sub', paid:'Paid', free:'Free'};
j('/api/cookbook/sources').then(d=>{const el=document.getElementById('models');el.innerHTML='';
  (d.sections||[]).forEach(s=>{if(!s.count)return;
    const items=(s.models||[]).slice(0,18).map(m=>{
      const tier=(typeof m==='object'?m.tier:'')||'';
      const cls=tier?'chip '+tier:(s.remote?'chip rem':'chip free');
      const lbl=TIER_LABEL[tier];
      const tag=lbl?`<span class="tag">${lbl}</span>`:'';
      return `<span class="${cls}">${m.model||m}${tag}</span>`;
    }).join('');
    el.innerHTML+=`<div style="margin-bottom:10px"><b style="font-size:13px">${s.name}</b> <span style="color:var(--faint);font-size:12px">${s.remote?'· cloud':'· local'}</span><br>${items}</div>`;});
  if(!el.innerHTML)el.textContent='No models yet — open the Cookbook to serve one, or log in to a source in Plugins.';
}).catch(()=>{document.getElementById('models').textContent='Sign in to view models.';});
// First-run nudge: no model endpoint connected → surface the setup banner.
j('/api/model-endpoints').then(d=>{const n=Array.isArray(d)?d.length:((d&&d.endpoints||[]).length);
  if(!n){const b=document.getElementById('setup-banner');if(b)b.style.display='';}}).catch(()=>{});
</script>
<script src="/static/js/concierge.js"></script>
</body></html>"""


_COOKBOOK = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/static/mentor-icon.png">
<title>Mentor — Cookbook</title>
<style>
 :root, [data-theme="dark"]{
   --bg:#000; --bg-2:#0a0a0c;
   --surface:rgba(28,28,30,0.78); --surface-2:rgba(44,44,46,0.85);
   --sep:rgba(255,255,255,0.08); --sep-2:rgba(255,255,255,0.14);
   --txt:rgba(255,255,255,0.96); --dim:rgba(255,255,255,0.58); --faint:rgba(255,255,255,0.36);
   --brass:#e0a95e; --cyan:#64d2ff; --accent:#0a84ff;
   --ok:#30d158; --warn:#ffd60a; --err:#ff453a;
   --tint:rgba(255,255,255,0.04); --tint-2:rgba(255,255,255,0.06);
   --shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px rgba(0,0,0,0.5);
 }
 [data-theme="light"]{
   --bg:#fbfbfd; --bg-2:#f2f2f7;
   --surface:rgba(255,255,255,0.78); --surface-2:rgba(248,248,250,0.92);
   --sep:rgba(0,0,0,0.08); --sep-2:rgba(0,0,0,0.14);
   --txt:#1d1d1f; --dim:rgba(60,60,67,0.6); --faint:rgba(60,60,67,0.36);
   --brass:#b8843a; --cyan:#0a83af; --accent:#0071e3;
   --ok:#248a3d; --warn:#a04400; --err:#c41e3a;
   --tint:rgba(0,0,0,0.04); --tint-2:rgba(0,0,0,0.06);
   --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 10px 30px rgba(0,0,0,0.06);
 }
 [data-theme="atlas"]{
   --bg:#f4ede0; --bg-2:#ebe2cf;
   --surface:rgba(252,247,236,0.84); --surface-2:rgba(245,238,222,0.94);
   --sep:rgba(43,58,74,0.12); --sep-2:rgba(43,58,74,0.2);
   --txt:#1f2d3d; --dim:rgba(31,45,61,0.64); --faint:rgba(31,45,61,0.4);
   --brass:#9b6826; --cyan:#1f5471; --accent:#9b6826;
   --ok:#3a7f2b; --warn:#a36a00; --err:#a32d2d;
   --tint:rgba(43,58,74,0.04); --tint-2:rgba(43,58,74,0.07);
   --shadow: 0 1px 0 rgba(255,255,255,0.5) inset, 0 8px 22px rgba(43,58,74,0.08);
 }
 *{box-sizing:border-box} option{background:var(--bg-2);color:var(--txt)} html,body{margin:0;height:100%}
 body{ background: radial-gradient(120% 80% at 50% -10%, var(--bg-2), var(--bg)) fixed;
   color: var(--txt); font: 15px/1.6 -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif;
   font-feature-settings:"kern","liga","ss01"; -webkit-font-smoothing: antialiased;
   padding: 56px 32px 80px; max-width: 1100px; margin: 0 auto; letter-spacing:-0.005em; }
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:16px;margin-bottom:4px}
 .mark{ font:300 38px/1.05 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif; letter-spacing:-0.04em }
 .tag{ color:var(--faint); font-size:13px; margin-bottom:28px; letter-spacing:-0.003em }
 .pill{ font:500 11px/1.2 inherit; padding:4px 10px; border-radius:99px; background:var(--tint-2);
   border:1px solid var(--sep); color:var(--dim); display:inline-flex; align-items:center; gap:4px }
 .pill.ok{ color:var(--ok); background:color-mix(in srgb,var(--ok) 12%,transparent); border-color:color-mix(in srgb,var(--ok) 30%,transparent) }
 .pill.warn{ color:var(--warn); background:color-mix(in srgb,var(--warn) 12%,transparent); border-color:color-mix(in srgb,var(--warn) 30%,transparent) }
 .pill.err{ color:var(--err); background:color-mix(in srgb,var(--err) 14%,transparent); border-color:color-mix(in srgb,var(--err) 35%,transparent) }
 .sec-title{ color:var(--faint); font-size:11px; letter-spacing:1.5px; margin:30px 0 12px; text-transform:uppercase; font-weight:600 }
 .help-btn{ width:20px; height:20px; padding:0; border-radius:99px; border:1px solid var(--sep-2);
   background:var(--tint-2); color:var(--dim); font:600 11px/1 inherit; cursor:pointer;
   vertical-align:middle; margin-left:8px; transition:color .15s, border-color .15s }
 .help-btn:hover{ color:var(--accent); border-color:var(--accent) }
 .help-pop{ margin:0 0 14px }
 .help-pop .h{ font-size:11px; font-weight:600; letter-spacing:.04em; text-transform:uppercase; color:var(--accent); margin-bottom:6px }
 .help-pop .b{ font-size:13px; line-height:1.5; color:var(--txt) }
 .help-pop .b p{ margin:0 0 8px } .help-pop .b p:last-child{ margin-bottom:0 }
 .help-pop .b ul,.help-pop .b ol{ margin:6px 0; padding-left:20px } .help-pop .b li{ margin:2px 0 }
 .help-pop .b code{ font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:12px; background:var(--tint-2); border:1px solid var(--sep); border-radius:4px; padding:1px 5px }
 .help-pop .b strong{ font-weight:600 }
 .card{ background:var(--surface); border:1px solid var(--sep); border-radius:14px; padding:18px 20px;
   backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
   box-shadow: var(--shadow); margin-bottom:14px; }
 .card h3{ margin:0 0 4px; font-weight:600; font-size:15px; letter-spacing:-0.01em }
 .row{ display:flex; align-items:center; gap:10px }
 .grow{ flex:1; min-width:0 }
 .muted{ color:var(--dim) } .faint{ color:var(--faint) }
 .mono{ font-family: ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace; font-size:12px }
 .btn{ display:inline-flex; align-items:center; gap:6px; padding:8px 14px; border-radius:10px; cursor:pointer;
   background:var(--surface-2); border:1px solid var(--sep-2); color:var(--txt); font:500 13px/1 inherit;
   transition: background .15s, border-color .15s, transform .12s }
 .btn:hover{ background:var(--tint-2); border-color:var(--brass); transform:translateY(-1px) }
 .btn:disabled{ opacity:.5; cursor:default; transform:none }
 .btn.mini{ padding:5px 10px; font-size:12px; border-radius:8px }
 .btn.mini.rec-tier{ opacity:.55 } .btn.mini.rec-tier.on{ opacity:1; border-color:var(--brass); color:var(--brass); background:color-mix(in srgb,var(--brass) 8%,transparent) }
 input.fld, textarea.fld{ width:100%; background:var(--tint); color:var(--txt); border:1px solid var(--sep-2);
   border-radius:9px; padding:9px 11px; font:13px/1.4 inherit; outline:none; transition:border-color .15s }
 input.fld:focus, textarea.fld:focus{ border-color:var(--brass) }
 textarea.fld{ font-family: ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace; resize:vertical }
 .fld-row{ display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; margin-top:8px }
 .fld-row > label{ flex:1; min-width:150px; display:block }
 .fld-row .lab{ color:var(--faint); font-size:11px; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; display:block }
 .actmsg{ font-size:12px; margin-top:8px; min-height:16px }
 /* hardware grid */
 .hw-grid{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px }
 @media(max-width:760px){ .hw-grid{ grid-template-columns:repeat(2,1fr) } }
 .hw{ padding:14px; border:1px solid var(--sep); border-radius:12px; background:var(--tint) }
 .hw .k{ color:var(--faint); font-size:11px; text-transform:uppercase; letter-spacing:.06em }
 .hw .v{ font-weight:600; font-size:18px; margin-top:4px; letter-spacing:-0.01em }
 .hw .s{ color:var(--dim); font-size:12px }
 /* item rows */
 .item{ display:flex; align-items:center; gap:10px; padding:9px 0; border-top:1px solid var(--sep) }
 .item:first-of-type{ border-top:none }
 .item .name{ font-weight:500; letter-spacing:-0.003em }
 .item .meta{ color:var(--dim); font-size:12px }
 .badge{ font:600 9px/1 -apple-system,system-ui,sans-serif; letter-spacing:.05em; text-transform:uppercase;
   padding:3px 6px; border-radius:5px; background:var(--tint-2); color:var(--dim); border:1px solid var(--sep) }
 .badge.ok{ color:var(--ok); border-color:color-mix(in srgb,var(--ok) 30%,transparent); background:color-mix(in srgb,var(--ok) 10%,transparent) }
 .badge.fit{ color:var(--cyan); border-color:color-mix(in srgb,var(--cyan) 30%,transparent); background:color-mix(in srgb,var(--cyan) 10%,transparent) }
 .badge.run{ color:var(--brass); border-color:color-mix(in srgb,var(--brass) 35%,transparent); background:color-mix(in srgb,var(--brass) 10%,transparent) }
 .badge.err{ color:var(--err); border-color:color-mix(in srgb,var(--err) 35%,transparent); background:color-mix(in srgb,var(--err) 12%,transparent) }
 /* progress bar */
 .bar{ height:6px; border-radius:99px; background:var(--tint-2); overflow:hidden; margin-top:6px }
 .bar > i{ display:block; height:100%; background:linear-gradient(90deg,var(--cyan),var(--brass)); transition:width .4s ease }
 /* tier chips (match /app) */
 .chip{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--dim);
   border:1px solid var(--sep); border-radius:7px; padding:4px 10px; margin:0 6px 6px 0;
   font-family: ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace; background:var(--tint) }
 .chip.rem{ border-color:color-mix(in srgb,var(--cyan) 30%,transparent); color:var(--cyan); background:color-mix(in srgb,var(--cyan) 8%,transparent) }
 .chip .tag{ font:600 9px/1 -apple-system,system-ui,sans-serif; letter-spacing:.04em; text-transform:uppercase; padding:2px 5px; border-radius:4px; opacity:.85 }
 .chip.subscription{ border-color:color-mix(in srgb,var(--accent) 30%,transparent); color:var(--accent); background:color-mix(in srgb,var(--accent) 6%,transparent) }
 .chip.subscription .tag{ background:color-mix(in srgb,var(--accent) 20%,transparent); color:var(--accent) }
 .chip.paid{ border-color:color-mix(in srgb,var(--brass) 35%,transparent); color:var(--brass); background:color-mix(in srgb,var(--brass) 8%,transparent) }
 .chip.paid .tag{ background:color-mix(in srgb,var(--brass) 22%,transparent); color:var(--brass) }
 .chip.free .tag{ background:color-mix(in srgb,var(--ok) 16%,transparent); color:var(--ok) }
 .rec{ padding:12px 0; border-top:1px solid var(--sep) } .rec:first-child{ border-top:none }
 .rec .role{ font:600 11px/1 inherit; letter-spacing:.05em; text-transform:uppercase; color:var(--brass) }
 .rec .why{ color:var(--dim); font-size:13px; margin-top:3px }
 .topbar{ position:fixed; top:14px; right:18px; display:flex; gap:8px; align-items:center; z-index:50 }
 .jump{ display:inline-flex; align-items:center; gap:6px; padding:7px 14px; background:var(--surface);
   border:1px solid var(--sep); border-radius:99px; color:var(--txt); font:500 12px/1 inherit; letter-spacing:-0.003em;
   backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%); box-shadow:var(--shadow); transition: background .15s, border-color .15s }
 .jump:hover{ background:var(--tint-2); border-color:var(--sep-2) }
 .jump .arrow{ color:var(--dim) }
 .theme-switch{ display:flex; gap:2px; background:var(--surface); border:1px solid var(--sep); border-radius:99px; padding:3px;
   backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%); box-shadow:var(--shadow) }
 .theme-switch button{ background:transparent; border:none; color:var(--dim); padding:5px 11px; border-radius:99px; cursor:pointer; font:500 11px/1 inherit; transition: background .15s, color .15s }
 .theme-switch button:hover{ color:var(--txt) }
 .theme-switch button[aria-current="true"]{ background:var(--txt); color:var(--bg) }
 ::-webkit-scrollbar{ width:10px; height:10px } ::-webkit-scrollbar-track{ background:transparent }
 ::-webkit-scrollbar-thumb{ background:var(--sep-2); border-radius:5px } ::-webkit-scrollbar-thumb:hover{ background:var(--dim) }
</style></head><body>
<nav class="topbar" aria-label="Section navigation">
  <a class="jump" href="/app">Home</a><a class="jump" href="/">Chat</a><a class="jump" href="/app/office">Office</a><a class="jump" href="/app/code">Code</a><a class="jump" href="/app/cookbook">Cookbook</a><a class="jump" href="/manage">Admin</a>
  <div class="theme-switch" aria-label="Theme">
    <button data-theme-set="dark">Dark</button>
    <button data-theme-set="light">Light</button>
    <button data-theme-set="atlas">Atlas</button>
  </div>
</nav>

<div class="top"><div class="mark">Cookbook</div><span id="hw-pill" class="pill">reading hardware…</span></div>
<div class="tag">Scan &amp; serve models · what fits this machine, what's downloaded, and what's running</div>

<div class="sec-title">This machine <button class="help-btn" data-topic="The 'This machine' panel in the Cookbook — the detected hardware (GPU, VRAM, RAM, CPU, inference backend)">?</button></div>
<div class="card"><div id="hw" class="hw-grid"><div class="muted">detecting…</div></div></div>

<div class="sec-title">Running now <button class="help-btn" data-topic="The 'Running now' panel — models currently being served or downloaded, with live progress, phase and tokens/sec">?</button></div>
<div class="card"><div id="tasks" class="muted">checking for serving / downloading jobs…</div></div>

<div class="sec-title">Get a model <button class="help-btn" data-topic="The 'Get a model' panel — the easy way is to pick from the ranked 'Fits this machine' list and click Download, then Serve from 'Downloaded & ready'. Advanced users can download by Hugging Face repo ID or serve a custom command.">?</button></div>
<div class="card">
  <div class="why" style="margin:0;color:var(--dim);font-size:13px">Easiest way — no typing: pick a model in <b>Fits this machine</b> below and click <b>Download</b>. When it's ready it shows up in <b>Downloaded &amp; ready</b> — click <b>Serve</b> there and you're done. Mentor fills in the repo ID and the command for you.</div>
  <div class="row" style="margin-top:10px"><button class="btn" id="jump-fits">Browse models that fit my machine ↓</button></div>
  <div id="dl-msg" class="actmsg muted" style="margin-top:8px"></div>
  <div id="serve-msg" class="actmsg muted"></div>
  <details style="margin-top:10px"><summary class="faint" style="cursor:pointer;font-size:12px">Advanced — download by repo ID, or serve a custom command</summary>
    <div style="margin-top:12px">
      <div class="row"><span class="grow"><b style="font-size:14px">Download</b> <span class="faint" style="font-size:12px">— pull a model from Hugging Face into the local cache (files only, safe)</span></span></div>
      <div class="fld-row">
        <label><span class="lab">Hugging Face repo id</span><input id="dl-repo" class="fld" placeholder="e.g. Qwen/Qwen3-4B-GGUF"></label>
        <label style="flex:0 0 220px"><span class="lab">Include glob (optional)</span><input id="dl-include" class="fld" placeholder="*Q4_K_M*"></label>
        <button class="btn" id="dl-btn">Download</button>
      </div>
      <hr style="border:none;border-top:1px solid var(--sep);margin:16px 0">
      <div class="row"><span class="grow"><b style="font-size:14px">Serve</b> <span class="faint" style="font-size:12px">— start an inference server. Review the command first; it loads the model into VRAM.</span></span></div>
      <div class="fld-row">
        <label style="flex:0 0 240px"><span class="lab">Model / repo (label)</span><input id="serve-repo" class="fld" placeholder="e.g. qwen3-4b"></label>
        <label style="flex:0 0 130px"><span class="lab">GPUs (optional)</span><input id="serve-gpus" class="fld" placeholder="0  or  0,1"></label>
      </div>
      <div class="fld-row"><label><span class="lab">Command (editable — runs in a tmux session)</span><textarea id="serve-cmd" class="fld" rows="2" placeholder="ollama run qwen3:4b"></textarea></label></div>
      <div class="faint" style="font-size:11px;margin-top:6px">Examples — Ollama: <span class="mono">ollama run qwen3:4b</span> · llama.cpp: <span class="mono">llama-server -m model.gguf -ngl 99 -c 8192</span> · vLLM: <span class="mono">vllm serve Qwen/Qwen3-4B --max-num-seqs 4</span></div>
      <div class="fld-row"><button class="btn" id="serve-btn">Launch server</button></div>
    </div>
  </details>
</div>

<div class="sec-title">Recommended roles <button class="help-btn" data-topic="The 'Recommended roles' feature — the teacher model assigns the best available model to each role (coder, planner, vision, …) within the tiers you allow, and gives you one-click actions to download/connect/assign each one.">?</button></div>
<div class="card">
  <div class="muted" style="font-size:13px;margin-bottom:8px">Tell me what kind of models you want considered, and I'll pick the best one per role from those — with one-click actions to make each one ready.</div>
  <div style="margin:6px 0 8px">
    <div class="faint" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Which tiers to consider</div>
    <div id="rec-tiers" class="row" style="gap:6px;flex-wrap:wrap">
      <button class="btn mini rec-tier on" data-tier="local" type="button" title="Private — runs on your machine">🖥 Local (private)</button>
      <button class="btn mini rec-tier on" data-tier="free" type="button" title="Free cloud tier (gratis nivå)">💚 Free cloud</button>
      <button class="btn mini rec-tier" data-tier="subscription" type="button" title="ChatGPT / Claude / OpenCode Zen subscription">★ Subscription</button>
      <button class="btn mini rec-tier" data-tier="paid" type="button" title="Per-request paid API (costs money)">$ Paid API</button>
    </div>
  </div>
  <div class="row" style="gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
    <label style="display:flex;align-items:center;gap:6px;font-size:12px"><input type="checkbox" id="rec-ready"> Only models that work right now (no extra setup)</label>
    <span style="flex:1"></span>
    <button class="btn" id="rec-btn">✨ Recommend roles</button>
  </div>
  <div id="rec" style="margin-top:10px"></div>
</div>

<div class="sec-title" style="display:flex;align-items:center;gap:8px">Fits this machine <button class="help-btn" data-topic="The 'Fits this machine' list — catalog models ranked against your VRAM/RAM, showing which ones can actually run locally and a fit score">?</button>
  <span style="flex:1"></span>
  <select id="fits-sort" style="font:inherit;font-size:11px;text-transform:none;letter-spacing:0;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:7px;padding:4px 8px;cursor:pointer">
    <option value="score">Sort: best fit</option>
    <option value="vram">VRAM: low → high</option>
    <option value="size">Size: small → large</option>
    <option value="ctx">Context: long → short</option>
    <option value="speed">Speed: fast → slow</option>
  </select>
</div>
<div class="card"><div id="fits" class="muted">ranking models against your hardware…</div></div>

<div class="sec-title">Downloaded &amp; ready <button class="help-btn" data-topic="The 'Downloaded & ready' list — models already in the local cache (Hugging Face / GGUF) that are ready to serve without downloading">?</button></div>
<div class="card"><div id="cached" class="muted">scanning local model cache…</div></div>

<div class="sec-title">By source <button class="help-btn" data-topic="The 'By source' panel — every model grouped by provider (local fleet + logged-in cloud sources), tagged free / subscription / paid">?</button></div>
<div class="card"><div id="sources" class="muted">loading model sources…</div></div>

<script nonce="{{CSP_NONCE}}">
(function(){
  const saved=localStorage.getItem('ody-theme')||'dark';
  document.documentElement.setAttribute('data-theme',saved);
  document.querySelectorAll('[data-theme-set]').forEach(b=>{
    if(b.dataset.themeSet===saved)b.setAttribute('aria-current','true');
    b.addEventListener('click',()=>{const t=b.dataset.themeSet;
      document.documentElement.setAttribute('data-theme',t); localStorage.setItem('ody-theme',t);
      document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current')); b.setAttribute('aria-current','true');});
  });
})();
const $=s=>document.querySelector(s);
let HW_CONTEXT='', HW_VRAM=0, HW_RAM=0;  // hardware summary + numeric VRAM/RAM (for headroom-aware fit)
const j=(u,o)=>fetch(u,Object.assign({credentials:'same-origin',headers:{'Content-Type':'application/json'}},o)).then(r=>{if(!r.ok)throw r.status;return r.json();});
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
const adminNote='<span class="muted" style="font-size:13px">Admin only — sign in as an admin to use this.</span>';

// 1) Hardware
j('/api/hwfit/system').then(s=>{
  const pill=$('#hw-pill');
  pill.textContent=(s.has_gpu?(s.gpu_name||'GPU'):'CPU only')+(s.gpu_vram_gb?` · ${s.gpu_vram_gb}GB`:'');
  pill.className='pill '+(s.has_gpu?'ok':'warn');
  const cell=(k,v,sub)=>`<div class="hw"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div>${sub?`<div class="s">${esc(sub)}</div>`:''}</div>`;
  $('#hw').innerHTML=
    cell('GPU', s.has_gpu?(s.gpu_name||'—'):'None', s.has_gpu?`${s.gpu_count||1}× · ${s.backend||''}`:'CPU inference')+
    cell('VRAM', s.gpu_vram_gb?`${s.gpu_vram_gb} GB`:'—', s.unified_memory?'unified memory':'')+
    cell('RAM', `${s.available_ram_gb||'?'} GB free`, `of ${s.total_ram_gb||'?'} GB`)+
    cell('CPU', `${s.cpu_cores||'?'} cores`, s.cpu_name||'');
  HW_CONTEXT = `${s.has_gpu?(s.gpu_name||'GPU')+' with '+(s.gpu_vram_gb||'?')+'GB VRAM ('+(s.backend||'')+')':'no GPU, CPU-only'}, ${s.total_ram_gb||'?'}GB RAM (${s.available_ram_gb||'?'}GB free)`;
  HW_VRAM = +(s.gpu_vram_gb||0); HW_RAM = +(s.available_ram_gb||0);
  loadFits();
}).catch(e=>{ $('#hw').innerHTML = e===401?adminNote:'<span class="muted">Could not read hardware.</span>'; $('#hw-pill').textContent='hardware n/a'; loadFits(); });

// 2) Running now — poll every 3s
function renderTasks(d){
  const el=$('#tasks'); const tasks=(d&&d.tasks)||[];
  if(!tasks.length){ el.innerHTML='<span class="muted" style="font-size:13px">Nothing serving or downloading right now.</span>'; return; }
  el.innerHTML=tasks.map(t=>{
    const st=(t.status||'').toLowerCase();
    const bcls=st==='ready'||st==='completed'?'ok':st==='error'||st==='stopped'||st==='crashed'?'err':'run';
    const pct=Math.max(0,Math.min(100,parseInt(t.progress||'0',10)||0));
    const phase=t.phase||t.status||'';
    const showBar=st==='running'||st==='downloading';
    const stopped=st==='stopped'||st==='error'||st==='crashed';
    const sid=t.session_id||'';
    return `<div class="item"><span class="badge ${bcls}">${esc(t.type||'task')}</span>`
      +`<span class="grow"><div class="name">${esc(t.model||sid||'job')}</div>`
      +`<div class="meta">${esc(phase)}${t.tps?` · ${esc(t.tps)} tok/s`:''}${t.reqs?` · ${esc(t.reqs)} reqs`:''}${t.remote&&t.remote!=='local'?` · ${esc(t.remote)}`:''}</div>`
      +(showBar?`<div class="bar"><i style="width:${pct}%"></i></div>`:'')
      +(st==='error'&&t.error?`<div class="meta" style="color:var(--err)">${esc(t.error)}</div>`:'')
      +`</span>`
      +(stopped?`<span class="task-actions" style="display:flex;gap:4px;flex-shrink:0">`
        +`<button class="btn mini" onclick="restartTask('${esc(sid)}')">Restart</button>`
        +`<button class="btn mini" style="opacity:.6" onclick="clearTask('${esc(sid)}')">Remove</button></span>`
        :`<span class="badge ${bcls}">${esc(t.status||'')}</span>`)
      +`</div>`;
  }).join('');
}
async function restartTask(sid){ if(!sid)return;
  try{ await j('/api/cookbook/tasks/'+encodeURIComponent(sid)+'/restart',{method:'POST'}); }
  catch(e){ try{ await j('/api/model/serve',{method:'POST',body:JSON.stringify({session_id:sid})}); }catch(e2){} }
  pollTasks(); }
async function clearTask(sid){ if(!sid||!confirm('Remove this task from the list?'))return;
  try{ await j('/api/cookbook/tasks/'+encodeURIComponent(sid),{method:'DELETE'}); }catch(e){}
  pollTasks(); }
function pollTasks(){ j('/api/cookbook/tasks/status').then(renderTasks)
  .catch(e=>{ if(e===401) $('#tasks').innerHTML=adminNote; }); }
pollTasks(); setInterval(pollTasks,3000);

// 3) Recommend roles (on demand)
// Tier picker — toggles the chips on/off (multi-select). At least one must be on.
document.querySelectorAll('.rec-tier').forEach(b=>b.addEventListener('click',()=>{
  b.classList.toggle('on');
  if(!document.querySelectorAll('.rec-tier.on').length) b.classList.add('on'); // never zero
}));
// Map a "role" label from the AI to an actual Mentor role-setting key, so the
// "Assign as <role>" button writes to the right place.
const REC_ROLE_KEY={
  coder:'aider_model', planner:'default_model', vision:'vision_model',
  cheap_utility:'utility_model', chat_generalist:'default_model',
  embeddings:'', // not a chat-model setting; skip "assign"
};
async function _assignRole(role, model, endpoint, btn){
  const key=REC_ROLE_KEY[role]; if(!key){ btn.textContent='—'; return; }
  const spec=endpoint && endpoint!=='local' ? (model+'@'+endpoint) : model;
  btn.disabled=true; btn.textContent='Assigning…';
  try{ await j('/api/manage/setting',{method:'POST',body:JSON.stringify({key:key,value:spec})}); btn.textContent='Assigned ✓'; }
  catch(e){ btn.textContent='failed'; btn.disabled=false; }
}
async function _downloadAndAssign(role, model, btn){
  btn.disabled=true; btn.textContent='Downloading…';
  try{ await j('/api/model/download',{method:'POST',body:JSON.stringify({repo_id:model, platform:'linux'})}); btn.textContent='Started — see Running now ↑'; setTimeout(()=>{ pollTasks(); _assignRole(role, model, 'local', btn); }, 2000); }
  catch(e){ btn.textContent='download failed'; btn.disabled=false; }
}
$('#rec-btn').addEventListener('click',async()=>{
  const btn=$('#rec-btn'), out=$('#rec');
  const tiers=Array.from(document.querySelectorAll('.rec-tier.on')).map(b=>b.dataset.tier);
  const readyOnly=$('#rec-ready').checked;
  btn.disabled=true; btn.textContent='Asking AI…';
  out.innerHTML='<span class="muted" style="font-size:13px">The teacher model is choosing the best model per role within your preferences…</span>';
  try{
    const url='/api/cookbook/recommend?tiers='+encodeURIComponent(tiers.join(','))+'&ready_only='+(readyOnly?'true':'false');
    const r=await j(url,{method:'POST'});
    if(!r.ok){ out.innerHTML=`<span class="muted" style="font-size:13px">${esc(r.detail||'No recommendation available.')}</span>`; }
    else{
      const recs=r.recommendations||{};
      const rows=Array.isArray(recs)? recs.map(x=>[x.role,x]) : Object.keys(recs).map(k=>[k,recs[k]]);
      if(!rows.length){ out.innerHTML='<span class="muted" style="font-size:13px">No roles suggested with these filters — try widening the tier choice or turning off "ready only".</span>'; }
      else {
        out.innerHTML=rows.map(([role,x])=>{
          const remote=!!x.remote, tier=x.tier||(remote?'cloud':'local');
          const tierC=tier==='free'?'var(--ok)':tier==='subscription'?'var(--cyan)':tier==='paid'?'var(--warn)':'var(--brass)';
          const tierTag='<span style="font-size:9px;border:1px solid color-mix(in srgb,'+tierC+' 45%,transparent);color:'+tierC+';border-radius:4px;padding:1px 5px;text-transform:uppercase;margin-left:6px">'+esc(tier)+'</span>';
          const src=x.endpoint||x.source||(remote?'cloud':'local');
          const ready=x.ready!==false;
          const canAssign=!!REC_ROLE_KEY[role];
          const actions=[];
          if(remote && !ready) actions.push('<button class="btn mini" data-rec-connect="1">Connect '+esc(src)+'</button>');
          if(!remote && !ready) actions.push('<button class="btn mini" data-rec-dl="'+esc(x.model)+'" data-rec-role="'+esc(role)+'">Download &amp; assign</button>');
          if(canAssign && ready) actions.push('<button class="btn mini" data-rec-assign="1" data-rec-role="'+esc(role)+'" data-rec-model="'+esc(x.model)+'" data-rec-ep="'+esc(remote?src:'local')+'">Assign as '+esc(role)+'</button>');
          if(!canAssign) actions.push('<span class="faint" style="font-size:11px">(no direct app role — used internally)</span>');
          return '<div class="rec" style="border-bottom:1px solid var(--sep);padding:10px 0">'
            +'<div><span class="role" style="font-weight:600">'+esc(role)+'</span> → <b>'+esc(x.model||'')+'</b>'+tierTag
            +' <span class="muted" style="font-size:11px">· '+esc(src)+(ready?'':' · needs setup')+'</span></div>'
            +(x.why?'<div class="why muted" style="font-size:12px;margin-top:3px">'+esc(x.why)+'</div>':'')
            +'<div class="row" style="gap:6px;margin-top:6px">'+actions.join('')+'</div></div>';
        }).join('')
        + '<div class="muted" style="font-size:11px;margin-top:10px">Scope: '+esc(r.scope||'both')+' · considered '+(r.counts?r.counts.considered:0)+' candidates</div>';
        // wire row buttons
        out.querySelectorAll('[data-rec-assign]').forEach(b=>b.onclick=()=>_assignRole(b.dataset.recRole, b.dataset.recModel, b.dataset.recEp, b));
        out.querySelectorAll('[data-rec-dl]').forEach(b=>b.onclick=()=>_downloadAndAssign(b.dataset.recRole, b.dataset.recDl, b));
        out.querySelectorAll('[data-rec-connect]').forEach(b=>b.onclick=()=>{ window.location.href='/manage#connect'; });
      }
    }
  }catch(e){ out.innerHTML=`<span class="muted" style="font-size:13px">${e===401?'Admin only.':'Recommendation failed.'}</span>`; }
  btn.disabled=false; btn.textContent='✨ Recommend roles';
});

// 4) Fits this machine — RESERVE headroom for the OS + browser (they run
// alongside the model and use real VRAM/RAM), so we never recommend a model
// that would starve the desktop.
const VRAM_RESERVE=3, RAM_RESERVE=4;  // GB kept free for KDE Plasma + browser
let FITS=[];
// Robust stat readers — the ranker's field names vary, so fall back across the
// likely keys instead of trusting one.
const _vramOf=m=>+(m.vram_q4_gb||m.vram_gb||m.required_gb||0);
const _sizeOf=m=>+(m.size_gb||m.required_gb||m.params_b||0);
const _ctxOf=m=>+(m.context_length||m.context||0);
const _spdOf=m=>+(m.speed_tps||m.tps||0);
const _scoreOf=m=>+(m.score||0);
function renderFits(){
  const el=$('#fits');
  const by=($('#fits-sort')&&$('#fits-sort').value)||'score';
  let ms=FITS.slice();
  if(by==='vram') ms.sort((a,b)=>_vramOf(a)-_vramOf(b));
  else if(by==='size') ms.sort((a,b)=>_sizeOf(a)-_sizeOf(b));
  else if(by==='ctx') ms.sort((a,b)=>_ctxOf(b)-_ctxOf(a));
  else if(by==='speed') ms.sort((a,b)=>_spdOf(b)-_spdOf(a));
  else ms.sort((a,b)=>_scoreOf(b)-_scoreOf(a));
  ms=ms.slice(0,24);
  const effV = HW_VRAM>0 ? Math.max(0, +(HW_VRAM-VRAM_RESERVE).toFixed(1)) : 0;
  const banner = HW_VRAM>0
    ? `<div class="muted" style="font-size:12px;margin-bottom:8px">Reserving <b>~${VRAM_RESERVE} GB VRAM</b> + <b>~${RAM_RESERVE} GB RAM</b> for your desktop + browser → recommending models up to <b>~${effV} GB</b> (of ${HW_VRAM} GB).</div>`
    : '';
  if(!ms.length){ el.innerHTML=banner+'<span class="muted" style="font-size:13px">Nothing fits once desktop+browser headroom is reserved — try a smaller/quantized model, or free VRAM.</span>'; return; }
  el.innerHTML=banner+ms.map(m=>{
    const name=m.model||m.name||'?'; const v=_vramOf(m); const spd=_spdOf(m);
    return `<div class="item"><span class="badge fit">fits</span>`
      +`<span class="grow"><div class="name">${esc(name)}</div>`
      +`<div class="meta">${v?`~${esc(v)} GB VRAM`:''}${_ctxOf(m)?` · ${esc(_ctxOf(m))} ctx`:''}${m.size_gb?` · ${esc(m.size_gb)} GB`:''}${spd?` · ~${esc(Math.round(spd))} tok/s`:''}</div></span>`
      +`${m.score!=null?`<span class="badge" title="Fit score">${Math.round(_scoreOf(m))}</span>`:''}`
      +`${m.name?`<button class="btn mini" data-dl="${esc(m.name)}">Download</button>`:''}</div>`;
  }).join('');
}
function loadFits(){
  const effV = HW_VRAM>0 ? Math.max(0, +(HW_VRAM-VRAM_RESERVE).toFixed(1)) : 0;
  j('/api/hwfit/models?limit=80').then(d=>{
    let ms=(d&&d.models)||[];
    if(HW_VRAM>0) ms=ms.filter(m=>{const v=_vramOf(m);return v>0&&v<=effV;});
    else ms=ms.filter(m=>m.fit);
    FITS=ms; renderFits();
  }).catch(e=>{ $('#fits').innerHTML = e===401?adminNote:'<span class="muted">Could not rank models.</span>'; });
}
(function(){const s=$('#fits-sort'); if(s) s.addEventListener('change', renderFits);})();

// 5) Downloaded & ready
j('/api/model/cached').then(d=>{
  const el=$('#cached'); const ms=(d&&d.models)||[];
  if(!ms.length){ el.innerHTML='<span class="muted" style="font-size:13px">No downloaded models found in the local cache yet.</span>'; return; }
  el.innerHTML=ms.map(m=>{
    const ready=(m.status==='ready'&&!m.has_incomplete);
    return `<div class="item"><span class="badge ${ready?'ok':''}">${ready?'ready':esc(m.status||'partial')}</span>`
      +`<span class="grow"><div class="name">${esc(m.repo_id||'?')}</div>`
      +`<div class="meta">${esc(m.size||'')}${m.is_gguf?' · GGUF':''}${m.is_local_dir?' · local dir':''}</div></span>`
      +`${m.repo_id?`<button class="btn mini" data-serve="${esc(m.repo_id)}" data-gguf="${m.is_gguf?'1':''}">Serve</button>`:''}</div>`;
  }).join('');
}).catch(e=>{ $('#cached').innerHTML = e===401?adminNote:'<span class="muted">Could not scan the model cache.</span>'; });

// 6) By source (tier chips)
const TIER_LABEL={subscription:'Sub', paid:'Paid', free:'Free'};
j('/api/cookbook/sources').then(d=>{
  const el=$('#sources'); el.innerHTML='';
  (d.sections||[]).forEach(s=>{ if(!s.count)return;
    const items=(s.models||[]).slice(0,40).map(m=>{
      const tier=(typeof m==='object'?m.tier:'')||'';
      const cls=tier?'chip '+tier:(s.remote?'chip rem':'chip free');
      const lbl=TIER_LABEL[tier]; const tag=lbl?`<span class="tag">${lbl}</span>`:'';
      const name=(typeof m==='object'?(m.model||m.role):m)||'?';
      return `<span class="${cls}" title="${esc((typeof m==='object'&&m.why)||'')}">${esc(name)}${tag}</span>`;
    }).join('');
    el.innerHTML+=`<div style="margin-bottom:12px"><b style="font-size:13px">${esc(s.name)}</b> <span class="faint" style="font-size:12px">${s.remote?'· cloud':'· local'} · ${s.count}</span><br>${items}</div>`;
  });
  if(!el.innerHTML) el.innerHTML='<span class="muted" style="font-size:13px">No model sources yet — log in to one in Plugins, or serve a local model.</span>';
}).catch(e=>{ $('#sources').innerHTML = e===401?adminNote:'<span class="muted">Could not load sources.</span>'; });

// ── Actions: download & serve ───────────────────────────────────────────────
function setMsg(id,text,kind){ const el=$('#'+id); if(!el)return; el.textContent=text||'';
  el.style.color = kind==='err'?'var(--err)':kind==='ok'?'var(--ok)':'var(--dim)'; }
async function downloadModel(repo,include){
  repo=(repo||'').trim(); if(!repo){ setMsg('dl-msg','Enter a Hugging Face repo id first.','err'); return; }
  setMsg('dl-msg','Starting download…');
  try{
    const r=await j('/api/model/download',{method:'POST',body:JSON.stringify({repo_id:repo, include:(include||'').trim()||null, platform:'linux'})});
    if(r.ok){ setMsg('dl-msg','Download started — watch "Running now" above. ('+(r.session_id||'')+')','ok'); pollTasks(); }
    else setMsg('dl-msg', r.error||r.detail||'Download failed to start.','err');
  }catch(e){ setMsg('dl-msg', e===401?'Admin only.':'Download request failed.','err'); }
}
async function serveModel(repo,cmd,gpus){
  repo=(repo||'').trim(); cmd=(cmd||'').trim();
  if(!cmd){ setMsg('serve-msg','Enter the serve command to run.','err'); return; }
  if(!confirm('Launch this server now?\n\n'+cmd+'\n\nThis loads the model into VRAM and starts an inference process.')) return;
  setMsg('serve-msg','Launching…');
  try{
    const r=await j('/api/model/serve',{method:'POST',body:JSON.stringify({repo_id:repo||cmd, cmd:cmd, gpus:(gpus||'').trim()||null, platform:'linux'})});
    if(r.ok){ setMsg('serve-msg','Server launching — watch "Running now" above. ('+(r.session_id||'')+')','ok'); pollTasks(); }
    else setMsg('serve-msg', r.error||r.detail||'Serve failed to start.','err');
  }catch(e){ setMsg('serve-msg', e===401?'Admin only.':'Serve request failed.','err'); }
}
$('#dl-btn').addEventListener('click',()=>downloadModel($('#dl-repo').value,$('#dl-include').value));
$('#serve-btn').addEventListener('click',()=>serveModel($('#serve-repo').value,$('#serve-cmd').value,$('#serve-gpus').value));
(function(){const b=$('#jump-fits'); if(b)b.onclick=()=>{const f=$('#fits'); if(f)f.scrollIntoView({behavior:'smooth',block:'start'});};})();

// Per-item buttons: a fit row's Download prefills + runs; a cached row's Serve
// prefills the form (with a sensible default command) for review, then scrolls.
document.addEventListener('click',(e)=>{
  const dl=e.target.closest('[data-dl]');
  if(dl){ $('#dl-repo').value=dl.dataset.dl; downloadModel(dl.dataset.dl,$('#dl-include').value);
    const t=$('#tasks'); if(t) t.scrollIntoView({behavior:'smooth',block:'center'}); return; }
  const sv=e.target.closest('[data-serve]');
  if(sv){ const repo=sv.dataset.serve; const base=repo.split('/').pop();
    // One-click: build the command for them and launch (serveModel shows a
    // confirm with the exact command — that's the review, no form to fill).
    const cmd = sv.dataset.gguf ? ('llama-server -m '+repo+' -ngl 99 -c 8192') : ('ollama run '+base.toLowerCase());
    serveModel(base, cmd, ''); return; }
});

// In-context AI explainers: a "?" on each section asks the teacher model what it
// is and what it means for THIS machine (Robert's standing wish — explain every
// function right where it's shown).
document.addEventListener('click', async (e)=>{
  const b=e.target.closest('.help-btn'); if(!b) return;
  const title=b.closest('.sec-title'); if(!title) return;
  const next=title.nextElementSibling;
  if(next && next.classList.contains('help-pop')){ next.remove(); return; }
  const pop=document.createElement('div'); pop.className='help-pop card';
  pop.innerHTML='<div class="muted" style="font-size:12px">AI is explaining…</div>';
  title.parentNode.insertBefore(pop, title.nextSibling);
  try{
    const r=await j('/api/manage/explain-topic',{method:'POST',body:JSON.stringify({topic:b.dataset.topic, context:HW_CONTEXT})});
    if(r.ok){ pop.innerHTML='<div class="h">AI guide</div><div class="b"></div>'; pop.querySelector('.b').innerHTML=mdToHtml(r.explanation); }
    else pop.innerHTML=`<span class="muted" style="font-size:13px">${esc(r.detail||'No explanation available.')}</span>`;
  }catch(err){ pop.innerHTML=`<span class="muted" style="font-size:13px">${err===401?'Admin only.':'Explanation failed.'}</span>`; }
});
</script>
<script src="/static/js/concierge.js"></script>
</body></html>"""


_OFFICE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/static/mentor-icon.png">
<title>Mentor — Office</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.78);--surface-2:rgba(44,44,46,0.85);--sep:rgba(255,255,255,0.08);--sep-2:rgba(255,255,255,0.14);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--ok:#30d158;--warn:#ffd60a;--err:#ff453a;--tint:rgba(255,255,255,0.04);--tint-2:rgba(255,255,255,0.06);--shadow:0 1px 0 rgba(255,255,255,0.04) inset,0 10px 30px rgba(0,0,0,0.5);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#f2f2f7;--surface:rgba(255,255,255,0.78);--surface-2:rgba(248,248,250,0.92);--sep:rgba(0,0,0,0.08);--sep-2:rgba(0,0,0,0.14);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.36);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--ok:#248a3d;--warn:#a04400;--err:#c41e3a;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.06);--shadow:0 1px 2px rgba(0,0,0,0.04),0 10px 30px rgba(0,0,0,0.06);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#ebe2cf;--surface:rgba(252,247,236,0.84);--surface-2:rgba(245,238,222,0.94);--sep:rgba(43,58,74,0.12);--sep-2:rgba(43,58,74,0.2);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--ok:#3a7f2b;--warn:#a36a00;--err:#a32d2d;--tint:rgba(43,58,74,0.04);--tint-2:rgba(43,58,74,0.07);--shadow:0 1px 0 rgba(255,255,255,0.5) inset,0 8px 22px rgba(43,58,74,0.08);}
 *{box-sizing:border-box} option{background:var(--bg-2);color:var(--txt)} html,body{margin:0;height:100%}
 body{background:radial-gradient(120% 80% at 50% -10%,var(--bg-2),var(--bg)) fixed;color:var(--txt);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased;padding:56px 32px 80px;max-width:1100px;margin:0 auto;letter-spacing:-0.005em}
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:16px;margin-bottom:4px}
 .mark{font:300 38px/1.05 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif;letter-spacing:-0.04em}
 .tag{color:var(--faint);font-size:13px;margin-bottom:24px}
 .pill{font:500 11px/1.2 inherit;padding:4px 10px;border-radius:99px;background:var(--tint-2);border:1px solid var(--sep);color:var(--dim);display:inline-flex;align-items:center;gap:5px}
 .pill.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
 .pill.warn{color:var(--warn);background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}
 .sec-title{color:var(--faint);font-size:11px;letter-spacing:1.5px;margin:28px 0 12px;text-transform:uppercase;font-weight:600}
 .card{background:var(--surface);border:1px solid var(--sep);border-radius:14px;padding:18px 20px;backdrop-filter:blur(24px) saturate(140%);-webkit-backdrop-filter:blur(24px) saturate(140%);box-shadow:var(--shadow);margin-bottom:14px}
 .row{display:flex;align-items:center;gap:10px} .grow{flex:1;min-width:0} .muted{color:var(--dim)} .faint{color:var(--faint)}
 .mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px}
 .grid{display:grid;gap:14px;grid-template-columns:repeat(2,1fr)} @media(max-width:760px){.grid{grid-template-columns:1fr}}
 .emp{display:flex;gap:12px;align-items:flex-start;background:var(--surface);border:1px solid var(--sep);border-radius:14px;padding:16px;box-shadow:var(--shadow)}
 @keyframes roomspin{to{transform:rotate(360deg)}}
 .ava{width:42px;height:42px;border-radius:11px;flex-shrink:0;display:grid;place-items:center;font-weight:700;font-size:17px;color:#0b0b0d}
 .emp .nm{font-weight:600;letter-spacing:-0.01em} .emp .rl{color:var(--dim);font-size:12px}
 .emp .meta{color:var(--faint);font-size:11px;margin-top:6px;font-family:ui-monospace,Menlo,monospace}
 .badge{font:600 9px/1 -apple-system,system-ui,sans-serif;letter-spacing:.05em;text-transform:uppercase;padding:3px 7px;border-radius:5px;background:var(--tint-2);color:var(--dim);border:1px solid var(--sep)}
 .badge.idle{color:var(--dim)} .badge.thinking{color:var(--cyan);border-color:color-mix(in srgb,var(--cyan) 35%,transparent)} .badge.done{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 35%,transparent)}
 .btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:10px;cursor:pointer;background:var(--surface-2);border:1px solid var(--sep-2);color:var(--txt);font:500 13px/1 inherit;transition:background .15s,border-color .15s,transform .12s}
 .btn:hover{background:var(--tint-2);border-color:var(--brass);transform:translateY(-1px)} .btn:disabled{opacity:.5;cursor:default;transform:none}
 .btn.mini{padding:5px 9px;font-size:12px;border-radius:8px} .btn.danger:hover{border-color:var(--err);color:var(--err)}
 input.fld,textarea.fld,select.fld{width:100%;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:9px;padding:9px 11px;font:13px/1.4 inherit;outline:none}
 input.fld:focus,textarea.fld:focus,select.fld:focus{border-color:var(--brass)}
 textarea.fld{font-family:inherit;resize:vertical}
 label.lab{display:block;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px}
 .chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--dim);border:1px solid var(--sep-2);border-radius:99px;padding:5px 11px;margin:0 6px 6px 0;cursor:pointer;user-select:none}
 .chip.on{color:var(--brass);border-color:var(--brass);background:color-mix(in srgb,var(--brass) 10%,transparent)}
 .preset{cursor:pointer}
 .topbar{position:fixed;top:14px;right:18px;display:flex;gap:8px;align-items:center;z-index:50}
 .jump{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;background:var(--surface);border:1px solid var(--sep);border-radius:99px;color:var(--txt);font:500 12px/1 inherit;box-shadow:var(--shadow)}
 .jump:hover{background:var(--tint-2)} .theme-switch{display:flex;gap:2px;background:var(--surface);border:1px solid var(--sep);border-radius:99px;padding:3px;box-shadow:var(--shadow)}
 .theme-switch button{background:transparent;border:none;color:var(--dim);padding:5px 11px;border-radius:99px;cursor:pointer;font:500 11px/1 inherit}
 .theme-switch button[aria-current="true"]{background:var(--txt);color:var(--bg)}
 .out{white-space:pre-wrap;font-size:13px;line-height:1.5;color:var(--txt);background:var(--tint);border:1px solid var(--sep);border-radius:10px;padding:12px 14px;margin-top:8px}
 ::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:var(--sep-2);border-radius:5px}
</style></head><body>
<nav class="topbar"><a class="jump" href="/app">Home</a><a class="jump" href="/">Chat</a><a class="jump" href="/app/office">Office</a><a class="jump" href="/app/code">Code</a><a class="jump" href="/app/cookbook">Cookbook</a><a class="jump" href="/manage">Admin</a>
 <div class="theme-switch"><button data-theme-set="dark">Dark</button><button data-theme-set="light">Light</button><button data-theme-set="atlas">Atlas</button></div></nav>

<div class="top"><div class="mark">Office</div><span id="cap" class="pill">checking capacity…</span></div>
<div class="tag">Your team of AI agents — hire employees with a role &amp; personality, then put them to work.</div>

<div class="sec-title">The office</div>
<div class="card" style="padding:0;overflow:hidden;background:var(--bg-2)"><canvas id="office" style="display:block;width:100%;height:200px;image-rendering:pixelated"></canvas></div>

<div class="sec-title">The team</div>
<div id="team" class="muted">loading…</div>

<div class="sec-title">The room</div>
<div class="card">
  <div id="room" style="max-height:400px;overflow:auto;display:flex;flex-direction:column;gap:8px"></div>
  <div class="row" style="margin-top:12px">
    <select id="target" class="fld" style="flex:0 0 170px"><option value="team">Whole team</option></select>
    <input id="say" class="fld" style="flex:1" placeholder="message the team or one agent…">
    <button class="btn" id="say-btn">Send</button>
  </div>
  <div class="row" style="margin-top:6px"><span class="grow faint" style="font-size:11px" id="room-hint">A team message uses a few model calls (capped). DM one agent = 1 call.</span><button class="btn mini" id="room-clear">Clear room</button></div>
  <div id="room-hint-live" class="faint" style="font-size:11px;color:var(--brass);min-height:14px;margin-top:2px"></div>
</div>

<div class="sec-title">Hire an agent</div>
<div class="card">
  <div class="faint" style="font-size:12px;margin-bottom:6px">Pick a role to start (it pre-fills a sensible goal, tools &amp; tone), then tweak.</div>
  <div id="presets"></div>
  <label class="lab">Name</label><input id="f-name" class="fld" placeholder="e.g. Iris">
  <label class="lab">Role / title (be specific)</label><input id="f-role" class="fld" placeholder="e.g. Local-model Research Specialist">
  <label class="lab">Goal (one sentence — the outcome)</label><input id="f-goal" class="fld" placeholder="e.g. Find the best option with sources, fast">
  <label class="lab">Personality</label>
  <select id="f-pers" class="fld"><option value="concise professional">Concise professional</option><option value="warm collaborator">Warm collaborator</option><option value="blunt honest critic">Blunt honest critic</option><option value="playful but sharp">Playful but sharp</option><option value="meticulous and careful">Meticulous &amp; careful</option></select>
  <label class="lab">Backstory / working style (optional)</label><textarea id="f-back" class="fld" rows="2" placeholder="optional — how they approach the work, standards they hold"></textarea>
  <label class="lab">Model</label><select id="f-model" class="fld"><option value="">— app default —</option></select>
  <label class="lab">Tools they can use</label><div id="f-tools"></div>
  <div class="faint" style="font-size:11px;margin-top:4px">Agents use these tools when working (web search, fetch, etc.), gated by the Aegis firewall. Agents set to "ask first" won't run code tools (bash/python) on their own.</div>
  <label class="lab">Autonomy</label>
  <select id="f-auto" class="fld"><option value="approve">Ask me before risky actions</option><option value="auto">Act on its own</option></select>
  <div class="row" style="margin-top:10px"><button class="btn" id="draft-btn">Draft system prompt with AI</button><span id="draft-msg" class="muted" style="font-size:12px"></span></div>
  <div id="sp-wrap" style="display:none"><label class="lab">System prompt (AI-drafted, editable)</label><textarea id="f-sp" class="fld" rows="4"></textarea></div>
  <div class="row" style="margin-top:12px"><button class="btn" id="hire-btn">Hire</button><span id="hire-msg" class="muted" style="font-size:12px"></span></div>
</div>

<script nonce="{{CSP_NONCE}}">
(function(){const s=localStorage.getItem('ody-theme')||'dark';document.documentElement.setAttribute('data-theme',s);
 document.querySelectorAll('[data-theme-set]').forEach(b=>{if(b.dataset.themeSet===s)b.setAttribute('aria-current','true');
  b.addEventListener('click',()=>{const t=b.dataset.themeSet;document.documentElement.setAttribute('data-theme',t);localStorage.setItem('ody-theme',t);document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','true');});});})();
const $=s=>document.querySelector(s);
const j=(u,o)=>fetch(u,Object.assign({credentials:'same-origin',headers:{'Content-Type':'application/json'}},o)).then(r=>{if(!r.ok)throw r.status;return r.json();});
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const TOOLS=["web_search","web_fetch","bash","python","read_file","manage_notes","manage_calendar","manage_research","manage_memory","create_document","edit_image","trigger_research"];
const PRESETS=[
 {role:"Researcher",goal:"Find and synthesize accurate, current info with sources",tools:["web_search","web_fetch","trigger_research","manage_research"],pers:"meticulous and careful"},
 {role:"Coder",goal:"Write and edit correct, idiomatic code",tools:["bash","python","read_file"],pers:"concise professional"},
 {role:"Planner / PM",goal:"Break goals into clear tasks and keep them on track",tools:["manage_notes","manage_calendar"],pers:"concise professional"},
 {role:"Editor",goal:"Polish writing for clarity, tone and correctness",tools:["create_document","read_file"],pers:"meticulous and careful"},
 {role:"Analyst",goal:"Find patterns in data and explain them simply",tools:["python","read_file"],pers:"concise professional"},
 {role:"Secretary",goal:"Handle scheduling, reminders and routing",tools:["manage_calendar","manage_notes"],pers:"warm collaborator"},
 {role:"Critic / Red-team",goal:"Find flaws and stress-test ideas honestly",tools:["web_search","read_file"],pers:"blunt honest critic"},
 {role:"Archivist",goal:"Keep and recall the team's memory",tools:["manage_memory","manage_research"],pers:"meticulous and careful"}];
let selTools=new Set();

// capacity banner
j('/api/agents/capacity').then(c=>{const el=$('#cap');const cap=c.budget||3;
  window.__teamCap = cap;
  el.textContent=(c.concurrent?'Concurrent team':'Private — agents take turns')+' · up to '+cap+'/msg';el.className='pill '+(c.concurrent?'ok':'warn');
  $('#room-hint').textContent=c.note+' '+c.privacy+' · DM one agent = 1 call · a team message wakes up to '+cap+' agents (capped, to protect your usage).';}).catch(()=>{});

// presets
$('#presets').innerHTML=PRESETS.map((p,i)=>`<span class="chip preset" data-i="${i}">${esc(p.role)}</span>`).join('');
$('#presets').querySelectorAll('.preset').forEach(c=>c.onclick=()=>{const p=PRESETS[+c.dataset.i];
  $('#f-role').value=p.role;$('#f-goal').value=p.goal;$('#f-pers').value=p.pers;
  selTools=new Set(p.tools);renderTools();if(!$('#f-name').value)$('#f-name').focus();});

// tools
function renderTools(){$('#f-tools').innerHTML=TOOLS.map(t=>`<span class="chip tool ${selTools.has(t)?'on':''}" data-t="${t}">${t}</span>`).join('');
  $('#f-tools').querySelectorAll('.tool').forEach(c=>c.onclick=()=>{const t=c.dataset.t;selTools.has(t)?selTools.delete(t):selTools.add(t);renderTools();});}
renderTools();

// model dropdown (discovered)
j('/api/agents/models').then(d=>{const sel=$('#f-model');
  const det=(d.details&&d.details.length)?d.details:(d.models||[]).map(s=>({spec:s,kind:''}));
  det.forEach(m=>{const o=document.createElement('option');o.value=m.spec;
    const tag=m.kind==='local'?'  ·  🖥 local · private, free':(m.kind==='cloud'?'  ·  ☁ cloud':'');
    o.textContent=m.spec+tag;sel.appendChild(o);});}).catch(()=>{});

// team list
function statusCls(s){return s==='thinking'?'thinking':s==='done'?'done':'idle';}
// ── Pixel-art office: a tiny animated room, one desk + character per agent ──
(function(){ const oc=$('#office'); if(!oc) return; const cx=oc.getContext('2d'); let OAG=[], raf=0;
  function cssv(n,f){ const v=getComputedStyle(document.documentElement).getPropertyValue(n).trim(); return v||f; }
  function fit(){ const w=oc.clientWidth||600,h=oc.clientHeight||200,d=Math.min(2,window.devicePixelRatio||1); oc.width=w*d; oc.height=h*d; cx.setTransform(d,0,0,d,0,0); cx.imageSmoothingEnabled=false; }
  function draw(t){
    const W=oc.clientWidth||600,H=oc.clientHeight||200;
    const wall=cssv('--bg-2','#0a0a0c'),floor=cssv('--surface-2','#1c1c1e'),brass=cssv('--brass','#e0a95e'),cyan=cssv('--cyan','#64d2ff'),line=cssv('--sep-2','#333'),ink=cssv('--txt','#eee'),ok=cssv('--ok','#30d158'),warn=cssv('--warn','#ffd60a');
    cx.clearRect(0,0,W,H);
    const fy=Math.round(H*0.62);
    cx.fillStyle=wall; cx.fillRect(0,0,W,fy);
    cx.fillStyle=floor; cx.fillRect(0,fy,W,H-fy);
    cx.fillStyle=line; cx.fillRect(0,fy,W,1);
    // window with twinkling stars + brass guide-star (the Mentor motif)
    const wx=Math.round(W*0.05),wy=Math.round(H*0.12),ww=Math.round(W*0.24),wh=Math.round(H*0.34);
    cx.fillStyle=line; cx.fillRect(wx-2,wy-2,ww+4,wh+4); cx.fillStyle='#05070d'; cx.fillRect(wx,wy,ww,wh);
    for(let i=0;i<16;i++){ const sx=wx+((i*53)%ww),sy=wy+((i*89)%wh),tw=(Math.sin(t/600+i)+1)/2; cx.fillStyle='rgba(255,255,255,'+(0.2+0.6*tw)+')'; cx.fillRect(sx,sy,1,1); }
    const gx=wx+Math.round(ww*0.68),gy=wy+Math.round(wh*0.4); cx.fillStyle=brass; cx.fillRect(gx-1,gy,3,1); cx.fillRect(gx,gy-1,1,3);
    const agents=OAG.length?OAG:[{color:brass,status:'idle',ghost:1},{color:cyan,status:'idle',ghost:1}];
    const n=Math.min(agents.length,7),slot=W/(n+0.3);
    for(let i=0;i<n;i++){
      const a=agents[i],col=a.color||brass,bx=Math.round(slot*(i+0.55)),deskY=fy-2;
      const work=/work|think|busy|run/i.test(a.status||''),needs=/input|wait|ask/i.test(a.status||'');
      const bob=Math.round(Math.sin(t/430+i*1.3)*1.3*(work?1.8:1));
      const chx=bx,chy=fy-Math.round(H*0.30)+bob;
      cx.fillStyle=col; cx.fillRect(chx-4,chy+6,9,10);                                  // body
      const arm=work?Math.round(Math.sin(t/110+i)*1.5):0;
      cx.fillRect(chx-6,chy+8+arm,2,5); cx.fillRect(chx+5,chy+8-arm,2,5);               // arms
      cx.fillStyle='#e8c39e'; cx.fillRect(chx-3,chy,7,7);                               // head
      cx.fillStyle='#3a2d22'; cx.fillRect(chx-3,chy-1,7,2);                             // hair
      const blink=((t/1000+i)%4)<0.12; cx.fillStyle=blink?'#e8c39e':'#222'; cx.fillRect(chx-1,chy+3,1,1); cx.fillRect(chx+2,chy+3,1,1);
      const dw=Math.round(slot*0.6); cx.fillStyle=line; cx.fillRect(bx-Math.round(dw/2),deskY,dw,Math.round(H*0.10)); // desk
      const mw=Math.round(dw*0.5),mh=Math.round(H*0.12),mx=bx-Math.round(mw/2),my=deskY-mh-1;
      cx.fillStyle='#0a0c10'; cx.fillRect(mx-1,my-1,mw+2,mh+2);
      const mc=needs?warn:work?ok:cyan, g=work?(0.5+0.5*Math.abs(Math.sin(t/200+i))):needs?(0.5+0.5*Math.abs(Math.sin(t/350+i))):0.5;
      cx.fillStyle=mc; cx.globalAlpha=0.3+0.55*g; cx.fillRect(mx,my,mw,mh); cx.globalAlpha=1;
      cx.fillStyle=line; cx.fillRect(bx-1,my+mh,2,2);                                    // stand
      if(a.name && !a.ghost){ cx.fillStyle=ink; cx.font='9px ui-monospace,monospace'; cx.textAlign='center'; cx.fillText((a.name[0]||'').toUpperCase(),bx,chy-3); }
    }
    raf=requestAnimationFrame(draw);
  }
  window.addEventListener('resize',fit);
  window.__office=function(agents){ OAG=agents||[]; fit(); if(!raf) raf=requestAnimationFrame(draw); };
  fit(); raf=requestAnimationFrame(draw);
})();
function loadTeam(){ j('/api/agents').then(d=>{const el=$('#team');const a=d.agents||[];
  TEAM_AGENTS = a.map(x=>({id:x.id, name:x.name, color:(x.color||'var(--cyan)')}));
  if(window.__office) window.__office(a);
  if(!a.length){el.innerHTML='<span class="muted" style="font-size:13px">No agents yet — hire your first employee below.</span>';return;}
  el.className='grid'; el.innerHTML=a.map(x=>`<div class="emp"><div class="ava" style="background:${esc(x.color||'#e0a95e')}">${esc((x.name||'?').slice(0,1).toUpperCase())}</div>
    <div class="grow"><div class="row"><span class="nm grow">${esc(x.name)}</span><span class="badge ${statusCls(x.status)}">${esc(x.status||'idle')}</span></div>
    <div class="rl">${esc(x.role||'')}</div>
    <div class="meta">${esc((x.model||'app default'))} · ${(x.tools||[]).length} tools · ${esc(x.autonomy==='auto'?'auto':'asks first')}</div>
    <div class="row" style="margin-top:8px"><button class="btn mini danger" data-del="${esc(x.id)}">Fire</button></div></div></div>`).join('');
  el.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{if(!confirm('Remove this agent?'))return;await j('/api/agents/'+b.dataset.del,{method:'DELETE'});loadTeam();});
  const tgt=$('#target'); if(tgt) tgt.innerHTML='<option value="team">Whole team</option>'+a.map(x=>`<option value="${esc(x.id)}">@ ${esc(x.name)}</option>`).join('');
 }).catch(e=>{$('#team').innerHTML='<span class="muted">'+(e===401?'Admin only.':'Could not load team.')+'</span>';});}
loadTeam();

// ── The room ──────────────────────────────────────────────────────────────
// Keep a typed copy of the team so the in-flight placeholders can render the
// right name + colour + initial for every agent that's actually working.
let TEAM_AGENTS=[];
function roomMsg(m){
  if(m.role==='user') return `<div style="align-self:flex-end;max-width:80%;background:color-mix(in srgb,var(--accent) 18%,transparent);border:1px solid color-mix(in srgb,var(--accent) 30%,transparent);border-radius:12px 12px 4px 12px;padding:9px 12px">${esc(m.text)}</div>`;
  const team=m.role==='team';
  const av=team?'★':esc((m.agent_name||'?').slice(0,1).toUpperCase());
  const col=team?'var(--brass)':(m.color||'var(--cyan)');
  const pending=!!m.pending;
  const body = pending
    ? `<div style="display:flex;align-items:center;gap:8px;color:var(--dim)"><span class="room-spin" style="width:10px;height:10px;border-radius:50%;border:2px solid var(--sep-2);border-top-color:${col};display:inline-block;animation:roomspin 0.9s linear infinite;flex-shrink:0"></span><span class="room-elapsed" data-since="${m.since||Date.now()}">${esc(m.text||'thinking…')}</span></div>`
    : `<div style="white-space:pre-wrap">${esc(m.text)}</div>`;
  return `<div style="align-self:flex-start;max-width:88%;display:flex;gap:8px"><div class="ava" style="width:28px;height:28px;border-radius:8px;font-size:13px;background:${col}">${av}</div>`
    +`<div style="background:var(--tint);border:1px solid var(--sep);border-radius:12px 12px 12px 4px;padding:9px 12px;min-width:160px"><div class="faint" style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">${esc(m.agent_name||'agent')}</div>${body}</div></div>`;
}
function renderRoom(msgs){const el=$('#room'); if(!msgs||!msgs.length){el.innerHTML='<span class="muted" style="font-size:13px">No messages yet. Say hi to your team below.</span>';return;}
  el.innerHTML=msgs.map(roomMsg).join(''); el.scrollTop=el.scrollHeight;}
let roomMsgs=[];
let _roomTicker=null;
function _tickElapsed(){ document.querySelectorAll('.room-elapsed[data-since]').forEach(el=>{
  const since=parseInt(el.dataset.since||'0',10); if(!since)return;
  const s=Math.max(1,Math.round((Date.now()-since)/1000));
  let stage='thinking'; if(s>=45)stage='still working'; else if(s>=20)stage='working';
  el.textContent = `${stage} · ${s}s`;
}); }
function startRoomTicker(){ if(_roomTicker) return; _roomTicker=setInterval(_tickElapsed,1000); }
function stopRoomTicker(){ if(_roomTicker){clearInterval(_roomTicker);_roomTicker=null;} }
function loadRoom(){ j('/api/agents/room').then(d=>{roomMsgs=d.messages||[];renderRoom(roomMsgs);}).catch(()=>{}); }
loadRoom();
async function sayNow(){
  const inp=$('#say'); const text=(inp.value||'').trim(); if(!text)return;
  const target=$('#target').value||'team'; inp.value='';
  roomMsgs.push({role:'user',text:text});
  // Insert one pending placeholder PER agent that'll actually be woken — so the
  // user sees who is working, not a single silent 'thinking…'.
  const since=Date.now();
  let placeholders=[];
  if(target==='team'){
    const cap=(window.__teamCap||TEAM_AGENTS.length||3);
    const woken=TEAM_AGENTS.slice(0, Math.min(TEAM_AGENTS.length, cap));
    placeholders=woken.map(a=>({role:'agent',agent_name:a.name,color:a.color,text:'thinking…',pending:true,since}));
    if(!placeholders.length) placeholders=[{role:'team',agent_name:'Team',text:'thinking…',pending:true,since}];
  } else {
    const a=TEAM_AGENTS.find(x=>x.id===target);
    placeholders=[{role:'agent',agent_name:(a&&a.name)||'…',color:(a&&a.color)||'var(--cyan)',text:'thinking…',pending:true,since}];
  }
  placeholders.forEach(p=>roomMsgs.push(p));
  renderRoom(roomMsgs); startRoomTicker();
  // Soft hint when waits get long — only added once.
  let hintAdded=false;
  const hintTimer=setTimeout(()=>{ const el=$('#room-hint-live');
    if(el && !hintAdded){ hintAdded=true; el.textContent='Agents work in parallel — first reply lands first. Cloud models ~5–20s, local 10–60s+.'; }
  }, 8000);
  try{ const r=await j('/api/agents/say',{method:'POST',body:JSON.stringify({text:text,target:target})});
    // Drop ALL pending placeholders, then push the real replies.
    roomMsgs = roomMsgs.filter(m=>!m.pending);
    if(r.ok){ (r.messages||[]).forEach(m=>{ if(m.role!=='user') roomMsgs.push(m); }); }
    else roomMsgs.push({role:'agent',agent_name:'note',text:r.detail||'failed'});
    renderRoom(roomMsgs);
  }catch(e){
    roomMsgs = roomMsgs.filter(m=>!m.pending);
    roomMsgs.push({role:'agent',agent_name:'note',text:'failed: '+e}); renderRoom(roomMsgs);
  }
  finally{ clearTimeout(hintTimer); stopRoomTicker(); const el=$('#room-hint-live'); if(el) el.textContent=''; }
}
$('#say-btn').onclick=sayNow;
$('#say').addEventListener('keydown',e=>{if(e.key==='Enter')sayNow();});
$('#room-clear').onclick=async()=>{ if(!confirm('Clear the room transcript?'))return; await j('/api/agents/room',{method:'DELETE'}); roomMsgs=[]; renderRoom(roomMsgs); };

// draft system prompt
$('#draft-btn').onclick=async()=>{const m=$('#draft-msg');m.textContent='Drafting…';
  try{const r=await j('/api/agents/draft',{method:'POST',body:JSON.stringify({name:$('#f-name').value,role:$('#f-role').value,goal:$('#f-goal').value,personality:$('#f-pers').value,backstory:$('#f-back').value})});
    if(r.ok){$('#sp-wrap').style.display='';$('#f-sp').value=r.system_prompt;m.textContent='';}else m.textContent=r.detail||'failed';
  }catch(e){m.textContent='failed: '+e;}};

// hire
$('#hire-btn').onclick=async()=>{const m=$('#hire-msg');const name=$('#f-name').value.trim();
  if(!name){m.textContent='give them a name';return;}
  m.textContent='Hiring…';
  try{const r=await j('/api/agents',{method:'POST',body:JSON.stringify({name:name,role:$('#f-role').value,goal:$('#f-goal').value,personality:$('#f-pers').value,backstory:$('#f-back').value,model:$('#f-model').value,tools:[...selTools],autonomy:$('#f-auto').value,system_prompt:$('#f-sp').value})});
    if(r.ok){m.textContent='Hired '+r.agent.name+' ✓';$('#f-name').value='';$('#f-role').value='';$('#f-goal').value='';$('#f-back').value='';$('#f-sp').value='';$('#sp-wrap').style.display='none';selTools=new Set();renderTools();loadTeam();}
    else m.textContent=r.detail||'failed';
  }catch(e){m.textContent='failed: '+e;}};

// run the team
</script>
<script src="/static/js/concierge.js"></script>
</body></html>"""


_SETUP = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/static/mentor-icon.png">
<title>Mentor — Set up your AI</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.78);--surface-2:rgba(44,44,46,0.85);--sep:rgba(255,255,255,0.08);--sep-2:rgba(255,255,255,0.14);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--ok:#30d158;--warn:#ffd60a;--err:#ff453a;--tint:rgba(255,255,255,0.04);--tint-2:rgba(255,255,255,0.06);--shadow:0 1px 0 rgba(255,255,255,0.04) inset,0 10px 30px rgba(0,0,0,0.5);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#f2f2f7;--surface:rgba(255,255,255,0.78);--surface-2:rgba(248,248,250,0.92);--sep:rgba(0,0,0,0.08);--sep-2:rgba(0,0,0,0.14);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.36);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--ok:#248a3d;--warn:#a04400;--err:#c41e3a;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.06);--shadow:0 1px 2px rgba(0,0,0,0.04),0 10px 30px rgba(0,0,0,0.06);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#ebe2cf;--surface:rgba(252,247,236,0.84);--surface-2:rgba(245,238,222,0.94);--sep:rgba(43,58,74,0.12);--sep-2:rgba(43,58,74,0.2);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--ok:#3a7f2b;--warn:#a36a00;--err:#a32d2d;--tint:rgba(43,58,74,0.04);--tint-2:rgba(43,58,74,0.07);--shadow:0 1px 0 rgba(255,255,255,0.5) inset,0 8px 22px rgba(43,58,74,0.08);}
 *{box-sizing:border-box} option{background:var(--bg-2);color:var(--txt)} html,body{margin:0;height:100%}
 body{background:radial-gradient(120% 80% at 50% -10%,var(--bg-2),var(--bg)) fixed;color:var(--txt);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased;padding:56px 32px 80px;max-width:760px;margin:0 auto;letter-spacing:-0.005em}
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:16px;margin-bottom:4px}
 .mark{font:300 38px/1.05 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif;letter-spacing:-0.04em}
 .tag{color:var(--faint);font-size:13px;margin-bottom:24px}
 .pill{font:500 11px/1.2 inherit;padding:4px 10px;border-radius:99px;background:var(--tint-2);border:1px solid var(--sep);color:var(--dim);display:inline-flex;align-items:center;gap:5px}
 .pill.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
 .pill.warn{color:var(--warn);background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}
 .card{background:var(--surface);border:1px solid var(--sep);border-radius:14px;padding:20px;backdrop-filter:blur(24px) saturate(140%);-webkit-backdrop-filter:blur(24px) saturate(140%);box-shadow:var(--shadow);margin-bottom:14px}
 .row{display:flex;align-items:center;gap:10px} .grow{flex:1;min-width:0} .muted{color:var(--dim)} .faint{color:var(--faint)}
 .mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px}
 .btn{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:10px;cursor:pointer;background:var(--surface-2);border:1px solid var(--sep-2);color:var(--txt);font:500 13px/1 inherit;transition:background .15s,border-color .15s,transform .12s}
 .btn:hover{background:var(--tint-2);border-color:var(--brass);transform:translateY(-1px)} .btn:disabled{opacity:.5;cursor:default;transform:none}
 .btn.primary{background:color-mix(in srgb,var(--accent) 16%,transparent);border-color:color-mix(in srgb,var(--accent) 40%,transparent);color:var(--accent)}
 .btn.primary:hover{border-color:var(--accent)}
 .btn.mini{padding:6px 11px;font-size:12px;border-radius:8px}
 input.fld,textarea.fld,select.fld{width:100%;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:9px;padding:9px 11px;font:13px/1.4 inherit;outline:none}
 input.fld:focus,textarea.fld:focus,select.fld:focus{border-color:var(--brass)}
 textarea.fld{font-family:ui-monospace,"SF Mono",Menlo,monospace;resize:vertical}
 label.lab{display:block;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px}
 .badge{font:600 9px/1 -apple-system,system-ui,sans-serif;letter-spacing:.05em;text-transform:uppercase;padding:3px 7px;border-radius:5px;background:var(--tint-2);color:var(--dim);border:1px solid var(--sep)}
 .badge.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 30%,transparent);background:color-mix(in srgb,var(--ok) 10%,transparent)}
 .badge.fit{color:var(--cyan);border-color:color-mix(in srgb,var(--cyan) 30%,transparent);background:color-mix(in srgb,var(--cyan) 10%,transparent)}
 .badge.run{color:var(--brass);border-color:color-mix(in srgb,var(--brass) 35%,transparent);background:color-mix(in srgb,var(--brass) 10%,transparent)}
 .badge.err{color:var(--err);border-color:color-mix(in srgb,var(--err) 35%,transparent);background:color-mix(in srgb,var(--err) 12%,transparent)}
 .hw-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
 @media(max-width:560px){.hw-grid{grid-template-columns:repeat(1,1fr)}}
 .hw{padding:14px;border:1px solid var(--sep);border-radius:12px;background:var(--tint)}
 .hw .k{color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
 .hw .v{font-weight:600;font-size:18px;margin-top:4px;letter-spacing:-0.01em}
 .hw .s{color:var(--dim);font-size:12px}
 .bar{height:6px;border-radius:99px;background:var(--tint-2);overflow:hidden;margin-top:6px}
 .bar > i{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),var(--brass));transition:width .4s ease}
 /* step progress */
 .steps{display:flex;align-items:center;gap:6px;margin:0 0 18px;flex-wrap:wrap}
 .dot{display:flex;align-items:center;gap:8px}
 .dot .n{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font:600 12px/1 inherit;border:1px solid var(--sep-2);background:var(--tint);color:var(--dim);flex-shrink:0}
 .dot.on .n{background:var(--accent);border-color:var(--accent);color:#fff}
 .dot.done .n{background:color-mix(in srgb,var(--ok) 22%,transparent);border-color:color-mix(in srgb,var(--ok) 45%,transparent);color:var(--ok)}
 .dot .lbl{font-size:11px;color:var(--faint);white-space:nowrap}
 .dot.on .lbl{color:var(--txt)} .dot.done .lbl{color:var(--dim)}
 .dot .ln{width:18px;height:1px;background:var(--sep-2);margin:0 2px}
 @media(max-width:560px){.dot .lbl{display:none}.dot .ln{width:10px}}
 .step{display:none} .step.active{display:block}
 .why{color:var(--dim);font-size:13px;margin:0 0 14px;line-height:1.55}
 .nav{display:flex;align-items:center;gap:10px;margin-top:18px;position:sticky;bottom:0;padding:12px 0 8px;background:linear-gradient(to top,var(--bg) 70%,transparent);z-index:20}
 .nav .btn.primary{box-shadow:0 0 0 1px color-mix(in srgb,var(--accent) 45%,transparent),0 0 16px color-mix(in srgb,var(--accent) 22%,transparent)}
 .nav .grow{flex:1}
 .opt{display:flex;align-items:center;gap:12px;padding:11px 13px;border:1px solid var(--sep-2);border-radius:11px;background:var(--tint);cursor:pointer;margin-bottom:8px;transition:border-color .15s,background .15s}
 .opt:hover{border-color:var(--brass)}
 .opt.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 8%,transparent)}
 .opt .rd{width:18px;height:18px;border-radius:50%;border:2px solid var(--sep-2);flex-shrink:0;display:grid;place-items:center}
 .opt.on .rd{border-color:var(--accent)} .opt.on .rd::after{content:"";width:9px;height:9px;border-radius:50%;background:var(--accent)}
 .opt .name{font-weight:500;letter-spacing:-0.003em} .opt .meta{color:var(--dim);font-size:12px}
 .actmsg{font-size:12px;margin-top:10px;min-height:16px}
 .done-hero{text-align:center;padding:18px 0}
 .done-hero .big{font-size:40px;margin-bottom:6px}
 .topbar{position:fixed;top:14px;right:18px;display:flex;gap:8px;align-items:center;z-index:50}
 .jump{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;background:var(--surface);border:1px solid var(--sep);border-radius:99px;color:var(--txt);font:500 12px/1 inherit;box-shadow:var(--shadow)}
 .jump:hover{background:var(--tint-2)} .theme-switch{display:flex;gap:2px;background:var(--surface);border:1px solid var(--sep);border-radius:99px;padding:3px;box-shadow:var(--shadow)}
 .theme-switch button{background:transparent;border:none;color:var(--dim);padding:5px 11px;border-radius:99px;cursor:pointer;font:500 11px/1 inherit}
 .theme-switch button[aria-current="true"]{background:var(--txt);color:var(--bg)}
 .tabs{display:flex;gap:8px;margin-bottom:16px}
 .tab{flex:1;padding:12px;border:1px solid var(--sep-2);border-radius:11px;background:var(--tint);color:var(--dim);cursor:pointer;font:500 13px/1.3 inherit;text-align:center;transition:border-color .15s,background .15s,color .15s}
 .tab:hover{border-color:var(--brass)} .tab.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--txt)}
 .tabpane{animation:fade .2s ease} @keyframes fade{from{opacity:0}to{opacity:1}}
 @keyframes setupglow{0%,100%{box-shadow:0 0 0 1px color-mix(in srgb,var(--accent) 30%,transparent),0 0 20px color-mix(in srgb,var(--accent) 14%,transparent)}50%{box-shadow:0 0 0 1px color-mix(in srgb,var(--accent) 50%,transparent),0 0 34px color-mix(in srgb,var(--accent) 28%,transparent)}}
 #assistant-card{animation:setupglow 3.6s ease-in-out infinite}
 @keyframes asstattn{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 0%,transparent)}50%{box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 32%,transparent)}}
 #asst-input.attn{border-color:var(--accent)!important;animation:asstattn 1.1s ease-in-out infinite}
 @keyframes asseturgent{0%,100%{box-shadow:0 0 0 2px var(--warn),0 0 14px color-mix(in srgb,var(--warn) 30%,transparent)}50%{box-shadow:0 0 0 2px var(--warn),0 0 42px color-mix(in srgb,var(--warn) 62%,transparent)}}
 #assistant-card.urgent{animation:asseturgent .9s ease-in-out infinite!important}
 .provgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
 @media(max-width:560px){.provgrid{grid-template-columns:repeat(2,1fr)}}
 .prov{padding:11px 10px;border:1px solid var(--sep-2);border-radius:10px;background:var(--tint);cursor:pointer;font:500 12.5px/1.2 inherit;color:var(--txt);text-align:center;transition:border-color .15s,background .15s}
 .prov:hover{border-color:var(--brass)} .prov.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent)}
 .prov .ph{display:block;color:var(--faint);font-size:10px;margin-top:3px;font-weight:400}
 ::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:var(--sep-2);border-radius:5px}
</style></head><body>
<nav class="topbar"><a class="jump" href="/app">Home</a><a class="jump" href="/">Chat</a><a class="jump" href="/app/office">Office</a><a class="jump" href="/app/code">Code</a><a class="jump" href="/app/cookbook">Cookbook</a><a class="jump" href="/manage">Admin</a>
 <div class="theme-switch"><button data-theme-set="dark">Dark</button><button data-theme-set="light">Light</button><button data-theme-set="atlas">Atlas</button></div></nav>

<div class="top"><div class="mark">Set up your AI</div><span id="stepcap" class="pill">Step 1 of 3</span></div>
<div class="tag">A calm, guided walk from nothing to a working AI agent — connect a brain (local or cloud), then hire your first helper. Everything happens right here.</div>

<div class="steps" id="steps">
  <div class="dot" data-s="1"><span class="n">1</span><span class="lbl">Connect AI</span></div><span class="ln"></span>
  <div class="dot" data-s="2"><span class="n">2</span><span class="lbl">Hire</span></div><span class="ln"></span>
  <div class="dot" data-s="3"><span class="n">3</span><span class="lbl">Done</span></div>
</div>

<!-- STEP 1 — Connect AI (Local | Cloud, all in one place) -->
<div class="step" data-step="1">
  <div class="card">
    <p class="why">Two ways to give Mentor a brain — pick what fits you:<br>
      <b>🖥 Local</b> — the AI runs on your own computer. <b>Free</b> and <b>fully private</b> (nothing leaves your machine), but needs a decent graphics card and a one-time install (Ollama), and the first model can take a while to download.<br>
      <b>☁ Cloud</b> — connect a company's AI over the internet. <b>Instant</b> and very capable. You need an <b>API key</b> (we show you exactly where to get one — several are <b>free to start</b>, like OpenRouter, Groq and Gemini; bigger models cost per use). Your prompts are sent to that company.<br>
      <span class="faint">Not sure? If you have a gaming-grade graphics card, try Local. Otherwise Cloud is the quickest path.</span></p>

    <!-- Concierge / guide AI — a small free model that explains things and (next)
         can run setup for you. Separate from the main work model below. -->
    <div style="border:1px solid color-mix(in srgb,var(--cyan) 35%,transparent);background:color-mix(in srgb,var(--cyan) 6%,transparent);border-radius:11px;padding:14px;margin:0 0 16px">
      <div style="font-weight:600;margin-bottom:3px">First: pick a model for Atlas <span class="faint" style="font-weight:400;font-size:12px">— your setup guide; free, explains things &amp; can set the rest up for you</span></div>
      <div class="why" style="margin:0 0 10px;font-size:13px">Atlas is your in-app guide (separate from the main work model below). It only guides + runs setup, so a small free one is perfect. Recommended: <b>Groq</b> — free, fast, ~1 minute.</div>
      <div id="cg-tiers" class="provgrid" style="grid-template-columns:repeat(2,1fr)"></div>
      <div id="cg-action" style="display:none;margin-top:10px"></div>
      <div id="cg-msg" class="actmsg muted" style="margin-top:6px"></div>
    </div>

    <!-- Active assistant — the guide AI does setup for you (powered by the concierge above). -->
    <div id="assistant-card" style="border:1px solid var(--sep-2);border-radius:11px;padding:14px;margin:0 0 16px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
        <span style="font-weight:600">✦ Atlas — let the guide set it up for you</span>
        <a id="asst-ready" href="/" title="Open Mentor" style="display:none;font-size:10px;color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border:1px solid color-mix(in srgb,var(--ok) 30%,transparent);border-radius:99px;padding:2px 7px;text-decoration:none">● Mentor is ready</a>
      </div>
      <div class="why" style="margin:0 0 8px;font-size:13px">Pick a model for Atlas above, then just tell it what you want — Atlas can install, download, connect and configure things for you, and you watch it happen.</div>
      <div id="asst-log" style="max-height:300px;overflow:auto;display:flex;flex-direction:column;gap:8px;margin-bottom:8px"></div>
      <div class="row" style="gap:8px"><input id="asst-input" class="fld" style="flex:1" placeholder="e.g. set me up for private local coding"><button class="btn primary" id="asst-send" type="button">Send</button></div>
    </div>

    <div class="faint" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:0 0 6px">Your main work model (for chat, code, research)</div>
    <div class="tabs">
      <button class="tab on" data-tab="local" type="button">🖥️ Run locally · private &amp; free</button>
      <button class="tab" data-tab="cloud" type="button">☁️ Connect a cloud API</button>
    </div>
    <details style="margin:0 0 14px"><summary class="faint" style="cursor:pointer;font-size:13px">💬 Not sure? Quick answers</summary>
      <div class="why" style="margin-top:8px">
        <b>Local or cloud?</b> Got a gaming-grade graphics card → Local (free &amp; private). No/old GPU, or want it working in a minute → Cloud, and pick a 💚 FREE provider.<br>
        <b>Does cloud cost money?</b> Not necessarily — OpenRouter, Groq and Gemini have free models (limited). Bigger models charge per use.<br>
        <b>What's an API key?</b> A secret code from the provider that lets Mentor use their AI. Pick a provider and we link you straight to the page that makes one.<br>
        <b>What's VRAM?</b> Your graphics card's memory — it decides how big a local model can be. More VRAM = smarter local models.
      </div>
    </details>

    <!-- LOCAL pane -->
    <div class="tabpane" data-pane="local">
      <div id="hw" class="hw-grid" style="margin-bottom:14px"><div class="muted">reading your hardware…</div></div>
      <div id="ollama-note"></div>
      <div class="card" id="free-helper-card" style="border-color:color-mix(in srgb,var(--ok) 40%,transparent);background:color-mix(in srgb,var(--ok) 6%,transparent);margin:0 0 14px">
        <div style="font-weight:600;margin-bottom:3px">✨ Easiest: a free local AI — no key, no cost</div>
        <div class="why" style="margin:0 0 10px">One click downloads a small model (~1.3 GB) that runs on your own machine — free, private, no API key. It powers chat and the in-app guides right away. You can add a bigger/cloud model anytime.</div>
        <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn primary" id="free-helper-btn" type="button">Set up free local AI</button><span id="free-helper-msg" class="faint" style="font-size:12px"></span></div>
      </div>
      <div class="faint" style="font-size:12px;margin:0 0 8px">…or pick a specific model below:</div>
      <div id="fit-banner" class="muted" style="font-size:12px;margin-bottom:10px"></div>
      <div id="models" class="muted">finding models that fit…</div>
      <div id="serve-wrap" hidden style="margin-top:14px;border-top:1px solid var(--sep);padding-top:14px">
        <div id="serve-pick" class="muted" style="font-size:13px;margin-bottom:10px"></div>
        <label class="lab">Command we'll run (you can leave this as-is)</label>
        <textarea id="serve-cmd" class="fld" rows="2"></textarea>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="serve-btn" type="button">Serve this model</button><button class="btn mini" id="serve-skip" type="button">Skip — already running</button></div>
        <div id="serve-msg" class="actmsg muted"></div>
        <div id="serve-tasks" style="margin-top:12px"></div>
      </div>
    </div>

    <!-- CLOUD pane -->
    <div class="tabpane" data-pane="cloud" hidden>
      <label class="lab">Pick a provider <span class="faint" style="text-transform:none;letter-spacing:0">— 💚 FREE = free to start, no card needed</span></label>
      <div id="provgrid" class="provgrid"></div>
      <div id="cl-help" class="why" style="margin:10px 0 0;display:none"></div>
      <label class="lab" style="margin-top:14px">API key <span class="faint" style="text-transform:none;letter-spacing:0">— a secret code from the provider; stored on your machine, never shared</span></label>
      <input id="cl-key" class="fld" type="password" placeholder="paste your API key" autocomplete="off">
      <div class="row" style="margin-top:12px"><button class="btn" id="cl-test" type="button" disabled>Test key</button><button class="btn primary" id="cl-connect" type="button" disabled>Connect</button><span id="cl-msg" class="actmsg muted"></span></div>
    </div>
  </div>
  <div class="nav"><a class="btn" href="/app">← Cancel</a><span class="grow"></span><button class="btn primary" id="s1-next">Next →</button></div>
</div>

<!-- STEP 2 — Hire a starter agent -->
<div class="step" data-step="2">
  <div class="card">
    <p class="why">Now hire your first helper. We've filled in a friendly, general-purpose assistant named <b>Iris</b> — she can search the web and read pages, and she'll ask before doing anything risky. Adjust if you like, then hire.</p>
    <label class="lab">Name</label><input id="a-name" class="fld" value="Iris">
    <label class="lab">Role / title</label><input id="a-role" class="fld" value="Generalist Assistant">
    <label class="lab">Goal (one sentence)</label><input id="a-goal" class="fld" value="Help with everyday questions and tasks, with sources, fast">
    <label class="lab">Personality</label>
    <select id="a-pers" class="fld"><option value="concise professional">Concise professional</option><option value="warm collaborator">Warm collaborator</option><option value="meticulous and careful">Meticulous &amp; careful</option></select>
    <label class="lab">Autonomy</label>
    <select id="a-auto" class="fld"><option value="approve">Ask me before risky actions</option><option value="auto">Act on its own</option></select>
    <div class="faint" style="font-size:12px;margin-top:10px">Tools: <span class="mono">web_search</span> · <span class="mono">web_fetch</span></div>
    <div class="row" style="margin-top:14px"><button class="btn primary" id="hire-btn">Hire Iris</button><span id="hire-msg" class="muted" style="font-size:12px"></span></div>
  </div>
  <div class="nav"><button class="btn" id="s2-back">← Back</button><span class="grow"></span><button class="btn primary" id="s2-next">Next →</button></div>
</div>

<!-- STEP 3 — Done -->
<div class="step" data-step="3">
  <div class="card">
    <div class="done-hero">
      <div class="big">🎉</div>
      <h2 style="margin:0 0 6px;font-weight:600;letter-spacing:-0.01em">You're set up</h2>
      <p class="why" id="done-summary" style="margin:0 auto;max-width:460px">A model is connected and your first helper has been hired. Meet your team in the Office, or head back to the dashboard.</p>
      <div class="row" style="justify-content:center;gap:10px;margin-top:18px">
        <a class="btn primary" href="/app/office">Meet your team →</a>
        <a class="btn" href="/app">Back to dashboard</a>
      </div>
    </div>
  </div>
</div>

<script nonce="{{CSP_NONCE}}">
(function(){const s=localStorage.getItem('ody-theme')||'dark';document.documentElement.setAttribute('data-theme',s);
 document.querySelectorAll('[data-theme-set]').forEach(b=>{if(b.dataset.themeSet===s)b.setAttribute('aria-current','true');
  b.addEventListener('click',()=>{const t=b.dataset.themeSet;document.documentElement.setAttribute('data-theme',t);localStorage.setItem('ody-theme',t);document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','true');});});})();
const $=s=>document.querySelector(s);
const j=(u,o)=>fetch(u,Object.assign({credentials:'same-origin',headers:{'Content-Type':'application/json'}},o)).then(r=>{if(!r.ok)throw r.status;return r.json();});
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const adminNote='<span class="muted" style="font-size:13px">Admin only — sign in as an admin to use this.</span>';

// ── wizard state ────────────────────────────────────────────────────────────
let STEP=1; const LAST=3;
let HW_VRAM=0, HW_RAM=0, HAS_GPU=false;
let CHOSEN=null;          // {name, repo, vram}
let CONNECTED=false, HIRED=false;
const VRAM_RESERVE=3, RAM_RESERVE=4;  // GB kept free for desktop + browser

function showStep(n){
  STEP=Math.max(1,Math.min(LAST,n));
  document.querySelectorAll('.step').forEach(el=>el.classList.toggle('active',+el.dataset.step===STEP));
  $('#stepcap').textContent='Step '+STEP+' of '+LAST;
  document.querySelectorAll('#steps .dot').forEach(d=>{const s=+d.dataset.s;
    d.classList.toggle('on',s===STEP); d.classList.toggle('done',s<STEP);});
}

// Bind navigation IMMEDIATELY (before any code that could throw) and keep the
// step buttons always clickable — the wizard must never trap the user. You can
// proceed at any time; nothing is mandatory, and setup is changeable later.
(function(){
  const n1=document.getElementById('s1-next'); if(n1){ n1.disabled=false; n1.onclick=()=>showStep(2); }
  const b2=document.getElementById('s2-back'); if(b2) b2.onclick=()=>showStep(1);
  const n2=document.getElementById('s2-next'); if(n2){ n2.disabled=false; n2.onclick=()=>showStep(3); }
})();

// ── tabs: Local | Cloud (everything happens in step 1, no handoff) ───────────
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
  const which=t.dataset.tab;
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===t));
  document.querySelectorAll('.tabpane').forEach(p=>{ p.hidden = p.dataset.pane!==which; });
  if(which==='local') loadModels();
  if(which==='cloud') renderProviders();
}));

// ── Concierge / guide AI picker — sets teacher_model (the light helper model) ──
const CONCIERGE=[
  {id:'groq', name:'Groq', tag:'fast · recommended', base:'https://api.groq.com/openai/v1', get:'https://console.groq.com/keys', prefer:['llama-3.3-70b','llama-3.1-8b-instant','llama']},
  {id:'openrouter', name:'OpenRouter', tag:'balanced · many models', base:'https://openrouter.ai/api/v1', get:'https://openrouter.ai/keys', req:true, prefer:[':free']},
  {id:'opencode', name:'OpenCode Zen', tag:'free tier + Go sub · cheap', base:'https://opencode.ai/zen/v1', get:'https://opencode.ai/auth', req:true, prefer:['deepseek','qwen3','glm','claude']},
  {id:'cerebras', name:'Cerebras', tag:'strong', base:'https://api.cerebras.ai/v1', get:'https://cloud.cerebras.ai', prefer:['gpt-oss-120b','llama-3.3-70b','llama']},
  {id:'local', name:'Local (Ollama)', tag:'private · no key', local:true},
];
function _cgPick(models, prefer){ for(const p of (prefer||[])){ const m=(models||[]).find(x=>String(x).toLowerCase().includes(p.toLowerCase())); if(m) return m; } return (models||[])[0]; }
function renderConciergeTiers(){
  const g=$('#cg-tiers'); if(!g) return;
  g.innerHTML=CONCIERGE.map((c,i)=>`<div class="prov" data-i="${i}">${esc(c.name)}<span class="ph">${esc(c.tag)}</span></div>`).join('');
  g.querySelectorAll('.prov').forEach(b=>b.onclick=()=>{
    g.querySelectorAll('.prov').forEach(x=>x.classList.remove('on')); b.classList.add('on');
    cgSelect(CONCIERGE[+b.dataset.i]);
  });
}
function cgSelect(c){
  const a=$('#cg-action'); a.style.display='';
  if(c.local){
    a.innerHTML='<div class="why" style="font-size:12px;margin:0 0 8px">Downloads a small model (~1.3 GB) that runs on your machine — free, private, no key.<br><span style="color:var(--warn)">Heads-up: a small local model can answer questions, but it often <b>can\'t reliably run the do-it-for-me actions</b> (it may invent model names). For the active assistant, a free cloud guide — <b>Groq</b> or <b>OpenCode Zen</b> — works much better. Local is great for privacy.</span></div>'
      +'<button class="btn primary" id="cg-local-go" type="button">Set up Atlas locally</button>';
    $('#cg-local-go').onclick=async()=>{ const m=$('#cg-msg'); $('#cg-local-go').disabled=true; m.textContent='Setting up — downloading (~1.3 GB)…'; m.style.color='var(--dim)';
      let r; try{ r=await j('/api/setup/free-helper',{method:'POST'}); }catch(e){ m.textContent='Could not start.'; $('#cg-local-go').disabled=false; return; }
      if(r&&r.need_ollama){ m.textContent='Install Ollama first (in the Local tab below), then retry.'; $('#cg-local-go').disabled=false; return; }
      const poll=setInterval(async()=>{ let s; try{ s=await j('/api/setup/free-helper/status'); }catch(e){ return; }
        if(s.log) m.textContent=String(s.log).slice(-120);
        if(s.status==='done'){ clearInterval(poll); m.textContent='✓ Atlas is ready (local).'; m.style.color='var(--ok)'; conciergeReady(); }
        else if(s.status==='failed'){ clearInterval(poll); m.textContent=String(s.log||'Failed').slice(-160); m.style.color='var(--err)'; $('#cg-local-go').disabled=false; } }, 3000); };
    return;
  }
  a.innerHTML='<div class="why" style="font-size:12px;margin:0 0 6px">Get a <b>free</b> key (no card needed) → <a href="'+esc(c.get)+'" target="_blank" rel="noopener" style="color:var(--cyan)">'+esc(c.get.replace(/^https?:\/\//,''))+'</a>, then paste it:</div>'
    +'<div class="row" style="gap:8px;flex-wrap:wrap"><input id="cg-key" class="fld" type="password" placeholder="paste your '+esc(c.name)+' key" style="flex:1;min-width:180px"><button class="btn primary" id="cg-go" type="button">Use for Atlas</button></div>';
  $('#cg-go').onclick=async()=>{ const m=$('#cg-msg'); const key=($('#cg-key').value||'').trim();
    if(!key){ m.textContent='Paste your '+c.name+' key first.'; m.style.color='var(--err)'; return; }
    $('#cg-go').disabled=true; m.textContent='Connecting to '+c.name+'…'; m.style.color='var(--dim)';
    try{
      const fd=new FormData(); fd.append('base_url',c.base); fd.append('api_key',key); fd.append('name',c.name); fd.append('model_type','llm');
      if(c.req) fd.append('require_models','true'); else fd.append('skip_probe','false');
      const res=await fetch('/api/model-endpoints',{method:'POST',body:fd,credentials:'same-origin'}); const d=await res.json();
      if(!res.ok){ m.textContent=d.detail||'Could not connect — check the key.'; m.style.color='var(--err)'; $('#cg-go').disabled=false; return; }
      const pick=_cgPick(d.models, c.prefer);
      if(!pick){ m.textContent='Connected, but no models came back — try another provider.'; m.style.color='var(--err)'; $('#cg-go').disabled=false; return; }
      const spec=pick+'@'+c.name;
      await fetch('/api/manage/setting',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'teacher_model',value:spec})});
      m.textContent='✓ Atlas is ready: '+pick+' ('+c.name+').'; m.style.color='var(--ok)'; conciergeReady();
    }catch(e){ m.textContent='Request failed.'; m.style.color='var(--err)'; $('#cg-go').disabled=false; }
  };
}
renderConciergeTiers();

// ── STEP 2: the active assistant — it talks AND does setup for you ────────────
// Shared with the floating concierge widget so the chat follows across pages.
const ASST=(function(){try{return JSON.parse(localStorage.getItem('mentor-asst-chat')||'[]')||[]}catch(e){return[]}})();
function asstSave(){try{localStorage.setItem('mentor-asst-chat',JSON.stringify(ASST.slice(-40)))}catch(e){}}
let asstBusy=false;
function asstBubble(role, text, thinking){
  const log=$('#asst-log'); const b=document.createElement('div');
  const me=role==='user';
  b.style.cssText='max-width:90%;padding:8px 11px;border-radius:10px;font-size:13px;white-space:pre-wrap;'
    +(me?'align-self:flex-end;background:color-mix(in srgb,var(--accent) 16%,transparent);border:1px solid color-mix(in srgb,var(--accent) 30%,transparent)'
        :'align-self:flex-start;background:var(--tint);border:1px solid var(--sep)');
  b.textContent=text;
  if(thinking && !me){
    const lnk=document.createElement('a'); lnk.href='#';
    lnk.style.cssText='display:block;margin-top:6px;font-size:11px;color:var(--faint);text-decoration:none;';
    lnk.textContent='💭 Resonnering';
    const box=document.createElement('div');
    box.style.cssText='display:none;margin-top:6px;padding:8px;background:var(--tint);border:1px solid var(--sep);border-radius:6px;font-size:11px;max-height:160px;overflow:auto;white-space:pre-wrap;color:var(--dim);line-height:1.45;';
    box.textContent=thinking;
    lnk.addEventListener('click',function(e){e.preventDefault();box.style.display=box.style.display==='none'?'':'none';});
    b.appendChild(lnk); b.appendChild(box);
  }
  log.appendChild(b); log.scrollTop=log.scrollHeight; return b;
}
function asstNote(text){ const log=$('#asst-log'); const b=document.createElement('div');
  b.style.cssText='align-self:center;font-size:11px;color:var(--faint)'; b.innerHTML='⚙ '+esc(text); log.appendChild(b); log.scrollTop=log.scrollHeight; }
async function _poll(url, ok, fail, max){ for(let i=0;i<(max||20);i++){ await new Promise(r=>setTimeout(r,3000)); let s; try{ s=await j(url); }catch(e){ continue; } const r=ok(s); if(r!==undefined) return r; if(fail&&fail(s)) return fail(s); } return 'still working (check the panels below)'; }
async function asstAct(a){
  const t=a&&a.type, args=(a&&a.args)||{};
  try{
    if(t==='detect_system'){ const s=await j('/api/hwfit/system'); return `GPU: ${s.gpu_name||'none'}, VRAM: ${s.gpu_vram_gb||0} GB, RAM: ${s.available_ram_gb||'?'} GB, Ollama installed: ${!!s.ollama_installed}`; }
    if(t==='install_ollama'){ const r=await j('/api/setup/install-ollama',{method:'POST'}); if(r&&r.already) return 'Ollama already installed';
      return await _poll('/api/setup/install-ollama/status', s=>s.installed?'Ollama installed ✓':undefined, s=>s.status==='failed'?('install failed: '+String(s.log||'').slice(-120)):false, 60); }
    if(t==='setup_free_helper'){ const r=await j('/api/setup/free-helper',{method:'POST'}); if(r&&r.need_ollama) return 'needs Ollama first — run install_ollama';
      return await _poll('/api/setup/free-helper/status', s=>s.status==='done'?'free local helper ready ✓':undefined, s=>s.status==='failed'?('failed: '+String(s.log||'').slice(-120)):false, 120); }
    if(t==='recommend_local'){ const d=await j('/api/hwfit/models?limit=80'); let ms=(d&&d.models)||[]; if(HW_VRAM>0){const ev=Math.max(0,HW_VRAM-VRAM_RESERVE); ms=ms.filter(m=>{const v=+(m.vram_q4_gb||m.vram_gb||0);return v>0&&v<=ev;});} ms=ms.slice(0,5).map(m=>m.model||m.name); return ms.length?('Top fits: '+ms.join(', ')):'nothing fits — suggest a cloud model'; }
    if(t==='serve_local'){ const model=args.model||''; if(!model) return 'no model given'; await j('/api/model/serve',{method:'POST',body:JSON.stringify({repo_id:model,cmd:'ollama run '+String(model).split('/').pop().toLowerCase(),platform:'linux'})});
      return await _poll('/api/cookbook/tasks/status', s=>((s&&s.tasks)||[]).some(x=>['ready','completed'].includes((x.status||'').toLowerCase()))?('serving '+model+' ✓'):undefined, null, 30); }
    if(t==='set_role'){ const role=args.role, spec=args.spec; if(!role||!spec) return 'missing role/spec'; await fetch('/api/manage/setting',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:role,value:spec})}); return 'set '+role+' = '+spec; }
    if(t==='auto_roles'){ const body=JSON.stringify({tiers:(args.tiers||null)}); const r=await j('/api/setup/auto-roles',{method:'POST',body:body}); if(!r.ok) return r.error||'could not auto-fill roles'; const a=r.assigned||{}; const fb=r.fallbacks||{}; const nfb=Object.values(fb).reduce((n,xs)=>n+(xs||[]).length,0); return 'roles filled — '+Object.keys(a).map(k=>k+'='+a[k]).join(', ')+(r.vision?' · vision ✓':' · no vision')+' · '+nfb+' fallbacks across '+(r.source_count||0)+' source(s).'+(r.note?' '+r.note:''); }
    if(t==='open_concierge'){ const el=$('#cg-tiers'); if(el) el.scrollIntoView({behavior:'smooth',block:'center'}); return 'opened the guide-AI / key picker for the user'; }
    if(t==='toggle_paid_models'){ const en=!!(args.enabled); await j('/api/manage/setting',{method:'POST',body:JSON.stringify({key:'opencode_include_paid',value:en})}); return en?'Paid API models are now VISIBLE.':'Paid API models are now HIDDEN.'; }
    return 'unknown action: '+t;
  }catch(e){ return 'action error: '+e; }
}
let asstStarted=false;
async function asstTurn(steps){
  if(steps<=0){ asstNote('Paused — say "continue" and I\'ll keep going.'); return; }
  let r; try{ r=await j('/api/setup/assistant',{method:'POST',body:JSON.stringify({messages:ASST})}); }
  catch(e){ asstBubble('assistant','I could not reach the backend. Try again in a moment.'); return; }
  if(r && r.need_model){ asstBubble('assistant','Pick a model for me in the card above — Groq (free, ~1 min) is the easiest. Then I\'ll take it from here.');
    const el=$('#cg-tiers'); if(el) el.scrollIntoView({behavior:'smooth',block:'center'}); return; }
  if(!r || !r.ok){ asstBubble('assistant', (r&&r.detail)||'Something went wrong — let\'s try that again.'); return; }
  if(r.reply){ ASST.push({role:'assistant',content:r.reply}); asstBubble('assistant', r.reply, r.thinking||''); asstSave(); }
  if(r.action && r.action.type){
    if(r.action.type==='done'){
      // Announce once; after that just keep the small badge so we don't spam.
      const badge=$('#asst-ready'); if(badge) badge.style.display='inline-block';
      let shown=false; try{ shown=sessionStorage.getItem('asst-ready-shown')==='1'; }catch(e){}
      if(!shown){
        asstNote('✓ Setup complete');
        asstBubble('assistant','You\'re all set 🎉 — open Mentor below, or keep chatting if you want to change anything.');
        const log=$('#asst-log'); if(log){ const w=document.createElement('div'); w.style.cssText='align-self:flex-start;display:flex;gap:8px;flex-wrap:wrap;margin-top:2px';
          w.innerHTML='<a class="btn primary" href="/" style="text-decoration:none">Open Mentor →</a><a class="btn" href="/app/office" style="text-decoration:none">Meet your agents</a>';
          log.appendChild(w); log.scrollTop=log.scrollHeight; }
        try{ sessionStorage.setItem('asst-ready-shown','1'); }catch(e){}
      }
      return;
    }
    asstNote('doing: '+r.action.type+(r.action.args&&r.action.args.model?(' ('+r.action.args.model+')'):''));
    const result=await asstAct(r.action);
    asstNote('result: '+String(result).slice(0,140));
    ASST.push({role:'user',content:'[action result] '+r.action.type+': '+result}); asstSave();
    if(['auto_roles','set_role','serve_local','setup_free_helper'].includes(r.action.type)) asstUrgentCheck();
    await asstTurn(steps-1);  // let it continue the plan toward "done"
  } else { asstAttn(true); }  // assistant asked / is waiting — glow for the user's turn
}
function asstAttn(on){ const i=$('#asst-input'); if(i) i.classList.toggle('attn',!!on); }
// Surface the ready badge on reload if we've already announced this session.
(function(){ try{ if(sessionStorage.getItem('asst-ready-shown')==='1'){ const b=$('#asst-ready'); if(b) b.style.display='inline-block'; } }catch(e){} })();
function asstUrgentCheck(){ j('/api/setup/role-status').then(s=>{ const c=$('#assistant-card'); if(c) c.classList.toggle('urgent', !!(s&&s.critical_missing)); }).catch(()=>{}); }
asstUrgentCheck();
async function asstKickoff(force){
  if(force){ asstStarted=false; ASST.length=0; const log=$('#asst-log'); if(log) log.innerHTML=''; }
  if(asstStarted||asstBusy) return; asstStarted=true; asstBusy=true; const b=$('#asst-send'); if(b)b.disabled=true;
  try{ await asstTurn(6); } finally { asstBusy=false; if(b)b.disabled=false; }
}
// Called when the user picks/sets up their guide AI — the assistant takes over.
function conciergeReady(){ try{ asstKickoff(true); const el=$('#assistant-card'); if(el) el.scrollIntoView({behavior:'smooth',block:'start'}); }catch(e){} }
async function asstSend(){
  asstAttn(false);
  if(asstBusy) return; const inp=$('#asst-input'); const text=(inp.value||'').trim(); if(!text) return;
  asstStarted=true; asstBusy=true; $('#asst-send').disabled=true; inp.value='';
  ASST.push({role:'user',content:text}); asstBubble('user', text); asstSave();
  await asstTurn(6);
  asstBusy=false; $('#asst-send').disabled=false; inp.focus();
}
// Render any conversation carried over from the floating widget / a previous visit.
(function(){ const log=$('#asst-log'); if(log && ASST.length){ ASST.forEach(m=>{ if((m.role==='user'||m.role==='assistant')){ const t=String(m.content||'').replace(/^\[.*?\]\s*/,''); if(t.indexOf('[action result]')!==0) asstBubble(m.role,t); } }); asstStarted=true; } })();
(function(){ const b=$('#asst-send'), i=$('#asst-input'); if(b) b.onclick=asstSend;
  if(i){ i.addEventListener('focus',()=>asstAttn(false)); i.addEventListener('keydown',e=>{ asstAttn(false); if(e.key==='Enter'){ e.preventDefault(); asstSend(); } }); }
  // Proactive: the assistant greets first and drives — it doesn't wait for you.
  setTimeout(()=>asstKickoff(false), 900); })();

// ── STEP 1 / LOCAL: hardware ─────────────────────────────────────────────────
j('/api/hwfit/system').then(s=>{
  HAS_GPU=!!s.has_gpu; HW_VRAM=+(s.gpu_vram_gb||0); HW_RAM=+(s.available_ram_gb||0);
  const cell=(k,v,sub)=>`<div class="hw"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div>${sub?`<div class="s">${esc(sub)}</div>`:''}</div>`;
  $('#hw').innerHTML=
    cell('GPU', s.has_gpu?(s.gpu_name||'—'):'None', s.has_gpu?`${s.gpu_count||1}× · ${s.backend||''}`:'CPU inference')+
    cell('VRAM', s.gpu_vram_gb?`${s.gpu_vram_gb} GB`:'—', s.unified_memory?'unified memory':'')+
    cell('RAM', `${s.available_ram_gb||'?'} GB free`, `of ${s.total_ram_gb||'?'} GB`);
  renderOllamaNote(s.ollama_installed!==false ? true : false);
  loadModels();
}).catch(e=>{ $('#hw').innerHTML = e===401?adminNote:'<span class="muted">Could not read your hardware — you can still serve a model below, or use the Cloud tab.</span>'; loadModels(); });

// Local models run through Ollama (the easiest engine). If it isn't installed,
// a non-technical user would hit a cryptic 'ollama not found' on Serve — so guide
// them to get it FIRST, with a real download link and a re-check button.
let OLLAMA_OK=true;
function renderOllamaNote(ok){
  OLLAMA_OK=!!ok; const el=$('#ollama-note'); if(!el) return;
  if(ok){ el.innerHTML=''; return; }
  el.innerHTML='<div class="card" style="border-color:color-mix(in srgb,var(--warn) 45%,transparent);background:color-mix(in srgb,var(--warn) 8%,transparent);margin:0 0 12px">'
    +'<div style="font-weight:600;margin-bottom:4px">One quick install first: Ollama</div>'
    +'<div class="why" style="margin:0 0 10px">Running a model on your own machine needs <b>Ollama</b> — a small, free helper app. I can install it for you, or you can download it yourself. (Prefer not to install anything? The <b>Cloud API</b> tab has free models too.)</div>'
    +'<div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn primary" id="ollama-install" type="button">Install Ollama for me</button><a class="btn" href="https://ollama.com/download" target="_blank" rel="noopener">Download manually →</a><span id="ollama-recheck-msg" class="faint" style="font-size:12px"></span></div>'
    +'<pre id="ollama-log" class="faint" style="font-family:ui-monospace,monospace;font-size:11px;margin:8px 0 0;white-space:pre-wrap;max-height:120px;overflow:auto"></pre></div>';
  const ib=$('#ollama-install'); if(ib) ib.onclick=async()=>{
    const m=$('#ollama-recheck-msg'); ib.disabled=true; m.textContent='Installing Ollama… (this can take a minute)';
    try{ await j('/api/setup/install-ollama',{method:'POST'}); }catch(e){ m.textContent='Could not start — use Download manually.'; ib.disabled=false; return; }
    const poll=setInterval(async()=>{ let s; try{ s=await j('/api/setup/install-ollama/status'); }catch(e){ return; }
      if(s.log){ const lg=$('#ollama-log'); if(lg) lg.textContent=String(s.log).slice(-1200); }
      if(s.installed){ clearInterval(poll); m.textContent='Installed ✓'; renderOllamaNote(true); modelsLoaded=false; loadModels(); }
      else if(s.status==='failed'){ clearInterval(poll); m.textContent='Auto-install didn\'t finish (it may need admin rights) — use Download manually, then re-open this page.'; ib.disabled=false; }
    },3000);
  };
}

// ── STEP 1 / LOCAL: pick a model that fits (headroom rule) ───────────────────
let modelsLoaded=false;
function loadModels(){
  if(modelsLoaded) return; modelsLoaded=true;
  const effV = HW_VRAM>0 ? Math.max(0, +(HW_VRAM-VRAM_RESERVE).toFixed(1)) : 0;
  $('#fit-banner').innerHTML = HW_VRAM>0
    ? `Reserving <b>~${VRAM_RESERVE} GB VRAM</b> + <b>~${RAM_RESERVE} GB RAM</b> for your desktop + browser → showing models up to <b>~${effV} GB</b> (of ${HW_VRAM} GB).`
    : 'No GPU detected — showing the smallest models that can run on CPU.';
  j('/api/hwfit/models?limit=80').then(d=>{
    let ms=(d&&d.models)||[];
    if(HW_VRAM>0) ms=ms.filter(m=>{const v=+(m.vram_q4_gb||m.vram_gb||0);return v>0&&v<=effV;});
    else ms=ms.filter(m=>m.fit);
    ms=ms.slice(0,12);
    const el=$('#models');
    if(!ms.length){ el.innerHTML='<span class="muted" style="font-size:13px">Nothing fits once desktop + browser headroom is reserved. Pick a smaller / more-quantized model, or switch to the <b>Cloud API</b> tab above.</span>'; return; }
    function selectModel(i){
      const m=ms[i]; if(!m) return;
      el.querySelectorAll('.opt').forEach(x=>x.classList.remove('on'));
      const node=el.querySelector('.opt[data-i="'+i+'"]'); if(node) node.classList.add('on');
      CHOSEN={ name:(m.model||m.name||''), repo:(m.name||m.model||''), vram:(m.vram_q4_gb||m.vram_gb||0) };
      modelCmdDirty=false; ensureServeCmd();
      $('#serve-wrap').hidden=false;
    }
    // ✨ "pick for me" = the ranker's top fit for this hardware. No circular LLM
    // dependency (there's no model connected yet) — it's the honest best score.
    el.innerHTML='<div class="row" style="margin-bottom:10px"><button class="btn" id="rec-btn" type="button">✨ Pick the best for my machine</button><span id="rec-why" class="faint" style="font-size:12px"></span></div>'
      + ms.map((m,i)=>{
      const name=m.model||m.name||'?'; const v=m.vram_q4_gb||m.vram_gb;
      return `<div class="opt" data-i="${i}"><span class="rd"></span>`
        +`<span class="grow"><div class="name">${esc(name)}</div>`
        +`<div class="meta">${v?`~${esc(v)} GB VRAM`:''}${m.context_length?` · ${esc(m.context_length)} ctx`:''}${m.size_gb?` · ${esc(m.size_gb)} GB`:''}</div></span>`
        +`${i===0?'<span class="badge run">recommended</span>':''}<span class="badge fit">fits</span></div>`;
    }).join('');
    el.querySelectorAll('.opt').forEach(o=>o.onclick=()=>selectModel(+o.dataset.i));
    const rb=$('#rec-btn'); if(rb) rb.onclick=()=>{ selectModel(0); const m=ms[0];
      if(m) $('#rec-why').textContent='Chose '+(m.model||m.name)+' — highest fit score for your hardware (best balance of capability and speed).'; };
  }).catch(e=>{ $('#models').innerHTML = e===401?adminNote:'<span class="muted">Could not rank models — switch to the Cloud API tab, or serve a model by command below.</span>'; });
}

// ── STEP 1 / LOCAL: serve it ─────────────────────────────────────────────────
let modelCmdDirty=false;
$('#serve-cmd').addEventListener('input',()=>{ modelCmdDirty=true; });
function baseName(s){ return String(s||'').split('/').pop().toLowerCase(); }
function ensureServeCmd(){
  if(!CHOSEN){ $('#serve-pick').textContent='Pick a model above, or skip if one is already running.'; return; }
  $('#serve-pick').innerHTML='Chosen model: <b>'+esc(CHOSEN.name)+'</b>'+(CHOSEN.vram?` · ~${esc(CHOSEN.vram)} GB VRAM`:'');
  if(!modelCmdDirty) $('#serve-cmd').value='ollama run '+baseName(CHOSEN.name);
}
function setMsg(id,text,kind){ const el=$('#'+id); if(!el)return; el.textContent=text||'';
  el.style.color = kind==='err'?'var(--err)':kind==='ok'?'var(--ok)':'var(--dim)'; }
function markConnected(msg){ CONNECTED=true; $('#s1-next').disabled=false; if(msg) setMsg('serve-msg',msg,'ok'); }
function renderServeTasks(d){
  const el=$('#serve-tasks'); const tasks=(d&&d.tasks)||[];
  if(!tasks.length){ el.innerHTML=''; return; }
  el.innerHTML=tasks.map(t=>{
    const st=(t.status||'').toLowerCase();
    const bcls=st==='ready'||st==='completed'?'ok':st==='error'?'err':'run';
    const pct=Math.max(0,Math.min(100,parseInt(t.progress||'0',10)||0));
    const phase=t.phase||t.status||'';
    const showBar=st==='running'||st==='downloading';
    return `<div class="row" style="align-items:flex-start;gap:8px;margin-bottom:8px"><span class="badge ${bcls}">${esc(t.type||'task')}</span>`
      +`<span class="grow"><div class="name" style="font-weight:500">${esc(t.model||t.session_id||'job')}</div>`
      +`<div class="meta muted" style="font-size:12px">${esc(phase)}${t.tps?` · ${esc(t.tps)} tok/s`:''}</div>`
      +(showBar?`<div class="bar"><i style="width:${pct}%"></i></div>`:'')
      +(st==='error'&&t.error?`<div class="meta" style="color:var(--err);font-size:12px">${esc(t.error)}</div>`:'')
      +`</span><span class="badge ${bcls}">${esc(t.status||'')}</span></div>`;
  }).join('');
}
let pollTimer=null;
function pollTasks(){ j('/api/cookbook/tasks/status').then(d=>{
    renderServeTasks(d);
    const tasks=(d&&d.tasks)||[];
    const ready=tasks.some(t=>['ready','completed'].includes((t.status||'').toLowerCase()));
    if(ready){ markConnected('Your model is up and running.'); }
  }).catch(()=>{}); }
$('#serve-btn').onclick=async()=>{
  const cmd=($('#serve-cmd').value||'').trim();
  if(!cmd){ setMsg('serve-msg','Nothing to run — pick a model first, or skip.','err'); return; }
  const repo = CHOSEN ? (CHOSEN.repo||CHOSEN.name) : cmd;
  setMsg('serve-msg','Starting your model…');
  $('#serve-btn').disabled=true;
  try{
    const r=await j('/api/model/serve',{method:'POST',body:JSON.stringify({repo_id:repo, cmd:cmd, platform:'linux'})});
    if(r.ok){ setMsg('serve-msg','Starting up — watch the progress below.','ok');
      if(!pollTimer){ pollTasks(); pollTimer=setInterval(pollTasks,3000); }
      markConnected();
    } else { setMsg('serve-msg', r.error||r.detail||'Could not start the model.','err'); $('#serve-btn').disabled=false; }
  }catch(e){ setMsg('serve-msg', e===401?'Admin only.':'Could not start the model.','err'); $('#serve-btn').disabled=false; }
};
$('#serve-skip').onclick=()=>{ markConnected('Skipped — assuming a model is already running.'); };

// ✨ One-click free local helper: pull a small model (no key) + set it as the
// helper/teacher model, so chat + the "?" guides work for free, instantly.
(function(){ const fhb=$('#free-helper-btn'); if(!fhb) return;
  fhb.onclick=async()=>{ const m=$('#free-helper-msg'); fhb.disabled=true;
    m.textContent='Setting up — downloading the model (~1.3 GB, a few minutes)…';
    let r; try{ r=await j('/api/setup/free-helper',{method:'POST'}); }catch(e){ m.textContent='Could not start.'; fhb.disabled=false; return; }
    if(r && r.need_ollama){ m.textContent='Install Ollama first (button above), then try again.'; fhb.disabled=false; renderOllamaNote(false); return; }
    const poll=setInterval(async()=>{ let s; try{ s=await j('/api/setup/free-helper/status'); }catch(e){ return; }
      if(s.log) m.textContent=String(s.log).slice(-130);
      if(s.status==='done'){ clearInterval(poll); m.textContent='Free local AI ready ✓ — chat & guides now work, no key.'; markConnected(); }
      else if(s.status==='failed'){ clearInterval(poll); m.textContent=String(s.log||'Setup failed.').slice(-180); fhb.disabled=false; }
    }, 3000);
  };
})();

// ── STEP 1 / CLOUD: connect a provider API (in the same place) ───────────────
const PROVIDERS=[
  {name:'Anthropic', url:'https://api.anthropic.com', hint:'Claude', get:'https://console.anthropic.com/settings/keys', cost:'pay-as-you-go (needs billing set up)'},
  {name:'OpenAI', url:'https://api.openai.com/v1', hint:'GPT', get:'https://platform.openai.com/api-keys', cost:'pay-as-you-go (needs billing set up)'},
  {name:'OpenRouter', url:'https://openrouter.ai/api/v1', hint:'many models', req:true, free:true, get:'https://openrouter.ai/keys', cost:'free models available (limited); others pay-as-you-go'},
  {name:'OpenCode Zen', url:'https://opencode.ai/zen/v1', hint:'free + Go sub · cheap', req:true, free:true, get:'https://opencode.ai/auth', cost:'free tier (usage-limited) · OpenCode Go subscription is much cheaper than Claude Max for the GLM/Qwen3/DeepSeek pool · Claude/GPT pay-as-you-go on top'},
  {name:'DeepSeek', url:'https://api.deepseek.com/v1', hint:'cheap & strong', get:'https://platform.deepseek.com/api_keys', cost:'pay-as-you-go (very cheap)'},
  {name:'Groq', url:'https://api.groq.com/openai/v1', hint:'very fast', free:true, get:'https://console.groq.com/keys', cost:'free to start (generous free tier)'},
  {name:'Google Gemini', url:'https://generativelanguage.googleapis.com/v1beta/openai', hint:'Gemini', free:true, get:'https://aistudio.google.com/apikey', cost:'free tier (no card needed to start)'},
  {name:'Mistral', url:'https://api.mistral.ai/v1', hint:'Mistral', free:true, get:'https://console.mistral.ai/api-keys', cost:'free tier + pay-as-you-go'},
  {name:'Together AI', url:'https://api.together.xyz/v1', hint:'open models', get:'https://api.together.ai/settings/api-keys', cost:'pay-as-you-go'},
  {name:'xAI Grok', url:'https://api.x.ai/v1', hint:'Grok', get:'https://console.x.ai', cost:'pay-as-you-go'},
  {name:'Z.AI', url:'https://api.z.ai/api/paas/v4', hint:'GLM', get:'https://z.ai/manage-apikey/apikey-list', cost:'pay-as-you-go'},
  {name:'Ollama Cloud', url:'https://ollama.com/api', hint:'hosted Ollama', req:true, get:'https://ollama.com/settings/keys', cost:'subscription / pay-as-you-go'},
];
let CLOUD=null, provRendered=false;
function renderProviders(){
  if(provRendered) return; provRendered=true;
  const g=$('#provgrid');
  g.innerHTML=PROVIDERS.map((p,i)=>`<div class="prov" data-i="${i}">${esc(p.name)}${p.free?' <span style="color:var(--ok);font-size:9px;border:1px solid color-mix(in srgb,var(--ok) 40%,transparent);border-radius:4px;padding:0 3px;vertical-align:1px">FREE</span>':''}<span class="ph">${esc(p.hint)}</span></div>`).join('');
  g.querySelectorAll('.prov').forEach(b=>b.onclick=()=>{
    g.querySelectorAll('.prov').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); CLOUD=PROVIDERS[+b.dataset.i];
    $('#cl-connect').disabled=false; $('#cl-test').disabled=false;
    const h=$('#cl-help');
    if(h && CLOUD.get){ h.style.display='';
      h.innerHTML='<b>'+esc(CLOUD.name)+':</b> get a free API key here → <a href="'+esc(CLOUD.get)+'" target="_blank" rel="noopener" style="color:var(--cyan)">'+esc(CLOUD.get.replace(/^https?:\/\//,''))+'</a>'
        +'<br>Sign in, create a key, copy the long code, paste it above. <b>Cost:</b> '+esc(CLOUD.cost||'see the provider')+'. Your prompts are sent to '+esc(CLOUD.name)+'.'; }
    else if(h){ h.style.display='none'; }
  });
}
// Validate the key BEFORE committing — explicit feedback so a wrong key is caught
// here, not later when hiring an agent.
$('#cl-test').onclick=async()=>{
  if(!CLOUD){ setMsg('cl-msg','Pick a provider first.','err'); return; }
  const key=($('#cl-key').value||'').trim();
  if(!key){ setMsg('cl-msg','Paste your API key to test.','err'); return; }
  $('#cl-test').disabled=true; setMsg('cl-msg','Testing '+CLOUD.name+'…');
  try{
    const fd=new FormData(); fd.append('base_url',CLOUD.url); fd.append('api_key',key);
    const res=await fetch('/api/model-endpoints/test',{method:'POST',body:fd,credentials:'same-origin'});
    const d=await res.json();
    if(res.ok && d.online){ setMsg('cl-msg','✓ Key works — '+(d.count||0)+' model'+((d.count||0)!==1?'s':'')+' available. Click Connect to save.','ok'); }
    else { setMsg('cl-msg','✗ '+(d.ping_error||'Could not reach '+CLOUD.name+' — check the key.'),'err'); }
  }catch(e){ setMsg('cl-msg', e===401?'Admin only.':'Test failed.','err'); }
  $('#cl-test').disabled=false;
};
$('#cl-connect').onclick=async()=>{
  if(!CLOUD){ setMsg('cl-msg','Pick a provider first.','err'); return; }
  const key=($('#cl-key').value||'').trim();
  if(!key){ setMsg('cl-msg','Paste your API key for '+CLOUD.name+'.','err'); return; }
  $('#cl-connect').disabled=true; setMsg('cl-msg','Connecting to '+CLOUD.name+'…');
  try{
    const fd=new FormData();
    fd.append('base_url',CLOUD.url); fd.append('api_key',key);
    fd.append('name',CLOUD.name); fd.append('model_type','llm');
    if(CLOUD.req) fd.append('require_models','true'); else fd.append('skip_probe','false');
    const res=await fetch('/api/model-endpoints',{method:'POST',body:fd,credentials:'same-origin'});
    const d=await res.json();
    if(res.ok){ const n=d.models?d.models.length:0;
      setMsg('cl-msg','Connected — found '+n+' model'+(n!==1?'s':'')+'.','ok');
      CONNECTED=true; $('#s1-next').disabled=false;
    } else { setMsg('cl-msg', d.detail||'Could not connect — check the key.','err'); $('#cl-connect').disabled=false; }
  }catch(e){ setMsg('cl-msg', e===401?'Admin only.':'Connection failed.','err'); $('#cl-connect').disabled=false; }
};

// ── STEP 2: hire a starter agent ─────────────────────────────────────────────
$('#hire-btn').onclick=async()=>{
  const name=($('#a-name').value||'').trim();
  if(!name){ $('#hire-msg').textContent='Give your helper a name first.'; return; }
  $('#hire-btn').disabled=true; $('#hire-msg').textContent='Hiring…'; $('#hire-msg').style.color='var(--dim)';
  try{
    const r=await j('/api/agents',{method:'POST',body:JSON.stringify({
      name:name, role:$('#a-role').value, goal:$('#a-goal').value,
      personality:$('#a-pers').value, tools:['web_search','web_fetch'],
      autonomy:$('#a-auto').value })});
    if(r.ok){ HIRED=true; $('#hire-msg').textContent='Hired '+esc((r.agent&&r.agent.name)||name)+' ✓'; $('#hire-msg').style.color='var(--ok)';
      $('#hire-btn').textContent='Hired'; $('#s2-next').disabled=false;
      $('#done-summary').textContent='A model is connected and '+name+' has been hired. Meet your team in the Office, or head back to the dashboard.';
    } else { $('#hire-msg').textContent=r.detail||'Could not hire.'; $('#hire-msg').style.color='var(--err)'; $('#hire-btn').disabled=false; }
  }catch(e){ $('#hire-msg').textContent = e===401?'Admin only.':'Could not hire.'; $('#hire-msg').style.color='var(--err)'; $('#hire-btn').disabled=false; }
};

// ── navigation ──────────────────────────────────────────────────────────────
$('#s1-next').onclick=()=>showStep(2);
$('#s2-back').onclick=()=>showStep(1);
$('#s2-next').onclick=()=>showStep(3);

showStep(1);
</script>
<script src="/static/js/concierge.js"></script>
</body></html>"""


_CODE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/static/mentor-icon.png">
<title>Mentor — Code</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.78);--surface-2:rgba(44,44,46,0.85);--sep:rgba(255,255,255,0.08);--sep-2:rgba(255,255,255,0.14);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--ok:#30d158;--warn:#ffd60a;--err:#ff453a;--tint:rgba(255,255,255,0.04);--tint-2:rgba(255,255,255,0.06);--shadow:0 1px 0 rgba(255,255,255,0.04) inset,0 10px 30px rgba(0,0,0,0.5);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#f2f2f7;--surface:rgba(255,255,255,0.78);--surface-2:rgba(248,248,250,0.92);--sep:rgba(0,0,0,0.08);--sep-2:rgba(0,0,0,0.14);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.36);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--ok:#248a3d;--warn:#a04400;--err:#c41e3a;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.06);--shadow:0 1px 2px rgba(0,0,0,0.04),0 10px 30px rgba(0,0,0,0.06);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#ebe2cf;--surface:rgba(252,247,236,0.84);--surface-2:rgba(245,238,222,0.94);--sep:rgba(43,58,74,0.12);--sep-2:rgba(43,58,74,0.2);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--ok:#3a7f2b;--warn:#a36a00;--err:#a32d2d;--tint:rgba(43,58,74,0.04);--tint-2:rgba(43,58,74,0.07);--shadow:0 1px 0 rgba(255,255,255,0.5) inset,0 8px 22px rgba(43,58,74,0.08);}
 *{box-sizing:border-box} option{background:var(--bg-2);color:var(--txt)} html,body{margin:0;height:100%}
 body{background:radial-gradient(120% 80% at 50% -10%,var(--bg-2),var(--bg)) fixed;color:var(--txt);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased;padding:56px 32px 32px;max-width:880px;margin:0 auto;letter-spacing:-0.005em}
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:16px;margin-bottom:4px}
 .mark{font:300 38px/1.05 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif;letter-spacing:-0.04em}
 .tag{color:var(--faint);font-size:13px;margin-bottom:18px}
 .pill{font:500 11px/1.2 inherit;padding:4px 10px;border-radius:99px;background:var(--tint-2);border:1px solid var(--sep);color:var(--dim);display:inline-flex;align-items:center;gap:5px}
 .pill.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
 .pill.warn{color:var(--warn);background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}
 .row{display:flex;align-items:center;gap:10px} .grow{flex:1;min-width:0} .muted{color:var(--dim)} .faint{color:var(--faint)}
 .mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px}
 .btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:10px;cursor:pointer;background:var(--surface-2);border:1px solid var(--sep-2);color:var(--txt);font:500 13px/1 inherit;transition:background .15s,border-color .15s,transform .12s}
 .btn:hover{background:var(--tint-2);border-color:var(--brass);transform:translateY(-1px)} .btn:disabled{opacity:.5;cursor:default;transform:none}
 .btn.mini{padding:5px 9px;font-size:12px;border-radius:8px}
 .btn.primary{background:color-mix(in srgb,var(--brass) 22%,var(--surface-2));border-color:color-mix(in srgb,var(--brass) 55%,var(--sep-2))}
 .btn.primary:hover{background:color-mix(in srgb,var(--brass) 32%,var(--surface-2))}
 input.fld,textarea.fld,select.fld{width:100%;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:9px;padding:9px 11px;font:13px/1.4 inherit;outline:none}
 input.fld:focus,textarea.fld:focus,select.fld:focus{border-color:var(--brass)}
 textarea.fld{font-family:inherit;resize:vertical}
 label.lab{display:block;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px}
 select.fld{cursor:pointer}

 /* Setup bar — collapsed by default, summary chip on top */
 .setup-bar{margin-bottom:18px}
 .setup-row{display:flex;align-items:stretch;gap:8px}
 .setup-toggle{flex:1;background:var(--surface);border:1px solid var(--sep);border-radius:12px;padding:11px 14px;display:flex;align-items:center;gap:10px;color:var(--txt);cursor:pointer;text-align:left;font:13px/1.4 inherit;box-shadow:var(--shadow);min-width:0}
 .setup-toggle:hover{background:var(--tint-2)}
 .setup-summary{flex:1;display:flex;align-items:center;gap:6px;min-width:0;color:var(--dim);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .setup-summary b{color:var(--txt);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:260px;display:inline-block;vertical-align:bottom}
 .setup-summary .dot{width:3px;height:3px;border-radius:50%;background:var(--faint);display:inline-block;flex-shrink:0;margin:0 4px}
 .setup-chev{transition:transform .18s;color:var(--faint);font-size:10px;flex-shrink:0}
 .setup-toggle[aria-expanded="true"] .setup-chev{transform:rotate(180deg)}
 .setup-side{display:flex;align-items:center;gap:6px;flex-shrink:0}
 .setup-side .btn{background:var(--surface);border:1px solid var(--sep);box-shadow:var(--shadow)}
 .setup-body{margin-top:10px;padding:14px 16px;background:var(--surface);border:1px solid var(--sep);border-radius:12px;box-shadow:var(--shadow)}

 /* Conversation */
 .convo{display:flex;flex-direction:column;gap:14px;padding:4px 0 12px;min-height:200px}
 .empty{color:var(--dim);font-size:14px;text-align:center;padding:36px 16px 24px;line-height:1.65}
 .empty b{color:var(--txt);font-weight:500}

 /* Bubbles */
 .turn{display:flex;flex-direction:column;gap:6px;animation:fade .25s ease-out}
 @keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
 .bub{max-width:80%;padding:11px 14px;border-radius:14px;font-size:14px;line-height:1.55;white-space:pre-wrap;word-wrap:break-word;overflow-wrap:break-word;border:1px solid var(--sep);box-shadow:var(--shadow)}
 .bub .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--faint);margin-bottom:4px;font-weight:600}
 .bub.user{align-self:flex-end;background:color-mix(in srgb,var(--brass) 16%,var(--surface));border-color:color-mix(in srgb,var(--brass) 30%,var(--sep));border-radius:14px 14px 4px 14px}
 .bub.user .lbl{color:color-mix(in srgb,var(--brass) 80%,var(--dim))}
 .bub.ai{align-self:flex-start;background:var(--surface);border-radius:14px 14px 14px 4px}
 .bub.ai .lbl{color:var(--brass)}
 .bub.ai.err{border-color:color-mix(in srgb,var(--err) 40%,var(--sep));background:color-mix(in srgb,var(--err) 8%,var(--surface))}
 .bub.ai.err .lbl{color:var(--err)}

 /* Narrator line — system messages, no bubble */
 .narr{align-self:center;max-width:92%;color:var(--faint);font-size:12px;line-height:1.6;font-style:italic;text-align:center;padding:2px 6px}
 .narr b{color:var(--dim);font-style:normal;font-weight:500}
 .narr.warn b{color:var(--warn)}

 /* Pending bubble — spinner + stage + elapsed + progress bar */
 .pending{display:flex;align-items:center;gap:10px;min-width:220px}
 .spin{width:14px;height:14px;border:2px solid var(--sep-2);border-top-color:var(--brass);border-radius:50%;display:inline-block;animation:spin .7s linear infinite;flex-shrink:0}
 @keyframes spin{to{transform:rotate(360deg)}}
 .stage{color:var(--dim);font-size:13px;flex:1;min-width:0}
 .elapsed{color:var(--faint);font-size:11px;font-variant-numeric:tabular-nums;flex-shrink:0}
 .progress{height:2px;background:color-mix(in srgb,var(--brass) 18%,transparent);border-radius:2px;overflow:hidden;margin-top:8px;position:relative}
 .progress::after{content:"";position:absolute;left:-30%;top:0;height:100%;width:30%;background:var(--brass);animation:slide 1.6s ease-in-out infinite}
 @keyframes slide{50%{left:100%}100%{left:100%}}

 /* "Klemmer" — collapsible technical details inside a result bubble */
 .turn details{margin-top:10px;border-top:1px solid var(--sep);padding-top:8px}
 .turn details + details{border-top:1px solid var(--sep);margin-top:6px;padding-top:6px}
 .turn summary{cursor:pointer;color:var(--dim);font-size:12px;list-style:none;display:inline-flex;align-items:center;gap:6px;padding:3px 0;user-select:none;font-weight:500}
 .turn summary::-webkit-details-marker{display:none}
 .turn summary::before{content:"▸";color:var(--faint);font-size:10px;transition:transform .15s;display:inline-block;width:8px}
 .turn details[open] summary::before{transform:rotate(90deg)}
 .turn summary:hover{color:var(--txt)}
 pre.diff{white-space:pre-wrap;font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px;background:var(--tint);border:1px solid var(--sep);border-radius:10px;padding:11px 13px;max-height:420px;overflow:auto;margin:8px 0 0;line-height:1.45}
 .file-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
 .file-list .f{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--dim);background:var(--tint);border:1px solid var(--sep);border-radius:6px;padding:3px 8px}
 .branch-tag{display:inline-flex;align-items:center;gap:5px;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--brass);background:color-mix(in srgb,var(--brass) 10%,transparent);border:1px solid color-mix(in srgb,var(--brass) 30%,transparent);border-radius:6px;padding:2px 7px;margin-right:8px;vertical-align:middle}
 .stat{color:var(--faint);font-size:12px}
 .stat .plus{color:var(--ok)} .stat .minus{color:var(--err)}

 /* Composer — sticks to bottom of viewport while scrolling */
 .composer-wrap{position:sticky;bottom:14px;margin-top:16px;z-index:5}
 .composer{display:flex;gap:8px;align-items:flex-end;background:var(--surface);border:1px solid var(--sep-2);border-radius:14px;padding:10px;box-shadow:var(--shadow);backdrop-filter:blur(24px) saturate(140%);-webkit-backdrop-filter:blur(24px) saturate(140%)}
 .composer textarea{flex:1;background:transparent;color:var(--txt);border:none;outline:none;resize:none;font:14px/1.5 inherit;padding:6px 8px;max-height:200px;min-height:24px;overflow-y:auto}
 .composer textarea::placeholder{color:var(--faint)}
 .composer .send{background:var(--brass);color:#0b0b0d;border:none;border-radius:10px;padding:9px 16px;font:600 13px/1 inherit;cursor:pointer;flex-shrink:0;transition:transform .12s,opacity .15s}
 .composer .send:hover{transform:translateY(-1px)}
 .composer .send:disabled{opacity:.45;cursor:default;transform:none}
 .composer-foot{display:flex;gap:6px;align-items:center;padding:8px 4px 0;font-size:11px;color:var(--faint);flex-wrap:wrap}
 .composer-foot .lbl{color:var(--faint);font-size:11px;margin-right:2px}
 .ex{cursor:pointer;color:var(--dim);background:var(--tint);border:1px solid var(--sep);border-radius:99px;padding:4px 10px;font:inherit;font-size:11px}
 .ex:hover{color:var(--txt);border-color:var(--brass)}

 .topbar{position:fixed;top:14px;right:18px;display:flex;gap:8px;align-items:center;z-index:50}
 .jump{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;background:var(--surface);border:1px solid var(--sep);border-radius:99px;color:var(--txt);font:500 12px/1 inherit;box-shadow:var(--shadow)}
 .jump:hover{background:var(--tint-2)} .theme-switch{display:flex;gap:2px;background:var(--surface);border:1px solid var(--sep);border-radius:99px;padding:3px;box-shadow:var(--shadow)}
 .theme-switch button{background:transparent;border:none;color:var(--dim);padding:5px 11px;border-radius:99px;cursor:pointer;font:500 11px/1 inherit}
 .theme-switch button[aria-current="true"]{background:var(--txt);color:var(--bg)}
 ::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:var(--sep-2);border-radius:5px}
</style></head><body>
<nav class="topbar"><a class="jump" href="/app">Home</a><a class="jump" href="/">Chat</a><a class="jump" href="/app/office">Office</a><a class="jump" href="/app/code">Code</a><a class="jump" href="/app/cookbook">Cookbook</a><a class="jump" href="/manage">Admin</a>
 <div class="theme-switch"><button data-theme-set="dark">Dark</button><button data-theme-set="light">Light</button><button data-theme-set="atlas">Atlas</button></div></nav>

<div class="top"><div class="mark">Code</div><span id="aider-pill" class="pill">checking…</span></div>
<div class="tag">Vibe-code a real repository — describe a change, the AI edits files on a safe branch and shows you the diff. Free &amp; private with a local coder model.</div>

<!-- Collapsible setup -->
<div class="setup-bar">
  <div class="setup-row">
    <button class="setup-toggle" id="setup-toggle" aria-expanded="false" type="button">
      <span class="setup-summary" id="setup-summary">loading setup…</span>
      <span class="setup-chev">▾</span>
    </button>
    <div class="setup-side">
      <button class="btn mini" id="convo-clear" type="button" title="Start a fresh conversation">New chat</button>
    </div>
  </div>
  <div class="setup-body" id="setup-body" style="display:none">
    <div id="inst-row"></div>
    <label class="lab">Repository</label>
    <div class="row">
      <select id="proj" class="fld" style="flex:1"><option>scanning for repos…</option></select>
      <button class="btn" id="proj-new" type="button" title="Start a brand-new app from scratch">＋ New</button>
      <button class="btn" id="proj-refresh" type="button" title="Rescan for git repos">↻</button>
    </div>
    <div id="proj-custom" style="display:none;margin-top:8px"><input id="proj-path" class="fld" placeholder="/full/path/to/your/repo"></div>
    <div id="newproj" style="display:none;margin-top:8px;padding:11px;border:1px solid var(--sep-2);border-radius:9px;background:var(--tint)">
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <input id="np-name" class="fld" style="flex:1;min-width:150px" placeholder="project name — e.g. my-notes-app">
        <select id="np-kind" class="fld" style="flex:0 0 220px">
          <option value="gtk">Linux desktop app · GTK</option>
          <option value="qt">Linux desktop app · Qt (PySide6)</option>
          <option value="flask">Web app · Flask</option>
          <option value="cli">Command-line tool</option>
          <option value="empty">Empty project</option>
        </select>
        <button class="btn primary" id="np-create" type="button">Create</button>
      </div>
      <div id="np-msg" class="faint" style="font-size:12px;margin-top:6px">Mentor scaffolds a runnable starter app + git repo under <span class="mono">~/mentor-projects</span>, then you describe what to build below.</div>
    </div>
    <label class="lab">Coder model</label>
    <select id="model" class="fld"><option>loading models…</option></select>
    <label class="lab">Files to focus on (optional)</label>
    <input id="files" class="fld" placeholder="leave blank — the AI picks the files itself">
    <div class="faint" style="font-size:11px;margin-top:10px">Edits run on a feature branch (never main) and are <b>not committed</b> — you review the diff, then commit what you like.</div>
  </div>
</div>

<!-- Conversation -->
<div id="convo" class="convo"></div>

<!-- Composer -->
<div class="composer-wrap">
  <div class="composer">
    <textarea id="instr" rows="1" placeholder="Describe what to build or change…  (Enter to send · Shift+Enter for newline)"></textarea>
    <button class="send" id="run-btn" type="button">Send</button>
  </div>
  <div class="composer-foot" id="ex-foot"><span class="lbl">Try:</span></div>
</div>

<script nonce="{{CSP_NONCE}}">
(function(){const s=localStorage.getItem('ody-theme')||'dark';document.documentElement.setAttribute('data-theme',s);
 document.querySelectorAll('[data-theme-set]').forEach(b=>{if(b.dataset.themeSet===s)b.setAttribute('aria-current','true');
  b.addEventListener('click',()=>{const t=b.dataset.themeSet;document.documentElement.setAttribute('data-theme',t);localStorage.setItem('ody-theme',t);document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','true');});});})();
const $=s=>document.querySelector(s);
const j=(u,o)=>fetch(u,Object.assign({credentials:'same-origin',headers:{'Content-Type':'application/json'}},o)).then(r=>{if(!r.ok)throw r.status;return r.json();});
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const STORE='mentor-code-convo-v1';
let aiderReady=false, PROJECTS=[], MODELS=[];
// turns[i] = {kind:'user'|'narr'|'ai'|'pending'|'error', text?, stage?, since?, result?, log?, warn?, jobId?}
let turns=[];
let busy=false;
let elapsedTimer=null;
let activePoll=null;

const EXAMPLES=[
  'Build a GTK desktop app: a window with a sidebar list of notes and a + button that adds one, saved to ~/.mentor-notes.json. Clean, modern look.',
  'Make a Qt (PySide6) Pomodoro timer with start/pause/reset, a big countdown, and a system-tray icon.',
  'Build a Flask web dashboard showing live CPU, RAM and disk usage with small charts, auto-refreshing every 2 seconds.',
  'Create a command-line tool that watches a folder and converts every new image to WebP, printing a summary.',
  'Add a Settings dialog with a dark-mode toggle that persists between launches.',
];

function loadTurns(){ try{ const v=JSON.parse(localStorage.getItem(STORE)||'[]'); return Array.isArray(v)?v.filter(t=>t&&t.kind):[]; }catch(e){ return []; } }
function saveTurns(){ try{ localStorage.setItem(STORE,JSON.stringify(turns)); }catch(e){} }
window.addEventListener('beforeunload', saveTurns);

function shortPath(p){ if(!p) return '—'; return p.replace(/^\/home\/[^\/]+/,'~').replace(/^\/Users\/[^\/]+/,'~'); }
function shortModel(m){ return m? m.replace(/^ollama\//,'') : '—'; }

// ── Setup panel ───────────────────────────────────────────────────────────

function setupSummary(){
  const proj=chosenProject(), model=chosenModel();
  const s=$('#setup-summary');
  if(!aiderReady){ s.innerHTML='<span style="color:var(--warn)">⚠ Aider not installed</span><span class="dot"></span><span>tap to set up</span>'; return; }
  if(!proj){ s.innerHTML='<span style="color:var(--warn)">No project picked</span><span class="dot"></span><span>tap to choose</span>'; return; }
  if(!model){ s.innerHTML='<span style="color:var(--warn)">No coder model</span><span class="dot"></span><span>tap to choose</span>'; return; }
  s.innerHTML='repo <b>'+esc(shortPath(proj))+'</b><span class="dot"></span>model <b>'+esc(shortModel(model))+'</b>';
}

function toggleSetup(force){
  const t=$('#setup-toggle'), b=$('#setup-body');
  const open = (force===undefined) ? (t.getAttribute('aria-expanded')!=='true') : !!force;
  t.setAttribute('aria-expanded', open?'true':'false');
  b.style.display = open?'':'none';
}

async function load(){
  let st={};
  try{ st=await j('/api/code/status'); }
  catch(e){
    $('#setup-summary').textContent = e===401 ? 'Admin only — sign in as an admin.' : 'Could not load the Code workspace.';
    return;
  }
  aiderReady=!!st.aider_installed;
  $('#aider-pill').textContent=aiderReady?'Aider ready':'Aider not installed';
  $('#aider-pill').className='pill '+(aiderReady?'ok':'warn');
  $('#inst-row').innerHTML = aiderReady ? '' :
    '<div class="row" style="margin-bottom:12px"><span class="pill warn">setup</span><span class="grow" style="font-size:13px">Aider (the editor engine) isn\'t installed yet. It installs isolated — it never touches Mentor\'s own environment.</span><button class="btn" id="inst-btn" type="button">Install Aider</button></div><div id="inst-msg" class="muted" style="font-size:12px;margin-bottom:10px"></div>';
  const ib=$('#inst-btn'); if(ib) ib.onclick=installAider;
  await Promise.all([loadProjects(st.project), loadModels(st.model)]);
  setupSummary();
  if(!aiderReady || !chosenProject() || !chosenModel()) toggleSetup(true);
}

async function loadProjects(cur){
  let d={}; try{ d=await j('/api/code/projects'); }catch(e){ return; }
  PROJECTS=d.projects||[]; cur=cur||d.current||'';
  const sel=$('#proj'); sel.innerHTML='';
  if(!PROJECTS.length){ const o=document.createElement('option');o.value='';o.textContent='(no git repos found — choose Other folder…)';sel.appendChild(o); }
  PROJECTS.forEach(p=>{const o=document.createElement('option');o.value=p;o.textContent=p;if(p===cur)o.selected=true;sel.appendChild(o);});
  const oth=document.createElement('option');oth.value='__other__';oth.textContent='Other folder…';sel.appendChild(oth);
  if(cur && PROJECTS.indexOf(cur)<0){ oth.selected=true; $('#proj-custom').style.display=''; $('#proj-path').value=cur; }
  sel.onchange=()=>{ $('#proj-custom').style.display = sel.value==='__other__'?'':'none'; setupSummary(); };
  $('#proj-path').addEventListener('input', setupSummary);
}

async function loadModels(cur){
  let d={}; try{ d=await j('/api/code/models'); }catch(e){}
  MODELS=(d&&d.models)||[]; cur=cur||(d&&d.current)||'';
  const sel=$('#model'); sel.innerHTML='';
  if(!MODELS.length){ const o=document.createElement('option');o.value='';o.textContent='(no local models running — start one in Cookbook, or pick custom)';sel.appendChild(o); }
  MODELS.forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=m;if(m===cur)o.selected=true;sel.appendChild(o);});
  const oth=document.createElement('option');oth.value='__other__';oth.textContent='Other / custom…';sel.appendChild(oth);
  if(cur && MODELS.indexOf(cur)<0){ oth.selected=true; showModelCustom(cur); }
  sel.onchange=()=>{ if(sel.value==='__other__') showModelCustom(''); else hideModelCustom(); setupSummary(); };
}
function showModelCustom(v){ let el=$('#model-custom'); if(!el){ el=document.createElement('input'); el.id='model-custom'; el.className='fld'; el.placeholder='e.g. ollama/qwen2.5-coder:7b'; el.style.marginTop='8px'; $('#model').insertAdjacentElement('afterend',el); el.addEventListener('input', setupSummary); } el.value=v||''; el.style.display=''; }
function hideModelCustom(){ const el=$('#model-custom'); if(el) el.style.display='none'; }
function chosenProject(){ const s=$('#proj'); if(!s) return ''; return s.value==='__other__'?($('#proj-path').value||'').trim():s.value; }
function chosenModel(){ const s=$('#model'); if(!s) return ''; return s.value==='__other__'?(($('#model-custom')||{}).value||'').trim():s.value; }

async function installAider(){
  const msg=$('#inst-msg'); const b=$('#inst-btn'); if(b)b.disabled=true; msg.textContent='Installing (isolated — can take a few minutes)…';
  try{ await j('/api/manage/install-aider',{method:'POST'}); }catch(e){ msg.textContent='could not start install: '+e; if(b)b.disabled=false; return; }
  const poll=setInterval(async()=>{ try{ const s=await j('/api/code/status'); if(s.aider_installed){ clearInterval(poll); msg.textContent='Installed ✓'; load(); } }catch(e){} }, 3000);
}

$('#setup-toggle').addEventListener('click', ()=>toggleSetup());
$('#proj-refresh').onclick=()=>loadProjects();
$('#proj-new').onclick=()=>{ const n=$('#newproj'); n.style.display = n.style.display==='none'?'':'none'; if(n.style.display==='')$('#np-name').focus(); };
$('#np-create').onclick=async()=>{
  const name=($('#np-name').value||'').trim(); const kind=$('#np-kind').value; const m=$('#np-msg');
  if(!name){ m.textContent='Give the project a name.'; m.style.color='var(--err)'; return; }
  m.textContent='Creating…'; m.style.color='var(--dim)'; $('#np-create').disabled=true;
  try{ const r=await j('/api/code/new-project',{method:'POST',body:JSON.stringify({name,kind})});
    if(r.ok){ m.textContent='Created ✓ — now describe what to build below.'; m.style.color='var(--ok)';
      await loadProjects(r.path); $('#newproj').style.display='none'; $('#np-name').value=''; setupSummary(); }
    else { m.textContent=r.error||'Could not create.'; m.style.color='var(--err)'; }
  }catch(e){ m.textContent=e===401?'Admin only.':'Could not create.'; m.style.color='var(--err)'; }
  $('#np-create').disabled=false;
};

// Example chips under the composer
(function(){ const c=$('#ex-foot'); if(!c) return;
  EXAMPLES.forEach((e)=>{
    const b=document.createElement('button');
    b.type='button'; b.className='ex';
    b.textContent=e.split(':')[0].split(' ').slice(0,4).join(' ')+'…';
    b.title=e;
    b.onclick=()=>{ $('#instr').value=e; $('#instr').focus(); autoGrow($('#instr')); };
    c.appendChild(b);
  });
})();

// ── Rendering ─────────────────────────────────────────────────────────────

function colorDiff(diff){
  const lines=String(diff).split('\n').map(l=>{
    let col='var(--dim)';
    if(l.startsWith('+++')||l.startsWith('---')) col='var(--faint)';
    else if(l.startsWith('@@')) col='var(--cyan)';
    else if(l[0]==='+') col='var(--ok)';
    else if(l[0]==='-') col='var(--err)';
    return '<span style="color:'+col+'">'+esc(l)+'</span>';
  }).join('\n');
  return '<pre class="diff">'+lines+'</pre>';
}

function diffStats(diff){
  if(!diff) return null;
  let plus=0,minus=0;
  String(diff).split('\n').forEach(l=>{
    if(l.startsWith('+++')||l.startsWith('---')) return;
    if(l[0]==='+') plus++; else if(l[0]==='-') minus++;
  });
  return {plus,minus};
}

function renderTurn(t){
  if(t.kind==='user'){
    return '<div class="turn"><div class="bub user"><div class="lbl">You</div>'+esc(t.text)+'</div></div>';
  }
  if(t.kind==='narr'){
    return '<div class="turn"><div class="narr'+(t.warn?' warn':'')+'">'+(t.html||esc(t.text||''))+'</div></div>';
  }
  if(t.kind==='pending'){
    const stage = t.stage || 'starting…';
    return '<div class="turn"><div class="bub ai">'
      +'<div class="lbl">Mentor</div>'
      +'<div class="pending"><span class="spin"></span><span class="stage">'+esc(stage)+'</span><span class="elapsed" data-since="'+(t.since||Date.now())+'">0s</span></div>'
      +'<div class="progress"></div>'
      +'</div></div>';
  }
  if(t.kind==='error'){
    let h='<div class="turn"><div class="bub ai err"><div class="lbl">Mentor</div>'+esc(t.text||'Something went wrong.');
    if(t.log){ h+='<details><summary>What Aider reported</summary><pre class="diff" style="max-height:240px">'+esc(t.log)+'</pre></details>'; }
    h+='</div></div>';
    return h;
  }
  if(t.kind==='ai'){
    const r=t.result||{};
    const stats=diffStats(r.diff);
    const summary = r.response && r.response.trim() ? r.response.trim() : 'Done — review the diff below. Nothing has been committed.';
    let h='<div class="turn"><div class="bub ai"><div class="lbl">Mentor</div>'+esc(summary);
    let meta='';
    if(r.branch_created) meta+='<span class="branch-tag">'+esc(r.branch_created)+'</span>';
    if(stats) meta+='<span class="stat"><span class="plus">+'+stats.plus+'</span> / <span class="minus">−'+stats.minus+'</span>'+(r.files_used&&r.files_used.length?(' across '+r.files_used.length+' file'+(r.files_used.length===1?'':'s')):'')+'</span>';
    if(meta) h+='<div style="margin-top:10px">'+meta+'</div>';
    if(r.diff && r.diff.trim()){
      h+='<details><summary>See the diff</summary>'+colorDiff(r.diff)+'</details>';
    }
    if(r.files_used && r.files_used.length){
      h+='<details><summary>Files edited ('+r.files_used.length+')</summary><div class="file-list">'+r.files_used.map(f=>'<span class="f">'+esc(f)+'</span>').join('')+'</div></details>';
    }
    if(r.log){
      h+='<details><summary>Aider\'s raw log</summary><pre class="diff" style="max-height:240px">'+esc(r.log)+'</pre></details>';
    }
    h+='</div></div>';
    return h;
  }
  return '';
}

function emptyState(){
  return '<div class="empty"><b>Vibe-code a real repo.</b><br>Describe what to build below — a feature, a redesign, or a whole new app.<br>Mentor edits files on a safe branch and shows you the diff. Nothing is committed.</div>';
}

function renderConvo(){
  const el=$('#convo');
  if(!turns.length){ el.innerHTML=emptyState(); return; }
  el.innerHTML = turns.map(renderTurn).join('');
}

function scrollToBottom(){
  requestAnimationFrame(()=>{ window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'}); });
}

function pushTurn(t){ turns.push(t); saveTurns(); renderConvo(); scrollToBottom(); return turns.length-1; }
function updateTurn(i, patch){ if(i<0||i>=turns.length) return; Object.assign(turns[i],patch); renderConvo(); }
function replaceTurn(i, t){ if(i<0||i>=turns.length) return; turns.splice(i,1,t); saveTurns(); renderConvo(); scrollToBottom(); }

function tickElapsed(){
  document.querySelectorAll('.elapsed[data-since]').forEach(el=>{
    const since=parseInt(el.dataset.since||'0',10); if(!since)return;
    const s=Math.max(1,Math.round((Date.now()-since)/1000));
    el.textContent = s<60 ? s+'s' : Math.floor(s/60)+'m '+(s%60)+'s';
  });
}
function startElapsed(){ if(elapsedTimer) return; elapsedTimer=setInterval(tickElapsed,1000); }
function stopElapsed(){ if(elapsedTimer){clearInterval(elapsedTimer); elapsedTimer=null;} }

// ── Composer ──────────────────────────────────────────────────────────────

function autoGrow(t){ if(!t) return; t.style.height='auto'; t.style.height=Math.min(200, t.scrollHeight)+'px'; }
const instrEl=$('#instr');
instrEl.addEventListener('input', e=>autoGrow(e.target));
instrEl.addEventListener('keydown', e=>{
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); onSend(); }
});

$('#run-btn').onclick=onSend;
$('#convo-clear').onclick=()=>{
  if(busy){ if(!confirm('A run is in progress. Cancel it and start a fresh conversation?')) return; if(activePoll){clearInterval(activePoll); activePoll=null;} stopElapsed(); busy=false; $('#run-btn').disabled=false; }
  else if(turns.length && !confirm('Start a fresh conversation? Past turns will be cleared.')) return;
  turns=[]; saveTurns(); renderConvo();
};

async function onSend(){
  if(busy) return;
  const text=(instrEl.value||'').trim();
  if(!text) return;
  if(!aiderReady){ pushTurn({kind:'narr', warn:true, html:'<b>Aider isn\'t installed yet.</b> Open the setup panel above to install it.'}); toggleSetup(true); return; }
  const project=chosenProject(), model=chosenModel();
  if(!project){ pushTurn({kind:'narr', warn:true, html:'<b>No repository picked.</b> Open the setup panel above to choose one.'}); toggleSetup(true); return; }
  if(!model){ pushTurn({kind:'narr', warn:true, html:'<b>No coder model picked.</b> Open the setup panel above to choose one.'}); toggleSetup(true); return; }
  const files=($('#files')?$('#files').value:'').trim();

  // Clear the composer the moment the user sends — like a real chat.
  instrEl.value=''; autoGrow(instrEl);
  busy=true; $('#run-btn').disabled=true;

  pushTurn({kind:'user', text});
  pushTurn({kind:'narr', html:'Working in <b>'+esc(shortPath(project))+'</b> with <b>'+esc(shortModel(model))+'</b> on a safe branch.'+(files?' Focusing on <b>'+esc(files)+'</b>.':'')});
  const pIdx = pushTurn({kind:'pending', stage:'starting…', since:Date.now()});
  startElapsed();

  let r;
  try{
    r=await j('/api/code/edit',{method:'POST',body:JSON.stringify({instruction:text,files,project,model})});
  } catch(e){
    stopElapsed();
    replaceTurn(pIdx, {kind:'error', text:'Couldn\'t start the edit: '+(e===401?'admin only — sign in as an admin.':String(e))});
    busy=false; $('#run-btn').disabled=false; return;
  }
  if(!r.ok){
    stopElapsed();
    replaceTurn(pIdx, {kind:'error', text:r.error||'Couldn\'t start the edit.'});
    busy=false; $('#run-btn').disabled=false; return;
  }

  const id=r.job_id;
  updateTurn(pIdx, {jobId: id});
  saveTurns();
  pollJob(id, pIdx);
}

function pollJob(id, pIdx){
  busy=true; $('#run-btn').disabled=true; startElapsed();
  let misses=0;
  activePoll=setInterval(async()=>{
    let job; try{ job=await j('/api/code/jobs/'+id); }catch(e){ return; }
    if(job.error==='no such job'){
      misses++;
      if(misses>=2){ clearInterval(activePoll); activePoll=null; stopElapsed();
        replaceTurn(pIdx, {kind:'narr', html:'The job expired (Mentor was probably restarted). Send the same prompt again to retry.'});
        busy=false; $('#run-btn').disabled=false; }
      return;
    }
    misses=0;
    if(job.stage && turns[pIdx] && turns[pIdx].kind==='pending') updateTurn(pIdx, {stage: job.stage});
    if(job.status==='done' || job.status==='failed'){
      clearInterval(activePoll); activePoll=null; stopElapsed();
      const res=job.result||{};
      if(job.status==='failed' || res.error){
        replaceTurn(pIdx, {kind:'error', text: res.error || 'The edit didn\'t finish.', log: res.log||''});
      } else {
        replaceTurn(pIdx, {kind:'ai', result: res});
      }
      busy=false; $('#run-btn').disabled=false;
    }
  }, 1500);
}

// ── Boot ──────────────────────────────────────────────────────────────────

turns = loadTurns();
renderConvo();
autoGrow(instrEl);

// Resume any in-flight job from a previous page visit.
(function resumeJob(){
  for(let i=0; i<turns.length; i++){
    if(turns[i].kind==='pending' && turns[i].jobId){
      turns[i].since = Date.now();
      renderConvo();
      pollJob(turns[i].jobId, i);
      return;
    }
  }
})();

load();
</script>
<script src="/static/js/concierge.js"></script>
</body></html>"""


_WORKSPACE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/static/mentor-icon.png">
<title>Mentor — Workspace</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.92);--surface-2:rgba(44,44,46,0.9);--sep:rgba(255,255,255,0.10);--sep-2:rgba(255,255,255,0.16);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--tint:rgba(255,255,255,0.05);--tint-2:rgba(255,255,255,0.08);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#eef0f4;--surface:rgba(255,255,255,0.95);--surface-2:rgba(245,245,248,0.95);--sep:rgba(0,0,0,0.10);--sep-2:rgba(0,0,0,0.16);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.4);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.07);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#e7dcc6;--surface:rgba(252,247,236,0.96);--surface-2:rgba(245,238,222,0.96);--sep:rgba(43,58,74,0.14);--sep-2:rgba(43,58,74,0.22);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--tint:rgba(43,58,74,0.05);--tint-2:rgba(43,58,74,0.08);}
 *{box-sizing:border-box} option{background:var(--bg-2);color:var(--txt)} html,body{margin:0;height:100%;overflow:hidden}
 body{background:var(--bg);color:var(--txt);font:13px/1.4 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased;display:flex;flex-direction:column}
 a{color:inherit;text-decoration:none}
 .ws-bar{flex:0 0 auto;display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--surface);border-bottom:1px solid var(--sep);flex-wrap:wrap}
 .ws-bar .mark{font:500 14px/1 -apple-system,system-ui,sans-serif;letter-spacing:-0.02em;margin-right:4px}
 .ws-bar .grow{flex:1}
 .wb{display:inline-flex;align-items:center;gap:5px;padding:6px 10px;border-radius:8px;cursor:pointer;background:var(--surface-2);border:1px solid var(--sep-2);color:var(--txt);font:500 12px/1 inherit;transition:background .12s,border-color .12s}
 .wb:hover{border-color:var(--brass);background:var(--tint-2)}
 .wb.ghost{background:transparent}
 .ws-area{flex:1 1 auto;min-height:0;display:flex}
 .ws-split{display:flex;flex:1 1 0;min-width:0;min-height:0}
 .ws-row{flex-direction:row} .ws-col{flex-direction:column}
 .ws-pane{display:flex;flex-direction:column;flex:1 1 0;min-width:0;min-height:0;background:var(--bg-2);border:1px solid var(--sep);border-radius:10px;margin:5px;overflow:hidden}
 .ws-head{flex:0 0 auto;display:flex;align-items:center;gap:4px;padding:5px 6px;background:var(--surface);border-bottom:1px solid var(--sep)}
 .ws-surface{background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:6px;padding:3px 6px;font:600 12px/1 inherit;cursor:pointer;outline:none;max-width:160px}
 .ws-grow{flex:1}
 .ws-btn{background:transparent;border:1px solid transparent;color:var(--dim);border-radius:6px;width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:13px;line-height:1}
 .ws-btn:hover{background:var(--tint-2);color:var(--txt);border-color:var(--sep-2)}
 .ws-frame{flex:1 1 auto;width:100%;border:0;background:var(--bg);min-height:0}
 .ws-divider{flex:0 0 auto;position:relative;z-index:2}
 .ws-divider-v{width:6px;cursor:col-resize} .ws-divider-h{height:6px;cursor:row-resize}
 .ws-divider::after{content:"";position:absolute;inset:0;margin:auto;background:var(--sep-2);border-radius:99px;transition:background .12s}
 .ws-divider-v::after{width:2px;height:30px} .ws-divider-h::after{height:2px;width:30px}
 .ws-divider:hover::after{background:var(--brass)}
 .ws-dragging .ws-frame{pointer-events:none}
 .ws-dragging{cursor:grabbing}
 .theme-switch{display:flex;gap:2px;background:var(--surface-2);border:1px solid var(--sep-2);border-radius:99px;padding:2px}
 .theme-switch button{background:transparent;border:none;color:var(--dim);padding:4px 9px;border-radius:99px;cursor:pointer;font:500 11px/1 inherit}
 .theme-switch button[aria-current="true"]{background:var(--txt);color:var(--bg)}
</style></head><body>
<div class="ws-bar">
  <span class="mark">✦ Workspace</span>
  <a class="wb ghost" href="/app">← Exit</a>
  <span style="width:1px;height:18px;background:var(--sep-2);margin:0 2px"></span>
  <button class="wb" id="ws-add">＋ Pane</button>
  <button class="wb ghost" data-preset="single" title="One pane">▢</button>
  <button class="wb ghost" data-preset="cols2" title="Two columns">▥</button>
  <button class="wb ghost" data-preset="grid" title="Four panes (2×2)">⊞</button>
  <span class="faint" style="font-size:11px;margin-left:4px">Drag dividers to resize · each pane is a live Mentor screen</span>
  <span class="grow"></span>
  <div class="theme-switch"><button data-theme-set="dark">Dark</button><button data-theme-set="light">Light</button><button data-theme-set="atlas">Atlas</button></div>
</div>
<div class="ws-area" id="ws"></div>
<script nonce="{{CSP_NONCE}}">
(function(){const s=localStorage.getItem('ody-theme')||'dark';document.documentElement.setAttribute('data-theme',s);
 document.querySelectorAll('[data-theme-set]').forEach(b=>{if(b.dataset.themeSet===s)b.setAttribute('aria-current','true');
  b.addEventListener('click',()=>{const t=b.dataset.themeSet;document.documentElement.setAttribute('data-theme',t);localStorage.setItem('ody-theme',t);document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','true');});});})();

const SURFACES=[
  {name:'Chat', url:'/'},
  {name:'Dashboard', url:'/app'},
  {name:'Office', url:'/app/office'},
  {name:'Code', url:'/app/code'},
  {name:'Cookbook', url:'/app/cookbook'},
  {name:'Set up', url:'/app/setup'},
  {name:'Admin', url:'/manage'},
];
const WS=document.getElementById('ws');
let uid=0; const nid=()=>'p'+(++uid)+'-'+(Date.now()%9999);
function mk(tag,cls){const e=document.createElement(tag);if(cls)e.className=cls;return e;}

// ── layout tree: leaf {type:'leaf',id,url} | split {type:'split',dir,ratio,a,b} ──
const PRESETS={
  single:()=>({type:'leaf',id:nid(),url:'/'}),
  cols2:()=>({type:'split',dir:'row',ratio:0.58,a:{type:'leaf',id:nid(),url:'/'},b:{type:'leaf',id:nid(),url:'/manage'}}),
  grid:()=>({type:'split',dir:'row',ratio:0.5,
    a:{type:'split',dir:'col',ratio:0.5,a:{type:'leaf',id:nid(),url:'/'},b:{type:'leaf',id:nid(),url:'/app/office'}},
    b:{type:'split',dir:'col',ratio:0.5,a:{type:'leaf',id:nid(),url:'/manage'},b:{type:'leaf',id:nid(),url:'/app/code'}}}),
};
let root=load()||PRESETS.cols2();

function save(){ try{ localStorage.setItem('ws-layout', JSON.stringify(root)); }catch(e){} }
function load(){ try{ const v=JSON.parse(localStorage.getItem('ws-layout')); return (v&&v.type)?v:null; }catch(e){ return null; } }

function findParent(node,target){ if(node.type!=='split')return null;
  if(node.a===target||node.b===target)return node;
  return findParent(node.a,target)||findParent(node.b,target); }
function replaceNode(target,repl){ if(root===target){root=repl;return;} const p=findParent(root,target); if(!p)return; if(p.a===target)p.a=repl; else p.b=repl; }

function splitLeaf(leaf,dir){ const nl={type:'leaf',id:nid(),url:leaf.url};
  replaceNode(leaf,{type:'split',dir,ratio:0.5,a:leaf,b:nl}); rerender(); }
function closeLeaf(leaf){ if(root===leaf)return; const p=findParent(root,leaf); if(!p)return;
  replaceNode(p, p.a===leaf?p.b:p.a); rerender(); }

function renderLeaf(node){
  const pane=mk('div','ws-pane'); pane.dataset.id=node.id;
  const head=mk('div','ws-head');
  const sel=mk('select','ws-surface');
  sel.innerHTML=SURFACES.map(s=>'<option value="'+s.url+'"'+(s.url===node.url?' selected':'')+'>'+s.name+'</option>').join('');
  sel.onchange=()=>{ node.url=sel.value; const f=pane.querySelector('iframe'); if(f)f.src=node.url; save(); };
  head.appendChild(sel);
  head.appendChild(mk('span','ws-grow'));
  const mkbtn=(t,title,fn)=>{const b=mk('button','ws-btn');b.textContent=t;b.title=title;b.onclick=fn;head.appendChild(b);return b;};
  mkbtn('▥','Split left / right',()=>splitLeaf(node,'row'));
  mkbtn('▤','Split top / bottom',()=>splitLeaf(node,'col'));
  mkbtn('↻','Reload',()=>{const f=pane.querySelector('iframe'); if(f)f.src=f.src;});
  mkbtn('⤢','Open full',()=>{ window.location.href=node.url; });
  mkbtn('✕','Close pane',()=>closeLeaf(node));
  const frame=mk('iframe','ws-frame'); frame.src=node.url; frame.setAttribute('title',node.url);
  pane.appendChild(head); pane.appendChild(frame);
  return pane;
}
function renderNode(node){
  if(node.type==='leaf') return renderLeaf(node);
  const wrap=mk('div','ws-split '+(node.dir==='row'?'ws-row':'ws-col'));
  const a=renderNode(node.a), b=renderNode(node.b);
  a.style.flex='0 0 '+(node.ratio*100)+'%'; b.style.flex='1 1 0';
  const div=mk('div','ws-divider '+(node.dir==='row'?'ws-divider-v':'ws-divider-h'));
  attachDrag(div,node,wrap,a);
  wrap.appendChild(a); wrap.appendChild(div); wrap.appendChild(b);
  return wrap;
}
function attachDrag(div,node,wrap,aEl){
  div.addEventListener('mousedown',e=>{ e.preventDefault(); WS.classList.add('ws-dragging');
    const move=ev=>{ const r=wrap.getBoundingClientRect();
      let ratio = node.dir==='row' ? (ev.clientX-r.left)/r.width : (ev.clientY-r.top)/r.height;
      ratio=Math.max(0.12,Math.min(0.88,ratio)); node.ratio=ratio; aEl.style.flex='0 0 '+(ratio*100)+'%'; };
    const up=()=>{ document.removeEventListener('mousemove',move); document.removeEventListener('mouseup',up); WS.classList.remove('ws-dragging'); save(); };
    document.addEventListener('mousemove',move); document.addEventListener('mouseup',up);
  });
}
function rerender(){ WS.innerHTML=''; WS.appendChild(renderNode(root)); save(); }

// toolbar
document.getElementById('ws-add').onclick=()=>{ // split the first leaf we find, rightward
  let n=root; while(n.type==='split') n=n.a; splitLeaf(n,'row'); };
document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>{ root=PRESETS[b.dataset.preset](); rerender(); });
rerender();
</script>
<script src="/static/js/concierge.js"></script>
</body></html>"""
