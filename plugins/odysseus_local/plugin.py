"""odysseus_local — first-party plugin and reference example.

Encodes our hardware/topology + model decisions as DATA the rest of the app can
consult, instead of hard-coding them into core. It demonstrates four plugin
surfaces:

  • cookbook  — node hardware profiles (with daily-driver VRAM headroom) and a
                curated, multilingual-first model catalog with placement notes.
  • tools     — `local_fleet`: the agent can ask where a workload should run.
  • routes    — GET /api/plugins/local/catalog for the UI / scripts.
  • hooks     — a build_prompt hook so the agent knows the fleet exists.

This file is the template to copy when writing new plugins. Keep secrets and
host-specific addresses OUT of here — Tailscale names belong in settings/.env.
"""
from __future__ import annotations

import json

from src import fleet

# ── Fleet topology (roles decided 2026-06-06) ────────────────────────────────
# reserved_vram_gb = headroom kept free for the desktop on a daily-driver GPU so
# model fit never chokes KDE/browser. usable = total - reserved.
NODES = [
    {
        "id": "fedora", "kind": "nvidia-gpu", "role": "gpu-coprocessor-on-demand",
        "vram_gb": 24, "reserved_vram_gb": 6, "ram_gb": 32,
        "always_on": False, "daily_driver": True,
        "serving": "ollama-native", "keep_alive": "0",
        "notes": "Daily-driver (KDE). Summon for heavy/agentic jobs; let it sleep otherwise.",
    },
    {
        "id": "mac-mini-m4", "kind": "apple-unified", "role": "always-on-brain",
        "vram_gb": 24, "reserved_vram_gb": 8, "ram_gb": 24,
        "always_on": True, "daily_driver": False,
        "serving": "ollama-native", "keep_alive": "30m",
        "notes": "Runs the app + light MoE + embeddings 24/7. Low power.",
    },
    {
        "id": "m1-mbp", "kind": "apple-unified", "role": "dev-and-mobile",
        "vram_gb": 16, "reserved_vram_gb": 6, "ram_gb": 16,
        "always_on": False, "daily_driver": False, "serving": "ollama-native",
        "notes": "Dev/mobile client; occasional worker.",
    },
    {
        "id": "old-mbp-mint", "kind": "cpu-only", "role": "utility",
        "vram_gb": 0, "reserved_vram_gb": 0, "ram_gb": 8,
        "always_on": True, "daily_driver": False, "serving": "none",
        "notes": "CPU utility node: Radicale/SearXNG/Postgres/ntfy/cron. No inference.",
    },
]

# ── Curated model catalog (see research-cache: local-models-2026-coding-moe-fallbacks) ──
# target_node is the recommended home; vram_gb is the Q4 footprint estimate.
CATALOG = [
    {"role": "moe-default", "model": "gpt-oss-20b", "target_node": "mac-mini-m4",
     "vram_gb": 13, "why": "Always-on MoE: fast, strong tools, fits with app+embeddings."},
    {"role": "moe-planner", "model": "qwen3-30b-a3b-thinking", "target_node": "fedora",
     "vram_gb": 18, "why": "Heavy planning/agentic, 256K ctx; summon on Fedora GPU."},
    {"role": "moe-planner-fast", "model": "qwen3.6-35b-a3b", "target_node": "fedora",
     "vram_gb": 22, "full_gpu_only": True,
     "why": "Faster MoE when GPU is fully free (night/idle) — needs the whole 24GB."},
    {"role": "coder", "model": "qwen3.6-27b", "target_node": "fedora",
     "vram_gb": 17, "why": "Agentic coder, SWE-bench 77.2, vision baked in."},
    {"role": "coder-light", "model": "qwen2.5-coder-14b", "target_node": "mac-mini-m4",
     "vram_gb": 9, "why": "Fast local coding/FIM on the always-on node."},
    {"role": "utility", "model": "qwen3.6-4b", "target_node": "mac-mini-m4",
     "vram_gb": 3, "why": "Cheap classification: triage, tagging, routing, titles."},
    {"role": "embeddings", "model": "jinaai/jina-embeddings-v3", "target_node": "mac-mini-m4",
     "vram_gb": 2, "why": "Multilingual RAG (Norwegian). 1024-dim. See reindex script."},
]


