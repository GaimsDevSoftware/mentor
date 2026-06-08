/* Mentor floating concierge — the setup assistant that FOLLOWS you across pages.
   Shares its conversation with the setup wizard via localStorage, so switching
   pages mid-onboarding doesn't lose the thread. Minimizable + closable + drag.
   While a long task runs (download/serve) it asks useful get-to-know questions
   so the wait is productive. Theme-aware via the page's CSS vars. */
(function () {
  if (window.__mentorConcierge) return;
  try { if (window.top !== window.self) return; } catch (e) { return; } // not inside Workspace panes / iframes
  window.__mentorConcierge = true;
  var path = (location.pathname || '').replace(/\/+$/, '');
  if (path === '/app/setup') return; // setup has its own embedded assistant (shares the same chat)

  var LS = 'mentor-asst-chat', CLOSED = 'mentor-asst-closed';
  function load() { try { return JSON.parse(localStorage.getItem(LS) || '[]') || []; } catch (e) { return []; } }
  function save() { try { localStorage.setItem(LS, JSON.stringify(ASST.slice(-40))); } catch (e) {} }
  var ASST = load();
  var busy = false, started = false, waiting = false, waitIdx = 0;

  var style = document.createElement('style');
  style.textContent = [
    '@keyframes mc-pulse{0%,100%{box-shadow:0 6px 22px rgba(0,0,0,.45),0 0 0 0 color-mix(in srgb,var(--accent,#0a84ff) 55%,transparent)}50%{box-shadow:0 6px 22px rgba(0,0,0,.45),0 0 0 10px color-mix(in srgb,var(--accent,#0a84ff) 0%,transparent)}}',
    '@keyframes mc-glow{0%,100%{box-shadow:0 14px 44px rgba(0,0,0,.55),0 0 0 1px color-mix(in srgb,var(--accent,#0a84ff) 35%,transparent),0 0 22px color-mix(in srgb,var(--accent,#0a84ff) 18%,transparent)}50%{box-shadow:0 14px 44px rgba(0,0,0,.55),0 0 0 1px color-mix(in srgb,var(--accent,#0a84ff) 55%,transparent),0 0 38px color-mix(in srgb,var(--accent,#0a84ff) 34%,transparent)}}',
    '#mc-launch{position:fixed;right:18px;bottom:18px;z-index:99998;display:flex;align-items:center;gap:8px;height:46px;padding:0 16px;border-radius:99px;background:var(--accent,#0a84ff);color:#fff;border:none;cursor:pointer;font:600 13px/1 -apple-system,system-ui,sans-serif;box-shadow:0 6px 22px rgba(0,0,0,.45);animation:mc-pulse 2.6s ease-out infinite}',
    '#mc-panel{position:fixed;right:18px;bottom:18px;z-index:99999;width:360px;max-width:92vw;height:480px;max-height:78vh;display:none;flex-direction:column;background:var(--surface,#15171c);color:var(--txt,#eee);border:1px solid var(--sep-2,rgba(255,255,255,.16));border-radius:14px;overflow:hidden;font:13px/1.45 -apple-system,system-ui,sans-serif;backdrop-filter:blur(20px);animation:mc-glow 3.4s ease-in-out infinite}',
    '#mc-panel.mc-working{animation:mc-glow 1.3s ease-in-out infinite}',
    '@keyframes mc-urgent{0%,100%{box-shadow:0 14px 44px rgba(0,0,0,.55),0 0 0 2px var(--warn,#ffd60a),0 0 14px color-mix(in srgb,var(--warn,#ffd60a) 30%,transparent)}50%{box-shadow:0 14px 44px rgba(0,0,0,.55),0 0 0 2px var(--warn,#ffd60a),0 0 44px color-mix(in srgb,var(--warn,#ffd60a) 65%,transparent)}}',
    '#mc-panel.mc-urgent{animation:mc-urgent .85s ease-in-out infinite}',
    '@keyframes mc-launch-urgent{0%,100%{box-shadow:0 6px 22px rgba(0,0,0,.45),0 0 0 0 color-mix(in srgb,var(--warn,#ffd60a) 70%,transparent)}50%{box-shadow:0 6px 22px rgba(0,0,0,.45),0 0 0 12px color-mix(in srgb,var(--warn,#ffd60a) 0%,transparent)}}',
    '#mc-launch.mc-urgent{background:var(--warn,#ffd60a);color:#000;animation:mc-launch-urgent .85s ease-out infinite}',
    '#mc-head{display:flex;align-items:center;gap:8px;padding:10px 12px;background:var(--surface-2,#1c1f26);border-bottom:1px solid var(--sep,rgba(255,255,255,.1));cursor:move;user-select:none}',
    '#mc-head b{flex:1;font-size:13px}',
    '#mc-head button{background:transparent;border:none;color:var(--dim,#aaa);cursor:pointer;font-size:16px;width:26px;height:26px;border-radius:6px;line-height:1}',
    '#mc-head button:hover{background:var(--tint-2,rgba(255,255,255,.1));color:var(--txt,#fff)}',
    '#mc-log{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px}',
    '.mc-b{max-width:88%;padding:8px 11px;border-radius:10px;white-space:pre-wrap;font-size:13px}',
    '.mc-u{align-self:flex-end;background:color-mix(in srgb,var(--accent,#0a84ff) 20%,transparent);border:1px solid color-mix(in srgb,var(--accent,#0a84ff) 34%,transparent)}',
    '.mc-a{align-self:flex-start;background:var(--tint,rgba(255,255,255,.06));border:1px solid var(--sep,rgba(255,255,255,.1))}',
    '.mc-n{align-self:center;font-size:11px;color:var(--faint,#8a8a8a)}',
    '#mc-foot{display:flex;gap:6px;padding:10px;border-top:1px solid var(--sep,rgba(255,255,255,.1))}',
    '#mc-in{flex:1;background:var(--tint,rgba(255,255,255,.06));color:var(--txt,#eee);border:1px solid var(--sep-2,rgba(255,255,255,.14));border-radius:8px;padding:8px;outline:none;font:inherit;transition:border-color .2s}',
    '#mc-in.mc-attn{border-color:var(--accent,#0a84ff);animation:mc-inattn 1.1s ease-in-out infinite}',
    '@keyframes mc-inattn{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent,#0a84ff) 0%,transparent)}50%{box-shadow:0 0 0 4px color-mix(in srgb,var(--accent,#0a84ff) 32%,transparent)}}',
    '#mc-launch.mc-attn{animation:mc-pulse 1s ease-out infinite}',
    '#mc-send{background:var(--accent,#0a84ff);color:#fff;border:none;border-radius:8px;padding:8px 14px;cursor:pointer;font:inherit}'
  ].join('\n');
  document.head.appendChild(style);

  var launch = document.createElement('button');
  launch.id = 'mc-launch'; launch.title = 'Atlas — your setup guide';
  launch.innerHTML = '✦ Atlas';
  var panel = document.createElement('div');
  panel.id = 'mc-panel';
  panel.innerHTML = '<div id="mc-head"><b>✦ Atlas</b><span id="mc-ready" style="display:none;font-size:10px;color:var(--ok,#30d158);background:color-mix(in srgb,var(--ok,#30d158) 12%,transparent);border:1px solid color-mix(in srgb,var(--ok,#30d158) 30%,transparent);border-radius:99px;padding:2px 7px;margin-left:6px" title="Open Mentor">● Mentor is ready</span><button id="mc-min" title="Minimize">—</button><button id="mc-close" title="Close">✕</button></div>'
    + '<div id="mc-log"></div>'
    + '<div id="mc-foot"><input id="mc-in" placeholder="Tell me what you want…"><button id="mc-send">Send</button></div>';
  document.body.appendChild(launch);
  document.body.appendChild(panel);
  var log = panel.querySelector('#mc-log'), inp = panel.querySelector('#mc-in');

  function bubble(role, text, thinking) {
    var b = document.createElement('div');
    b.className = 'mc-b ' + (role === 'user' ? 'mc-u' : 'mc-a');
    b.textContent = text;
    if (thinking && role === 'assistant') {
      var link = document.createElement('a');
      link.href = '#';
      link.style.cssText = 'display:block;margin-top:6px;font-size:11px;color:var(--faint,#8a8a8a);text-decoration:none;';
      link.textContent = '💭 Resonnering';
      var box = document.createElement('div');
      box.style.cssText = 'display:none;margin-top:6px;padding:8px;background:var(--tint,rgba(255,255,255,.04));border:1px solid var(--sep,rgba(255,255,255,.1));border-radius:6px;font-size:11px;max-height:160px;overflow:auto;white-space:pre-wrap;color:var(--dim,#aaa);line-height:1.45;';
      box.textContent = thinking;
      link.addEventListener('click', function(e) { e.preventDefault(); box.style.display = box.style.display === 'none' ? '' : 'none'; });
      b.appendChild(link);
      b.appendChild(box);
    }
    log.appendChild(b); log.scrollTop = log.scrollHeight;
  }
  function note(t) {
    var b = document.createElement('div'); b.className = 'mc-n'; b.textContent = '⚙ ' + t;
    log.appendChild(b); log.scrollTop = log.scrollHeight;
  }
  function render() {
    log.innerHTML = '';
    ASST.forEach(function (m) {
      if (m.role === 'assistant' || m.role === 'user') {
        var t = String(m.content || '').replace(/^\[.*?\]\s*/, '');
        if (t.indexOf('[action result]') === 0) return;
        bubble(m.role, t);
      }
    });
  }
  function openP() {
    panel.style.display = 'flex'; launch.style.display = 'none';
    try { localStorage.removeItem(CLOSED); } catch (e) {}
    // Re-surface the ready badge if we've already announced once this session.
    try {
      if (sessionStorage.getItem('mc-ready-shown') === '1') {
        var b = panel.querySelector('#mc-ready');
        if (b) { b.style.display = 'inline-block'; b.style.cursor = 'pointer'; b.onclick = function(){ window.location.href = '/'; }; }
      }
    } catch (e) {}
    render(); offerScreenContext();
    if (!started && !busy) kickoff();
  }
  function minP() { panel.style.display = 'none'; launch.style.display = 'flex'; }
  function closeP() { panel.style.display = 'none'; launch.style.display = 'none'; try { localStorage.setItem(CLOSED, '1'); } catch (e) {} }
  panel.querySelector('#mc-min').onclick = minP;
  panel.querySelector('#mc-close').onclick = closeP;
  launch.onclick = openP;

  // ── screen-share context (ASK FIRST every session) ─────────────────────────
  // Most of the time the thing the user wants help with is right there on
  // screen. Offer (once per session, opt-in) to capture a frame and feed it to
  // the vision model so the assistant has visual context for the conversation.
  var SCREEN_ASKED_KEY = 'mentor-asst-screenasked';  // sessionStorage flag
  function offerScreenContext() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) return; // no API
    try { if (sessionStorage.getItem(SCREEN_ASKED_KEY) === '1') return; } catch (e) {}
    if (log.querySelector('.mc-screenoffer')) return;
    var offer = document.createElement('div');
    offer.className = 'mc-screenoffer mc-b mc-a';
    offer.innerHTML =
      '<div style="margin-bottom:6px">📷 <b>Vil du dele skjermen?</b> Jeg får ofte mer kontekst — det du vil ha hjelp med ligger gjerne åpent allerede.</div>' +
      '<div class="muted" style="font-size:11px;margin-bottom:8px">Tips: del skjermen i to (snap Mentor til den ene siden og det du vil vise på den andre), så ser jeg begge deler i samme bilde. Du må velge skjerm hver gang; bildet brukes kun for å beskrive konteksten.</div>' +
      '<div style="display:flex;gap:6px;flex-wrap:wrap">' +
      '<button class="mc-screen-yes" style="background:var(--accent,#0a84ff);color:#fff;border:none;padding:6px 12px;border-radius:6px;font:inherit;font-size:12px;cursor:pointer">Del skjermen</button>' +
      '<button class="mc-screen-no" style="background:transparent;color:inherit;border:1px solid var(--sep-2,rgba(255,255,255,.14));padding:6px 12px;border-radius:6px;font:inherit;font-size:12px;cursor:pointer">Nei takk</button>' +
      '</div>';
    log.appendChild(offer); log.scrollTop = log.scrollHeight;
    offer.querySelector('.mc-screen-no').onclick = function () {
      try { sessionStorage.setItem(SCREEN_ASKED_KEY, '1'); } catch (e) {}
      offer.remove();
    };
    offer.querySelector('.mc-screen-yes').onclick = async function () {
      try { sessionStorage.setItem(SCREEN_ASKED_KEY, '1'); } catch (e) {}
      offer.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
      var status = document.createElement('div');
      status.className = 'mc-n'; status.textContent = 'Velg skjerm / vindu…';
      log.appendChild(status); log.scrollTop = log.scrollHeight;
      var stream = null;
      try {
        stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'monitor' }, audio: false });
      } catch (e) {
        status.textContent = 'Skjermdeling avbrutt.'; offer.remove(); return;
      }
      try {
        var v = document.createElement('video'); v.srcObject = stream;
        await new Promise(function (res) { v.onloadedmetadata = function () { v.play().then(res, res); }; });
        await new Promise(function (res) { setTimeout(res, 220); });  // ensure first frame is painted
        var w = Math.min(v.videoWidth || 1280, 1600), h = Math.round(v.videoHeight * (w / (v.videoWidth || 1280)));
        var c = document.createElement('canvas'); c.width = w; c.height = h;
        c.getContext('2d').drawImage(v, 0, 0, w, h);
        var b64 = c.toDataURL('image/png', 0.92);
        stream.getTracks().forEach(function (t) { t.stop(); });
        status.textContent = 'Analyserer skjermbildet med synsmodellen…';
        var r;
        try { r = await J('/api/setup/vision-context', { method: 'POST', body: JSON.stringify({ image_b64: b64 }) }); }
        catch (e) { status.textContent = 'Kunne ikke kontakte synsmodellen.'; offer.remove(); return; }
        if (r && r.need_vision) {
          status.textContent = 'Ingen synsmodell satt — kjør auto_roles for å fylle vision_model først.'; offer.remove(); return;
        }
        if (!r || !r.ok) {
          status.textContent = (r && r.detail) || 'Synsmodellen feilet.'; offer.remove(); return;
        }
        // Feed the description into the conversation as if the user told us.
        var msg = '[Jeg har akkurat delt skjermen min. Slik ser den ut nå:]\n' + r.description;
        ASST.push({ role: 'user', content: msg }); save();
        status.textContent = '✓ La til skjermbildet som kontekst.';
        offer.remove();
        // Nudge the assistant to USE the new context now.
        if (!busy) { busy = true; work(1); try { await turn(6); } finally { busy = false; work(0); } }
      } catch (e) {
        try { stream.getTracks().forEach(function (t) { t.stop(); }); } catch (_) {}
        status.textContent = 'Klarte ikke å lage skjermbilde: ' + e; offer.remove();
      }
    };
  }

  (function () {
    var h = panel.querySelector('#mc-head'), dx, dy, drag = false;
    h.addEventListener('mousedown', function (e) {
      drag = true; var r = panel.getBoundingClientRect(); dx = e.clientX - r.left; dy = e.clientY - r.top;
      panel.style.right = 'auto'; panel.style.bottom = 'auto'; e.preventDefault();
      function mv(ev) { if (!drag) return; panel.style.left = Math.max(0, ev.clientX - dx) + 'px'; panel.style.top = Math.max(0, ev.clientY - dy) + 'px'; }
      function up() { drag = false; document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); }
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
    });
  })();

  var J = function (u, o) { return fetch(u, Object.assign({ credentials: 'same-origin', headers: { 'Content-Type': 'application/json' } }, o)).then(function (r) { return r.json(); }); };
  function poll(url, okfn, failfn, max) {
    return new Promise(function (res) {
      var i = 0; var t = setInterval(function () {
        i++;
        J(url).then(function (s) {
          var r = okfn(s); if (r !== undefined) { clearInterval(t); res(r); return; }
          if (failfn) { var f = failfn(s); if (f) { clearInterval(t); res(f); return; } }
          if (i >= (max || 40)) { clearInterval(t); res('still running in the background'); }
        }).catch(function () { if (i >= (max || 40)) { clearInterval(t); res('still running'); } });
      }, 3000);
    });
  }
  var WAIT_Q = [
    'While that runs — what will you mainly use Mentor for? Coding, research, writing, or a bit of everything?',
    'Quick one while we wait: do you want everything private/local, or is cloud fine for the heavy lifting?',
    'Meanwhile — how technical are you? I\'ll match my explanations.',
    'While it downloads: any tools you already rely on (a specific editor, git workflow, languages)?'
  ];
  function askWaiting() {
    var q = WAIT_Q[waitIdx % WAIT_Q.length]; waitIdx++;
    ASST.push({ role: 'assistant', content: q }); bubble('assistant', q); save();
    waiting = true; // answers now feed context (no new turn) until the task finishes
  }

  async function act(a) {
    var t = a && a.type, args = (a && a.args) || {};
    try {
      if (t === 'detect_system') { var s = await J('/api/hwfit/system'); return 'GPU ' + (s.gpu_name || 'none') + ', VRAM ' + (s.gpu_vram_gb || 0) + 'GB, RAM ' + (s.available_ram_gb || '?') + 'GB, Ollama ' + (s.ollama_installed ? 'installed' : 'not installed'); }
      if (t === 'install_ollama') { var r = await J('/api/setup/install-ollama', { method: 'POST' }); if (r && r.already) return 'Ollama already installed'; askWaiting(); return await poll('/api/setup/install-ollama/status', function (s) { return s.installed ? 'Ollama installed' : undefined; }, function (s) { return s.status === 'failed' ? 'install failed' : false; }, 60); }
      if (t === 'setup_free_helper') { var r2 = await J('/api/setup/free-helper', { method: 'POST' }); if (r2 && r2.need_ollama) return 'needs Ollama first'; askWaiting(); return await poll('/api/setup/free-helper/status', function (s) { return s.status === 'done' ? 'free local helper ready' : undefined; }, function (s) { return s.status === 'failed' ? 'failed' : false; }, 120); }
      if (t === 'recommend_local') { var d = await J('/api/hwfit/models?limit=60'); var ms = ((d && d.models) || []).slice(0, 5).map(function (m) { return m.model || m.name; }); return ms.length ? ('Top fits: ' + ms.join(', ')) : 'nothing fits locally — suggest a cloud model'; }
      if (t === 'serve_local') { var model = args.model || ''; if (!model) return 'no model given'; await J('/api/model/serve', { method: 'POST', body: JSON.stringify({ repo_id: model, cmd: 'ollama run ' + String(model).split('/').pop().toLowerCase(), platform: 'linux' }) }); askWaiting(); return await poll('/api/cookbook/tasks/status', function (s) { return (((s && s.tasks) || []).some(function (x) { return ['ready', 'completed'].indexOf((x.status || '').toLowerCase()) >= 0; })) ? ('serving ' + model) : undefined; }, null, 30); }
      if (t === 'set_role') { if (!args.role || !args.spec) return 'missing role/spec'; await fetch('/api/manage/setting', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: args.role, value: args.spec }) }); return 'set ' + args.role + ' = ' + args.spec; }
      if (t === 'auto_roles') { var body = JSON.stringify({ tiers: (args.tiers || null) }); var rr = await J('/api/setup/auto-roles', { method: 'POST', body: body }); if (!rr.ok) return rr.error || 'could not auto-fill roles'; var aa = rr.assigned || {}; var fb = rr.fallbacks || {}; var nfb = 0; for (var k in fb) { nfb += (fb[k] || []).length; } return 'roles filled — ' + Object.keys(aa).map(function (k) { return k + '=' + aa[k]; }).join(', ') + (rr.vision ? ' · vision ok' : ' · no vision') + ' · ' + nfb + ' fallbacks across ' + (rr.source_count || 0) + ' source(s).' + (rr.note ? ' ' + rr.note : ''); }
      if (t === 'open_concierge') { location.href = '/app/setup'; return 'sent the user to the setup picker'; }
      if (t === 'toggle_paid_models') { var en = !!(args.enabled); await J('/api/manage/setting', { method: 'POST', body: JSON.stringify({ key: 'opencode_include_paid', value: en }) }); return en ? 'Paid API models are now VISIBLE (Claude, GPT, Gemini, Grok). They cost per request on top of any subscription.' : 'Paid API models are now HIDDEN. Only free + subscription models are shown.'; }
      return 'unknown action ' + t;
    } catch (e) { return 'action error: ' + e; }
  }

  async function turn(steps) {
    if (steps <= 0) { note('Paused — say "continue".'); return; }
    var r;
    try { r = await J('/api/setup/assistant', { method: 'POST', body: JSON.stringify({ messages: ASST }) }); }
    catch (e) { bubble('assistant', 'I could not reach the backend — try again in a moment.'); return; }
    if (r && r.need_model) { bubble('assistant', 'I need a model first — taking you to Setup.'); setTimeout(function () { location.href = '/app/setup'; }, 1200); return; }
    if (!r || !r.ok) { bubble('assistant', (r && r.detail) || 'Something went wrong — let\'s try again.'); return; }
    if (r.reply) { ASST.push({ role: 'assistant', content: r.reply }); bubble('assistant', r.reply, r.thinking || ''); save(); }
    if (r.action && r.action.type) {
      if (r.action.type === 'done') {
        // Only announce ready ONCE per session — after that, just a tiny header
        // badge so the chat doesn't fill with repeated 'You're all set' bubbles.
        var alreadyShown = false;
        try { alreadyShown = sessionStorage.getItem('mc-ready-shown') === '1'; } catch (e) {}
        var badge = panel.querySelector('#mc-ready');
        if (badge) {
          badge.style.display = 'inline-block';
          badge.style.cursor = 'pointer';
          badge.onclick = function () { window.location.href = '/'; };
        }
        if (!alreadyShown) {
          note('✓ Setup complete');
          bubble('assistant', 'You\'re all set 🎉 — open Mentor below, or keep chatting if you want to change anything.');
          var w = document.createElement('div'); w.className = 'mc-b mc-a'; w.style.padding = '8px';
          w.innerHTML = '<a href="/" style="display:inline-block;background:var(--accent,#0a84ff);color:#fff;padding:8px 14px;border-radius:8px;text-decoration:none;font-weight:600">Open Mentor →</a>';
          log.appendChild(w); log.scrollTop = log.scrollHeight;
          try { sessionStorage.setItem('mc-ready-shown', '1'); } catch (e) {}
        }
        save(); return;
      }
      note('doing: ' + r.action.type + (r.action.args && r.action.args.model ? (' (' + r.action.args.model + ')') : ''));
      var result = await act(r.action); waiting = false;
      note('result: ' + String(result).slice(0, 120));
      if (['auto_roles', 'set_role', 'serve_local', 'setup_free_helper'].indexOf(r.action.type) >= 0) recheckRoles();
      ASST.push({ role: 'user', content: '[action result] ' + r.action.type + ': ' + result }); save();
      await turn(steps - 1);
    } else {
      attn(true); // assistant asked something / is waiting — glow for the user's turn
    }
  }
  function work(on) { try { panel.classList.toggle('mc-working', !!on); } catch (e) {} }
  function attn(on) { try { inp.classList.toggle('mc-attn', !!on); launch.classList.toggle('mc-attn', !!on); } catch (e) {} }
  function urgent(on) { try { panel.classList.toggle('mc-urgent', !!on); launch.classList.toggle('mc-urgent', !!on); launch.innerHTML = on ? '⚠ Atlas' : '✦ Atlas'; } catch (e) {} }
  function recheckRoles() { J('/api/setup/role-status').then(function (s) { if (s && !s.critical_missing) urgent(false); }).catch(function () {}); }
  async function kickoff() { if (started || busy) return; started = true; busy = true; work(1); try { await turn(6); } finally { busy = false; work(0); } }
  async function send() {
    attn(false);
    var text = (inp.value || '').trim(); if (!text) return; inp.value = '';
    ASST.push({ role: 'user', content: text }); bubble('user', text); save();
    if (waiting) return; // captured as context during a long task — don't start a turn
    if (busy) return; busy = true; work(1); try { await turn(6); } finally { busy = false; work(0); }
  }
  panel.querySelector('#mc-send').onclick = send;
  inp.addEventListener('focus', function () { attn(false); });
  inp.addEventListener('keydown', function (e) { attn(false); if (e.key === 'Enter') { e.preventDefault(); send(); } });

  // Show the launcher on app pages (unless the user closed it). If there's an
  // ongoing conversation, it's clearly continuable from here.
  var wasClosed = false; try { wasClosed = localStorage.getItem(CLOSED) === '1'; } catch (e) {}
  launch.style.display = wasClosed ? 'none' : 'flex';
  window.Concierge = { open: openP, minimize: minP, close: closeP };
  // Proactively raise unfilled important roles (default / vision-for-images): if
  // any are missing, glow urgently and open so the assistant can ask how to fill.
  if (!wasClosed) {
    J('/api/setup/role-status').then(function (s) { if (s && s.critical_missing) { urgent(true); openP(); } }).catch(function () {});
  }
})();
