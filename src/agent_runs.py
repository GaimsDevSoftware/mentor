"""Detached agent-run manager.

Keeps an agent/chat stream running server-side after the SSE client disconnects
(tab close, navigate away, refresh). The streaming generator is drained by a
background asyncio task into a per-session replay buffer; SSE clients SUBSCRIBE
to that buffer (replay everything so far, then live). Closing the SSE only drops
the subscriber — the drain task keeps going.

The wrapped generator already persists the assistant message to the session on
completion, so reopening the session shows the finished result even if nobody
was connected when it finished. Reconnecting mid-run replays the buffer + streams
live (pick up where it is).

Durability scope: in-memory, survives as long as the server process runs (tab
close / navigation / refresh). It does NOT survive a server restart.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)

# ── SSE protocol contract ───────────────────────────────────────────────────
# Bumped when the event shape changes in a way clients must know about. Sent
# once per run in the opening `meta` event so a client can detect a server
# newer than itself and prompt a reload (Phase 1 of the queue redesign).
SSE_PROTOCOL_VERSION = 1

# The terminal sentinel every run MUST end with. The drain loop guarantees it
# is emitted exactly once, on every exit path (normal, error, cancel, or the
# upstream generator finishing WITHOUT sending it). Clients use this as the
# authoritative "this turn is over" signal — not the raw HTTP connection close,
# which the detached-run model can leave open while a slow upstream is still
# being awaited.
_DONE_EVENT = "data: [DONE]\n\n"

# If the wrapped generator produces NOTHING (no chunk, no completion) for this
# long, the run is considered wedged (upstream provider hung, dropped the
# socket without closing, model died mid-thought). The drain force-terminates
# and emits [DONE] so the client's turn state can settle and its queue drains.
# Generous so a cold on-demand model load or a long legitimate reasoning pass
# isn't killed — the client's own stall UX (nudge at 60s) fires first.
_RUN_IDLE_TIMEOUT_S = 300.0

# When a new run replaces an in-flight one (run-now / rapid re-send), the new
# run briefly waits for the previous one to finish cancelling so the two turns'
# session saves stay sequential rather than interleaved. That wait MUST be
# bounded: if the previous run's cancellation is wedged — e.g. its generator is
# deep in a long, not-promptly-interruptible tool call so aclose() doesn't
# return quickly — an unbounded wait blocks the NEW turn forever. The client
# subscribes to the new run, receives nothing, and sits on "Thinking…" until the
# conversation is restarted (the run-now stuck-state). Sequential saves are a
# nicety, not a correctness requirement (the previous run's own finally still
# persists its partial whenever it eventually unwinds), so past this timeout the
# new run proceeds regardless rather than stay wedged behind the old one.
_PREV_RUN_DRAIN_TIMEOUT_S = 8.0


class _Run:
    __slots__ = ("buffer", "subscribers", "status", "task", "evict_task", "run_id")

    def __init__(self, run_id: str = "") -> None:
        self.buffer: list = []          # ordered SSE event strings (replay log)
        self.subscribers: set = set()   # one asyncio.Queue per connected client
        self.status: str = "running"    # running | done | error | stopped
        self.task: Optional[asyncio.Task] = None
        self.evict_task: Optional[asyncio.Task] = None
        self.run_id: str = run_id       # stable id for this turn (SSE meta)


_RUNS: Dict[str, _Run] = {}

_run_counter = 0


def _next_run_id(session_id: str) -> str:
    """Monotonic per-process run id. Cheap, unique within a server lifetime,
    and good enough to disambiguate rapid re-sends on the same session.
    (Avoids time/random so it stays deterministic for tests.)"""
    global _run_counter
    _run_counter += 1
    return f"run-{_run_counter}"


def _meta_event(run_id: str, session_id: str) -> str:
    """The opening SSE event carrying the protocol contract. Older clients
    ignore unknown event types, so emitting this is backward compatible."""
    payload = {"type": "meta", "run_id": run_id, "session_id": session_id,
               "v": SSE_PROTOCOL_VERSION}
    return f"event: meta\ndata: {json.dumps(payload)}\n\n"

# How long a FINISHED run (and its full replay buffer) is retained after the
# last subscriber disconnects, so a reconnect within the window can still
# replay the result. After this, the run is evicted to bound memory — without
# it, every session that ever streamed kept its entire event log forever.
_EVICT_GRACE_S = 180


def _publish(run: _Run, ev: str) -> None:
    """Append one SSE event and fan it out to every live subscriber."""
    run.buffer.append(ev)
    seq = len(run.buffer) - 1
    for q in list(run.subscribers):
        try:
            q.put_nowait((seq, ev))
        except Exception:
            pass


def _schedule_evict(session_id: str) -> None:
    """(Re)arm a grace-period eviction for a terminal run with no subscribers.
    Identity-checked so a run that gets replaced/reused is never evicted by a
    stale timer."""
    run = _RUNS.get(session_id)
    if run is None:
        return
    if run.evict_task and not run.evict_task.done():
        run.evict_task.cancel()

    async def _evict(run_ref: _Run) -> None:
        try:
            await asyncio.sleep(_EVICT_GRACE_S)
        except asyncio.CancelledError:
            return
        cur = _RUNS.get(session_id)
        if cur is run_ref and cur.status != "running" and not cur.subscribers:
            _RUNS.pop(session_id, None)

    run.evict_task = asyncio.create_task(_evict(run))


def is_active(session_id: str) -> bool:
    r = _RUNS.get(session_id)
    return bool(r and r.status == "running")


def get_status(session_id: str) -> Optional[str]:
    r = _RUNS.get(session_id)
    return r.status if r else None


async def _drain(session_id: str, agen: AsyncGenerator[str, None],
                 prev_task: Optional[asyncio.Task] = None,
                 run_id: Optional[str] = None) -> None:
    """Pull every event from the wrapped generator into the run buffer, fanning
    each out to live subscribers. Runs to completion regardless of subscribers.

    SSE contract (Phase 1): the run ALWAYS starts with a `meta` event carrying
    {run_id, session_id, v} and ALWAYS ends with exactly one `[DONE]` event —
    on every exit path: normal completion, the upstream generator finishing
    without sending [DONE], an error, a cancel, or an idle timeout. Clients
    treat [DONE] as the authoritative end-of-turn signal."""
    run = _RUNS.get(session_id)
    if run is None:
        return
    # If this run replaced an in-flight one (rapid double-send), wait for that
    # one to fully finish first. Its CancelledError handler calls aclose(), which
    # persists its partial response — letting it complete before we start writing
    # keeps the two runs' session saves sequential instead of interleaved.
    if prev_task is not None and not prev_task.done():
        try:
            await asyncio.wait({prev_task}, timeout=_PREV_RUN_DRAIN_TIMEOUT_S)
        except asyncio.CancelledError:
            raise            # our own cancellation — propagate
        except Exception:
            pass
        if not prev_task.done():
            # Previous run didn't finish cancelling in time (likely wedged in a
            # long tool call). Proceed anyway so THIS turn isn't blocked behind
            # it forever — its own finally still persists its partial when it
            # eventually unwinds. This is the fix for the run-now stuck-on-
            # "Thinking…" state.
            logger.warning("[agent-run] %s: previous run did not finish cancelling within "
                           "%ss — proceeding so this turn isn't wedged behind it.",
                           session_id, int(_PREV_RUN_DRAIN_TIMEOUT_S))

    # Opening contract event. Unknown event types are ignored by older clients,
    # so this is backward compatible.
    _publish(run, _meta_event(run_id or "", session_id))

    saw_done = False           # did the wrapped generator emit [DONE] itself?
    try:
        # Manually pump the generator so we can apply a per-chunk idle timeout —
        # `async for` gives no hook to detect an upstream that hangs forever.
        agen_iter = agen.__aiter__()
        while True:
            try:
                ev = await asyncio.wait_for(agen_iter.__anext__(), timeout=_RUN_IDLE_TIMEOUT_S)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                logger.warning("[agent-run] %s idle for %ss — force-closing so the client can recover.",
                               session_id, int(_RUN_IDLE_TIMEOUT_S))
                run.status = "error"
                _publish(
                    run,
                    "event: error\n"
                    f"data: {json.dumps({'error': f'No response from the model for {int(_RUN_IDLE_TIMEOUT_S)}s — the stream was closed. Try again or switch models.', 'status': 504})}\n\n",
                )
                # Close the wrapped generator so its own finally (partial-save,
                # _active_streams cleanup) runs deterministically rather than
                # waiting for GC.
                try:
                    await agen.aclose()
                except Exception:
                    pass
                break
            if ev == _DONE_EVENT or ev == "data: [DONE]\n\n":
                saw_done = True
                logger.info("[agent-run] %s saw [DONE] from generator", session_id)
            _publish(run, ev)
        if run.status == "running":
            run.status = "done"
        logger.info("[agent-run] %s generator finished (saw_done=%s, status=%s)",
                    session_id, saw_done, run.status)
    except asyncio.CancelledError:
        run.status = "stopped"
        # Let the wrapped generator's own CancelledError handler run (it saves
        # the partial response to the session).
        try:
            await agen.aclose()
        except Exception:
            pass
        # Cancelled runs still get a [DONE] so a still-connected client (or a
        # reconnect replaying the buffer) settles its turn instead of hanging.
        if not saw_done:
            _publish(run, _DONE_EVENT)
            saw_done = True
        raise            # propagate cancellation after recording the sentinel
    except Exception as e:
        logger.error("[agent-run] %s failed: %s", session_id, e, exc_info=True)
        run.status = "error"
        _publish(
            run,
            "event: error\n"
            f"data: {json.dumps({'error': 'Agent run failed before completion.', 'status': 500})}\n\n",
        )
    finally:
        # THE guarantee: every run ends with exactly one [DONE], whatever path
        # we took to get here. If the wrapped generator already sent it, don't
        # double up. (The CancelledError branch re-raises, so its own emit above
        # is the one that runs for cancels.)
        if not saw_done and run.status != "stopped":
            logger.info("[agent-run] %s finally: generator never sent [DONE] (status=%s) — emitting guaranteed [DONE]",
                        session_id, run.status)
            _publish(run, _DONE_EVENT)
        logger.info("[agent-run] %s closing: waking %d subscriber(s) with end sentinel",
                    session_id, len(run.subscribers))
        # Wake every subscriber with the end sentinel so their SSE closes.
        for q in list(run.subscribers):
            try:
                q.put_nowait((None, None))
            except Exception:
                pass
        # Run is terminal — arm the grace timer so it (and its buffer) is
        # eventually freed even if nobody ever reconnects. subscribe() cancels
        # this on connect and re-arms on disconnect.
        _schedule_evict(session_id)


def start(session_id: str, agen: AsyncGenerator[str, None]) -> _Run:
    """Start a detached run draining `agen` for a session. If a run is already in
    flight for this session (e.g. a rapid double-send), it's cancelled first."""
    prev = _RUNS.get(session_id)
    prev_task: Optional[asyncio.Task] = None
    if prev:
        if prev.task and not prev.task.done():
            prev.task.cancel()
            prev_task = prev.task   # new run awaits this before it starts writing
        if prev.evict_task and not prev.evict_task.done():
            prev.evict_task.cancel()
    run_id = _next_run_id(session_id)
    run = _Run(run_id=run_id)
    _RUNS[session_id] = run
    run.task = asyncio.create_task(_drain(session_id, agen, prev_task, run_id))
    return run


