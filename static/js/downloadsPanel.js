// ============================================
// GLOBAL DOWNLOADS PANEL
// A drawer reachable from every page via the rail "Downloads" button. Shows
// in-progress model downloads with a live progress bar + approximate time left,
// and finished ones clearly marked with useful info + a one-click "use this
// model" (serve) action.
//
// READ-ONLY VIEW — by design. It parses the task state the Cookbook background
// monitor already persists (localStorage 'cookbook-tasks' + each task.output),
// so it never double-drives a download (no extra retries/notifications/polls).
// The monitor runs globally regardless of which UI is open, so task.output stays
// fresh and the bars move even when the Cookbook modal is closed.
// ============================================

const TASKS_KEY = 'cookbook-tasks';
const _etaSamples = new Map();   // sessionId -> [{t, p}] rolling overall-% samples
let _drawer = null;
let _renderTimer = null;
let _railTimer = null;
let _open = false;
let _lastSig = null;

// ── data ──────────────────────────────────────────────────────────────────
function _loadDownloads() {
  let tasks = [];
  try { tasks = JSON.parse(localStorage.getItem(TASKS_KEY)) || []; } catch { tasks = []; }
  return (Array.isArray(tasks) ? tasks : []).filter(t => t && t.type === 'download');
}
function _isActive(t) { return t.status === 'running' || t.status === 'queued'; }
function _isDone(t) { return t.status === 'done'; }
function _isBad(t) { return ['error', 'stopped', 'crashed', 'failed'].includes(t.status); }

function _esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s == null ? '' : s);
  return d.innerHTML.replace(/"/g, '&quot;');   // safe for text AND attributes
}
function _short(repo) { return String(repo || '').split('/').pop() || String(repo || ''); }

function _fmtEta(sec) {
  if (!isFinite(sec) || sec < 0) return '';
  if (sec < 60) return Math.max(1, Math.round(sec)) + 's';
  if (sec < 3600) { const m = Math.floor(sec / 60), s = Math.round(sec % 60); return s ? `${m}m ${s}s` : `${m}m`; }
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60); return m ? `${h}h ${m}m` : `${h}h`;
}

// Latest overall progress from a tmux snapshot (task.output). Mirrors the
// signals cookbookRunning.js uses: shard-of-N overall, hf_transfer aggregate,
// "Fetching N files", trailing N%| , and the transfer speed.
function _parseProgress(out) {
  out = String(out || '');
  if (!out) return { pct: null, speed: '' };
  const last = (re) => { const m = [...out.matchAll(re)]; return m.length ? m[m.length - 1] : null; };
  const speedM = last(/([\d.]+\s*[KMG]i?B)\/s/gi);
  const speed = speedM ? speedM[1].replace(/\s+/g, '') + '/s' : '';
  const dlAggM = last(/Downloading\s*\(incomplete[^)]*\):\s*(\d+)%/g);
  const dlAgg = dlAggM ? parseInt(dlAggM[1], 10) : null;
  const fetchM = last(/Fetching\s+\d+\s+files:\s*(\d+)%/g);
  const fetchPct = fetchM ? parseInt(fetchM[1], 10) : null;
  const shardM = last(/model-(\d+)-of-(\d+)\.(?:safetensors|bin)/g);
  const lastPctM = last(/(\d+)%\|/g);
  const lastPct = lastPctM ? parseInt(lastPctM[1], 10) : null;
  let pct = null;
  if (shardM) {
    const cur = parseInt(shardM[1], 10), tot = parseInt(shardM[2], 10);
    if (tot > 1) {
      const frac = dlAgg != null ? dlAgg / 100 : (lastPct != null ? lastPct / 100 : 0);
      pct = Math.round((((cur - 1) + frac) / tot) * 100);
      if (fetchPct != null) pct = Math.max(pct, fetchPct);
    }
  }
  if (pct == null && dlAgg != null) pct = Math.max(dlAgg, fetchPct != null ? fetchPct : 0);
  if (pct == null && fetchPct != null) pct = fetchPct;
  if (pct == null && lastPct != null) pct = lastPct;
  if ((out.includes('DOWNLOAD_OK') || /100%\|/.test(out)) && pct == null) pct = 100;
  return { pct, speed };
}

