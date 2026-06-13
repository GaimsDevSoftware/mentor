/*
 * selfCoderStatus.js — sidebar traffic-light for the Self-coder engine.
 *
 * Polls /api/plugins/self_coder/status and paints a colored dot on the
 * sidebar "Self-coder" item (and the rail wrench icon) so you can tell at a
 * glance whether the autonomous coder is idle, working, stuck, failed, or done
 * — without opening the panel. Hover the dot for the live detail.
 *
 *   grey   = idle (nothing running)
 *   blue   = working (aider is producing output)  · pulsing
 *   amber  = STALLED — no output for a while, may be stuck · pulsing
 *   red    = failed (incl. killed after the hard timeout)
 *   green  = verified / applied (a change is ready or landed)
 *
 * Fully self-contained: no imports, no CSS file (uses element.style + the Web
 * Animations API so it stays CSP-safe), defensive about missing DOM.
 */
(() => {
  const ENDPOINT = '/api/plugins/self_coder/status';
  const POLL_MS = 4000;

  const COLORS = {
    idle:  'var(--faint, #8a8a8a)',
    blue:  '#3b82f6',
    amber: '#f59e0b',
    red:   '#ef4444',
    green: '#22c55e',
  };

  function _mkDot(size) {
    const d = document.createElement('span');
    d.className = 'sc-status-dot';
    d.style.display = 'inline-block';
    d.style.width = size + 'px';
    d.style.height = size + 'px';
    d.style.borderRadius = '50%';
    d.style.flexShrink = '0';
    d.style.background = COLORS.idle;
    d.style.transition = 'background 0.3s ease';
    d.style.boxShadow = '0 0 0 0 transparent';
    d._anim = null;
    return d;
  }

  // Sidebar list-item dot (right-aligned via the existing .grow span) + a small
  // overlay dot on the compact rail icon.
  function _ensureDots() {
    const dots = [];
    const side = document.getElementById('tool-selfcoder-btn');
    if (side && !side.querySelector('.sc-status-dot')) {
      const d = _mkDot(8);
      d.style.marginLeft = '6px';
      d.style.alignSelf = 'center';
      side.appendChild(d);
    }
    if (side) dots.push(side.querySelector('.sc-status-dot'));

    const rail = document.getElementById('rail-selfcoder');
    if (rail && !rail.querySelector('.sc-status-dot')) {
      if (getComputedStyle(rail).position === 'static') rail.style.position = 'relative';
      const d = _mkDot(7);
      d.style.position = 'absolute';
      d.style.top = '3px';
      d.style.right = '3px';
      d.style.border = '1px solid var(--bg, #1c1c1c)';
      rail.appendChild(d);
    }
    if (rail) dots.push(rail.querySelector('.sc-status-dot'));
    return dots.filter(Boolean);
  }

  function _pulse(dot, on, fast) {
    if (dot._anim) { try { dot._anim.cancel(); } catch {} dot._anim = null; }
    if (on && dot.animate) {
      dot._anim = dot.animate(
        [{ opacity: 1, transform: 'scale(1)' },
         { opacity: 0.35, transform: 'scale(0.82)' },
         { opacity: 1, transform: 'scale(1)' }],
        { duration: fast ? 900 : 1500, iterations: Infinity, easing: 'ease-in-out' });
    } else {
      dot.style.opacity = '1';
    }
  }

  function _ageText(s) {
    if (s == null) return '';
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    return `${Math.round(s / 3600)}h ago`;
  }

  function _label(st) {
    const map = {
      idle: 'Self-coder: idle',
      blue: 'Self-coder: working…',
      amber: 'Self-coder: STALLED — may be stuck',
      red: 'Self-coder: failed',
      green: 'Self-coder: change ready/applied',
    };
    const base = map[st.light] || `Self-coder: ${st.state || 'unknown'}`;
    const bits = [base];
    if (st.instruction) bits.push(`“${st.instruction}”`);
    if (st.age_seconds != null && st.active) bits.push(`last activity ${_ageText(st.age_seconds)}`);
    if (st.light === 'red' && st.detail) bits.push(st.detail);
    return bits.join(' · ');
  }

  function _paint(dots, st) {
    const color = COLORS[st.light] || COLORS.idle;
    const pulsing = st.light === 'blue' || st.light === 'amber';
    const title = _label(st);
    dots.forEach((d) => {
      d.style.background = color;
      if (st.light === 'amber') d.style.boxShadow = '0 0 6px 1px rgba(245,158,11,0.7)';
      else if (st.light === 'red') d.style.boxShadow = '0 0 5px 1px rgba(239,68,68,0.6)';
      else d.style.boxShadow = '0 0 0 0 transparent';
      d.title = title;
      _pulse(d, pulsing, st.light === 'amber');
    });
    // also surface on the parent so the whole row has a tooltip
    const side = document.getElementById('tool-selfcoder-btn');
    if (side) side.title = title;
  }

  async function _tick() {
    const dots = _ensureDots();
    if (!dots.length) return;
    try {
      const r = await fetch(ENDPOINT, { headers: { 'Accept': 'application/json' } });
      if (!r.ok) return;
      const st = await r.json();
      _paint(dots, st);
    } catch {
      /* network hiccup — leave the last known color */
    }
  }

  function _start() {
    _tick();
    setInterval(_tick, POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _start);
  } else {
    _start();
  }
})();
