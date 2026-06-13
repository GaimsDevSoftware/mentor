/**
 * chatFloat.js — float / pin toggle for the main chat, PLUS pop-out
 * windows for opening multiple sessions side by side.
 *
 * Two features:
 *  1. Float/pin: detach the main chat-container as a draggable window.
 *  2. Pop-out: open ANY session in its own floating mini-chat window
 *     (independent SSE stream, own input bar). Multiple can coexist.
 */

import { makeWindowDraggable } from './windowDrag.js';
import markdownModule from './markdown.js';
import * as Modals from './modalManager.js';

const LS_KEY = 'ody-chat-floated';
const API = window.location.origin;

let _floated = false;
let _btn = null;
const _popouts = new Map();   // sessionId → { modal, sse, … }
let _popoutCounter = 0;
// Bring-to-front: any interaction with a pop-out raises it above the others.
// Starts above the static .modal stack (250) and modalManager's bump base (300).
let _popoutTopZ = 600;
function _raisePopout(modal) {
  if (modal) modal.style.setProperty('z-index', String(++_popoutTopZ), 'important');
}

// ── Minimize pop-outs to a dock of chips ─────────────────────────────────────
let _minDock = null;
function _ensureMinDock() {
  if (!_minDock) {
    _minDock = document.createElement('div');
    _minDock.id = 'popout-min-dock';
    _minDock.style.cssText = 'position:fixed;left:12px;bottom:12px;display:flex;gap:6px;flex-wrap:wrap;z-index:9000;max-width:60vw';
    document.body.appendChild(_minDock);
  }
  _minDock.style.display = 'flex';
  return _minDock;
}
function _clearChip(st) {
  if (st && st.chip) { st.chip.remove(); st.chip = null; }
  if (_minDock && !_minDock.children.length) _minDock.style.display = 'none';
}
function _minimizePopout(sessionId) {
  const st = _popouts.get(sessionId);
  if (!st || !st.modal || st.chip) return;
  st.modal.style.display = 'none';
  const name = st.modal.querySelector('.popout-chat-title')?.textContent || String(sessionId).slice(0, 8);
  const chip = document.createElement('button');
  chip.className = 'popout-min-chip';
  chip.title = 'Gjenåpne ' + name;
  chip.textContent = '💬 ' + name;
  chip.style.cssText = 'background:var(--card,#1f1f25);color:var(--fg,#e8e8e8);border:1px solid var(--bubble-border,#2c2c35);border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
  chip.addEventListener('click', () => _restorePopout(sessionId));
  st.chip = chip;
  _ensureMinDock().appendChild(chip);
}
function _restorePopout(sessionId) {
  const st = _popouts.get(sessionId);
  if (!st || !st.modal) return;
  st.modal.style.display = 'flex';
  _raisePopout(st.modal);
  _clearChip(st);
}

