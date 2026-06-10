// turnManager.js — single source of truth for chat turn lifecycle + queue.
//
// Phase 2 of the queue redesign. Before this, chat.js tracked turn state
// across ~11 module-level flags (isStreaming, _draining, _sendInFlight,
// _streamSawDone, _streamShouldStop, _msgQueue, _activeTurnText, …). Forgetting
// to reset one in any of the many error/abort/background paths left the queue
// wedged — the entire class of bugs we kept chasing.
//
// TurnManager owns the authoritative streaming flag, the message queue, the
// drain lock, and the stream-activity clock. Every place that used to flip
// isStreaming now flips it HERE; every transition out of streaming schedules a
// drain automatically, so the queue can never be stranded by a path that
// "forgot" to drain. chat.js keeps the DOM-coupled bits (rendering the queue
// bar, actually submitting the next message) and registers them as callbacks.
//
// Design notes:
//  - `queue` is a plain array, shared BY REFERENCE with chat.js's `_msgQueue`,
//    so the existing splice/shift/length call sites keep working unchanged.
//  - This is per-SPA-instance state. Each floating popup window is its own
//    instance with its own TurnManager — intentional isolation (Phase 5 adds
//    opt-in cross-window messaging on top, not shared state).

function createTurnManager() {
  const listeners = Object.create(null); // event name -> Set<fn>
  const queue = [];                      // {text, attachments?, priority?, _resumed?}

  let streaming = false;     // authoritative: is a turn's stream live right now?
  let draining = false;      // re-entrancy lock while auto-sending the next item
  let lastActivity = 0;      // ms timestamp of the last stream event (reader read)
  let drainExecutor = null;  // chat.js sets this: (item) => Promise|void — submits
  let drainTimer = null;     // coalesces multiple scheduleDrain() calls into one

  function on(evt, fn) {
    (listeners[evt] || (listeners[evt] = new Set())).add(fn);
    return () => { const s = listeners[evt]; if (s) s.delete(fn); };
  }
  function emit(evt, payload) {
    const s = listeners[evt];
    if (!s) return;
    for (const fn of Array.from(s)) {
      try { fn(payload); } catch (e) { console.error(`[turnManager] listener for ${evt} threw`, e); }
    }
  }

  // ── Streaming authority ──────────────────────────────────────────────────
  function setStreaming(v) {
    v = !!v;
    if (streaming === v) return;
    streaming = v;
    if (streaming) {
      lastActivity = Date.now();
    }
    emit('streaming-changed', streaming);
    // Leaving the streaming state is the ONE canonical drain trigger. Every
    // path that ends a turn — normal [DONE], abort, error, stall, background
    // completion — funnels through here, so the queue always gets a chance to
    // advance without each path remembering to call drain itself.
    if (!streaming) scheduleDrain();
  }
  function isStreaming() { return streaming; }

  // ── Stream-activity clock (for the stall watchdog) ───────────────────────
  function markActivity() { lastActivity = Date.now(); }
  function quietMs() { return lastActivity ? (Date.now() - lastActivity) : 0; }

  // ── Queue operations ─────────────────────────────────────────────────────
  function enqueue(item, opts) {
    const priority = !!(opts && opts.priority);
    if (priority) queue.unshift(item); else queue.push(item);
    emit('queue-changed', queue);
    if (!streaming) scheduleDrain();
  }
  function removeAt(idx) {
    if (idx < 0 || idx >= queue.length) return;
    queue.splice(idx, 1);
    emit('queue-changed', queue);
  }
  function prioritize(idx) {
    if (idx <= 0 || idx >= queue.length) return;
    queue.unshift(queue.splice(idx, 1)[0]);
    emit('queue-changed', queue);
  }
  function has(predicate) { return queue.some(predicate); }
  function size() { return queue.length; }
  function clear() {
    if (!queue.length) return;
    queue.length = 0;
    emit('queue-changed', queue);
  }
  function notifyChanged() { emit('queue-changed', queue); }

  // ── Draining ─────────────────────────────────────────────────────────────
  function setDrainExecutor(fn) { drainExecutor = fn; }

  function scheduleDrain() {
    if (drainTimer) return;
    drainTimer = setTimeout(() => { drainTimer = null; drain(); }, 0);
  }

  function drain() {
    if (draining || streaming || queue.length === 0 || !drainExecutor) return;
    draining = true;
    try {
      const next = queue.shift();
      emit('queue-changed', queue);
      // Executor is synchronous (fill composer + form.requestSubmit()). We
      // deliberately do NOT await it: requestSubmit() kicks off the next turn
      // synchronously, which flips streaming back to true, so the lock only
      // needs to cover this synchronous span. Resetting `draining` in a sync
      // finally (no await) means an exception or a quirky environment can
      // never leave the lock stuck true and wedge the queue.
      drainExecutor(next);
    } catch (e) {
      console.error('[turnManager] drain executor threw', e);
    } finally {
      draining = false;
    }
  }

  function isDraining() { return draining; }

  // Periodic safety net: if we're idle (not streaming, not draining, not
  // mid-send) but the queue has items, force a drain. Catches any exotic path
  // that ended a turn without going through setStreaming(false) — belt to the
  // setStreaming suspenders.
  function startSafetyDrain(isSendInFlight) {
    return setInterval(() => {
      if (queue.length === 0 || streaming || draining) return;
      if (typeof isSendInFlight === 'function' && isSendInFlight()) return;
      console.warn('[turnManager] safety drain — stranded queue of', queue.length);
      scheduleDrain();
    }, 2000);
  }

  return {
    queue,
    on, emit,
    setStreaming, isStreaming,
    markActivity, quietMs,
    enqueue, removeAt, prioritize, has, size, clear, notifyChanged,
    setDrainExecutor, scheduleDrain, drain, isDraining,
    startSafetyDrain,
  };
}

const turnManager = createTurnManager();
export default turnManager;
export { createTurnManager };