def _nodes():
    """THIS machine in single mode; the curated topology in fleet mode."""
    return fleet.nodes(NODES)


def _catalog():
    """In single mode every model targets the one detected machine."""
    if fleet.is_single():
        tgt = fleet.this_machine()["id"]
        return [{**m, "target_node": tgt} for m in CATALOG]
    return CATALOG


def _fleet_payload() -> dict:
    principles = ["Local-first; Claude/cloud only as escalation.",
                  "Respect the GPU's desktop headroom (reserved_vram_gb)."]
    if fleet.is_single():
        principles.insert(0, "Single machine: models load one at a time (swap); each must "
                             "fit usable VRAM. The app works fully on its own.")
    else:
        principles.insert(1, "Never pool VRAM across machines; split by ROLE, not by tensor.")
    return {"mode": fleet.mode(), "summary": fleet.summary(),
            "nodes": _nodes(), "catalog": _catalog(), "principles": principles}


# ── tool handler ──────────────────────────────────────────────────────────────

async def _local_fleet(content: str, owner) -> dict:
    """Tool: report fleet topology + recommended placement. Optional JSON arg
    {"role": "coder"} or {"node": "fedora"} filters the answer."""
    role = node = None
    try:
        if content and content.strip().startswith("{"):
            q = json.loads(content)
            role = (q.get("role") or "").strip().lower() or None
            node = (q.get("node") or "").strip().lower() or None
    except (ValueError, TypeError):
        pass
    all_nodes, all_cat = _nodes(), _catalog()
    catalog = all_cat
    if role:
        catalog = [c for c in catalog if c["role"] == role]
    nodes = all_nodes
    if node:
        nodes = [n for n in all_nodes if n["id"] == node]
        catalog = [c for c in all_cat if c["target_node"] == node]
    return {"response": f"Model placement ({fleet.summary()}).",
            "mode": fleet.mode(), "nodes": nodes, "catalog": catalog,
            "exit_code": 0}


# ── cookbook provider ─────────────────────────────────────────────────────────

class _CookbookProvider:
    """Consumed by the Cookbook layer via plugin_system.get_cookbook_providers()."""
    name = "odysseus_local"

    def profiles(self):
        """Named hardware profiles with usable VRAM after desktop headroom."""
        out = []
        for n in _nodes():
            usable = max(0, n["vram_gb"] - n.get("reserved_vram_gb", 0))
            out.append({**n, "usable_vram_gb": usable})
        return out

    def catalog(self):
        return list(_catalog())

    def score(self, model, system):
        """Optional fit hint: penalise models that would exceed a daily-driver's
        usable VRAM. Returns None to defer to the default scorer."""
        try:
            target = (model or {}).get("vram_gb")
            if target is None:
                return None
            for n in _nodes():
                if n["id"] == (model or {}).get("target_node"):
                    usable = n["vram_gb"] - n.get("reserved_vram_gb", 0)
                    return 1.0 if target <= usable else max(0.0, usable / target)
        except Exception:
            return None
        return None


# ── build_prompt hook ─────────────────────────────────────────────────────────

def _prompt_hook(prompt: str, context: dict) -> str:
    """Tell the agent the fleet exists and how to query it."""
    note = (f"\n\n## Setup ({fleet.summary()})\n"
            "To answer where a model/workload should run, call the `local_fleet` tool "
            "(optional JSON {\"role\":\"coder\"}). Prefer local models; cloud/Claude is "
            "escalation-only.")
    if fleet.is_single():
        note += (" This is a SINGLE machine — models load one at a time (swap), so pick "
                 "ones that each fit its VRAM.")
    return prompt + note


# ── registration ──────────────────────────────────────────────────────────────

