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
    '#mc-in{flex:1;background:var(--tint,rgba(255,255,255,.06));color:var(--txt,#eee);border:1px solid var(--sep-2,rgba(255,255,255,.14));border-radius:8px;padding:8px;outline:none;font:inherit}',
    '#mc-send{background:var(--accent,#0a84ff);color:#fff;border:none;border-radius:8px;padding:8px 14px;cursor:pointer;font:inherit}'
  ].join('\n');
  document.head.appendChild(style);

  var launch = document.createElement('button');
  launch.id = 'mc-launch'; launch.title = 'Setup assistant';
  launch.innerHTML = '💬 Setup help';
  var panel = document.createElement('div');
  panel.id = 'mc-panel';
  panel.innerHTML = '<div id="mc-head"><b>✦ Setup assistant</b><button id="mc-min" title="Minimize">—</button><button id="mc-close" title="Close">✕</button></div>'
    + '<div id="mc-log"></div>'
    + '<div id="mc-foot"><input id="mc-in" placeholder="Tell me what you want…"><button id="mc-send">Send</button></div>';
  document.body.appendChild(launch);
  document.body.appendChild(panel);
  var log = panel.querySelector('#mc-log'), inp = panel.querySelector('#mc-in');

  function bubble(role, text) {
    var b = document.createElement('div');
    b.className = 'mc-b ' + (role === 'user' ? 'mc-u' : 'mc-a');
    b.textContent = text; log.appendChild(b); log.scrollTop = log.scrollHeight;
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
  function openP() { panel.style.display = 'flex'; launch.style.display = 'none'; try { localStorage.removeItem(CLOSED); } catch (e) {} render(); if (!started && !busy) kickoff(); }
  function minP() { panel.style.display = 'none'; launch.style.display = 'flex'; }
  function closeP() { panel.style.display = 'none'; launch.style.display = 'none'; try { localStorage.setItem(CLOSED, '1'); } catch (e) {} }
  panel.querySelector('#mc-min').onclick = minP;
  panel.querySelector('#mc-close').onclick = closeP;
  launch.onclick = openP;

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
      if (t === 'open_concierge') { location.href = '/app/setup'; return 'sent the user to the setup picker'; }
      return 'unknown action ' + t;
    } catch (e) { return 'action error: ' + e; }
  }

  async function turn(steps) {
    if (steps <= 0) { note('Paused — say "continue".'); return; }
    var r;
    try { r = await J('/api/setup/assistant', { method: 'POST', body: JSON.stringify({ messages: ASST }) }); }
    catch (e) { bubble('assistant', 'I could not reach the guide AI — try again in a moment.'); return; }
    if (r && r.need_model) { bubble('assistant', 'Pick a guide AI in Setup first — taking you there.'); setTimeout(function () { location.href = '/app/setup'; }, 1200); return; }
    if (!r || !r.ok) { bubble('assistant', (r && r.detail) || 'Something went wrong — let\'s try again.'); return; }
    if (r.reply) { ASST.push({ role: 'assistant', content: r.reply }); bubble('assistant', r.reply); save(); }
    if (r.action && r.action.type) {
      if (r.action.type === 'done') { note('✓ Setup complete'); bubble('assistant', 'You\'re all set 🎉 — open Chat whenever you like. I\'m here if you want to change anything.'); save(); return; }
      note('doing: ' + r.action.type + (r.action.args && r.action.args.model ? (' (' + r.action.args.model + ')') : ''));
      var result = await act(r.action); waiting = false;
      note('result: ' + String(result).slice(0, 120));
      ASST.push({ role: 'user', content: '[action result] ' + r.action.type + ': ' + result }); save();
      await turn(steps - 1);
    }
  }
  function work(on) { try { panel.classList.toggle('mc-working', !!on); } catch (e) {} }
  async function kickoff() { if (started || busy) return; started = true; busy = true; work(1); try { await turn(6); } finally { busy = false; work(0); } }
  async function send() {
    var text = (inp.value || '').trim(); if (!text) return; inp.value = '';
    ASST.push({ role: 'user', content: text }); bubble('user', text); save();
    if (waiting) return; // captured as context during a long task — don't start a turn
    if (busy) return; busy = true; work(1); try { await turn(6); } finally { busy = false; work(0); }
  }
  panel.querySelector('#mc-send').onclick = send;
  inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); send(); } });

  // Show the launcher on app pages (unless the user closed it). If there's an
  // ongoing conversation, it's clearly continuable from here.
  var wasClosed = false; try { wasClosed = localStorage.getItem(CLOSED) === '1'; } catch (e) {}
  launch.style.display = wasClosed ? 'none' : 'flex';
  window.Concierge = { open: openP, minimize: minP, close: closeP };
})();