const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ── SVGs ──
const FLOAT_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>`;
const PIN_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16h14v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>`;
const POPOUT_ICON = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`;

function _getContainer() { return document.getElementById('chat-container'); }
function _getTopBar()    { return document.querySelector('.chat-top-bar'); }

// ═══════════════════════════════════════════════════════════════════════════
//  1.  FLOAT / PIN  (main chat-container)
// ═══════════════════════════════════════════════════════════════════════════

function doFloat() {
  if (_floated) return;
  const container = _getContainer();
  const topBar = _getTopBar();
  if (!container) return;
  _floated = true;
  const ph = document.createElement('div');
  ph.id = 'chat-float-placeholder';
  ph.className = 'chat-float-placeholder';
  ph.innerHTML = '<span>Chat is floating — click <b>pin</b> to return it here</span>';
  container.parentElement.insertBefore(ph, container);
  container.classList.add('chat-floated');
  container.style.top = '60px';
  container.style.left = (window.innerWidth - 560) + 'px';
  container.style.right = '';
  if (topBar) {
    makeWindowDraggable(container, {
      content: container,
      header: topBar,
      enableDock: false,
      enableResize: false,
    });
  }
  _updateBtn();
  try { localStorage.setItem(LS_KEY, '1'); } catch {}
}

function doPin() {
  if (!_floated) return;
  const container = _getContainer();
  if (!container) return;
  _floated = false;
  container.classList.remove('chat-floated');
  container.style.position = '';
  container.style.top = '';
  container.style.left = '';
  container.style.right = '';
  container.style.width = '';
  container.style.height = '';
  container.style.transform = '';
  container.style.zIndex = '';
  const ph = document.getElementById('chat-float-placeholder');
  if (ph) ph.remove();
  const topBar = _getTopBar();
  if (topBar) { topBar.style.cursor = ''; topBar.style.userSelect = ''; }
  _updateBtn();
  try { localStorage.removeItem(LS_KEY); } catch {}
}

function toggle() { _floated ? doPin() : doFloat(); }

function _updateBtn() {
  if (!_btn) return;
  _btn.innerHTML = _floated ? PIN_ICON : FLOAT_ICON;
  _btn.title = _floated ? 'Pin chat back to page' : 'Float chat as window';
}

// ═══════════════════════════════════════════════════════════════════════════
//  2.  POP-OUT  (independent floating chat windows)
// ═══════════════════════════════════════════════════════════════════════════

/** Open a session in a standalone floating mini-chat. */
async function popOut(sessionId, sessionName) {
  if (_popouts.has(sessionId)) {
    const existing = _popouts.get(sessionId).modal;
    if (existing) { existing.style.display = 'flex'; _raisePopout(existing); return; }
  }

  _popoutCounter++;
  const n = _popoutCounter;
  const modalId = `popout-chat-${sessionId}`;
  const name = sessionName || sessionId.slice(0, 8);

  // Build modal
  const modal = document.createElement('div');
  modal.id = modalId;
  modal.className = 'modal popout-chat-modal';
  modal.style.display = 'flex';
  modal.innerHTML = `
    <div class="modal-content popout-chat-content">
      <div class="modal-header popout-chat-header">
        <h4 class="popout-chat-title">${esc(name)}</h4>
        <button class="close-btn popout-min" title="Minimer">&#x2014;</button>
        <button class="close-btn popout-close" title="Close">&#x2716;</button>
      </div>
      <div class="popout-chat-body">
        <div class="popout-history" id="ph-${n}">
          <div style="text-align:center;color:var(--faint);padding:20px">Loading…</div>
        </div>
        <div class="popout-compose">
          <textarea class="popout-input" rows="1" placeholder="Message…"></textarea>
          <button class="popout-send" type="button">Send</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(modal);

  const content = modal.querySelector('.modal-content');
  const header = modal.querySelector('.modal-header');
  makeWindowDraggable(modal, { content, header });

  // Raise to front on any interaction; raise now so the newest pop-out opens on
  // top. Capture phase so it fires before inner click handlers.
  modal.addEventListener('mousedown', () => _raisePopout(modal), true);
  _raisePopout(modal);

  // Stagger position
  const offsetX = 40 * ((n - 1) % 6);
  const offsetY = 40 * ((n - 1) % 6);
  content.style.position = 'relative';
  modal.style.top = (80 + offsetY) + 'px';
  modal.style.left = (window.innerWidth - 520 - offsetX) + 'px';

  // Store state
  const state = { modal, sse: null, abortCtrl: null };
  _popouts.set(sessionId, state);

  // Close handler
  modal.querySelector('.popout-close').addEventListener('click', () => closePopOut(sessionId));
  modal.querySelector('.popout-min').addEventListener('click', () => _minimizePopout(sessionId));
  modal.addEventListener('click', (e) => { if (e.target === modal) closePopOut(sessionId); });

  // Send handler
  const input = modal.querySelector('.popout-input');
  const sendBtn = modal.querySelector('.popout-send');
  const doSend = () => _popoutSend(sessionId, input, sendBtn);
  sendBtn.addEventListener('click', doSend);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); }
  });

  // Load history
  const histEl = modal.querySelector(`#ph-${n}`);
  try {
    const res = await fetch(`${API}/api/history/${sessionId}`);
    const data = await res.json();
    histEl.innerHTML = '';
    for (const msg of (data.history || [])) {
      _appendPopoutMsg(histEl, msg.role, msg.content, msg.model);
    }
    if (!data.history || data.history.length === 0) {
      histEl.innerHTML = '<div style="text-align:center;color:var(--faint);padding:20px;font-style:italic">No messages yet</div>';
    }
    histEl.scrollTop = histEl.scrollHeight;
  } catch (e) {
    histEl.innerHTML = `<div style="color:var(--err);padding:12px">Could not load history: ${esc(String(e))}</div>`;
  }

  input.focus();
}

