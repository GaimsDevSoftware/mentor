"""Unified debugger / diagnostics engine for the Cookbook.

One place that answers "what is wrong?" across the whole app — serving/endpoints,
embeddings + Chroma, the plugin system (including each plugin's own self-check),
Aegis, the autonomous loop, and the local fleet. Every check returns a plain,
actionable result so the UI can show *what* broke and *how to fix it*.

Result shape (one per finding):
    {"area": "...", "name": "...", "status": "ok"|"warn"|"error",
     "detail": "what we observed", "hint": "what to do about it"}

Design rules:
  • SAFE: checks never trigger heavy work (no model downloads/loads); network is
    limited to short socket probes with timeouts.
  • DEFENSIVE: every check is wrapped — one failing check can't break the report.
  • EXTENSIBLE: plugins contribute via a `diagnostic` hook; built-ins live here.
"""
from __future__ import annotations

import logging
import os
import socket
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _get(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def _ok(area, name, detail="", hint="", fix=None):
    d = {"area": area, "name": name, "status": "ok", "detail": detail, "hint": hint}
    if fix:
        d["fix"] = fix
    return d


def _warn(area, name, detail, hint, fix=None):
    d = {"area": area, "name": name, "status": "warn", "detail": detail, "hint": hint}
    if fix:
        d["fix"] = fix
    return d


def _err(area, name, detail, hint, fix=None):
    d = {"area": area, "name": name, "status": "error", "detail": detail, "hint": hint}
    if fix:
        d["fix"] = fix
    return d


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ── individual checks (each returns a list[result]) ──────────────────────────

def _check_plugins() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        from src import plugin_system
    except Exception as e:
        return [_err("plugins", "registry", f"plugin system unavailable: {e}",
                     "ensure src/plugin_system.py imports cleanly")]
    plugins = plugin_system.list_plugins()
    if not plugins:
        out.append(_warn("plugins", "discovery", "no plugins found",
                         "add a plugin under plugins/<name>/ with plugin.json (see docs/PLUGINS.md)"))
    for p in plugins:
        name = p.get("name", "?")
        st = p.get("status")
        if st == "loaded":
            out.append(_ok("plugins", name, f"v{p.get('version','?')} perms={p.get('permissions')}"))
        elif st == "disabled":
            out.append(_warn("plugins", name, "disabled in manifest",
                             'set "enabled": true in its plugin.json to load it'))
        else:
            out.append(_err("plugins", name, p.get("error") or "failed to load",
                            f"fix plugins/{name}/ (manifest permissions / entry module / register())",
                            fix={"kind": "plugin_repair", "plugin": name,
                                 "label": "Let Copilot fix this plugin"}))
    # Plugin debugger/cookbook-compatibility contract: every loaded plugin SHOULD
    # expose a diagnostic() hook so it's introspectable here.
    try:
        with_diag = plugin_system.plugins_with_diagnostic()
        for p in plugins:
            if p.get("status") == "loaded" and p.get("name") not in with_diag:
                out.append(_warn("plugins", f"{p['name']}:contract",
                                 "plugin has no diagnostic() hook (not debugger-compatible)",
                                 "add api.register_hook('diagnostic', fn) — see docs/PLUGINS.md"))
    except Exception:
        pass
    # Plugin self-checks (the "debug plugins" part).
    try:
        out.extend(plugin_system.run_diagnostics())
    except Exception as e:
        out.append(_warn("plugins", "self-checks", f"plugin diagnostics failed: {e}", "review plugin diagnostic() hooks"))
    return out


def _check_embeddings() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    intended = (_get("embedding_fastembed_model", "")
                or os.getenv("FASTEMBED_MODEL", "")
                or "sentence-transformers/all-MiniLM-L6-v2")
    http_url = os.getenv("EMBEDDING_URL", "")
    out.append(_ok("embeddings", "configured-model", f"intended: {intended}"))
    # #1444 trap: HTTP endpoint may shadow the intended fastembed model.
    if http_url:
        out.append(_warn("embeddings", "http-shadowing",
                         f"EMBEDDING_URL is set ({http_url}); if it serves a model it OVERRIDES the fastembed pick",
                         "unset EMBEDDING_URL (or ensure it serves the same model) to use the fastembed model"))
    # State sentinel vs intended (drift detection).
    try:
        import json
        from src.constants import DATA_DIR
        sp = os.path.join(DATA_DIR, "embedding_state.json")
        if os.path.exists(sp):
            prev = json.loads(open(sp, encoding="utf-8").read())
            if prev.get("model") and prev.get("model") != intended:
                out.append(_err("embeddings", "index-drift",
                                f"indexed with {prev.get('model')} (dim {prev.get('dim')}) but intended is {intended}",
                                "run: python scripts/reindex_embeddings.py --apply",
                                fix={"kind": "command", "command": "reindex_embeddings",
                                     "label": "Reindex embeddings now"}))
            else:
                out.append(_ok("embeddings", "index-state", f"indexed model matches ({prev.get('model')})"))
        else:
            out.append(_warn("embeddings", "index-state", "no embedding_state.json (never reindexed)",
                             "run python scripts/reindex_embeddings.py --apply after choosing the model"))
    except Exception as e:
        out.append(_warn("embeddings", "index-state", f"could not read state: {e}", ""))
    # Chroma reachability.
    host = os.getenv("CHROMADB_HOST", "localhost")
    port = int(os.getenv("CHROMADB_PORT", "8100") or 8100)
    if _port_open(host, port):
        out.append(_ok("embeddings", "chromadb", f"reachable at {host}:{port}"))
    else:
        out.append(_err("embeddings", "chromadb", f"not reachable at {host}:{port}",
                        "start the ChromaDB service (RAG + memory vectors need it)"))
    return out


def _check_fleet() -> List[Dict[str, Any]]:
    """Probe Ollama on the primary host + any LLM_HOSTS, and list configured nodes
    from cookbook providers."""
    out: List[Dict[str, Any]] = []
    hosts = []
    primary = os.getenv("LLM_HOST", "localhost")
    hosts.append(primary)
    for h in [x.strip() for x in os.getenv("LLM_HOSTS", "").split(",") if x.strip()]:
        if h not in hosts:
            hosts.append(h)
    for h in hosts:
        if _port_open(h, 11434):
            out.append(_ok("fleet", f"ollama@{h}", "Ollama reachable :11434"))
        else:
            out.append(_warn("fleet", f"ollama@{h}", "Ollama not reachable on :11434",
                             f"start Ollama on {h} (OLLAMA_HOST=0.0.0.0:11434) or fix LLM_HOSTS"))
    # Configured nodes from cookbook providers (informational).
    try:
        from src import plugin_system
        for prov in plugin_system.get_cookbook_providers():
            profiles = getattr(prov, "profiles", None)
            if callable(profiles):
                for n in profiles() or []:
                    out.append(_ok("fleet", f"node:{n.get('id')}",
                                   f"{n.get('role')} — usable VRAM {n.get('usable_vram_gb','?')}GB"))
    except Exception as e:
        out.append(_warn("fleet", "node-catalog", f"could not read provider profiles: {e}", ""))
    return out


def _check_aegis() -> List[Dict[str, Any]]:
    mode = str(_get("aegis_mode", "off") or "off").lower()
    if mode == "off":
        return [_warn("aegis", "mode", "firewall is OFF (no tool-call risk gating)",
                      'set aegis_mode="audit" to observe, then "enforce" to block',
                      fix={"kind": "setting", "key": "aegis_mode", "value": "audit",
                           "label": "Enable Aegis audit mode"})]
    block = _get("aegis_block_threshold", 80)
    return [_ok("aegis", "mode", f"{mode} (block≥{block})")]


def _check_autonomous_loop() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    enabled = bool(_get("improve_loop_enabled", True))
    teacher = (_get("improve_teacher_model", "") or _get("teacher_model", "") or "").strip()
    if enabled and not teacher:
        out.append(_warn("autonomous-loop", "teacher",
                         "loop enabled but no teacher_model configured",
                         "set teacher_model (e.g. claude-code-sonnet@Claude Code (OAuth)) or disable the loop"))
    else:
        out.append(_ok("autonomous-loop", "config", f"enabled={enabled} teacher={teacher or 'none'}"))
    try:
        from src import claude_budget
        st = claude_budget.status()
        coach = st.get("coach", {})
        out.append(_ok("autonomous-loop", "budget",
                       f"coach {coach.get('remaining','?')}/{coach.get('per_window','?')} left, "
                       f"resets in {coach.get('resets_in_min','?')}m"))
    except Exception as e:
        out.append(_warn("autonomous-loop", "budget", f"could not read budget: {e}", ""))
    return out


def _nvidia_vram_free():
    """(free_mb, total_mb) for the first NVIDIA GPU, or None. Safe/best-effort."""
    import subprocess
    for binp in ("nvidia-smi", "/usr/bin/nvidia-smi", "/usr/local/cuda/bin/nvidia-smi"):
        try:
            out = subprocess.run(
                [binp, "--query-gpu=memory.free,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4)
            if out.returncode == 0 and out.stdout.strip():
                free, total = [float(x) for x in out.stdout.strip().splitlines()[0].split(",")]
                return free, total
        except Exception:
            continue
    return None


def _check_context_memory() -> List[Dict[str, Any]]:
    """Why models stop mid-message: not enough RAM/VRAM (eviction/OOM) or not
    enough context budget left after the system prompt + thinking tokens."""
    out: List[Dict[str, Any]] = []

    # 1) System RAM headroom — low free RAM → swapping/eviction → generation stalls.
    try:
        import psutil
        vm = psutil.virtual_memory()
        avail = vm.available / 1e9
        total = vm.total / 1e9
        if avail < 2.5:
            out.append(_err("context-memory", "system-ram",
                            f"only {avail:.1f}GB of {total:.0f}GB RAM free",
                            "close apps / move always-on work to the M4; low RAM stalls or kills generation"))
        elif avail < 4.0:
            out.append(_warn("context-memory", "system-ram",
                             f"{avail:.1f}GB of {total:.0f}GB RAM free (tight)",
                             "watch memory; offload background work to the always-on node"))
        else:
            out.append(_ok("context-memory", "system-ram", f"{avail:.1f}GB of {total:.0f}GB free"))
    except Exception as e:
        out.append(_warn("context-memory", "system-ram", f"could not read RAM: {e}", ""))

    # 2) Free VRAM — the daily-driver desktop can steal it and evict the model
    #    mid-generation, which looks like "the model stopped mid-message".
    vram = _nvidia_vram_free()
    if vram is not None:
        free_mb, total_mb = vram
        free_gb, total_gb = free_mb / 1024, total_mb / 1024
        if free_gb < 1.5:
            out.append(_err("context-memory", "gpu-vram",
                            f"only {free_gb:.1f}GB of {total_gb:.0f}GB VRAM free",
                            "desktop/other model is using the GPU — model may be evicted mid-generation; "
                            "set OLLAMA_KEEP_ALIVE=0, free the GPU, or run the model on the M4"))
        elif free_gb < 3.0:
            out.append(_warn("context-memory", "gpu-vram",
                             f"{free_gb:.1f}GB of {total_gb:.0f}GB VRAM free (tight on a daily-driver)",
                             "leave headroom for KDE/browser so the model isn't evicted"))
        else:
            out.append(_ok("context-memory", "gpu-vram", f"{free_gb:.1f}GB of {total_gb:.0f}GB free"))

    # 3) Truncation guard — reasoning models put output in a <think> block first;
    #    if num_predict is spent there the answer comes back empty/truncated.
    no_think = bool(_get("agent_local_no_think", True))
    floor = int(_get("agent_local_min_predict", 8192) or 8192)
    if not no_think:
        out.append(_warn("context-memory", "thinking-guard",
                         "agent_local_no_think is OFF — reasoning models may spend the whole "
                         "output budget thinking and return an empty/truncated answer",
                         "set agent_local_no_think=true, or ensure a generous num_predict floor",
                         fix={"kind": "setting", "key": "agent_local_no_think", "value": True,
                              "label": "Enable thinking-truncation guard"}))
    elif floor < 2048:
        out.append(_warn("context-memory", "output-floor",
                         f"agent_local_min_predict={floor} is low; the answer may be truncated",
                         "raise agent_local_min_predict (e.g. 8192) so the answer always has room",
                         fix={"kind": "setting", "key": "agent_local_min_predict", "value": 8192,
                              "label": "Raise output floor to 8192"}))
    else:
        out.append(_ok("context-memory", "thinking-guard",
                       f"no_think on, output floor {floor}"))
    # Known coverage gap: the guard matches qwen3/deepseek-r/qwq, NOT gpt-oss.
    out.append(_warn("context-memory", "guard-coverage",
                     "thinking-guard matches qwen3/deepseek-r/qwq but NOT gpt-oss (also a reasoning model)",
                     "if using gpt-oss, broaden the matcher or add finish_reason=length retry handling"))

    # 4) Static prompt overhead vs a clamped context window — rules + skills sent
    #    every turn eat the window; with thinking + history this starves output.
    try:
        from src import regelverk
        rules_block = regelverk.render_rules_block(record=False) or ""
        rule_tok = len(rules_block) // 4
        skills_cap = int(_get("skill_max_injected", 3) or 3)
        est_skill_tok = skills_cap * 250  # rough per-skill budget
        overhead = rule_tok + est_skill_tok
        ctx = 32768  # representative clamped window (qwen3.6 on 24GB)
        frac = overhead / ctx
        detail = (f"~{overhead} tok always-on overhead (rules {rule_tok} + ~{est_skill_tok} skills) "
                  f"≈ {frac*100:.0f}% of a 32K window")
        if frac > 0.30:
            out.append(_warn("context-memory", "prompt-overhead", detail,
                             "trim regelverk_max_injected / skill_max_injected, or raise the model's num_ctx"))
        else:
            out.append(_ok("context-memory", "prompt-overhead", detail))
    except Exception as e:
        out.append(_warn("context-memory", "prompt-overhead", f"could not estimate: {e}", ""))

    return out


def _check_serving_config() -> List[Dict[str, Any]]:
    """KV-cache quantization + Flash Attention on the Ollama server fit longer
    context in much less VRAM → far fewer mid-generation evictions/stalls. These
    are set in the OLLAMA SERVER's environment (not the app), so this is advisory
    when Ollama runs elsewhere."""
    out: List[Dict[str, Any]] = []
    want_fa = bool(_get("ollama_flash_attention", True))
    want_kv = str(_get("ollama_kv_cache_type", "q8_0") or "q8_0")
    fa = os.environ.get("OLLAMA_FLASH_ATTENTION", "")
    kv = os.environ.get("OLLAMA_KV_CACHE_TYPE", "")
    if want_fa and fa not in ("1", "true", "True"):
        out.append(_warn("serving", "flash-attention",
                         "OLLAMA_FLASH_ATTENTION is not set on this host",
                         "on the Ollama server: export OLLAMA_FLASH_ATTENTION=1 (required for KV-cache quant)"))
    else:
        out.append(_ok("serving", "flash-attention", f"flash attention: {fa or 'on'}"))
    if want_kv and not kv:
        out.append(_warn("serving", "kv-cache-quant",
                         f"OLLAMA_KV_CACHE_TYPE not set (want {want_kv}) — KV cache uses fp16, ~2× VRAM",
                         f"on the Ollama server: export OLLAMA_KV_CACHE_TYPE={want_kv} "
                         "(q8_0 ≈ half the KV memory, tiny quality loss) → fits more context, fewer stalls"))
    else:
        out.append(_ok("serving", "kv-cache-quant", f"KV cache type: {kv or want_kv}"))
    return out


# Registry of built-in checks. Adding a check = one line here.
_CHECKS = [
    ("context-memory", _check_context_memory),
    ("serving", _check_serving_config),
    ("plugins", _check_plugins),
    ("embeddings", _check_embeddings),
    ("fleet", _check_fleet),
    ("aegis", _check_aegis),
    ("autonomous-loop", _check_autonomous_loop),
]


_RUNNING = False


def run_all(only_failures: bool = False) -> Dict[str, Any]:
    """Run every check and return a grouped, summarised report."""
    # Re-entrancy guard: a plugin's diagnostic hook must not call run_all() (it
    # runs inside run_all). If one does, break the recursion with a stub instead
    # of overflowing the stack.
    global _RUNNING
    if _RUNNING:
        return {"overall": "ok", "counts": {"ok": 0, "warn": 0, "error": 0},
                "groups": {}, "problems": [], "reentrant": True}
    _RUNNING = True
    try:
        return _run_all_inner(only_failures)
    finally:
        _RUNNING = False


def _run_all_inner(only_failures: bool = False) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for area, fn in _CHECKS:
        try:
            results.extend(fn() or [])
        except Exception as e:
            results.append(_err(area, "check", f"check crashed: {e}",
                                "this is a debugger bug — report the traceback"))
            logger.debug("debugger check %s crashed: %s", area, e, exc_info=True)

    if only_failures:
        results = [r for r in results if r.get("status") in ("warn", "error")]

    counts = {"ok": 0, "warn": 0, "error": 0}
    for r in results:
        counts[r.get("status", "ok")] = counts.get(r.get("status", "ok"), 0) + 1
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        groups.setdefault(r.get("area", "other"), []).append(r)

    overall = "error" if counts["error"] else ("warn" if counts["warn"] else "ok")
    # Plain-language one-liners for everything that's not ok.
    problems = [f"[{r['status'].upper()}] {r['area']}/{r['name']}: {r['detail']}"
                + (f" → {r['hint']}" if r.get("hint") else "")
                for r in results if r.get("status") in ("warn", "error")]
    return {"overall": overall, "counts": counts, "groups": groups, "problems": problems}
