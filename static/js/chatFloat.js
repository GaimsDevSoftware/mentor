/**
 * chatFloat.js — float / pin toggle for chat sessions.
 *
 * "Float" detaches the chat-container from the normal page flow and turns it
 * into a draggable, resizable overlay window.  "Pin" snaps it back.
 *
 * Uses makeWindowDraggable from windowDrag.js (same helper the tool modals use).
 */

import { makeWindowDraggable } from './windowDrag.js';

const LS_KEY = 'ody-chat-floated';

let _floated = false;
let _btn = null;

// SVGs
const FLOAT_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>`;
const PIN_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16h14v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>`;

function _getContainer() { return document.getElementById('chat-container'); }
function _getTopBar()    { return document.querySelector('.chat-top-bar'); }

function _injectStyle() {
  if (document.getElementById('chat-float-style')) return;
  const s = document.createElement('style');
  s.id = 'chat-float-style';
  s.textContent = `
/* ── Floated chat ── */
.chat-container.chat-floated {
  position: fixed !important;
  z-index: 9990;
  width: 520px;
  max-width: 92vw;
  height: 70vh;
  min-height: 320px;
  min-width: 320px;
  top: 60px;
  right: 60px;
  left: auto !important;
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
/* Placeholder that keeps the normal flow occupied */
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
/* Float/pin button */
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
`;
  document.head.appendChild(s);
}

function _createPlaceholder() {
  const ph = document.createElement('div');
  ph.id = 'chat-float-placeholder';
  ph.className = 'chat-float-placeholder';
  ph.innerHTML = '<span>Chat is floating — click <b>pin</b> to return it here</span>';
  return ph;
}

function doFloat() {
  if (_floated) return;
  const container = _getContainer();
  const topBar = _getTopBar();
  if (!container) return;
  _floated = true;

  // Insert placeholder in the container's original position
  const ph = _createPlaceholder();
  container.parentElement.insertBefore(ph, container);

  // Float
  container.classList.add('chat-floated');

  // Make draggable via the top bar
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

  // Remove floating styles and inline positioning from drag
  container.classList.remove('chat-floated');
  container.style.position = '';
  container.style.top = '';
  container.style.left = '';
  container.style.right = '';
  container.style.width = '';
  container.style.height = '';
  container.style.transform = '';
  container.style.zIndex = '';

  // Remove placeholder
  const ph = document.getElementById('chat-float-placeholder');
  if (ph) ph.remove();

  // Reset the top bar cursor (makeWindowDraggable set it to 'move')
  const topBar = _getTopBar();
  if (topBar) { topBar.style.cursor = ''; topBar.style.userSelect = ''; }

  _updateBtn();
  try { localStorage.removeItem(LS_KEY); } catch {}
}

function toggle() {
  if (_floated) doPin();
  else doFloat();
}

function _updateBtn() {
  if (!_btn) return;
  if (_floated) {
    _btn.innerHTML = PIN_ICON;
    _btn.title = 'Pin chat back to page';
  } else {
    _btn.innerHTML = FLOAT_ICON;
    _btn.title = 'Float chat as window';
  }
}

/** Call once after the DOM is ready. */
function init() {
  _injectStyle();

  // Create the button and insert it into the chat top bar
  const metaOverlay = document.querySelector('.chat-meta-overlay');
  if (!metaOverlay) return;

  _btn = document.createElement('button');
  _btn.type = 'button';
  _btn.className = 'chat-float-btn';
  _btn.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });

  // Insert before the export dropdown
  const exportWrap = document.getElementById('export-dropdown-wrap');
  if (exportWrap) {
    metaOverlay.insertBefore(_btn, exportWrap);
  } else {
    metaOverlay.appendChild(_btn);
  }

  _updateBtn();

  // Restore float state from localStorage
  try {
    if (localStorage.getItem(LS_KEY) === '1') {
      requestAnimationFrame(() => doFloat());
    }
  } catch {}
}

export { init, doFloat, doPin, toggle };
export default { init, doFloat, doPin, toggle };