function _appendPopoutMsg(container, role, content, model) {
  const isUser = (role === 'user');
  const div = document.createElement('div');
  div.className = 'popout-msg ' + (isUser ? 'popout-msg-user' : 'popout-msg-ai');
  const labelText = isUser ? 'You' : (model || 'AI');
  const bodyHtml = isUser ? esc(content) : markdownModule.mdToHtml(content || '');
  div.innerHTML = `<div class="popout-msg-label">${esc(labelText)}</div><div class="popout-msg-body">${bodyHtml}</div>`;
  container.appendChild(div);
  if (!isUser && window.hljs) div.querySelectorAll('pre code').forEach(b => window.hljs.highlightElement(b));
  return div;
}

async function _popoutSend(sessionId, input, sendBtn) {
  const text = (input.value || '').trim();
  if (!text) return;
  input.value = '';
  sendBtn.disabled = true;

  const state = _popouts.get(sessionId);
  if (!state) return;
  const histEl = state.modal.querySelector('.popout-history');
  if (!histEl) return;

  // Clear "no messages" placeholder
  const placeholder = histEl.querySelector('div[style*="font-style"]');
  if (placeholder) placeholder.remove();

  _appendPopoutMsg(histEl, 'user', text);
  histEl.scrollTop = histEl.scrollHeight;

  // Create a streaming AI bubble
  const aiDiv = document.createElement('div');
  aiDiv.className = 'popout-msg popout-msg-ai';
  aiDiv.innerHTML = '<div class="popout-msg-label">AI</div><div class="popout-msg-body popout-streaming"><span class="popout-cursor">▍</span></div>';
  histEl.appendChild(aiDiv);
  histEl.scrollTop = histEl.scrollHeight;
  const bodyEl = aiDiv.querySelector('.popout-msg-body');

  // Send via SSE
  const abortCtrl = new AbortController();
  state.abortCtrl = abortCtrl;
  const fd = new FormData();
  fd.append('message', text);
  fd.append('session', sessionId);

  try {
    const res = await fetch(`${API}/api/chat_stream`, {
      method: 'POST',
      body: fd,
      signal: abortCtrl.signal,
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accum = '';
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const json = JSON.parse(line.slice(6));
          if (json.delta) {
            accum += json.delta;
            bodyEl.innerHTML = markdownModule.mdToHtml(accum) + '<span class="popout-cursor">▍</span>';
            histEl.scrollTop = histEl.scrollHeight;
          } else if (json.type === 'done' || json.type === 'error') {
            break;
          }
        } catch {}
      }
    }
    // Finalize
    bodyEl.classList.remove('popout-streaming');
    bodyEl.innerHTML = markdownModule.mdToHtml(accum) || '<span style="opacity:.5">(empty response)</span>';
    if (window.hljs) bodyEl.querySelectorAll('pre code').forEach(b => window.hljs.highlightElement(b));
    // Update label with model name from response
    const labelEl = aiDiv.querySelector('.popout-msg-label');
    if (labelEl && accum) {
      try {
        const meta = await fetch(`${API}/api/history/${sessionId}`).then(r => r.json());
        const last = (meta.history || []).filter(m => m.role === 'assistant').pop();
        if (last && last.model) labelEl.textContent = last.model;
      } catch {}
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      bodyEl.innerHTML = `<span style="color:var(--err)">Error: ${esc(String(e))}</span>`;
    }
  } finally {
    sendBtn.disabled = false;
    state.abortCtrl = null;
    histEl.scrollTop = histEl.scrollHeight;
  }
}

