"""Coder-backend selection + command building + opencode event parsing.

Covers the Aider→OpenCode CLI swap chokepoint in src/code_edit.py: the
build_coder_cmd argv, resolve_opencode_model passthrough, the opencode
--format json event → (stage, log, error) parser, and select_coder_backend's
preference + graceful-fallback logic. No subprocess, no network, no DB:
native provider/model specs skip the endpoint lookup, and bins/settings are
monkeypatched.
"""
import sys
import types

import src.code_edit as ce


# ── resolve_opencode_model: native specs pass straight through ──

def test_resolve_opencode_model_passthrough_native_prefixes():
    for m in ("opencode-go/qwen3.7-max", "opencode/deepseek-v4-flash-free",
              "google/gemini-2.5-flash", "anthropic/claude-opus-4-8",
              "ollama/qwen3-coder"):
        assert ce.resolve_opencode_model(m) == m


def test_resolve_opencode_model_empty_is_none():
    assert ce.resolve_opencode_model("") is None
    assert ce.resolve_opencode_model(None) is None


# ── build_coder_cmd: opencode vs aider argv ──

def test_build_coder_cmd_opencode_shape():
    sel = {"backend": "opencode", "bin": "/oc", "model": "opencode-go/qwen3.7-max"}
    cmd = ce.build_coder_cmd(sel, "do the thing", ["a.py", "b.py"], cwd="/proj")
    # instruction MUST precede -f (greedy array), -f paths are absolute, and
    # --dangerously-skip-permissions auto-approves edits (non-interactive run).
    assert cmd == ["/oc", "run", "-m", "opencode-go/qwen3.7-max", "--format", "json",
                   "--dangerously-skip-permissions", "do the thing",
                   "-f", "/proj/a.py", "-f", "/proj/b.py"]


def test_build_coder_cmd_opencode_no_files():
    sel = {"backend": "opencode", "bin": "/oc", "model": "opencode/m"}
    cmd = ce.build_coder_cmd(sel, "msg", [])
    assert cmd == ["/oc", "run", "-m", "opencode/m", "--format", "json",
                   "--dangerously-skip-permissions", "msg"]


def test_build_coder_cmd_opencode_absolute_files_unchanged():
    sel = {"backend": "opencode", "bin": "/oc", "model": "opencode/m"}
    cmd = ce.build_coder_cmd(sel, "msg", ["/abs/x.py"], cwd="/proj")
    assert "-f" in cmd and "/abs/x.py" in cmd and "/proj/abs/x.py" not in cmd


def test_build_coder_cmd_aider_shape_with_flags():
    sel = {"backend": "aider", "bin": "/ai", "model": "openai/x"}
    cmd = ce.build_coder_cmd(sel, "msg", ["a.py"], no_git=True, pretty=False)
    assert cmd[0] == "/ai" and "--model" in cmd and "openai/x" in cmd
    assert "--yes-always" in cmd and "--no-auto-commits" in cmd
    assert "--no-git" in cmd and "--no-pretty" in cmd
    # aider takes the instruction via --message and files as bare args
    assert cmd[cmd.index("--message") + 1] == "msg"
    assert cmd[-1] == "a.py"


def test_build_coder_cmd_aider_default_no_extra_flags():
    sel = {"backend": "aider", "bin": "/ai", "model": "m"}
    cmd = ce.build_coder_cmd(sel, "msg", [])
    assert "--no-git" not in cmd and "--no-pretty" not in cmd


# ── opencode_event: JSON event → (stage, log, is_error) ──

def test_opencode_event_tool_read_is_analyzing():
    ev = ('{"type":"tool_use","part":{"tool":"read",'
          '"state":{"input":{"filePath":"/p/calc.py"}}}}')
    stage, log, err = ce.opencode_event(ev)
    assert stage == "analyzing the repo…"
    assert "calc.py" in log and err is False


def test_opencode_event_tool_edit_is_writing_with_filename():
    ev = ('{"type":"tool_use","part":{"tool":"edit",'
          '"state":{"input":{"filePath":"/p/routes/api.py"}}}}')
    stage, log, err = ce.opencode_event(ev)
    assert stage == "writing changes to api.py…"
    assert err is False


def test_opencode_event_text_carries_log_only():
    stage, log, err = ce.opencode_event('{"type":"text","part":{"text":"Done."}}')
    assert stage is None and log == "Done." and err is False


def test_opencode_event_error_flagged():
    stage, log, err = ce.opencode_event('{"type":"error","error":"boom"}')
    assert err is True and "boom" in log


def test_opencode_event_non_json_returns_raw_line():
    stage, log, err = ce.opencode_event("not json at all")
    assert stage is None and log == "not json at all" and err is False


def test_opencode_event_blank_is_all_none():
    assert ce.opencode_event("   ") == (None, None, False)


# ── select_coder_backend: preference + graceful fallback ──

