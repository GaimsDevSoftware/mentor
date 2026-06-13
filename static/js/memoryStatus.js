/*
 * memoryStatus.js — live VRAM + system-RAM indicator for the Mentor sidebar,
 * a red near-full top banner, and a "Frigjør minne" button that opens a
 * checklist of loaded Ollama models to unload.
 *
 * Polls /api/sysmem/status. Sits next to the Self-coder traffic-light and
 * mirrors its self-contained, CSP-safe style (element.style + Web Animations
 * API, no inline handlers, no CSS file, defensive about missing DOM).
 *
 *   green  = ok    (< warn threshold)
 *   amber  = warn  (>= 80% used)  -> sidebar dot + soft top banner
 *   red    = crit  (>= 92% used)  -> sidebar dot pulses + red top banner
 */
(() => {
  const STATUS = '/api/sysmem/status';
  const FREE = '/api/sysmem/free';
  const POLL_MS = 5000;

  const COLORS = { ok: '#22c55e', warn: '#f59e0b', crit: '#ef4444',
                   idle: 'var(--faint, #8a8a8a)' };

  let _lastLevel = 'ok';
  let _bannerDismissedAt = 'none'; // track which level the user dismissed

  // ── small helpers ──────────────────────────────────────────────
  function _el(tag, style, text) {
    const e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (text != null) e.textContent = text;
    return e;
  }
  function _bar(pct, color) {
    const wrap = _el('span',
      'display:inline-block;width:34px;height:6px;border-radius:3px;'
      + 'background:var(--border,#333);overflow:hidden;vertical-align:middle;');
    const fill = _el('span',
      `display:block;height:100%;width:${Math.min(100, pct || 0)}%;`
      + `background:${color};transition:width .4s ease,background .4s ease;`);
    wrap.appendChild(fill);
    return wrap;
  }

  // ── sidebar pill ───────────────────────────────────────────────
  function _ensurePill() {
    let pill = document.getElementById('mem-status-pill');
    if (pill) return pill;
    const host = document.querySelector('.sidebar-inner') || document.getElementById('sidebar');
    if (!host) return null;
    pill = _el('div',
      'display:flex;align-items:center;gap:7px;margin:6px 8px;padding:5px 8px;'
      + 'border-radius:8px;cursor:pointer;font-size:11px;color:var(--fg,#ddd);'
      + 'border:1px solid var(--border,#333);background:var(--panel,#16181d);'
      + 'user-select:none;');
    pill.id = 'mem-status-pill';
    pill.title = 'Minnebruk (VRAM + RAM) — klikk for å frigjøre minne';

    const dot = _el('span',
      'width:8px;height:8px;border-radius:50%;flex-shrink:0;background:'
      + COLORS.idle + ';transition:background .3s ease;');
    dot.id = 'mem-status-dot';

    const body = _el('span', 'display:flex;flex-direction:column;gap:3px;flex:1;min-width:0;');
    body.id = 'mem-status-body';

    pill.appendChild(dot);
    pill.appendChild(body);
    pill.addEventListener('click', openModal);
    host.appendChild(pill);
    return pill;
  }

  function _row(label, block) {
    const r = _el('span', 'display:flex;align-items:center;gap:6px;white-space:nowrap;');
    r.appendChild(_el('span', 'width:30px;color:var(--faint,#9aa);', label));
    if (!block) { r.appendChild(_el('span', 'color:var(--faint,#9aa);', 'n/a')); return r; }
    const color = block.pct >= 92 ? COLORS.crit : block.pct >= 80 ? COLORS.warn : COLORS.ok;
    r.appendChild(_bar(block.pct, color));
    r.appendChild(_el('span', 'color:var(--fg,#ddd);min-width:30px;', block.pct + '%'));
    r.appendChild(_el('span', 'color:var(--faint,#9aa);font-size:10px;',
      `${block.used_gb}/${block.total_gb}G`));
    return r;
  }

  function _pulse(dot, on) {
    if (dot._anim) { try { dot._anim.cancel(); } catch {} dot._anim = null; }
    if (on && dot.animate) {
      dot._anim = dot.animate(
        [{ opacity: 1, transform: 'scale(1)' },
         { opacity: 0.4, transform: 'scale(0.82)' },
         { opacity: 1, transform: 'scale(1)' }],
        { duration: 1000, iterations: Infinity, easing: 'ease-in-out' });
    } else { dot.style.opacity = '1'; }
  }

  function _paintPill(st) {
    const pill = _ensurePill();
    if (!pill) return;
    const dot = document.getElementById('mem-status-dot');
    const body = document.getElementById('mem-status-body');
    const color = COLORS[st.level] || COLORS.idle;
    dot.style.background = color;
    dot.style.boxShadow = st.level === 'crit' ? '0 0 6px 1px rgba(239,68,68,.7)'
      : st.level === 'warn' ? '0 0 5px 1px rgba(245,158,11,.6)' : 'none';
    _pulse(dot, st.level === 'crit');
    body.replaceChildren(_row('VRAM', st.vram), _row('RAM', st.ram));
    pill.title = `VRAM ${st.vram ? st.vram.pct + '%' : 'n/a'} · RAM ${st.ram ? st.ram.pct + '%' : 'n/a'}`
      + ' — klikk for å frigjøre minne';
  }

  // ── top banner ─────────────────────────────────────────────────
  function _banner() {
    let b = document.getElementById('mem-banner');
    if (b) return b;
    b = _el('div',
      'position:fixed;top:0;left:0;right:0;z-index:9000;display:none;'
      + 'align-items:center;justify-content:center;gap:14px;padding:8px 16px;'
      + 'font-size:13px;font-weight:600;color:#fff;'
      + 'box-shadow:0 2px 10px rgba(0,0,0,.35);');
    b.id = 'mem-banner';
    const msg = _el('span'); msg.id = 'mem-banner-msg';
    const free = _el('button',
      'border:none;border-radius:6px;padding:5px 12px;cursor:pointer;'
      + 'font-weight:700;font-size:12px;background:rgba(255,255,255,.95);color:#111;');
    free.textContent = 'Frigjør minne';
    free.addEventListener('click', openModal);
    const x = _el('button',
      'border:none;background:transparent;color:#fff;cursor:pointer;'
      + 'font-size:18px;line-height:1;padding:0 4px;', '×');
    x.title = 'Skjul';
    x.addEventListener('click', () => { _bannerDismissedAt = _lastLevel; b.style.display = 'none'; });
    b.appendChild(msg); b.appendChild(free); b.appendChild(x);
    document.body.appendChild(b);
    return b;
  }

  function _paintBanner(st) {
    const b = _banner();
    if (st.level === 'ok') { b.style.display = 'none'; _bannerDismissedAt = 'none'; return; }
    // Re-show if severity escalated since the user dismissed it.
    if (_bannerDismissedAt === st.level) { b.style.display = 'none'; return; }
    if (st.level === 'warn' && _bannerDismissedAt === 'crit') { /* already saw worse */ }
    b.style.background = st.level === 'crit'
      ? 'linear-gradient(90deg,#dc2626,#ef4444)'
      : 'linear-gradient(90deg,#d97706,#f59e0b)';
    const which = (st.vram && st.vram.pct >= st.ram?.pct ? 'GPU-minnet (VRAM)' : 'systemminnet (RAM)');
    const pct = st.worst_pct;
    document.getElementById('mem-banner-msg').textContent =
      st.level === 'crit'
        ? `⚠ ${which} er nesten fullt (${pct}%) — frigjør minne for å unngå at modeller faller til CPU.`
        : `${which} fyller seg opp (${pct}%).`;
    b.style.display = 'flex';
  }

  // ── free-memory modal ──────────────────────────────────────────
  async function openModal() {
    let st;
    try { st = await (await fetch(STATUS, { headers: { Accept: 'application/json' } })).json(); }
    catch { st = null; }
    const models = (st && st.models) || [];

    const overlay = _el('div',
      'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.5);'
      + 'display:flex;align-items:center;justify-content:center;');
    const card = _el('div',
      'background:var(--panel,#16181d);color:var(--fg,#eee);border:1px solid var(--border,#333);'
      + 'border-radius:12px;padding:18px 20px;min-width:360px;max-width:480px;'
      + 'box-shadow:0 12px 40px rgba(0,0,0,.5);font-size:13px;');
    card.appendChild(_el('div',
      'font-size:15px;font-weight:700;margin-bottom:4px;', 'Frigjør minne'));
    const sub = st && (st.vram || st.ram)
      ? `VRAM ${st.vram ? st.vram.pct + '%' : 'n/a'} · RAM ${st.ram ? st.ram.pct + '%' : 'n/a'}`
      : 'Kunne ikke lese minnestatus.';
    card.appendChild(_el('div', 'color:var(--faint,#9aa);margin-bottom:12px;', sub));

    const list = _el('div', 'display:flex;flex-direction:column;gap:6px;max-height:260px;overflow:auto;');
    const checks = [];
    if (!models.length) {
      list.appendChild(_el('div', 'color:var(--faint,#9aa);padding:8px 0;',
        'Ingen modeller er lastet i Ollama akkurat nå.'));
    }
    models.forEach((m) => {
      const row = _el('label',
        'display:flex;align-items:center;gap:9px;padding:7px 9px;border-radius:8px;'
        + 'border:1px solid var(--border,#333);cursor:pointer;');
      const cb = _el('input'); cb.type = 'checkbox'; cb.value = m.name; cb.style.cssText = 'cursor:pointer;';
      checks.push(cb);
      const info = _el('span', 'display:flex;flex-direction:column;gap:1px;flex:1;');
      info.appendChild(_el('span', 'font-weight:600;', m.name));
      const onGpu = (m.processor || '').includes('GPU');
      info.appendChild(_el('span', 'color:var(--faint,#9aa);font-size:11px;',
        `${(m.size_mb / 1024).toFixed(1)} GB · ${m.processor}`));
      row.appendChild(cb); row.appendChild(info);
      const tag = _el('span',
        `font-size:10px;padding:2px 7px;border-radius:10px;`
        + `background:${onGpu ? 'rgba(34,197,94,.18)' : 'rgba(245,158,11,.18)'};`
        + `color:${onGpu ? '#22c55e' : '#f59e0b'};`, onGpu ? 'VRAM' : m.processor);
      row.appendChild(tag);
      list.appendChild(row);
    });
    card.appendChild(list);

    const btns = _el('div', 'display:flex;justify-content:flex-end;gap:8px;margin-top:16px;');
    const cancel = _el('button',
      'border:1px solid var(--border,#333);background:transparent;color:var(--fg,#ddd);'
      + 'border-radius:7px;padding:7px 14px;cursor:pointer;', 'Avbryt');
    cancel.addEventListener('click', () => overlay.remove());
    const go = _el('button',
      'border:none;border-radius:7px;padding:7px 14px;cursor:pointer;font-weight:700;'
      + 'background:#ef4444;color:#fff;', 'Frigjør valgte');
    if (!models.length) { go.disabled = true; go.style.opacity = '.5'; go.style.cursor = 'default'; }
    go.addEventListener('click', async () => {
      const picked = checks.filter((c) => c.checked).map((c) => c.value);
      if (!picked.length) { go.textContent = 'Velg minst én ↑'; return; }
      go.disabled = true; go.textContent = 'Frigjør…';
      try {
        const r = await fetch(FREE, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ models: picked }),
        });
        const res = await r.json();
        overlay.remove();
        if (res && res.status) { _paintPill(res.status); _paintBanner(res.status); _lastLevel = res.status.level; }
        else { _tick(); }
      } catch {
        go.disabled = false; go.textContent = 'Feilet — prøv igjen';
      }
    });
    btns.appendChild(cancel); btns.appendChild(go);
    card.appendChild(btns);

    overlay.appendChild(card);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.addEventListener('keydown', function esc(ev) {
      if (ev.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', esc); }
    });
    document.body.appendChild(overlay);
  }

  // ── poll loop ──────────────────────────────────────────────────
  async function _tick() {
    try {
      const r = await fetch(STATUS, { headers: { Accept: 'application/json' } });
      if (!r.ok) return;
      const st = await r.json();
      _paintPill(st);
      _paintBanner(st);
      _lastLevel = st.level;
    } catch { /* network hiccup — keep last paint */ }
  }

  function _start() { _tick(); setInterval(_tick, POLL_MS); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _start);
  } else { _start(); }
})();