function closePopOut(sessionId) {
  const state = _popouts.get(sessionId);
  if (!state) return;
  if (state.abortCtrl) state.abortCtrl.abort();
  if (state.modal) state.modal.remove();
  _clearChip(state);
  _popouts.delete(sessionId);
}

function isPopOut(sessionId) { return _popouts.has(sessionId); }

// ═══════════════════════════════════════════════════════════════════════════
//  3.  STYLES (injected once)
// ═══════════════════════════════════════════════════════════════════════════

function _injectStyle() {
  if (document.getElementById('chat-float-style')) return;
  const s = document.createElement('style');
  s.id = 'chat-float-style';
  s.textContent = `
/* ── Main float ── */
.chat-container.chat-floated {
  position: fixed !important;
  z-index: 9990;
  width: 520px;
  max-width: 92vw;
  height: 70vh;
  min-height: 320px;
  min-width: 320px;
  margin: 0 !important;
  padding: 0 !important;
  border-radius: 14px;
  border: 1px solid var(--sep-2, rgba(255,255,255,.14));
  background: var(--surface, var(--bg, #15171c));
  box-shadow: 0 16px 48px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.06);
  overflow: hidden;
  resize: both;
  flex: none !important;
}
.chat-container.chat-floated .chat-top-bar {
  cursor: move;
  user-select: none;
  border-bottom: 1px solid var(--sep, rgba(255,255,255,.1));
  padding: 8px 12px 6px !important;
  background: var(--surface-2, var(--tint-2, rgba(255,255,255,.04)));
}
.chat-float-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  color: var(--faint, #777);
  font-size: 13px;
  font-style: italic;
}
.chat-float-btn {
  background: transparent;
  border: none;
  color: var(--dim, #aaa);
  cursor: pointer;
  padding: 3px 5px;
  border-radius: 5px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  margin-left: 4px;
}
.chat-float-btn:hover {
  background: var(--tint-2, rgba(255,255,255,.1));
  color: var(--txt, #fff);
}

/* ── Pop-out session windows ── */
.popout-chat-content {
  width: 460px;
  max-width: 92vw;
  height: 520px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.popout-chat-header {
  cursor: move;
}
.popout-chat-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.popout-chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.popout-history {
  flex: 1;
  overflow-y: auto;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.popout-msg {
  max-width: 88%;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  word-wrap: break-word;
  border: 1px solid var(--sep);
}
.popout-msg-user {
  align-self: flex-end;
  background: color-mix(in srgb, var(--cyan) 14%, transparent);
  border-color: color-mix(in srgb, var(--cyan) 30%, transparent);
  border-radius: 12px 12px 4px 12px;
}
.popout-msg-ai {
  align-self: flex-start;
  background: var(--tint);
  border-radius: 12px 12px 12px 4px;
}
.popout-msg-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--faint);
  margin-bottom: 2px;
  font-weight: 600;
}
.popout-msg-user .popout-msg-label { color: var(--cyan); }
.popout-msg-ai .popout-msg-label { color: var(--brass, var(--accent)); }
.popout-msg-body { white-space: pre-wrap; }
.popout-msg-body pre { max-height: 200px; overflow: auto; }
.popout-msg-body p { margin: 0 0 6px; }
.popout-msg-body p:last-child { margin-bottom: 0; }
@keyframes popout-blink { 0%,100%{opacity:1} 50%{opacity:0} }
.popout-cursor { animation: popout-blink .6s step-end infinite; color: var(--accent); }
.popout-compose {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  border-top: 1px solid var(--sep);
  padding: 10px 14px;
}
.popout-input {
  flex: 1;
  background: var(--tint);
  color: var(--txt);
  border: 1px solid var(--sep-2);
  border-radius: 8px;
  padding: 8px 10px;
  font: 13px/1.4 inherit;
  outline: none;
  resize: none;
  min-height: 24px;
  max-height: 120px;
}
.popout-input:focus { border-color: var(--brass, var(--accent)); }
.popout-send {
  background: var(--brass, var(--accent));
  color: #0b0b0d;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font: 600 12px/1 inherit;
  cursor: pointer;
  flex-shrink: 0;
}
.popout-send:disabled { opacity: .45; cursor: default; }

/* ── Pop-out button on sidebar session items ── */
.session-popout-btn {
  background: transparent;
  border: none;
  color: var(--faint);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity .15s;
  flex-shrink: 0;
  line-height: 1;
}
.list-item:hover .session-popout-btn,
.list-item.active-session .session-popout-btn {
  opacity: .6;
}
.session-popout-btn:hover { opacity: 1 !important; color: var(--accent); }
`;
  document.head.appendChild(s);
}