async def subscribe(session_id: str) -> AsyncGenerator[str, None]:
    """Replay the run's buffer from the start, then stream live until it ends.
    Safe to call repeatedly (reconnect) and from multiple clients at once."""
    run = _RUNS.get(session_id)
    if run is None:
        return
    q: asyncio.Queue = asyncio.Queue()
    run.subscribers.add(q)            # register BEFORE replaying so nothing is missed
    # A live subscriber is connected — don't let a pending grace timer evict
    # the run out from under it mid-replay.
    if run.evict_task and not run.evict_task.done():
        run.evict_task.cancel()
    try:
        next_seq = 0
        while next_seq < len(run.buffer):
            yield run.buffer[next_seq]
            next_seq += 1
        if run.status != "running":
            return
        while True:
            seq, ev = await q.get()
            if seq is None:            # end sentinel
                while next_seq < len(run.buffer):   # flush any tail the sentinel raced
                    yield run.buffer[next_seq]
                    next_seq += 1
                break
            if seq >= next_seq:        # skip events already replayed from the buffer
                yield ev
                next_seq = seq + 1
    finally:
        run.subscribers.discard(q)
        # Last subscriber gone on a finished run — (re)arm eviction so the
        # buffer doesn't linger indefinitely.
        if not run.subscribers and run.status != "running":
            _schedule_evict(session_id)


def stop(session_id: str) -> bool:
    """Cancel an in-flight run (the wrapped generator saves its partial)."""
    run = _RUNS.get(session_id)
    if run and run.task and not run.task.done():
        run.task.cancel()
        return True
    return False
