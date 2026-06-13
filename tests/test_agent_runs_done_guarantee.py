"""Phase 1 of the queue redesign: agent_runs guarantees every detached run
emits exactly one `[DONE]` event and an opening `meta` event, on every exit
path. Clients rely on `[DONE]` as the authoritative end-of-turn signal; a
run that finishes without it used to leave the client's `isStreaming` stuck
true and the message queue wedged."""
import asyncio

from src import agent_runs


def _run_and_collect(gen_factory):
    """Start a detached run for `gen_factory()` and return all SSE events the
    subscriber sees, after the run has fully drained."""
    async def _go():
        agent_runs._RUNS.clear()
        sid = "test-sess"
        agent_runs.start(sid, gen_factory())
        await asyncio.sleep(0.05)  # let the detached drain task complete
        out = []
        async for ev in agent_runs.subscribe(sid):
            out.append(ev)
        return out
    return asyncio.run(_go())


def _assert_contract(events):
    assert any(e.startswith("event: meta") for e in events), "missing opening meta event"
    done = [e for e in events if e == "data: [DONE]\n\n"]
    assert len(done) == 1, f"expected exactly one [DONE], got {len(done)}"
    # [DONE] must be last.
    assert events[-1] == "data: [DONE]\n\n", "[DONE] must be the final event"


def test_generator_that_forgets_done_still_gets_one():
    async def no_done():
        yield 'data: {"delta": "hello"}\n\n'
        yield 'data: {"delta": " world"}\n\n'
    _assert_contract(_run_and_collect(no_done))


def test_generator_that_emits_done_is_not_doubled():
    async def with_done():
        yield 'data: {"delta": "hi"}\n\n'
        yield "data: [DONE]\n\n"
    _assert_contract(_run_and_collect(with_done))


def test_generator_that_raises_still_terminates():
    async def raises():
        yield 'data: {"delta": "partial"}\n\n'
        raise RuntimeError("upstream blew up")
    events = _run_and_collect(raises)
    _assert_contract(events)
    assert any("event: error" in e for e in events), "error path should surface an error event"


def test_empty_generator_terminates():
    async def empty():
        return
        yield  # unreachable, makes this an async generator
    _assert_contract(_run_and_collect(empty))


def test_meta_event_carries_contract_fields():
    import json
    async def gen():
        yield 'data: {"delta": "x"}\n\n'
    events = _run_and_collect(gen)
    meta = next(e for e in events if e.startswith("event: meta"))
    payload = json.loads(meta.split("data: ", 1)[1].strip())
    assert payload["type"] == "meta"
    assert payload["v"] == agent_runs.SSE_PROTOCOL_VERSION
    assert payload["session_id"] == "test-sess"
    assert payload["run_id"].startswith("run-")


def test_runnow_not_wedged_by_hung_previous_run(monkeypatch):
    """Run-now / rapid re-send: a NEW run must not be blocked forever behind a
    previous run whose cancellation is wedged (e.g. stuck in a long tool call so
    aclose() never returns). Regression for the run-now stuck-on-"Thinking…"
    state — the new run waits at most _PREV_RUN_DRAIN_TIMEOUT_S, then proceeds
    and still emits its meta + exactly one [DONE]."""
    # Shrink the cross-run wait so the test is fast; the production value is 8s.
    monkeypatch.setattr(agent_runs, "_PREV_RUN_DRAIN_TIMEOUT_S", 0.1)

    async def _go():
        agent_runs._RUNS.clear()
        sid = "test-sess"

        # Run A: when cancelled, its aclose() hangs (simulates a generator wedged
        # in a not-promptly-interruptible tool call).
        async def hangs_on_close():
            try:
                while True:
                    yield 'data: {"delta": "A"}\n\n'
                    await asyncio.sleep(0.01)
            except (GeneratorExit, asyncio.CancelledError):
                await asyncio.sleep(100)   # wedged cleanup
                raise

        async def quick_b():
            yield 'data: {"delta": "B"}\n\n'

        agent_runs.start(sid, hangs_on_close())
        await asyncio.sleep(0.05)          # let A start streaming
        agent_runs.start(sid, quick_b())   # run-now replaces A

        # B must finish within a bound (timeout + a margin), NOT hang forever.
        out = []
        try:
            async def _collect():
                async for ev in agent_runs.subscribe(sid):
                    out.append(ev)
            await asyncio.wait_for(_collect(), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        return out

    events = asyncio.run(_go())
    _assert_contract(events)               # B still emits meta + exactly one [DONE]
    assert any('"delta": "B"' in e for e in events), "the new run's own output should stream"