// ═══════════════════════════════════════════════════════════════════════════
//  4.  SIDEBAR WIRING  — inject pop-out buttons onto session items
// ═══════════════════════════════════════════════════════════════════════════

function _injectPopoutButtons() {
  const observer = new MutationObserver(() => {
    document.querySelectorAll('.list-item[data-session-id]:not([data-popout-wired])').forEach(el => {
      el.dataset.popoutWired = '1';
      const sid = el.dataset.sessionId;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'session-popout-btn';
      btn.title = 'Open in floating window';
      btn.innerHTML = POPOUT_ICON;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const name = el.querySelector('.grow')?.textContent || el.textContent.trim();
        popOut(sid, name);
      });
      el.appendChild(btn);
    });
  });

  const sessionList = document.getElementById('session-list');
  if (sessionList) {
    observer.observe(sessionList, { childList: true, subtree: true });
    // Wire existing items on init
    observer.takeRecords();
    document.querySelectorAll('.list-item[data-session-id]:not([data-popout-wired])').forEach(el => {
      el.dataset.popoutWired = '1';
      const sid = el.dataset.sessionId;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'session-popout-btn';
      btn.title = 'Open in floating window';
      btn.innerHTML = POPOUT_ICON;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const name = el.querySelector('.grow')?.textContent || el.textContent.trim();
        popOut(sid, name);
      });
      el.appendChild(btn);
    });
  }
}

// ═══════════════════════════════════════════════════════════════════════════
//  5.  INIT
// ═══════════════════════════════════════════════════════════════════════════

function init() {
  _injectStyle();

  // Float/pin button in chat top bar
  const metaOverlay = document.querySelector('.chat-meta-overlay');
  if (metaOverlay) {
    _btn = document.createElement('button');
    _btn.type = 'button';
    _btn.className = 'chat-float-btn';
    _btn.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });
    const exportWrap = document.getElementById('export-dropdown-wrap');
    if (exportWrap) metaOverlay.insertBefore(_btn, exportWrap);
    else metaOverlay.appendChild(_btn);
    _updateBtn();
  }

  // Restore float state
  try {
    if (localStorage.getItem(LS_KEY) === '1') {
      requestAnimationFrame(() => doFloat());
    }
  } catch {}

  // Inject pop-out buttons on sidebar session items
  _injectPopoutButtons();
}

export { init, doFloat, doPin, toggle, popOut, closePopOut, isPopOut };
export default { init, doFloat, doPin, toggle, popOut, closePopOut, isPopOut };
