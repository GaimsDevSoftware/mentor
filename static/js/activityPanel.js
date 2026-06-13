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
const POSITION_KEY = 'odysseus-activity-pos';

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

  _panel.append(head, _body);
  document.body.appendChild(_panel);

  _restorePosition();
  _makeDraggable(head, caret);
}

function _toggleCollapse(caret) {
  const now = _body.style.display === 'none';
  _body.style.display = now ? '' : 'none';
  caret.textContent = now ? '▾' : '▸';
  localStorage.setItem(COLLAPSE_KEY, now ? '0' : '1');
}

// Clamp a desired (left, top) inside the viewport, switch the panel from its
// default right/bottom anchoring to left/top, and apply it.
function _applyPos(left, top) {
  const w = _panel.offsetWidth || 360;
  const maxLeft = Math.max(0, window.innerWidth - w);
  const maxTop = Math.max(0, window.innerHeight - 40);   // keep the header grabbable
  left = Math.min(Math.max(0, left), maxLeft);
  top = Math.min(Math.max(0, top), maxTop);
  _panel.style.left = left + 'px';
  _panel.style.top = top + 'px';
  _panel.style.right = 'auto';
  _panel.style.bottom = 'auto';
}

function _savePos() {
  try {
    const r = _panel.getBoundingClientRect();
    localStorage.setItem(POSITION_KEY, JSON.stringify({ left: r.left, top: r.top }));
  } catch {}
}

function _restorePosition() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(POSITION_KEY) || 'null'); } catch {}
  if (saved && typeof saved.left === 'number' && typeof saved.top === 'number') {
    _applyPos(saved.left, saved.top);
  }
  // If the window shrinks, re-clamp so the panel never strands off-screen.
  window.addEventListener('resize', () => {
    if (_panel.style.left && _panel.style.left !== 'auto') {
      _applyPos(parseFloat(_panel.style.left), parseFloat(_panel.style.top));
    }
  });
}

// Drag the panel by its header. A press that doesn't move past a small
// threshold is treated as a click → collapse/expand, so the header keeps both
// behaviours (move + toggle).
function _makeDraggable(head, caret) {
  let startX = 0, startY = 0, baseLeft = 0, baseTop = 0, dragging = false, moved = false;
  head.style.cursor = 'grab';
  head.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true; moved = false;
    const r = _panel.getBoundingClientRect();
    baseLeft = r.left; baseTop = r.top;
    startX = e.clientX; startY = e.clientY;
    head.style.cursor = 'grabbing';
    try { head.setPointerCapture(e.pointerId); } catch {}
  });
  head.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (!moved && Math.abs(dx) + Math.abs(dy) > 4) moved = true;   // drag threshold
    if (moved) _applyPos(baseLeft + dx, baseTop + dy);
  });
  const end = (e) => {
    if (!dragging) return;
    dragging = false;
    head.style.cursor = 'grab';
    try { head.releasePointerCapture(e.pointerId); } catch {}
    if (moved) _savePos();          // a real drag → remember the new spot
    else _toggleCollapse(caret);    // a plain click → collapse/expand
  };
  head.addEventListener('pointerup', end);
  head.addEventListener('pointercancel', end);
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
  const [code, sc, heal] = await Promise.all([
    _get('/api/code/jobs'),
    _get('/api/plugins/self_coder/status'),
    _get('/api/manage/autoheal'),
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

  // Auto-heal events: a model silently switched (quota/offline → fallback).
  // Surface recent ones (last hour) so a behind-the-scenes model change is
  // never invisible to the user. (Read-only /api/manage/autoheal.)
  const _now = Date.now() / 1000;
  const heals = ((heal && heal.heals) || [])
    .filter(h => h && h.ts && (_now - h.ts) < 3600)
    .slice(-3).reverse();
  for (const h of heals) {
    const oldm = _esc(h.old || h.old_model || '?');
    const newm = _esc(h.new || h.new_model || '?');
    parts.push(
      `<div style="margin:6px 0;padding:6px 8px;border-radius:8px;background:var(--tint,#23232a)">` +
      `<div style="display:flex;gap:6px;align-items:baseline"><span style="color:var(--ok,#30d158)">↻</span>` +
      `<span style="flex:1;min-width:0">Model auto-switched · ${_esc(h.role || '')}: ${oldm} → ${newm} · ${_ago(h.ts)}</span></div>` +
      (h.reason ? `<div style="margin-top:4px;color:var(--dim,#9a9aa6)">${_esc(h.reason)}</div>` : '') +
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
