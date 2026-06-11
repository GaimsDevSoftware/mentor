// popup-chat.js — in-app floating chat panels.
//
// Two roles, decided by URL on load:
//
//  - Main window (no ?popup= in URL): wire the "↗" icon next to "New Chat"
//    so clicking it spawns a draggable floating chat panel INSIDE the main
//    Mentor window — not a separate OS window. Each panel is an <iframe>
//    pointed at /?popup=1, so the existing chat code "just works" inside
//    with its own session, queue, and stream. Multiple panels can stack.
//
//  - Popup window/iframe (?popup=1 in URL): switch to popup-mode chrome
//    (sidebar + topbar hidden, chat fills the frame). No tab bar here —
//    one chat per floating panel keeps state simple; users open more
//    panels by clicking "↗" again.

const isPopupMode = () =>
  new URLSearchParams(window.location.search).has('popup');

// ── Main window: trigger + floating panel ──────────────────────────────────
function setupTrigger() {
  const btn = document.getElementById('sidebar-popup-btn');
  if (!btn) return;
  btn.addEventListener('click', (e) => {
    // The popup btn lives inside the New Chat row; stop the row's default
    // "create new chat in THIS window" handler from also firing.
    e.stopPropagation();
    e.preventDefault();
    spawnFloatingChat();
  });
}

let _topZ = 1000;
let _spawnCount = 0;

function spawnFloatingChat() {
  const wrap = document.createElement('div');
  wrap.className = 'chat-popup-window';
  // Stagger placement so multiple popups don't sit exactly on top of each other.
  const offset = (_spawnCount++ % 6) * 28;
  const width = 460;
  const height = 680;
  // Anchor to upper-right of the viewport with stagger; clamp to viewport.
  const left = Math.max(20, window.innerWidth - width - 40 - offset);
  const top = Math.max(20, 60 + offset);
  wrap.style.left = left + 'px';
  wrap.style.top = top + 'px';
  wrap.style.width = width + 'px';
  wrap.style.height = height + 'px';
  wrap.style.zIndex = ++_topZ;

  // Title bar: drag handle, label, close.
  const bar = document.createElement('div');
  bar.className = 'chat-popup-titlebar';
  const grip = document.createElement('div');
  grip.className = 'chat-popup-grip';
  grip.innerHTML = '<span></span><span></span><span></span>';
  bar.appendChild(grip);
  const title = document.createElement('span');
  title.className = 'chat-popup-title';
  title.textContent = 'New chat';
  bar.appendChild(title);
  const closeBtn = document.createElement('button');
  closeBtn.className = 'chat-popup-close';
  closeBtn.title = 'Close';
  closeBtn.setAttribute('aria-label', 'Close popup chat');
  closeBtn.textContent = '×';
  closeBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    wrap.remove();
  });
  bar.appendChild(closeBtn);
  wrap.appendChild(bar);

  // Iframe with chat-only popup mode.
  const iframe = document.createElement('iframe');
  iframe.className = 'chat-popup-iframe';
  iframe.src = '/?popup=1';
  iframe.title = 'Chat popup';
  // The iframe needs same-origin + scripts to run the SPA; sandbox would
  // strip both. We rely on the existing auth cookie for access.
  wrap.appendChild(iframe);

  // Resize handle at bottom-right.
  const resize = document.createElement('div');
  resize.className = 'chat-popup-resize';
  wrap.appendChild(resize);

  document.body.appendChild(wrap);

  // Bring to front on any interaction with the panel.
  wrap.addEventListener('mousedown', () => bringToFront(wrap), true);

  attachDrag(wrap, bar);
  attachResize(wrap, resize);
  // Track session title from inside the iframe so the title bar reflects
  // what the user is actually chatting with.
  attachTitleSync(wrap, title, iframe);
}

function bringToFront(wrap) {
  wrap.style.zIndex = ++_topZ;
}

function attachDrag(wrap, handle) {
  let dragging = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;
  handle.addEventListener('mousedown', (e) => {
    // Ignore clicks on the close button — it has its own handler.
    if (e.target.closest('.chat-popup-close')) return;
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    startLeft = parseFloat(wrap.style.left || '0');
    startTop = parseFloat(wrap.style.top || '0');
    document.body.classList.add('chat-popup-dragging');
    e.preventDefault();
  });
  const onMove = (e) => {
    if (!dragging) return;
    // Clamp so the title bar can't be dragged fully off-screen.
    const nextLeft = Math.max(-wrap.offsetWidth + 80,
                              Math.min(window.innerWidth - 80,
                                       startLeft + e.clientX - startX));
    const nextTop = Math.max(0,
                             Math.min(window.innerHeight - 30,
                                      startTop + e.clientY - startY));
    wrap.style.left = nextLeft + 'px';
    wrap.style.top = nextTop + 'px';
  };
  const onUp = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('chat-popup-dragging');
  };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function attachResize(wrap, handle) {
  let resizing = false, startX = 0, startY = 0, startW = 0, startH = 0;
  handle.addEventListener('mousedown', (e) => {
    resizing = true;
    startX = e.clientX;
    startY = e.clientY;
    startW = wrap.offsetWidth;
    startH = wrap.offsetHeight;
    document.body.classList.add('chat-popup-dragging');
    e.preventDefault();
    e.stopPropagation();
  });
  const onMove = (e) => {
    if (!resizing) return;
    const w = Math.max(300, startW + (e.clientX - startX));
    const h = Math.max(280, startH + (e.clientY - startY));
    wrap.style.width = w + 'px';
    wrap.style.height = h + 'px';
  };
  const onUp = () => {
    if (!resizing) return;
    resizing = false;
    document.body.classList.remove('chat-popup-dragging');
  };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function attachTitleSync(wrap, titleEl, iframe) {
  // Poll the iframe for its current session title. Same-origin so we can
  // read its sessionModule directly. Stop polling when the panel goes away.
  const interval = setInterval(() => {
    if (!wrap.isConnected) { clearInterval(interval); return; }
    try {
      const w = iframe.contentWindow;
      if (!w || !w.sessionModule) return;
      const sid = w.sessionModule.getCurrentSessionId &&
                  w.sessionModule.getCurrentSessionId();
      if (!sid) return;
      const sessions = (w.sessionModule.getSessions &&
                        w.sessionModule.getSessions()) || [];
      const s = sessions.find(x => x && x.id === sid);
      if (s && s.title) {
        const t = String(s.title).slice(0, 40);
        if (titleEl.textContent !== t) titleEl.textContent = t;
      }
    } catch {
      // Cross-frame access errors stop us — rare on same origin, but ignore.
    }
  }, 2000);
}

// ── Iframe / popup-mode page: bare chat chrome ─────────────────────────────
function setupPopupChrome() {
  document.body.classList.add('popup-mode');
  // The CSS hides sidebar/topbar/etc. Everything else is just the regular
  // chat — composer, history, queue bar — running normally in its own
  // SPA instance. No tab bar in floating-panel mode; the host opens more
  // panels for more chats.
}

// ── Boot ───────────────────────────────────────────────────────────────────
function boot() {
  if (isPopupMode()) setupPopupChrome();
  else setupTrigger();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