def _patch_bins(monkeypatch, *, oc, ai, pref="opencode"):
    monkeypatch.setattr(ce, "opencode_bin", lambda: oc)
    fake_pf = types.ModuleType("src.plugin_forge")
    fake_pf.aider_bin = lambda: ai
    monkeypatch.setitem(sys.modules, "src.plugin_forge", fake_pf)
    fake_settings = types.ModuleType("src.settings")
    fake_settings.get_setting = lambda k, d=None: pref if k == "coder_backend" else d
    monkeypatch.setitem(sys.modules, "src.settings", fake_settings)
    # resolve_aider_model hits the DB; stub it to a deterministic pair.
    monkeypatch.setattr(ce, "resolve_aider_model", lambda m: (m, {"E": "1"}))


def test_select_prefers_opencode_when_available(monkeypatch):
    _patch_bins(monkeypatch, oc="/oc", ai="/ai", pref="opencode")
    sel = ce.select_coder_backend("opencode-go/qwen3.7-max")
    assert sel["backend"] == "opencode" and sel["bin"] == "/oc"
    assert sel["model"] == "opencode-go/qwen3.7-max" and not sel.get("fellback")


def test_select_falls_back_to_aider_when_opencode_missing(monkeypatch):
    _patch_bins(monkeypatch, oc=None, ai="/ai", pref="opencode")
    sel = ce.select_coder_backend("opencode-go/qwen3.7-max")
    assert sel["backend"] == "aider" and sel["fellback"] is True


def test_select_aider_pref_uses_aider(monkeypatch):
    _patch_bins(monkeypatch, oc="/oc", ai="/ai", pref="aider")
    sel = ce.select_coder_backend("opencode-go/qwen3.7-max")
    assert sel["backend"] == "aider" and not sel.get("fellback")


def test_select_aider_pref_falls_back_to_opencode_when_aider_missing(monkeypatch):
    _patch_bins(monkeypatch, oc="/oc", ai=None, pref="aider")
    sel = ce.select_coder_backend("opencode-go/qwen3.7-max")
    assert sel["backend"] == "opencode" and sel["fellback"] is True


def test_select_errors_when_nothing_usable(monkeypatch):
    _patch_bins(monkeypatch, oc=None, ai=None, pref="opencode")
    sel = ce.select_coder_backend("opencode-go/qwen3.7-max")
    assert sel["backend"] is None and sel["error"]


# ── list_coder_models: curated, source-grouped picker ──

import json as _json


class _EP:
    def __init__(self, base_url, models):
        self.base_url = base_url
        self.is_enabled = True
        self.cached_models = _json.dumps(models)
        self.pinned_models = "[]"


def _fake_core_db(monkeypatch, endpoints):
    mod = types.ModuleType("core.database")

    class _Q:
        def __init__(self, eps): self._eps = eps
        def filter(self, *a, **k): return self
        def all(self): return self._eps

    class _DB:
        def __init__(self, eps): self._eps = eps
        def query(self, *a, **k): return _Q(self._eps)
        def close(self): pass

    mod.SessionLocal = lambda: _DB(endpoints)
    mod.ModelEndpoint = type("ModelEndpoint", (), {"is_enabled": True})
    monkeypatch.setitem(sys.modules, "core.database", mod)


def _fake_ollama(monkeypatch, names):
    fake = types.ModuleType("httpx")

    class _Resp:
        def __init__(self, names): self._n = names
        def json(self): return {"models": [{"name": n} for n in self._n]}

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **k):
            if names is None:
                raise OSError("no ollama")
            return _Resp(names)

    fake.Client = _Client
    monkeypatch.setitem(sys.modules, "httpx", fake)


def test_list_coder_models_groups_go_and_freezen(monkeypatch):
    _fake_core_db(monkeypatch, [
        _EP("https://opencode.ai/zen/go/v1", ["kimi-k2.7-code", "glm-5.1", "gemini-x"]),
        _EP("https://opencode.ai/zen/v1",
            ["north-mini-code-free", "deepseek-v4-flash-free", "glm-5.1"]),
    ])
    _fake_ollama(monkeypatch, None)  # no local
    out = ce.list_coder_models()
    g = {x["source"]: x for x in out["groups"]}
    assert set(g) == {"go", "zen-free"}
    go_ids = [m["id"] for m in g["go"]["models"]]
    assert "opencode-go/kimi-k2.7-code" in go_ids
    assert all(i.startswith("opencode-go/") for i in go_ids)
    # zen-free group keeps ONLY the fully-free (-free) models
    zf = [m["id"] for m in g["zen-free"]["models"]]
    assert "opencode/north-mini-code-free" in zf
    assert "opencode/deepseek-v4-flash-free" in zf
    assert all(i.endswith("-free") for i in zf)
    assert "opencode/glm-5.1" not in zf
    # coder-suited models sort first within a group
    assert g["go"]["models"][0]["suited"] is True


def test_list_coder_models_local_group_with_caveat(monkeypatch):
    _fake_core_db(monkeypatch, [])
    _fake_ollama(monkeypatch, ["qwen3-coder:30b", "gemma4:12b"])
    out = ce.list_coder_models()
    g = {x["source"]: x for x in out["groups"]}
    assert "local" in g
    ids = [m["id"] for m in g["local"]["models"]]
    assert "ollama/qwen3-coder:30b" in ids
    assert g["local"].get("note")  # tool-calling caveat surfaced
