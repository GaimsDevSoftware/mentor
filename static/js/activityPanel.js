// ============================================================================
// activityPanel.js — always-visible "what's happening" panel for Code + Self-coder
// ----------------------------------------------------------------------------
// Polls the read-only /api/code/jobs and /api/plugins/self_coder/status surfaces
// and streams a live feed of what the background agents are doing: stage, raw
// terminal/Aider output tail, and status — so you always know whether anything
// is happening, without opening each job's log. Read-only; never mutates state.
// ============================================================================

const POLL_IDLE = 4000;   // ms when nothing is running
const POLL_BUSY = 1500;   // ms when something is running
const COLLAPSE_KEY = 'odysseus-activity-collapsed';

let _panel, _body, _dot, _timer = null, _busy = false;

function _esc(s) {
  return String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}
function _ago(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return s + 's siden';
  if (s < 3600) return Math.round(s / 60) + 'm siden';
  return Math.round(s / 3600) + 't siden';
}
async function _get(url) {
  try {
    const r = await fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function _build() {
  _panel = document.createElement('div');
  _panel.id = 'activity-panel';
  _panel.style.cssText =
    'position:fixed;right:14px;bottom:14px;width:360px;max-width:calc(100vw - 28px);' +
    'background:var(--card,#1b1b20);color:var(--fg,#e8e8e8);border:1px solid var(--sep,#2c2c35);' +
    'border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.35);z-index:8000;font-size:12px;' +
    'overflow:hidden;font-family:ui-sans-serif,system-ui,sans-serif';

  const head = document.createElement('div');
  head.style.cssText =
    'display:flex;align-items:center;gap:8px;padding:8px 10px;cursor:pointer;' +
    'border-bottom:1px solid var(--sep,#2c2c35);user-select:none';
  _dot = document.createElement('span');
  _dot.style.cssText = 'width:8px;height:8px;border-radius:50%;background:var(--faint,#6b6b78);flex:0 0 auto';
  const title = document.createElement('b');
  title.textContent = 'Aktivitet';
  title.style.flex = '1';
  const caret = document.createElement('span');
  caret.textContent = '▾';
  caret.style.opacity = '.6';
  head.append(_dot, title, caret);

  _body = document.createElement('div');
  _body.style.cssText = 'max-height:42vh;overflow:auto;padding:8px 10px;line-height:1.45';

  const collapsed = localStorage.getItem(COLLAPSE_KEY) === '1';
  if (collapsed) { _body.style.display = 'none'; caret.textContent = '▸'; }
  head.addEventListener('click', () => {
    const now = _body.style.display === 'none';
    _body.style.display = now ? '' : 'none';
    caret.textContent = now ? '▾' : '▸';
    localStorage.setItem(COLLAPSE_KEY, now ? '0' : '1');
  });

  _panel.append(head, _body);
  document.body.appendChild(_panel);
}

function _renderJob(j) {
  const running = j.status === 'running' || j.status === 'queued';
  const icon = running ? '●' : (j.status === 'done' ? '✓' : '✕');
  const color = running ? 'var(--warn,#e6a23c)' : (j.status === 'done' ? 'var(--ok,#30d158)' : 'var(--err,#ff5a5a)');
  const tail = (j.tail || []).slice(-8).map(_esc).join('\n');
  const when = running ? '' : ` · ${_ago(j.finished_at || j.started_at)}`;
  return (
    `<div style="margin:6px 0;padding:6px 8px;border-radius:8px;background:var(--tint,#23232a)">` +
    `<div style="display:flex;gap:6px;align-items:baseline">` +
    `<span style="color:${color}">${icon}</span>` +
    `<span style="flex:1;min-width:0">Code · ${_esc(j.stage || j.status || '')}${when}</span></div>` +
    (tail ? `<pre style="margin:6px 0 0;font:11px/1.4 ui-monospace,Menlo,monospace;color:var(--dim,#9a9aa6);white-space:pre-wrap;max-height:140px;overflow:auto">${tail}</pre>` : '') +
    `</div>`
  );
}

async function _tick() {
  const [code, sc] = await Promise.all([
    _get('/api/code/jobs'),
    _get('/api/plugins/self_coder/status'),
  ]);

  const parts = [];
  let anyRunning = false;

  const jobs = (code && code.jobs) || [];
  const active = jobs.filter(j => j.status === 'running' || j.status === 'queued');
  const recent = jobs.filter(j => j.status !== 'running' && j.status !== 'queued').slice(0, 2);
  if (active.length) anyRunning = true;
  for (const j of active) parts.push(_renderJob(j));

  if (sc && sc.active) {
    anyRunning = true;
    const st = _esc(sc.state || sc.status || 'arbeider');
    const age = sc.last_activity_ts ? ` · sist aktivitet ${_ago(sc.last_activity_ts)}` : '';
    const detail = _esc(sc.detail || sc.instruction || '');
    parts.push(
      `<div style="margin:6px 0;padding:6px 8px;border-radius:8px;background:var(--tint,#23232a)">` +
      `<div style="display:flex;gap:6px;align-items:baseline"><span style="color:var(--warn,#e6a23c)">●</span>` +
      `<span style="flex:1">Self-coder · ${st}${age}</span></div>` +
      (detail ? `<div style="margin-top:4px;color:var(--dim,#9a9aa6);white-space:pre-wrap">${detail}</div>` : '') +
      `</div>`
    );
  }

  if (!parts.length) {
    if (recent.length) {
      parts.push(`<div style="color:var(--faint,#6b6b78);margin-bottom:4px">Inaktiv — siste:</div>`);
      for (const j of recent) parts.push(_renderJob(j));
    } else {
      parts.push(`<div style="color:var(--faint,#6b6b78);padding:6px 2px">Inaktiv — ingenting kjører nå.</div>`);
    }
  }

  _body.innerHTML = parts.join('');
  _dot.style.background = anyRunning ? 'var(--warn,#e6a23c)' : 'var(--ok,#30d158)';
  _dot.style.boxShadow = anyRunning ? '0 0 8px var(--warn,#e6a23c)' : 'none';

  // Reschedule at the cadence that matches current activity.
  const next = anyRunning ? POLL_BUSY : POLL_IDLE;
  if (next !== (_busy ? POLL_BUSY : POLL_IDLE) || _timer == null) {
    _busy = anyRunning;
  }
  _timer = setTimeout(_tick, document.hidden ? POLL_IDLE * 2 : next);
}

function _init() {
  if (document.getElementById('activity-panel')) return;
  _build();
  _tick();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _init);
} else {
  _init();
}
