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

    return router


_HOME = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
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
 *{box-sizing:border-box} html,body{margin:0;height:100%}
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

<div class="sky" id="sky"><svg width="100%" height="100%" id="lines"></svg></div>

<div class="sec-title">Quick actions</div>
<div class="grid g3">
 <a class="card act" href="/app/setup"><span class="ic" style="color:var(--cyan)">🧭</span><div><h3>Set up</h3><div class="d">Guided AI setup.</div></div></a>
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
</script></body></html>"""


_COOKBOOK = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
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
 *{box-sizing:border-box} html,body{margin:0;height:100%}
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

<div class="sec-title">Get a model <button class="help-btn" data-topic="The 'Get a model' panel — download a model from Hugging Face to the local cache, or serve a model so it becomes a usable endpoint. Downloads only fetch files; serving loads the model into VRAM and starts an inference server.">?</button></div>
<div class="card">
  <div class="row"><span class="grow"><b style="font-size:14px">Download</b> <span class="faint" style="font-size:12px">— pull a model from Hugging Face into the local cache (files only, safe)</span></span></div>
  <div class="fld-row">
    <label><span class="lab">Hugging Face repo id</span><input id="dl-repo" class="fld" placeholder="e.g. Qwen/Qwen3-4B-GGUF"></label>
    <label style="flex:0 0 220px"><span class="lab">Include glob (optional)</span><input id="dl-include" class="fld" placeholder="*Q4_K_M*"></label>
    <button class="btn" id="dl-btn">Download</button>
  </div>
  <div id="dl-msg" class="actmsg muted"></div>
</div>
<div class="card">
  <div class="row"><span class="grow"><b style="font-size:14px">Serve</b> <span class="faint" style="font-size:12px">— start an inference server. Review the command first; it loads the model into VRAM.</span></span></div>
  <div class="fld-row">
    <label style="flex:0 0 240px"><span class="lab">Model / repo (label)</span><input id="serve-repo" class="fld" placeholder="e.g. qwen3-4b"></label>
    <label style="flex:0 0 130px"><span class="lab">GPUs (optional)</span><input id="serve-gpus" class="fld" placeholder="0  or  0,1"></label>
  </div>
  <div class="fld-row"><label><span class="lab">Command (editable — runs in a tmux session)</span><textarea id="serve-cmd" class="fld" rows="2" placeholder="ollama run qwen3:4b"></textarea></label></div>
  <div class="faint" style="font-size:11px;margin-top:6px">Examples — Ollama: <span class="mono">ollama run qwen3:4b</span> · llama.cpp: <span class="mono">llama-server -m model.gguf -ngl 99 -c 8192</span> · vLLM: <span class="mono">vllm serve Qwen/Qwen3-4B --max-num-seqs 4</span></div>
  <div class="fld-row"><button class="btn" id="serve-btn">Launch server</button></div>
  <div id="serve-msg" class="actmsg muted"></div>
</div>

<div class="sec-title">Recommended roles <button class="help-btn" data-topic="The 'Recommended roles' feature — the teacher model assigns the best available model to each role (coder, planner, vision, …)">?</button></div>
<div class="card">
  <div class="row"><span class="grow muted" style="font-size:13px">Let the teacher model pick the best model for each role (coder, planner, vision…) from what you actually have.</span>
    <button class="btn" id="rec-btn">Recommend roles</button></div>
  <div id="rec" style="margin-top:10px"></div>
</div>

<div class="sec-title">Fits this machine <button class="help-btn" data-topic="The 'Fits this machine' list — catalog models ranked against your VRAM/RAM, showing which ones can actually run locally and a fit score">?</button></div>
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
    const bcls=st==='ready'||st==='completed'?'ok':st==='error'?'err':'run';
    const pct=Math.max(0,Math.min(100,parseInt(t.progress||'0',10)||0));
    const phase=t.phase||t.status||'';
    const showBar=st==='running'||st==='downloading';
    return `<div class="item"><span class="badge ${bcls}">${esc(t.type||'task')}</span>`
      +`<span class="grow"><div class="name">${esc(t.model||t.session_id||'job')}</div>`
      +`<div class="meta">${esc(phase)}${t.tps?` · ${esc(t.tps)} tok/s`:''}${t.reqs?` · ${esc(t.reqs)} reqs`:''}${t.remote&&t.remote!=='local'?` · ${esc(t.remote)}`:''}</div>`
      +(showBar?`<div class="bar"><i style="width:${pct}%"></i></div>`:'')
      +(st==='error'&&t.error?`<div class="meta" style="color:var(--err)">${esc(t.error)}</div>`:'')
      +`</span><span class="badge ${bcls}">${esc(t.status||'')}</span></div>`;
  }).join('');
}
function pollTasks(){ j('/api/cookbook/tasks/status').then(renderTasks)
  .catch(e=>{ if(e===401) $('#tasks').innerHTML=adminNote; }); }
pollTasks(); setInterval(pollTasks,3000);

// 3) Recommend roles (on demand)
$('#rec-btn').addEventListener('click',async()=>{
  const btn=$('#rec-btn'), out=$('#rec'); btn.disabled=true; btn.textContent='Asking AI…';
  out.innerHTML='<span class="muted" style="font-size:13px">The teacher model is choosing the best model per role…</span>';
  try{
    const r=await j('/api/cookbook/recommend',{method:'POST'});
    if(!r.ok){ out.innerHTML=`<span class="muted" style="font-size:13px">${esc(r.detail||'No recommendation available.')}</span>`; }
    else{
      const recs=r.recommendations||{};
      const rows=Array.isArray(recs)
        ? recs.map(x=>[x.role,x])
        : Object.keys(recs).map(k=>[k,recs[k]]);
      out.innerHTML = rows.length? rows.map(([role,x])=>
        `<div class="rec"><span class="role">${esc(role)}</span> → <b>${esc(x.model||'')}</b>`
        +`${x.source&&x.source!=='local'?` <span class="badge">${esc(x.source)}</span>`:''}`
        +`${x.why?`<div class="why">${esc(x.why)}</div>`:''}</div>`).join('')
        : '<span class="muted" style="font-size:13px">No roles suggested.</span>';
    }
  }catch(e){ out.innerHTML=`<span class="muted" style="font-size:13px">${e===401?'Admin only.':'Recommendation failed.'}</span>`; }
  btn.disabled=false; btn.textContent='Recommend roles';
});

// 4) Fits this machine — RESERVE headroom for the OS + browser (they run
// alongside the model and use real VRAM/RAM), so we never recommend a model
// that would starve the desktop.
const VRAM_RESERVE=3, RAM_RESERVE=4;  // GB kept free for KDE Plasma + browser
function loadFits(){
  const el=$('#fits');
  const effV = HW_VRAM>0 ? Math.max(0, +(HW_VRAM-VRAM_RESERVE).toFixed(1)) : 0;
  j('/api/hwfit/models?limit=80').then(d=>{
    let ms=(d&&d.models)||[];
    if(HW_VRAM>0) ms=ms.filter(m=>{const v=+(m.vram_q4_gb||m.vram_gb||0);return v>0&&v<=effV;});
    else ms=ms.filter(m=>m.fit);
    ms=ms.slice(0,24);
    const banner = HW_VRAM>0
      ? `<div class="muted" style="font-size:12px;margin-bottom:8px">Reserving <b>~${VRAM_RESERVE} GB VRAM</b> + <b>~${RAM_RESERVE} GB RAM</b> for your desktop + browser → recommending models up to <b>~${effV} GB</b> (of ${HW_VRAM} GB).</div>`
      : '';
    if(!ms.length){ el.innerHTML=banner+'<span class="muted" style="font-size:13px">Nothing fits once desktop+browser headroom is reserved — try a smaller/quantized model, or free VRAM.</span>'; return; }
    el.innerHTML=banner+ms.map(m=>{
      const name=m.model||m.name||'?'; const v=m.vram_q4_gb||m.vram_gb;
      return `<div class="item"><span class="badge fit">fits</span>`
        +`<span class="grow"><div class="name">${esc(name)}</div>`
        +`<div class="meta">${v?`~${esc(v)} GB VRAM`:''}${m.context_length?` · ${esc(m.context_length)} ctx`:''}${m.size_gb?` · ${esc(m.size_gb)} GB`:''}</div></span>`
        +`${m.score!=null?`<span class="badge">${Math.round((m.score||0)*100)}</span>`:''}`
        +`${m.name?`<button class="btn mini" data-dl="${esc(m.name)}">Download</button>`:''}</div>`;
    }).join('');
  }).catch(e=>{ el.innerHTML = e===401?adminNote:'<span class="muted">Could not rank models.</span>'; });
}

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

// Per-item buttons: a fit row's Download prefills + runs; a cached row's Serve
// prefills the form (with a sensible default command) for review, then scrolls.
document.addEventListener('click',(e)=>{
  const dl=e.target.closest('[data-dl]');
  if(dl){ $('#dl-repo').value=dl.dataset.dl; $('#dl-repo').scrollIntoView({behavior:'smooth',block:'center'}); downloadModel(dl.dataset.dl,$('#dl-include').value); return; }
  const sv=e.target.closest('[data-serve]');
  if(sv){ const repo=sv.dataset.serve; const base=repo.split('/').pop();
    $('#serve-repo').value=base;
    $('#serve-cmd').value = sv.dataset.gguf ? ('llama-server -m '+repo+' -ngl 99 -c 8192') : ('ollama run '+base.toLowerCase());
    setMsg('serve-msg','Review the command, then "Launch server".');
    $('#serve-repo').scrollIntoView({behavior:'smooth',block:'center'}); return; }
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
</script></body></html>"""


