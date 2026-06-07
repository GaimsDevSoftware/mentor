"""app_routes — the start of our own front-end ("Celestial Terminal").

A modern, calm dashboard served at /app: your private AI fleet as a constellation,
system health at a glance, model sources, and big clear entry points. It consumes
the JSON APIs we already built; it's the foundation we grow the wrapper app from.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.auth_helpers import require_user


def setup_app_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/app")
    async def app_home(_user: str = Depends(require_user)) -> HTMLResponse:
        return HTMLResponse(_HOME)

    return router


_HOME = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Odysseus</title>
<style>
 :root{--void:#0B0E14;--void2:#080A0F;--surface:#11161F;--raised:#161D29;--line:#1F2733;
   --hair:#28323F;--txt:#F2F4F8;--dim:#9AA4B2;--faint:#5C6677;
   --brass:#E0A95E;--cyan:#5BB6C9;--ok:#6FCF97;--warn:#E0A95E;--err:#E06C75}
 *{box-sizing:border-box} html,body{margin:0;height:100%}
 body{background:radial-gradient(120% 90% at 50% -10%,#0d1118,var(--void2));color:var(--txt);
   font:15px/1.6 ui-sans-serif,system-ui,Inter,sans-serif;padding:32px;max-width:1100px;margin:0 auto}
 a{color:inherit;text-decoration:none}
 .top{display:flex;align-items:baseline;gap:14px;margin-bottom:4px}
 .mark{font-weight:200;letter-spacing:7px;font-size:30px}
 .pill{font-size:11px;padding:3px 10px;border-radius:99px;border:1px solid var(--line);color:var(--dim)}
 .pill.ok{color:var(--ok);border-color:#244} .pill.warn{color:var(--warn)} .pill.err{color:var(--err);border-color:#522}
 .tag{color:var(--faint);font-size:12px;letter-spacing:1px;margin-bottom:24px}
 .grid{display:grid;gap:14px} .g3{grid-template-columns:repeat(3,1fr)} .g2{grid-template-columns:repeat(2,1fr)}
 @media(max-width:760px){.g3,.g2{grid-template-columns:1fr}}
 .card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px}
 .card h3{margin:0 0 4px;font-weight:500;font-size:14px;letter-spacing:.3px}
 .card .d{color:var(--dim);font-size:13px}
 .act{display:flex;align-items:center;gap:12px;transition:border-color .15s}
 .act:hover{border-color:var(--cyan)} .act .ic{font-size:20px;width:28px;text-align:center}
 .sky{position:relative;height:150px;border:1px solid var(--line);border-radius:12px;
   background:linear-gradient(180deg,#0c1019,#0a0d14);overflow:hidden;margin-bottom:14px}
 .node{position:absolute;text-align:center;transform:translate(-50%,-50%)}
 .star{width:12px;height:12px;border-radius:50%;margin:0 auto 4px;box-shadow:0 0 14px 3px currentColor}
 .node small{color:var(--dim);font-size:11px;white-space:nowrap}
 .sec-title{color:var(--faint);font-size:12px;letter-spacing:2px;margin:22px 0 10px;text-transform:uppercase}
 .chip{display:inline-block;font-size:12px;color:var(--dim);border:1px solid var(--line);
   border-radius:6px;padding:3px 8px;margin:0 6px 6px 0;font-family:ui-monospace,monospace}
 .chip.rem{border-color:#2a3a44;color:var(--cyan)}
 svg line{stroke:var(--brass);stroke-opacity:.5} svg circle{fill:var(--faint)}
</style></head><body>
<div class="top"><div class="mark">ODYSSEUS</div><span id="health" class="pill">checking…</span></div>
<div class="tag">YOUR PRIVATE AI — LOCAL-FIRST · BY THE STARS, TOWARD HOME</div>

<div class="sky" id="sky"><svg width="100%" height="100%" id="lines"></svg></div>

<div class="sec-title">Do</div>
<div class="grid g3">
 <a class="card act" href="/"><span class="ic" style="color:var(--cyan)">✦</span><div><h3>Chat &amp; Agents</h3><div class="d">Talk, and let it act.</div></div></a>
 <a class="card act" href="/manage"><span class="ic" style="color:var(--brass)">⌘</span><div><h3>Plugins &amp; Diagnostics</h3><div class="d">Manage, fix, configure.</div></div></a>
 <a class="card act" href="/#research"><span class="ic" style="color:var(--cyan)">◎</span><div><h3>Deep Research</h3><div class="d">Gather &amp; synthesize.</div></div></a>
 <a class="card act" href="/#memory"><span class="ic" style="color:var(--brass)">✶</span><div><h3>Memory</h3><div class="d">What it remembers.</div></div></a>
 <a class="card act" href="/#cookbook"><span class="ic" style="color:var(--cyan)">▦</span><div><h3>Cookbook</h3><div class="d">Scan &amp; serve models.</div></div></a>
 <a class="card act" href="/manage"><span class="ic" style="color:var(--brass)">⚙</span><div><h3>Settings</h3><div class="d">Tune the system.</div></div></a>
</div>

<div class="sec-title">Models available</div>
<div id="models" class="d" style="color:var(--dim)">loading…</div>

<script>
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
// model sources
j('/api/cookbook/sources').then(d=>{const el=document.getElementById('models');el.innerHTML='';
  (d.sections||[]).forEach(s=>{if(!s.count)return;
    el.innerHTML+=`<div style="margin-bottom:10px"><b style="font-size:13px">${s.name}</b> <span class="${s.remote?'':''}" style="color:var(--faint)">${s.remote?'(cloud)':'(local)'}</span><br>`+
      (s.models||[]).slice(0,18).map(m=>`<span class="chip ${s.remote?'rem':''}">${m.model||m}</span>`).join('')+'</div>';});
  if(!el.innerHTML)el.textContent='No models yet — open the Cookbook to serve one, or log in to a source in Plugins.';
}).catch(()=>{document.getElementById('models').textContent='Sign in to view models.';});
</script></body></html>"""
