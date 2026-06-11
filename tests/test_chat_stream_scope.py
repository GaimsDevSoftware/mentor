"""Guard the scope invariant for the streaming turn in chat.js: anything the
`catch (err)` / `finally` blocks reference MUST be declared in the OUTER
function scope (before the streaming `try`), never with a block-scoped `let`
INSIDE the try.

Why this matters: a `let` declared inside the try is invisible to the finally.
That's exactly the bug that wedged the whole queue for a long time — the
finally referenced `_silenceTimer` (declared `let` inside the try) and threw
`ReferenceError` on its first line, so updateSubmitButton('idle') /
_setStreaming(false) never ran → isStreaming stuck true → every message queued
→ the first message looped. This test would have caught it.

The previous version of this test asserted one specific implementation shape
(forward-declared `let x = () => {}` arrows). The helpers were later refactored
to hoisted `function` declarations — equally valid (function declarations are
function-scoped and hoisted, so they're visible to catch/finally). So we assert
the INVARIANT (declared in outer scope, not block-scoped inside the try), not a
particular syntax.
"""
from pathlib import Path


def _slice_streaming_try(source: str):
    try_start = source.index("    try {\n      // Re-enable auto-scroll")
    catch_start = source.index("    } catch (err) {", try_start)
    finally_start = source.index("    } finally {", catch_start)
    # finally body ends at the next 4-space block close after it
    finally_end = source.index("\n    }", finally_start + len("    } finally {"))
    return {
        "outer": source[:try_start],
        "try_body": source[try_start:catch_start],
        "finally_body": source[finally_start:finally_end],
    }


def test_finally_cleanup_vars_declared_in_outer_scope():
    """The silence-indicator handles cleaned up in the finally must live at
    function scope — declaring them with `let` inside the try made the finally
    throw ReferenceError (the queue-wedging bug)."""
    src = _slice_streaming_try(Path("static/js/chat.js").read_text(encoding="utf-8"))
    for name in ("_silenceTimer", "_silenceEl"):
        # referenced in the finally …
        assert name in src["finally_body"], f"{name} not referenced in finally — test stale?"
        # … so it MUST be declared in the outer scope …
        assert f"let {name}" in src["outer"] or f"var {name}" in src["outer"], \
            f"{name} is cleaned up in finally but not declared in outer scope → ReferenceError risk"
        # … and NOT (re)declared with a block-scoped let inside the try.
        assert f"let {name}" not in src["try_body"], \
            f"{name} re-declared with let inside the try — shadows the outer binding the finally needs"


def test_stream_render_helpers_visible_to_catch():
    """Render/thinking helpers used in the catch must be defined in the outer
    scope (as hoisted function declarations or forward-declared arrows)."""
    src = _slice_streaming_try(Path("static/js/chat.js").read_text(encoding="utf-8"))
    for name in ("_renderStreamFlush", "_cancelThinkingTimer", "_removeThinkingSpinner"):
        in_outer = (f"function {name}(" in src["outer"]) or (f"let {name} " in src["outer"]) or (f"let {name}=" in src["outer"])
        assert in_outer, f"{name} not defined in outer scope → not visible to catch/finally"
