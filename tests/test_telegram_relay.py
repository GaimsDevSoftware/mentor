"""Telegram UI→phone relay logic (plugins/telegram _pending_pushes).

Guards the echo-safe, deduped relay: web-typed turns of the shared session are
pushed to Telegram exactly once; telegram-origin messages are never echoed back.
"""
import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "plugins", "telegram", "plugin.py")
_spec = importlib.util.spec_from_file_location("telegram_plugin_under_test", _PATH)
tg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tg)


def _m(role, content, source=None):
    return {"role": role, "content": content, "metadata": ({"source": source} if source else None)}


HIST = [
    _m("user", "hi from phone", "telegram"),
    _m("assistant", "already sent to phone", "telegram"),
    _m("user", "typed in web"),
    _m("assistant", "answer from web", "web"),
]


def test_first_sight_baselines_no_backfill():
    outs, marker = tg._pending_pushes(HIST, None)
    assert outs == [] and marker == len(HIST)


def test_echo_guard_skips_telegram_origin():
    # Even scanning from 0, the two telegram-origin messages are never pushed.
    outs, marker = tg._pending_pushes(HIST, 0)
    assert "🌐 (from web): typed in web" in outs
    assert "answer from web" in outs
    assert not any("phone" in o for o in outs)   # nothing telegram-origin leaked
    assert marker == len(HIST)


def test_only_new_after_marker():
    outs, marker = tg._pending_pushes(HIST, 2)
    assert outs == ["🌐 (from web): typed in web", "answer from web"] and marker == 4


def test_caught_up_is_noop():
    outs, marker = tg._pending_pushes(HIST, 4)
    assert outs == [] and marker == 4


def test_per_pass_cap():
    big = [_m("assistant", f"reply {i}", "web") for i in range(40)]
    outs, marker = tg._pending_pushes(big, 0)
    assert len(outs) == 15 and marker == 15   # rest delivered on the next pass