def _diagnostic():
    """Self-check consumed by the Cookbook debugger: verify the catalog is
    internally consistent and respects each node's usable-VRAM budget."""
    results = []
    node_by_id = {n["id"]: n for n in _nodes()}
    for m in _catalog():
        tgt = m.get("target_node")
        node = node_by_id.get(tgt)
        if node is None:
            results.append({"name": f"catalog:{m['model']}", "status": "error",
                            "detail": f"target_node {tgt!r} is not a known node",
                            "hint": "fix target_node in plugins/odysseus_local/plugin.py"})
            continue
        usable = node["vram_gb"] - node.get("reserved_vram_gb", 0)
        if m.get("vram_gb", 0) > usable:
            if m.get("full_gpu_only") and m.get("vram_gb", 0) <= node["vram_gb"]:
                # Intentional: only runs when the desktop frees the GPU (night/idle).
                results.append({"name": f"catalog:{m['model']}", "status": "ok",
                                "detail": f"{m['vram_gb']}GB — full-GPU-only (fits {node['vram_gb']}GB when desktop is idle)",
                                "hint": ""})
            else:
                results.append({"name": f"catalog:{m['model']}", "status": "warn",
                                "detail": f"{m['vram_gb']}GB > {usable}GB usable on {tgt} (after desktop headroom)",
                                "hint": f"move {m['model']} to a roomier node or use a smaller quant"})
    if not results:
        results.append({"name": "catalog", "status": "ok",
                        "detail": f"{len(_catalog())} models all fit their target node's usable VRAM"})
    return results


def _gb(n):
    try:
        return f"{n / 1e9:.1f}GB"
    except Exception:
        return "?"


def _gpu_vram():
    """Return (used_mb, total_mb) from nvidia-smi, or (None, None) if no NVIDIA GPU."""
    import subprocess
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        if out.returncode == 0 and out.stdout.strip():
            used, total = out.stdout.strip().split("\n")[0].split(",")
            return int(used.strip()), int(total.strip())
    except Exception:
        pass
    return None, None


def _stats():
    nodes = _nodes()
    n_local = len(nodes)
    # what's actually loaded in Ollama right now, with per-model VRAM footprint
    loaded = []  # (name, size_bytes)
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/ps", timeout=3)
        if r.status_code == 200:
            for m in (r.json() or {}).get("models", []):
                loaded.append((m.get("name", "?"), m.get("size_vram", m.get("size", 0))))
    except Exception:
        pass
    served = 0
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            served = len((r.json() or {}).get("models", []))
    except Exception:
        pass
    used_mb, total_mb = _gpu_vram()
    metrics = [
        {"label": "Nodes", "value": str(n_local)},
        {"label": "Models served", "value": str(served)},
        {"label": "Loaded now", "value": str(len(loaded)), "good": len(loaded) > 0},
    ]
    if total_mb:
        pct = int(used_mb / total_mb * 100) if total_mb else 0
        metrics.append({"label": "GPU VRAM",
                        "value": f"{used_mb//1024}/{total_mb//1024}GB",
                        "good": pct < 85})
    else:
        metrics.append({"label": "Catalog", "value": str(len(_catalog()))})

    mode = fleet.mode()
    if loaded:
        # per-model VRAM breakdown
        per = " · ".join(f"{n.split(':')[0]} {_gb(sz)}" for n, sz in loaded[:3])
        vram_note = ""
        if total_mb:
            free_gb = (total_mb - used_mb) / 1024
            vram_note = f" GPU: {used_mb//1024}/{total_mb//1024}GB used, {free_gb:.0f}GB free."
        insight = f"In VRAM now — {per}.{vram_note}"
        if total_mb and used_mb / total_mb > 0.90:
            insight += " VRAM is nearly full; the next model swap may evict this one."
            status = "warn"
        else:
            status = "ok"
    elif served > 0:
        insight = ("No model is warm in Ollama. First chat after a cold start will take longer "
                   "while the model loads into VRAM.")
        if total_mb:
            insight += f" GPU: {used_mb//1024}/{total_mb//1024}GB used by other processes."
        status = "warn"
    else:
        insight = "Ollama not reachable. Start it (or fix LLM_HOST) so the fleet has models to serve."
        status = "err"
    return {"metrics": metrics, "insight": insight, "status": status}


def register(api):
    api.register_tool(
        "local_fleet", _local_fleet,
        description="Report the local fleet topology and recommended model "
                    "placement (which node runs what). Optional JSON: role/node.",
        risk_category="read",
    )
    api.register_cookbook_provider(_CookbookProvider())
    api.register_hook("build_prompt", _prompt_hook)
    api.register_hook("diagnostic", _diagnostic)
    api.register_hook("stats", _stats)

    # Read-only HTTP surface for the UI / scripts.
    try:
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/api/plugins/local/catalog")
        async def local_catalog():
            return _fleet_payload()

        api.register_router(router)
    except Exception as e:  # FastAPI should always be present in the app
        api.logger.debug("router registration skipped: %s", e)
