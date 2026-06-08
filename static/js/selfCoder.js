/**
 * Self-coder panel — the autonomous code-improvement loop as a chat-style
 * tool modal in the main UI.  Follows the same modal/draggable/minimize
 * pattern as Calendar, Notes, Gallery etc.
 *
 * Opens from the sidebar "Self-coder" item or the rail wrench icon.
 */

import * as Modals from './modalManager.js';
import { makeWindowDraggable } from './windowDrag.js';

const MODAL_ID = 'selfcoder-modal';
const API = '/api/plugins/self_coder';

let _modal = null;
let _open = false;
let _busy = false;
let _timerHandle = null;

const _esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const _j = (url, opts) =>
  fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts))
    .then(r => r.json());

// ── Step labels ──
const STEP_LABEL = {
  branch_created: 'created branch', aider_starting: 'asking Aider to edit',
  aider_done: 'Aider finished', no_changes: 'no changes made',
  committed_on_branch: 'committed on branch', verify_starting: 'verifying…',
  verify_py_compile: 'compile check', verify_import_app: 'boot check',
  verify_pytest: 'running tests', decided: 'decision', error: 'error',
};

// ── Color diff ──
function _colorDiff(diff) {
  return String(diff || '').split('\n').map(l => {
    let c = 'var(--dim)';
    if (l.startsWith('+++') || l.startsWith('---')) c = 'var(--faint)';
    else if (l.startsWith('@@')) c = 'var(--cyan)';
    else if (l[0] === '+') c = 'var(--ok,#30d158)';
    else if (l[0] === '-') c = 'var(--err,#ff453a)';
    return `<span style="color:${c}">${_esc(l)}</span>`;
  }).join('\n');
}

// ── Chat helpers ──
function _log() { return _modal && _modal.querySelector('#sc-log'); }

function _bub(role, html, cls) {
  const log = _log(); if (!log) return null;
  const b = document.createElement('div');
  b.className = 'sc-bub ' + (cls || role);
  b.innerHTML = `<div class="sc-lbl">${role === 'user' ? 'You' : 'Mentor'}</div>${html}`;
  log.appendChild(b);
  log.scrollTop = log.scrollHeight;
  return b;
}

function _narr(html) {
  const log = _log(); if (!log) return;
  const n = document.createElement('div');
  n.className = 'sc-narr';
  n.innerHTML = html;
  log.appendChild(n);
  log.scrollTop = log.scrollHeight;
}

function _pending() {
  const log = _log(); if (!log) return null;
  const b = document.createElement('div');
  b.className = 'sc-bub ai';
  b.innerHTML = `<div class="sc-lbl">Mentor</div>
    <div class="sc-pend"><span class="sc-spin"></span>
    <span class="sc-stage">starting…</span>
    <span class="sc-elapsed" data-since="${Date.now()}">0s</span></div>`;
  log.appendChild(b);
  log.scrollTop = log.scrollHeight;
  return b;
}

function _setStage(bub, stage) {
  const el = bub && bub.querySelector('.sc-stage');
  if (el) el.textContent = stage;
}

function _startTimer() {
  if (_timerHandle) return;
  _timerHandle = setInterval(() => {
    document.querySelectorAll('.sc-elapsed[data-since]').forEach(el => {
      const s = Math.max(1, Math.round((Date.now() - parseInt(el.dataset.since || '0', 10)) / 1000));
      el.textContent = s < 60 ? s + 's' : Math.floor(s / 60) + 'm ' + (s % 60) + 's';
    });
  }, 1000);
}

function _stopTimer() {
  if (_timerHandle) { clearInterval(_timerHandle); _timerHandle = null; }
}

// ── Status badge ──
async function _loadStatus() {
  const badge = _modal && _modal.querySelector('#sc-status');
  if (!badge) return;
  try {
    const d = await _j(`${API}/proposals`);
    const n = (d.proposals || []).length;
    badge.textContent = n + ' proposal(s)';
  } catch {
    badge.textContent = 'offline';
  }
}