// Overall ETA from a rolling window of (pct, wall-clock) samples per download.
function _eta(sid, pct) {
  if (pct == null) return '';
  const now = Date.now();
  let s = _etaSamples.get(sid);
  if (!s) { s = []; _etaSamples.set(sid, s); }
  const last = s[s.length - 1];
  if (last && pct < last.p - 3) s.length = 0;        // resume re-check → forget stale rate
  if (!last || last.p !== pct) s.push({ t: now, p: pct });
  while (s.length > 2 && now - s[0].t > 90000) s.shift();
  if (pct >= 100) return 'finishing…';
  if (s.length >= 2) {
    const f = s[0], dP = pct - f.p, dT = (now - f.t) / 1000;
    if (dP > 0 && dT > 2) return '~' + _fmtEta((100 - pct) / (dP / dT)) + ' left';
  }
  return '';
}

// A finished download's total size, read from a "1.81G/2.49G"-style tail.
function _sizeBit(t) {
  const m = [...String(t.output || '').matchAll(/[\d.]+\s*[KMG]?i?B?\s*\/\s*([\d.]+)\s*([KMG])i?B?\b/gi)];
  if (!m.length) return '';
  const lastM = m[m.length - 1];
  return ` · ${lastM[1]} ${lastM[2]}B`;
}

// ── rendering ───────────────────────────────────────────────────────────────
function _activeMeta(t) {
  const { pct, speed } = _parseProgress(t.output);
  const eta = _eta(t.sessionId, pct);
  const bits = [eta, (speed && (pct == null || pct < 100)) ? speed : ''].filter(Boolean);
  return { pct, text: bits.join(' · ') || (t.status === 'queued' ? 'queued' : 'starting…') };
}

function _card(t) {
  const repo = (t.payload && t.payload.repo_id) || t.name || '';
  const dir = (t.payload && t.payload.local_dir) || '~/.cache/huggingface/hub';
  const cls = _isActive(t) ? 'run' : (_isDone(t) ? 'done' : (_isBad(t) ? 'bad' : ''));
  const badge = _isActive(t) ? (t.status === 'queued' ? 'queued' : 'downloading')
    : (_isDone(t) ? 'finished' : _esc(t.status || ''));
  let mid = '';
  if (_isActive(t)) {
    const { pct, text } = _activeMeta(t);
    const known = pct != null;
    mid = `<div class="dl-bar"><div class="dl-bar-fill ${known ? '' : 'indeterminate'}" style="width:${known ? Math.max(0, Math.min(100, pct)) : 0}%"></div></div>`
      + `<div class="dl-meta"><span class="dl-pct">${known ? Math.round(pct) + '%' : ''}</span><span class="dl-eta">${_esc(text)}</span></div>`;
  } else if (_isDone(t)) {
    mid = `<div class="dl-done-info">✓ Ready${_sizeBit(t)}</div>`
      + `<div class="dl-dir" title="${_esc(dir)}">${_esc(dir)}</div>`
      + `<div class="dl-actions"><button type="button" class="dl-act-serve" data-repo="${_esc(repo)}">Use this model →</button></div>`;
  } else if (_isBad(t)) {
    mid = `<div class="dl-baddy">${_esc(t.status || 'stopped')} — <button type="button" class="dl-act-cookbook dl-linkbtn">open in Cookbook to retry</button></div>`;
  }
  return `<div class="dl-item dl-${cls}" data-id="${_esc(t.sessionId)}">`
    + `<div class="dl-item-head"><span class="dl-name" title="${_esc(repo)}">${_esc(_short(repo))}</span>`
    + `<span class="dl-badge dl-badge-${cls}">${badge}</span></div>${mid}</div>`;
}

function _render() {
  if (!_open) return;
  const body = document.getElementById('dl-drawer-body');
  if (!body) return;
  const dls = _loadDownloads().sort((a, b) => (_isActive(b) - _isActive(a)) || ((b.ts || 0) - (a.ts || 0)));
  const sig = dls.map(t => t.sessionId + ':' + t.status).join('|');
  if (sig !== _lastSig) {
    _lastSig = sig;
    body.innerHTML = dls.length
      ? dls.map(_card).join('')
      : '<div class="dl-empty">No downloads yet.<br><span>Start one from the Cookbook’s “Fits this machine” list and it’ll show up here — on any page.</span></div>';
  }
  // Per-tick in-place update of active bars → smooth motion without rebuilding.
  dls.forEach(t => {
    if (!_isActive(t)) return;
    let it; try { it = body.querySelector(`.dl-item[data-id="${CSS.escape(t.sessionId)}"]`); } catch { it = null; }
    if (!it) return;
    const { pct, text } = _activeMeta(t);
    const known = pct != null;
    const fill = it.querySelector('.dl-bar-fill');
    if (fill) {
      fill.classList.toggle('indeterminate', !known);
      if (known) fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
    }
    const pe = it.querySelector('.dl-pct'); if (pe) pe.textContent = known ? Math.round(pct) + '%' : '';
    const ee = it.querySelector('.dl-eta'); if (ee) ee.textContent = text;
  });
}