_OFFICE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mentor — Office</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.78);--surface-2:rgba(44,44,46,0.85);--sep:rgba(255,255,255,0.08);--sep-2:rgba(255,255,255,0.14);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--ok:#30d158;--warn:#ffd60a;--err:#ff453a;--tint:rgba(255,255,255,0.04);--tint-2:rgba(255,255,255,0.06);--shadow:0 1px 0 rgba(255,255,255,0.04) inset,0 10px 30px rgba(0,0,0,0.5);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#f2f2f7;--surface:rgba(255,255,255,0.78);--surface-2:rgba(248,248,250,0.92);--sep:rgba(0,0,0,0.08);--sep-2:rgba(0,0,0,0.14);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.36);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--ok:#248a3d;--warn:#a04400;--err:#c41e3a;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.06);--shadow:0 1px 2px rgba(0,0,0,0.04),0 10px 30px rgba(0,0,0,0.06);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#ebe2cf;--surface:rgba(252,247,236,0.84);--surface-2:rgba(245,238,222,0.94);--sep:rgba(43,58,74,0.12);--sep-2:rgba(43,58,74,0.2);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--ok:#3a7f2b;--warn:#a36a00;--err:#a32d2d;--tint:rgba(43,58,74,0.04);--tint-2:rgba(43,58,74,0.07);--shadow:0 1px 0 rgba(255,255,255,0.5) inset,0 8px 22px rgba(43,58,74,0.08);}
 *{box-sizing:border-box} html,body{margin:0;height:100%}
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
j('/api/agents/capacity').then(c=>{const el=$('#cap');el.textContent=(c.concurrent?'Concurrent team':'Private — agents take turns');el.className='pill '+(c.concurrent?'ok':'warn');
  $('#room-hint').textContent=c.note+' '+c.privacy+' · team msg = a few calls (capped), DM = 1.';}).catch(()=>{});

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
j('/api/agents/models').then(d=>{const sel=$('#f-model');(d.models||[]).forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=m;sel.appendChild(o);});}).catch(()=>{});