// ── Send ──
async function _send() {
  if (_busy) return;
  const inp = _modal && _modal.querySelector('#sc-input');
  if (!inp) return;
  const text = (inp.value || '').trim();
  if (!text) return;
  inp.value = '';
  _busy = true;
  const sendBtn = _modal.querySelector('#sc-send-btn');
  if (sendBtn) sendBtn.disabled = true;

  _bub('user', _esc(text));
  _narr('Creating a safe branch and running the change…');
  const pend = _pending();
  _startTimer();

  let r;
  try {
    r = await _j(`${API}/propose`, {
      method: 'POST',
      body: JSON.stringify({ instruction: text, files: [] }),
    });
  } catch (e) {
    _stopTimer(); if (pend) pend.remove();
    _bub('ai', 'Could not start: ' + _esc(String(e)), 'ai err');
    _busy = false; if (sendBtn) sendBtn.disabled = false;
    return;
  }
  if (!r.ok) {
    _stopTimer(); if (pend) pend.remove();
    _bub('ai', _esc(r.detail || 'Failed to start.'), 'ai err');
    _busy = false; if (sendBtn) sendBtn.disabled = false;
    return;
  }

  const id = r.id || r.proposal_id;
  const poll = setInterval(async () => {
    let p;
    try { p = await _j(`${API}/proposals/${id}`); } catch { return; }
    const prog = p.progress || [];
    const last = prog[prog.length - 1];
    if (last) _setStage(pend, STEP_LABEL[last.step] || last.step);
    if (p.status !== 'building') {
      clearInterval(poll); _stopTimer(); if (pend) pend.remove();
      const dec = p.decision || {};
      let summary = dec.action
        ? (dec.action + ' — ' + (dec.why || ''))
        : (p.status === 'verified' ? 'Change verified and ready to apply.' : 'The change did not pass verification.');
      let html = `<div class="sc-lbl">Mentor</div>${_esc(summary)}`;
      if (p.diff && p.diff.trim()) {
        html += `<details class="sc-det"><summary>See the diff</summary><pre class="sc-diff">${_colorDiff(p.diff)}</pre></details>`;
      }
      if (p.aider_log) {
        html += `<details class="sc-det"><summary>Aider log</summary><pre class="sc-diff" style="max-height:200px">${_esc(p.aider_log.slice(-3000))}</pre></details>`;
      }
      const progHtml = prog.map(s => {
        const lbl = STEP_LABEL[s.step] || s.step;
        const ok = s.ok === false ? ' color:var(--err)' : s.ok === true ? ' color:var(--ok)' : '';
        return `<span style="font-size:11px;${ok}">${_esc(lbl)}</span>`;
      }).join(' → ');
      if (progHtml) html += `<details class="sc-det"><summary>Steps</summary><div style="margin-top:4px;line-height:1.8">${progHtml}</div></details>`;
      if (p.status === 'verified') {
        html += `<div style="margin-top:8px"><button class="sc-action-btn sc-apply" data-pid="${id}">Apply (merge + canary)</button> <button class="sc-action-btn sc-discard" data-pid="${id}">Discard</button></div>`;
      } else {
        html += `<div style="margin-top:8px"><button class="sc-action-btn sc-discard" data-pid="${id}">Discard</button></div>`;
      }
      _bub('ai', html, p.status === 'failed' ? 'ai err' : 'ai');
      _busy = false; if (sendBtn) sendBtn.disabled = false;
      _loadStatus();
    }
  }, 2000);
}

async function _apply(pid) {
  if (!confirm('Merge + restart with canary auto-rollback?')) return;
  const r = await _j(`${API}/proposals/${pid}/apply`, { method: 'POST' });
  _narr(_esc(r.detail || JSON.stringify(r)));
  _loadStatus();
}