// ── serve / cookbook hand-off ────────────────────────────────────────────────
async function _onBodyClick(e) {
  const serve = e.target.closest('.dl-act-serve');
  if (serve) {
    const repo = serve.dataset.repo || '';
    close();
    try {
      const m = await import('./cookbookServe.js');
      if (m && typeof m.openServePanelForRepo === 'function') { await m.openServePanelForRepo(repo); return; }
    } catch (_) { /* fall through */ }
    try { window.cookbookModule?.open({ tab: 'Serve', serveSearch: repo }); } catch (_) {}
    return;
  }
  if (e.target.closest('.dl-act-cookbook')) {
    close();
    try { window.cookbookModule?.open({ tab: 'Running' }); } catch (_) {}
  }
}

// ── rail button (visibility + active count badge) ────────────────────────────
function _syncRail() {
  const btn = document.getElementById('rail-downloads');
  if (!btn) return;
  const dls = _loadDownloads();
  const active = dls.filter(_isActive).length;
  btn.style.display = dls.length ? '' : 'none';
  let badge = btn.querySelector('.dl-rail-badge');
  if (active > 0) {
    if (!badge) { badge = document.createElement('span'); badge.className = 'dl-rail-badge'; btn.appendChild(badge); }
    badge.textContent = String(active);
  } else if (badge) { badge.remove(); }
  btn.classList.toggle('dl-rail-active', active > 0);
}

// ── open / close ─────────────────────────────────────────────────────────────
function _ensureDrawer() {
  if (_drawer) return _drawer;
  const d = document.createElement('div');
  d.id = 'downloads-drawer';
  d.className = 'dl-drawer';
  d.innerHTML = `
    <div class="dl-drawer-scrim"></div>
    <div class="dl-drawer-panel" role="dialog" aria-label="Downloads">
      <div class="dl-drawer-head">
        <span class="dl-drawer-title">Downloads</span>
        <button type="button" class="dl-drawer-close" title="Close" aria-label="Close">&#x2715;</button>
      </div>
      <div class="dl-drawer-body" id="dl-drawer-body"></div>
      <div class="dl-drawer-foot"><button type="button" class="dl-linkbtn" id="dl-open-cookbook">Open Cookbook for full controls →</button></div>
    </div>`;
  document.body.appendChild(d);
  d.querySelector('.dl-drawer-scrim').addEventListener('click', close);
  d.querySelector('.dl-drawer-close').addEventListener('click', close);
  d.querySelector('#dl-open-cookbook').addEventListener('click', () => {
    close();
    try { window.cookbookModule?.open({ tab: 'Running' }); } catch (_) {}
  });
  d.querySelector('.dl-drawer-body').addEventListener('click', _onBodyClick);
  _drawer = d;
  return d;
}

function open() {
  const d = _ensureDrawer();
  _open = true;
  _lastSig = null;
  // rAF so the slide-in transition runs from the off-screen start state.
  requestAnimationFrame(() => d.classList.add('on'));
  _render();
  if (_renderTimer) clearInterval(_renderTimer);
  _renderTimer = setInterval(_render, 1200);
}

function close() {
  _open = false;
  if (_drawer) _drawer.classList.remove('on');
  if (_renderTimer) { clearInterval(_renderTimer); _renderTimer = null; }
}

function toggle() { _open ? close() : open(); }

function init() {
  const btn = document.getElementById('rail-downloads');
  if (btn) btn.addEventListener('click', toggle);
  _syncRail();
  if (_railTimer) clearInterval(_railTimer);
  _railTimer = setInterval(_syncRail, 1500);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && _open) close(); });
}

export default { init, open, close, toggle };