// team list
function statusCls(s){return s==='thinking'?'thinking':s==='done'?'done':'idle';}
function loadTeam(){ j('/api/agents').then(d=>{const el=$('#team');const a=d.agents||[];
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
function roomMsg(m){
  if(m.role==='user') return `<div style="align-self:flex-end;max-width:80%;background:color-mix(in srgb,var(--accent) 18%,transparent);border:1px solid color-mix(in srgb,var(--accent) 30%,transparent);border-radius:12px 12px 4px 12px;padding:9px 12px">${esc(m.text)}</div>`;
  const team=m.role==='team';
  const av=team?'★':esc((m.agent_name||'?').slice(0,1).toUpperCase());
  const col=team?'var(--brass)':(m.color||'var(--cyan)');
  return `<div style="align-self:flex-start;max-width:88%;display:flex;gap:8px"><div class="ava" style="width:28px;height:28px;border-radius:8px;font-size:13px;background:${col}">${av}</div>`
    +`<div style="background:var(--tint);border:1px solid var(--sep);border-radius:12px 12px 12px 4px;padding:9px 12px"><div class="faint" style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">${esc(m.agent_name||'agent')}</div><div style="white-space:pre-wrap">${esc(m.text)}</div></div></div>`;
}
function renderRoom(msgs){const el=$('#room'); if(!msgs||!msgs.length){el.innerHTML='<span class="muted" style="font-size:13px">No messages yet. Say hi to your team below.</span>';return;}
  el.innerHTML=msgs.map(roomMsg).join(''); el.scrollTop=el.scrollHeight;}
let roomMsgs=[];
function loadRoom(){ j('/api/agents/room').then(d=>{roomMsgs=d.messages||[];renderRoom(roomMsgs);}).catch(()=>{}); }
loadRoom();
async function sayNow(){
  const inp=$('#say'); const text=(inp.value||'').trim(); if(!text)return;
  const target=$('#target').value||'team'; inp.value='';
  roomMsgs.push({role:'user',text:text}); renderRoom(roomMsgs);
  roomMsgs.push({role:team(target)?'team':'agent',agent_name:target==='team'?'Team':'…',text:'thinking…'}); renderRoom(roomMsgs);
  function team(t){return t==='team';}
  try{ const r=await j('/api/agents/say',{method:'POST',body:JSON.stringify({text:text,target:target})});
    roomMsgs.pop(); // drop the thinking placeholder
    if(r.ok){ (r.messages||[]).forEach(m=>{ if(m.role!=='user') roomMsgs.push(m); }); }
    else roomMsgs.push({role:'agent',agent_name:'note',text:r.detail||'failed'});
    renderRoom(roomMsgs);
  }catch(e){ roomMsgs.pop(); roomMsgs.push({role:'agent',agent_name:'note',text:'failed: '+e}); renderRoom(roomMsgs); }
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
</script></body></html>"""


_SETUP = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mentor — Set up your AI</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.78);--surface-2:rgba(44,44,46,0.85);--sep:rgba(255,255,255,0.08);--sep-2:rgba(255,255,255,0.14);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--ok:#30d158;--warn:#ffd60a;--err:#ff453a;--tint:rgba(255,255,255,0.04);--tint-2:rgba(255,255,255,0.06);--shadow:0 1px 0 rgba(255,255,255,0.04) inset,0 10px 30px rgba(0,0,0,0.5);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#f2f2f7;--surface:rgba(255,255,255,0.78);--surface-2:rgba(248,248,250,0.92);--sep:rgba(0,0,0,0.08);--sep-2:rgba(0,0,0,0.14);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.36);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--ok:#248a3d;--warn:#a04400;--err:#c41e3a;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.06);--shadow:0 1px 2px rgba(0,0,0,0.04),0 10px 30px rgba(0,0,0,0.06);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#ebe2cf;--surface:rgba(252,247,236,0.84);--surface-2:rgba(245,238,222,0.94);--sep:rgba(43,58,74,0.12);--sep-2:rgba(43,58,74,0.2);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--ok:#3a7f2b;--warn:#a36a00;--err:#a32d2d;--tint:rgba(43,58,74,0.04);--tint-2:rgba(43,58,74,0.07);--shadow:0 1px 0 rgba(255,255,255,0.5) inset,0 8px 22px rgba(43,58,74,0.08);}
 *{box-sizing:border-box} html,body{margin:0;height:100%}
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
 .nav{display:flex;align-items:center;gap:10px;margin-top:18px}
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
 ::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:var(--sep-2);border-radius:5px}
</style></head><body>
<nav class="topbar"><a class="jump" href="/app">Home</a><a class="jump" href="/">Chat</a><a class="jump" href="/app/office">Office</a><a class="jump" href="/app/code">Code</a><a class="jump" href="/app/cookbook">Cookbook</a><a class="jump" href="/manage">Admin</a>
 <div class="theme-switch"><button data-theme-set="dark">Dark</button><button data-theme-set="light">Light</button><button data-theme-set="atlas">Atlas</button></div></nav>

<div class="top"><div class="mark">Set up your AI</div><span id="stepcap" class="pill">Step 1 of 5</span></div>
<div class="tag">A calm, guided walk from nothing to a working local AI agent — we'll check your machine, pick a model that fits, serve it, and hire your first helper.</div>

<div class="steps" id="steps">
  <div class="dot" data-s="1"><span class="n">1</span><span class="lbl">Machine</span></div><span class="ln"></span>
  <div class="dot" data-s="2"><span class="n">2</span><span class="lbl">Pick model</span></div><span class="ln"></span>
  <div class="dot" data-s="3"><span class="n">3</span><span class="lbl">Serve</span></div><span class="ln"></span>
  <div class="dot" data-s="4"><span class="n">4</span><span class="lbl">Hire</span></div><span class="ln"></span>
  <div class="dot" data-s="5"><span class="n">5</span><span class="lbl">Done</span></div>
</div>

<!-- STEP 1 — This machine -->
<div class="step" data-step="1">
  <div class="card">
    <p class="why">First, let's look at what your computer can do. The two numbers that matter for running AI locally are <b>VRAM</b> (memory on your graphics card — this decides how big a model can be) and <b>RAM</b> (your computer's main memory).</p>
    <div id="hw" class="hw-grid"><div class="muted">reading your hardware…</div></div>
  </div>
  <div class="nav"><span class="grow"></span><button class="btn primary" id="s1-next" disabled>Next →</button></div>
</div>

<!-- STEP 2 — Pick a model that fits -->
<div class="step" data-step="2">
  <div class="card">
    <p class="why">Now pick the AI model to run. We only show models that will fit <b>with room to spare</b>, so your desktop and browser keep running smoothly. A bigger model is usually smarter but needs more memory.</p>
    <div id="fit-banner" class="muted" style="font-size:12px;margin-bottom:10px"></div>
    <div id="models" class="muted">finding models that fit…</div>
  </div>
  <div class="nav"><button class="btn" id="s2-back">← Back</button><span class="grow"></span><button class="btn primary" id="s2-next" disabled>Next →</button></div>
</div>

<!-- STEP 3 — Serve it -->
<div class="step" data-step="3">
  <div class="card">
    <p class="why">Let's start your model so the app can talk to it. This loads it into your graphics card and keeps it running in the background. It can take a minute the first time.</p>
    <div id="serve-pick" class="muted" style="font-size:13px;margin-bottom:10px"></div>
    <label class="lab">Command we'll run (you can leave this as-is)</label>
    <textarea id="serve-cmd" class="fld" rows="2"></textarea>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="serve-btn">Serve this model</button><button class="btn mini" id="serve-skip">Skip — already running</button></div>
    <div id="serve-msg" class="actmsg muted"></div>
    <div id="serve-tasks" style="margin-top:12px"></div>
  </div>
  <div class="nav"><button class="btn" id="s3-back">← Back</button><span class="grow"></span><button class="btn primary" id="s3-next" disabled>Next →</button></div>
</div>

<!-- STEP 4 — Hire a starter agent -->
<div class="step" data-step="4">
  <div class="card">
    <p class="why">Last step: hire your first helper. We've filled in a friendly, general-purpose assistant named <b>Iris</b> — she can search the web and read pages, and she'll ask before doing anything risky. Adjust if you like, then hire.</p>
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
  <div class="nav"><button class="btn" id="s4-back">← Back</button><span class="grow"></span><button class="btn primary" id="s4-next" disabled>Next →</button></div>
</div>

<!-- STEP 5 — Done -->
<div class="step" data-step="5">
  <div class="card">
    <div class="done-hero">
      <div class="big">🎉</div>
      <h2 style="margin:0 0 6px;font-weight:600;letter-spacing:-0.01em">You're set up</h2>
      <p class="why" id="done-summary" style="margin:0 auto;max-width:460px">Your machine is ready, a model is serving, and your first helper has been hired. Meet your team in the Office, or head back to the dashboard.</p>
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
let STEP=1; const LAST=5;
let HW_VRAM=0, HW_RAM=0, HAS_GPU=false;
let CHOSEN=null;          // {name, repo, vram}
let SERVED=false, HIRED=false;
const VRAM_RESERVE=3, RAM_RESERVE=4;  // GB kept free for desktop + browser

function showStep(n){
  STEP=Math.max(1,Math.min(LAST,n));
  document.querySelectorAll('.step').forEach(el=>el.classList.toggle('active',+el.dataset.step===STEP));
  $('#stepcap').textContent='Step '+STEP+' of '+LAST;
  document.querySelectorAll('#steps .dot').forEach(d=>{const s=+d.dataset.s;
    d.classList.toggle('on',s===STEP); d.classList.toggle('done',s<STEP);});
  if(STEP===3) ensureServeCmd();
}

// ── STEP 1: hardware ────────────────────────────────────────────────────────
j('/api/hwfit/system').then(s=>{
  HAS_GPU=!!s.has_gpu; HW_VRAM=+(s.gpu_vram_gb||0); HW_RAM=+(s.available_ram_gb||0);
  const cell=(k,v,sub)=>`<div class="hw"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div>${sub?`<div class="s">${esc(sub)}</div>`:''}</div>`;
  $('#hw').innerHTML=
    cell('GPU', s.has_gpu?(s.gpu_name||'—'):'None', s.has_gpu?`${s.gpu_count||1}× · ${s.backend||''}`:'CPU inference')+
    cell('VRAM', s.gpu_vram_gb?`${s.gpu_vram_gb} GB`:'—', s.unified_memory?'unified memory':'')+
    cell('RAM', `${s.available_ram_gb||'?'} GB free`, `of ${s.total_ram_gb||'?'} GB`);
  $('#s1-next').disabled=false;
}).catch(e=>{ $('#hw').innerHTML = e===401?adminNote:'<span class="muted">Could not read your hardware. You can still continue.</span>'; $('#s1-next').disabled=false; });

// ── STEP 2: pick a model that fits (headroom rule) ──────────────────────────
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
    if(!ms.length){ el.innerHTML='<span class="muted" style="font-size:13px">Nothing fits once desktop + browser headroom is reserved. Open the Cookbook to try a smaller or more-quantized model.</span>'; return; }
    el.innerHTML=ms.map((m,i)=>{
      const name=m.model||m.name||'?'; const v=m.vram_q4_gb||m.vram_gb;
      return `<div class="opt" data-i="${i}"><span class="rd"></span>`
        +`<span class="grow"><div class="name">${esc(name)}</div>`
        +`<div class="meta">${v?`~${esc(v)} GB VRAM`:''}${m.context_length?` · ${esc(m.context_length)} ctx`:''}${m.size_gb?` · ${esc(m.size_gb)} GB`:''}</div></span>`
        +`<span class="badge fit">fits</span></div>`;
    }).join('');
    el.querySelectorAll('.opt').forEach(o=>o.onclick=()=>{
      const m=ms[+o.dataset.i];
      el.querySelectorAll('.opt').forEach(x=>x.classList.remove('on'));
      o.classList.add('on');
      CHOSEN={ name:(m.model||m.name||''), repo:(m.name||m.model||''), vram:(m.vram_q4_gb||m.vram_gb||0) };
      $('#s2-next').disabled=false;
      modelCmdDirty=false;  // a fresh pick re-derives the serve command
    });
  }).catch(e=>{ $('#models').innerHTML = e===401?adminNote:'<span class="muted">Could not rank models. You can still continue and serve one in the Cookbook.</span>'; });
}

// ── STEP 3: serve it ────────────────────────────────────────────────────────
let modelCmdDirty=false;
$('#serve-cmd').addEventListener('input',()=>{ modelCmdDirty=true; });
function baseName(s){ return String(s||'').split('/').pop().toLowerCase(); }
function ensureServeCmd(){
  if(!CHOSEN){ $('#serve-pick').textContent='No model chosen — go back a step, or skip if one is already running.'; return; }
  $('#serve-pick').innerHTML='Chosen model: <b>'+esc(CHOSEN.name)+'</b>'+(CHOSEN.vram?` · ~${esc(CHOSEN.vram)} GB VRAM`:'');
  if(!modelCmdDirty) $('#serve-cmd').value='ollama run '+baseName(CHOSEN.name);
}
function setMsg(id,text,kind){ const el=$('#'+id); if(!el)return; el.textContent=text||'';
  el.style.color = kind==='err'?'var(--err)':kind==='ok'?'var(--ok)':'var(--dim)'; }
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
    if(ready){ SERVED=true; $('#s3-next').disabled=false;
      setMsg('serve-msg','Your model is up and running.','ok'); }
  }).catch(()=>{}); }
$('#serve-btn').onclick=async()=>{
  const cmd=($('#serve-cmd').value||'').trim();
  if(!cmd){ setMsg('serve-msg','Nothing to run — go back and pick a model, or skip.','err'); return; }
  const repo = CHOSEN ? (CHOSEN.repo||CHOSEN.name) : cmd;
  setMsg('serve-msg','Starting your model…');
  $('#serve-btn').disabled=true;
  try{
    const r=await j('/api/model/serve',{method:'POST',body:JSON.stringify({repo_id:repo, cmd:cmd, platform:'linux'})});
    if(r.ok){ setMsg('serve-msg','Starting up — watch the progress below.','ok');
      if(!pollTimer){ pollTasks(); pollTimer=setInterval(pollTasks,3000); }
      // allow continuing once launched (it keeps running in the background)
      $('#s3-next').disabled=false;
    } else { setMsg('serve-msg', r.error||r.detail||'Could not start the model.','err'); $('#serve-btn').disabled=false; }
  }catch(e){ setMsg('serve-msg', e===401?'Admin only.':'Could not start the model.','err'); $('#serve-btn').disabled=false; }
};
$('#serve-skip').onclick=()=>{ SERVED=true; $('#s3-next').disabled=false; setMsg('serve-msg','Skipped — assuming a model is already running.','ok'); };

// ── STEP 4: hire a starter agent ────────────────────────────────────────────
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
      $('#hire-btn').textContent='Hired'; $('#s4-next').disabled=false;
      $('#done-summary').textContent='Your machine is ready, a model is serving, and '+name+' has been hired. Meet your team in the Office, or head back to the dashboard.';
    } else { $('#hire-msg').textContent=r.detail||'Could not hire.'; $('#hire-msg').style.color='var(--err)'; $('#hire-btn').disabled=false; }
  }catch(e){ $('#hire-msg').textContent = e===401?'Admin only.':'Could not hire.'; $('#hire-msg').style.color='var(--err)'; $('#hire-btn').disabled=false; }
};

// ── navigation ──────────────────────────────────────────────────────────────
$('#s1-next').onclick=()=>{ loadModels(); showStep(2); };
$('#s2-back').onclick=()=>showStep(1);
$('#s2-next').onclick=()=>showStep(3);
$('#s3-back').onclick=()=>showStep(2);
$('#s3-next').onclick=()=>showStep(4);
$('#s4-back').onclick=()=>showStep(3);
$('#s4-next').onclick=()=>showStep(5);

showStep(1);
</script></body></html>"""


_CODE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mentor — Code</title>
<style>
 :root,[data-theme="dark"]{--bg:#000;--bg-2:#0a0a0c;--surface:rgba(28,28,30,0.78);--surface-2:rgba(44,44,46,0.85);--sep:rgba(255,255,255,0.08);--sep-2:rgba(255,255,255,0.14);--txt:rgba(255,255,255,0.96);--dim:rgba(255,255,255,0.58);--faint:rgba(255,255,255,0.36);--brass:#e0a95e;--cyan:#64d2ff;--accent:#0a84ff;--ok:#30d158;--warn:#ffd60a;--err:#ff453a;--tint:rgba(255,255,255,0.04);--tint-2:rgba(255,255,255,0.06);--shadow:0 1px 0 rgba(255,255,255,0.04) inset,0 10px 30px rgba(0,0,0,0.5);}
 [data-theme="light"]{--bg:#fbfbfd;--bg-2:#f2f2f7;--surface:rgba(255,255,255,0.78);--surface-2:rgba(248,248,250,0.92);--sep:rgba(0,0,0,0.08);--sep-2:rgba(0,0,0,0.14);--txt:#1d1d1f;--dim:rgba(60,60,67,0.6);--faint:rgba(60,60,67,0.36);--brass:#b8843a;--cyan:#0a83af;--accent:#0071e3;--ok:#248a3d;--warn:#a04400;--err:#c41e3a;--tint:rgba(0,0,0,0.04);--tint-2:rgba(0,0,0,0.06);--shadow:0 1px 2px rgba(0,0,0,0.04),0 10px 30px rgba(0,0,0,0.06);}
 [data-theme="atlas"]{--bg:#f4ede0;--bg-2:#ebe2cf;--surface:rgba(252,247,236,0.84);--surface-2:rgba(245,238,222,0.94);--sep:rgba(43,58,74,0.12);--sep-2:rgba(43,58,74,0.2);--txt:#1f2d3d;--dim:rgba(31,45,61,0.64);--faint:rgba(31,45,61,0.4);--brass:#9b6826;--cyan:#1f5471;--accent:#9b6826;--ok:#3a7f2b;--warn:#a36a00;--err:#a32d2d;--tint:rgba(43,58,74,0.04);--tint-2:rgba(43,58,74,0.07);--shadow:0 1px 0 rgba(255,255,255,0.5) inset,0 8px 22px rgba(43,58,74,0.08);}
 *{box-sizing:border-box} html,body{margin:0;height:100%}
 body{background:radial-gradient(120% 80% at 50% -10%,var(--bg-2),var(--bg)) fixed;color:var(--txt);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased;padding:56px 32px 80px;max-width:1000px;margin:0 auto;letter-spacing:-0.005em}
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:16px;margin-bottom:4px}
 .mark{font:300 38px/1.05 -apple-system,"SF Pro Display",Inter,system-ui,sans-serif;letter-spacing:-0.04em}
 .tag{color:var(--faint);font-size:13px;margin-bottom:24px}
 .pill{font:500 11px/1.2 inherit;padding:4px 10px;border-radius:99px;background:var(--tint-2);border:1px solid var(--sep);color:var(--dim);display:inline-flex;align-items:center;gap:5px}
 .pill.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
 .pill.warn{color:var(--warn);background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}
 .sec-title{color:var(--faint);font-size:11px;letter-spacing:1.5px;margin:26px 0 10px;text-transform:uppercase;font-weight:600}
 .card{background:var(--surface);border:1px solid var(--sep);border-radius:14px;padding:18px 20px;backdrop-filter:blur(24px) saturate(140%);-webkit-backdrop-filter:blur(24px) saturate(140%);box-shadow:var(--shadow);margin-bottom:14px}
 .row{display:flex;align-items:center;gap:10px} .grow{flex:1;min-width:0} .muted{color:var(--dim)} .faint{color:var(--faint)}
 .btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:10px;cursor:pointer;background:var(--surface-2);border:1px solid var(--sep-2);color:var(--txt);font:500 13px/1 inherit;transition:background .15s,border-color .15s,transform .12s}
 .btn:hover{background:var(--tint-2);border-color:var(--brass);transform:translateY(-1px)} .btn:disabled{opacity:.5;cursor:default;transform:none}
 input.fld,textarea.fld{width:100%;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:9px;padding:9px 11px;font:13px/1.4 inherit;outline:none}
 input.fld:focus,textarea.fld:focus{border-color:var(--brass)}
 textarea.fld{font-family:inherit;resize:vertical}
 label.lab{display:block;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px}
 pre.diff{white-space:pre-wrap;font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12px;background:var(--tint);border:1px solid var(--sep);border-radius:10px;padding:12px 14px;max-height:420px;overflow:auto;margin-top:8px}
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
<div class="tag">Vibe-code a real repository — describe a change, the AI edits files on a branch and shows you the diff. Nothing is committed; you review first. Free &amp; private with a local coder model.</div>

<div id="setup"></div>

<div class="sec-title">Make a change</div>
<div class="card">
  <label class="lab">What should change?</label>
  <textarea id="instr" class="fld" rows="3" placeholder="e.g. add a /api/health endpoint that returns {ok:true, version:...}"></textarea>
  <label class="lab">Files to focus on (optional — leave blank and the AI picks)</label>
  <input id="files" class="fld" placeholder="src/app.py routes/health.py">
  <div class="row" style="margin-top:10px"><button class="btn" id="run-btn">Vibe-code it</button><span id="run-msg" class="muted" style="font-size:12px"></span></div>
  <div id="result"></div>
</div>

<script nonce="{{CSP_NONCE}}">
(function(){const s=localStorage.getItem('ody-theme')||'dark';document.documentElement.setAttribute('data-theme',s);
 document.querySelectorAll('[data-theme-set]').forEach(b=>{if(b.dataset.themeSet===s)b.setAttribute('aria-current','true');
  b.addEventListener('click',()=>{const t=b.dataset.themeSet;document.documentElement.setAttribute('data-theme',t);localStorage.setItem('ody-theme',t);document.querySelectorAll('[data-theme-set]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','true');});});})();
const $=s=>document.querySelector(s);
const j=(u,o)=>fetch(u,Object.assign({credentials:'same-origin',headers:{'Content-Type':'application/json'}},o)).then(r=>{if(!r.ok)throw r.status;return r.json();});
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

let aiderReady=false;
async function loadSetup(){
  const el=$('#setup'); let st={};
  try{ st=await j('/api/manage/install-aider/status'); }catch(e){ el.innerHTML='<div class="card">'+(e===401?'Admin only.':'Could not check Aider.')+'</div>'; return; }
  aiderReady=!!st.installed;
  $('#aider-pill').textContent=aiderReady?'Aider ready':'Aider not installed'; $('#aider-pill').className='pill '+(aiderReady?'ok':'warn');
  // project path (from plugin settings, if present)
  let project='';
  try{ const ps=await j('/api/manage/plugin-settings'); const rows=(ps.settings||{}).aider_code||[]; const p=rows.find(r=>r.key==='aider_code_project'); project=p&&p.current||''; }catch(e){}
  el.innerHTML='<div class="sec-title">Project &amp; engine</div><div class="card">'
    +(aiderReady?'':'<div class="row" style="margin-bottom:10px"><span class="pill warn">setup</span><span class="grow">Aider (the code editor engine) isn\'t installed yet. It installs isolated — it never touches Mentor\'s own environment.</span><button class="btn" id="inst-btn">Install Aider</button></div><div id="inst-msg" class="muted" style="font-size:12px;margin-bottom:8px"></div>')
    +'<label class="lab">Repository path (the repo Aider may edit)</label>'
    +'<div class="row"><input id="proj" class="fld" style="flex:1" placeholder="/home/you/myrepo" value="'+esc(project)+'"><button class="btn" id="proj-save">Save</button></div>'
    +'<div class="faint" style="font-size:11px;margin-top:6px">Edits happen on a feature branch (never main). If "Vibe-code it" says the plugin is off, enable <b>aider_code</b> in Admin → Plugins, then restart.</div></div>';
  const ib=$('#inst-btn'); if(ib) ib.onclick=installAider;
  $('#proj-save').onclick=async()=>{ const v=$('#proj').value.trim(); const m=$('#proj-save'); m.textContent='…'; try{ await j('/api/manage/setting',{method:'POST',body:JSON.stringify({key:'aider_code_project',value:v})}); m.textContent='Saved'; }catch(e){ m.textContent='failed'; } setTimeout(()=>m.textContent='Save',1500); };
}
async function installAider(){
  const msg=$('#inst-msg'); const b=$('#inst-btn'); if(b)b.disabled=true; msg.textContent='Installing (isolated — can take a few minutes)…';
  try{ await j('/api/manage/install-aider',{method:'POST'}); }catch(e){ msg.textContent='could not start install: '+e; return; }
  const poll=setInterval(async()=>{ try{ const s=await j('/api/manage/install-aider/status'); if(s.installed){ clearInterval(poll); msg.textContent='Installed ✓'; loadSetup(); } else if(s.status==='failed'){ clearInterval(poll); msg.textContent='Install failed — see Admin → Vibe-code for the log.'; if(b)b.disabled=false; } else { msg.textContent='Installing… ('+(s.status||'working')+')'; } }catch(e){} }, 3000);
}
loadSetup();

$('#run-btn').onclick=async()=>{
  const instr=$('#instr').value.trim(); const files=$('#files').value.trim().split(/\s+/).filter(Boolean);
  const msg=$('#run-msg'), out=$('#result');
  if(!instr){ msg.textContent='Describe the change first.'; return; }
  if(!aiderReady){ msg.textContent='Install Aider first (above).'; return; }
  msg.textContent='Editing… with a local 30B coder this takes 2–5 min.'; out.innerHTML='';
  let r; try{ r=await j('/api/plugins/aider_code/edit',{method:'POST',body:JSON.stringify({instruction:instr,files:files})}); }
  catch(e){ msg.textContent = e===404 ? 'The aider_code plugin is off — enable it in Admin → Plugins, then restart.' : ('failed: '+e); return; }
  if(!r.ok && r.error){ msg.textContent=r.error; return; }
  const id=r.job_id||r.id; if(!id){ msg.textContent='no job id'; return; }
  const poll=setInterval(async()=>{
    let job; try{ job=await j('/api/plugins/aider_code/jobs/'+id); }catch(e){ return; }
    if(job.stage) msg.textContent=job.stage;
    if(job.done||job.result){ clearInterval(poll); const res=job.result||job; msg.textContent=res.msg||'Done — review the diff (nothing committed).';
      out.innerHTML='<div class="sec-title">Git diff (not committed)</div><pre class="diff">'+esc(res.diff||'(no diff)')+'</pre>'; }
  }, 2500);
};
</script></body></html>"""