async function _discard(pid) {
  if (!confirm('Discard this proposal?')) return;
  const r = await _j(`${API}/proposals/${pid}/discard`, { method: 'POST' });
  _narr(_esc(r.detail || 'Discarded.'));
  _loadStatus();
}

// ── Modal build ──
function _getModal() {
  if (_modal) return _modal;
  _modal = document.createElement('div');
  _modal.id = MODAL_ID;
  _modal.className = 'modal';
  _modal.style.display = 'none';
  _modal.innerHTML = `
    <div class="modal-content sc-modal-content">
      <div class="modal-header">
        <h4>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>Self-coder
          <span id="sc-status" style="font-size:11px;color:var(--faint);margin-left:8px;font-weight:400">…</span>
        </h4>
        <button class="close-btn" id="sc-close">&#x2716;</button>
      </div>
      <div class="modal-body sc-modal-body">
        <div class="sc-hint">Describe a change — the app makes it on a safe branch, verifies it, and presents the result. You approve before anything lands.</div>
        <div id="sc-log" class="sc-log"></div>
        <div class="sc-compose">
          <textarea id="sc-input" rows="1" placeholder="Describe the change…  (Enter to send)"></textarea>
          <button id="sc-send-btn" type="button">Send</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(_modal);

  // Close
  _modal.querySelector('#sc-close').addEventListener('click', closeSelfCoder);
  _modal.addEventListener('click', (e) => { if (e.target === _modal) closeSelfCoder(); });

  // Send
  _modal.querySelector('#sc-send-btn').addEventListener('click', _send);
  _modal.querySelector('#sc-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _send(); }
  });

  // Action delegation (apply/discard)
  _modal.querySelector('#sc-log').addEventListener('click', (e) => {
    const btn = e.target.closest('.sc-action-btn');
    if (!btn) return;
    const pid = btn.dataset.pid;
    if (btn.classList.contains('sc-apply')) _apply(pid);
    else if (btn.classList.contains('sc-discard')) _discard(pid);
  });

  // Draggable
  const content = _modal.querySelector('.modal-content');
  const header = _modal.querySelector('.modal-header');
  if (content && header) makeWindowDraggable(_modal, { content, header });

  return _modal;
}

// ── Inject styles (once) ──
let _styled = false;
function _ensureStyles() {
  if (_styled) return;
  _styled = true;
  const s = document.createElement('style');
  s.textContent = `
.sc-modal-content{width:480px;max-width:94vw;height:560px;max-height:80vh;display:flex;flex-direction:column}
.sc-modal-body{flex:1;display:flex;flex-direction:column;overflow:hidden;padding:0}
.sc-hint{font-size:12px;color:var(--faint);padding:10px 16px 0;line-height:1.5}
.sc-log{flex:1;display:flex;flex-direction:column;gap:10px;overflow:auto;padding:10px 16px}
.sc-bub{max-width:85%;padding:10px 13px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word;border:1px solid var(--sep)}
.sc-bub.user{align-self:flex-end;background:color-mix(in srgb,var(--cyan) 14%,transparent);border-color:color-mix(in srgb,var(--cyan) 30%,transparent);border-radius:12px 12px 4px 12px}
.sc-bub.ai{align-self:flex-start;background:var(--tint);border-radius:12px 12px 12px 4px}
.sc-lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin-bottom:3px;font-weight:600}
.sc-bub.user .sc-lbl{color:var(--cyan)}
.sc-bub.ai .sc-lbl{color:var(--brass,var(--accent))}
.sc-bub.err{border-color:color-mix(in srgb,var(--err,red) 40%,transparent)}
.sc-bub.err .sc-lbl{color:var(--err,red)}
.sc-narr{align-self:center;font-size:11px;color:var(--faint);font-style:italic;text-align:center;padding:2px 6px}
.sc-pend{display:flex;align-items:center;gap:8px}
.sc-spin{width:12px;height:12px;border:2px solid var(--sep-2);border-top-color:var(--brass,var(--accent));border-radius:50%;display:inline-block;animation:_scspin .7s linear infinite;flex-shrink:0}
@keyframes _scspin{to{transform:rotate(360deg)}}
.sc-elapsed{color:var(--faint);font-size:11px;font-variant-numeric:tabular-nums}
.sc-compose{display:flex;gap:6px;align-items:flex-end;border-top:1px solid var(--sep);padding:10px 16px}
.sc-compose textarea{flex:1;background:var(--tint);color:var(--txt);border:1px solid var(--sep-2);border-radius:8px;padding:8px 10px;font:13px/1.4 inherit;outline:none;resize:none;min-height:24px;max-height:140px}
.sc-compose textarea:focus{border-color:var(--brass,var(--accent))}
.sc-compose button{background:var(--brass,var(--accent));color:#0b0b0d;border:none;border-radius:8px;padding:8px 14px;font:600 12px/1 inherit;cursor:pointer;flex-shrink:0}
.sc-compose button:disabled{opacity:.45;cursor:default}
.sc-det{margin-top:8px;border-top:1px solid var(--sep);padding-top:6px}
.sc-det summary{cursor:pointer;color:var(--dim);font-size:11px;list-style:none;display:inline-flex;align-items:center;gap:5px;user-select:none;font-weight:500}
.sc-det summary::-webkit-details-marker{display:none}
.sc-det summary::before{content:"▸";color:var(--faint);font-size:9px;transition:transform .15s;display:inline-block;width:8px}
.sc-det[open] summary::before{transform:rotate(90deg)}
.sc-diff{white-space:pre-wrap;font:12px/1.4 ui-monospace,Menlo,monospace;background:var(--tint);border:1px solid var(--sep);border-radius:8px;padding:10px;max-height:300px;overflow:auto;margin-top:6px}
.sc-action-btn{border:none;border-radius:6px;padding:6px 12px;font:600 11px/1 inherit;cursor:pointer}
.sc-apply{background:var(--ok,#30d158);color:#000}
.sc-discard{background:var(--sep-2);color:var(--txt)}
.sc-action-btn:hover{filter:brightness(1.15)}
`;
  document.head.appendChild(s);
}

// ── Public API ──
function openSelfCoder() {
  _ensureStyles();
  if (_open) return;
  if (Modals.isMinimized(MODAL_ID)) {
    Modals.restore(MODAL_ID);
    _open = true;
    return;
  }
  _open = true;
  const modal = _getModal();
  modal.classList.remove('hidden', 'modal-minimized');
  const mc = modal.querySelector('.modal-content');
  if (mc) { mc.classList.remove('modal-closing', 'sheet-ready'); mc.style.transform = ''; mc.style.transition = ''; }
  modal.style.display = 'flex';
  Modals.register(MODAL_ID, {
    railBtnId: 'rail-selfcoder',
    sidebarBtnId: 'tool-selfcoder-btn',
    closeFn: () => _doClose(),
    restoreFn: () => {},
  });
  _loadStatus();
  const inp = modal.querySelector('#sc-input');
  if (inp) setTimeout(() => inp.focus(), 60);
}

function _doClose() {
  _open = false;
  _stopTimer();
  if (_modal) { _modal.style.display = 'none'; _modal.classList.add('hidden'); }
}

function closeSelfCoder() {
  if (!_open) return;
  Modals.close(MODAL_ID);
}

function isSelfCoderOpen() { return _open; }

function toggleSelfCoder() {
  if (_open) closeSelfCoder();
  else openSelfCoder();
}

const selfCoderModule = { openSelfCoder, closeSelfCoder, isSelfCoderOpen, toggleSelfCoder };
export { openSelfCoder, closeSelfCoder, isSelfCoderOpen, toggleSelfCoder };
export default selfCoderModule;
