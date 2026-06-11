"""Caveman compressor — guard the levels, especially the new 'caveman' speak.

The whole point of the plugin is real token savings; these tests pin the
invariants: caveman beats aggressive on prose, and NONE of the levels ever
corrupt protected spans (code, URLs).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins", "caveman"))

import caveman_compress as cc  # noqa: E402

PROSE = (
    "I'd be happy to help! Basically, the function is responsible for handling "
    "the authentication of the user. It is important to note that, in order to "
    "validate the token, you really just need to check the expiry. As you can "
    "see, this leads to a cleaner implementation. I hope this helps!"
)
CODE_MIX = (
    "To install the package, you basically just need to run the command. It is "
    "important that you use the correct version:\n```bash\npip install foo==1.2.3\n```\n"
    "As mentioned above, the config at https://example.com/config.json must exist."
)


def _ratio(text, level):
    _out, o, c = cc.compress(text, level)
    return (o - c) / o if o else 0.0


def test_caveman_beats_aggressive_on_prose():
    assert _ratio(PROSE, "caveman") > _ratio(PROSE, "aggressive") > 0


def test_caveman_hits_meaningful_savings():
    # Per-prose savings should land in the original skill's headline range,
    # not the old ~5%.
    assert _ratio(PROSE, "caveman") >= 0.40


def test_levels_are_monotonic():
    r = {lvl: _ratio(PROSE, lvl) for lvl in ("minimal", "structural", "aggressive", "caveman")}
    assert r["minimal"] <= r["structural"] <= r["aggressive"] <= r["caveman"]


def test_protected_spans_survive_every_level():
    for level in ("minimal", "structural", "aggressive", "caveman"):
        out, _o, _c = cc.compress(CODE_MIX, level)
        assert "pip install foo==1.2.3" in out, f"code mangled at {level}"
        assert "https://example.com/config.json" in out, f"URL mangled at {level}"


def test_never_returns_longer_than_input():
    for level in ("minimal", "structural", "aggressive", "caveman"):
        out, o, c = cc.compress(PROSE, level)
        assert c <= o and len(out) <= o


def test_empty_and_tiny_safe():
    assert cc.compress("", "caveman") == ("", 0, 0)
    # A terse string with nothing to drop should never grow.
    out, o, c = cc.compress("ok", "caveman")
    assert c <= o
