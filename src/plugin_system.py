"""In-process plugin system for Odysseus.

Trusted, developer-installed plugins with MAX freedom — but every plugin must
declare in a manifest WHICH surfaces it touches, and tool calls it registers
still flow through the Aegis firewall and the normal execute_tool_block gates.
Freedom with traceability, not freedom with blindness.

A plugin is a directory under `plugins/<name>/` containing:

    plugin.json        — manifest (name, version, permissions, entry)
    <entry>.py         — module exposing `def register(api): ...`

Manifest example:

    {
      "name": "odysseus_local",
      "version": "0.1.0",
      "description": "Our two-node fleet + curated model catalog",
      "permissions": ["tools", "hooks", "cookbook", "services", "routes"],
      "entry": "plugin",
      "enabled": true
    }

The `register(api)` function receives a PluginAPI bound to the plugin's declared
permissions and wires extension points:

    def register(api):
        api.register_tool("local_fleet", handler, description="...")
        api.register_hook("build_prompt", fn)
        api.register_cookbook_provider(provider)
        api.register_service(service_factory)      # async, started at boot
        api.register_router(my_fastapi_router)

Extension surfaces (what was opted into): tools, hooks, cookbook, services, routes.
UI panels are intentionally NOT a surface in this version.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import sys
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Permission strings ↔ surfaces. A plugin may only call register_* for surfaces
# it declared in manifest["permissions"].
_VALID_PERMISSIONS = {"tools", "hooks", "cookbook", "services", "routes"}
_VALID_HOOK_EVENTS = {"pre_tool", "post_tool", "build_prompt", "diagnostic"}


# ── registry state ───────────────────────────────────────────────────────────

_PLUGINS: List[Dict[str, Any]] = []          # loaded plugin metadata + status
_TOOLS: Dict[str, Dict[str, Any]] = {}        # tool_name -> {handler, plugin, ...}
_HOOKS: Dict[str, List[Dict[str, Any]]] = {}  # event -> [{plugin, fn}]
_COOKBOOK_PROVIDERS: List[Dict[str, Any]] = []
_SERVICES: List[Dict[str, Any]] = []          # {plugin, factory}
_ROUTERS: List[Dict[str, Any]] = []           # {plugin, router}
_REPAIRS: Dict[str, Any] = {}                 # plugin_name -> repair(finding)->dict
_PLUGIN_SETTINGS: Dict[str, List[Dict[str, Any]]] = {}  # plugin_name -> [descriptors]


def _reset() -> None:
    """Clear the registry (used by reload + tests)."""
    _PLUGINS.clear()
    _TOOLS.clear()
    _HOOKS.clear()
    _COOKBOOK_PROVIDERS.clear()
    _SERVICES.clear()
    _ROUTERS.clear()
    _REPAIRS.clear()
    _PLUGIN_SETTINGS.clear()


# ── the API handed to each plugin's register() ───────────────────────────────

class PluginAPI:
    """Capability object passed to a plugin's register(). Every method is gated
    on the plugin's manifest-declared permissions — calling one for an
    undeclared surface raises PermissionError, so the manifest is an honest,
    enforced description of what the plugin can do."""

    def __init__(self, name: str, permissions: set):
        self.name = name
        self._perms = set(permissions)
        self.logger = logging.getLogger(f"plugin.{name}")

    def _require(self, perm: str) -> None:
        if perm not in self._perms:
            raise PermissionError(
                f"Plugin {self.name!r} called a '{perm}' API but did not declare "
                f"\"{perm}\" in its manifest permissions {sorted(self._perms)}."
            )

    # — tools —
    def register_tool(self, name: str,
                      handler: Callable[[str, Optional[str]], Awaitable[Dict]],
                      *, description: str = "", risk_category: Optional[str] = None,
                      schema: Optional[Dict] = None) -> None:
        """Register an agent tool. `handler(content, owner)` -> result dict.
        It is dispatched from execute_tool_block AFTER the Aegis firewall and the
        admin/public gates, so plugin tools inherit all existing protections.
        `risk_category` (exec/system-write/external/data-write/read) tunes the
        Aegis base score for this tool."""
        self._require("tools")
        if name in _TOOLS:
            logger.warning("plugin %s: tool %r already registered by %s — overriding",
                           self.name, name, _TOOLS[name].get("plugin"))
        _TOOLS[name] = {"handler": handler, "plugin": self.name,
                        "description": description, "risk_category": risk_category,
                        "schema": schema}

    # — hooks —
    def register_hook(self, event: str, fn: Callable) -> None:
        """Register a lifecycle hook. Events:
          • pre_tool(tool, content, owner) -> None | dict   (dict result = veto/block)
          • post_tool(tool, content, result) -> None
          • build_prompt(prompt, context) -> str | None     (return modifies prompt)
          • diagnostic() -> dict | list[dict]               (self-check for the debugger:
              {name, status: ok|warn|error, detail, hint})
        """
        self._require("hooks")
        if event not in _VALID_HOOK_EVENTS:
            raise ValueError(f"unknown hook event {event!r}; valid: {sorted(_VALID_HOOK_EVENTS)}")
        _HOOKS.setdefault(event, []).append({"plugin": self.name, "fn": fn})

    def register_repair(self, fn: Callable) -> None:
        """Register a self-repair handler: `fn(finding) -> {ok, detail}`. The
        Cookbook debugger's one-click fix calls this for a finding from this
        plugin BEFORE falling back to a Copilot code-fix — so a plugin can heal
        itself (reset state, re-enable, re-create a file) without touching core."""
        self._require("hooks")
        _REPAIRS[self.name] = fn

    def register_settings(self, descriptors: List[Dict[str, Any]]) -> None:
        """Declare this plugin's own settings so the admin UI can render a form
        for them (shown under the plugin in /manage). Each descriptor:
          {key, label, type: bool|select|text|int, default, options?(select), secret?}
        Values live in the normal settings store (read via api.get_setting); this
        just describes them. No permission needed — it's declarative metadata."""
        if not isinstance(descriptors, list):
            return
        existing = {d.get("key") for d in _PLUGIN_SETTINGS.get(self.name, [])}
        _PLUGIN_SETTINGS.setdefault(self.name, []).extend(
            [d for d in descriptors if isinstance(d, dict) and d.get("key")
             and d["key"] not in existing])

    # — cookbook —
    def register_cookbook_provider(self, provider: Any) -> None:
        """Register a Cookbook provider. `provider` is any object/dict exposing
        optional callables: catalog() -> [model dicts], profiles() -> [hw profiles],
        score(model, system) -> float|None. Consumed by the cookbook layer."""
        self._require("cookbook")
        _COOKBOOK_PROVIDERS.append({"plugin": self.name, "provider": provider})

    # — services —
    def register_service(self, factory: Callable[[], Awaitable[None]]) -> None:
        """Register a background service. `factory()` returns a coroutine that is
        launched as a task at app startup."""
        self._require("services")
        _SERVICES.append({"plugin": self.name, "factory": factory})

    # — routes —
    def register_router(self, router: Any) -> None:
        """Register a FastAPI APIRouter, included into the app at load time."""
        self._require("routes")
        _ROUTERS.append({"plugin": self.name, "router": router})

    # — conveniences —
    def get_setting(self, key: str, default: Any = None) -> Any:
        try:
            from src.settings import get_setting
            v = get_setting(key, default)
            return default if v is None else v
        except Exception:
            return default

    def data_dir(self) -> str:
        try:
            from src.constants import DATA_DIR
            return DATA_DIR
        except Exception:
            return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


# ── loading ──────────────────────────────────────────────────────────────────

def _plugins_root() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")


def _load_one(plugin_dir: str) -> Dict[str, Any]:
    """Load a single plugin directory. Returns a status record (never raises)."""
    name = os.path.basename(plugin_dir.rstrip("/"))
    rec: Dict[str, Any] = {"name": name, "dir": plugin_dir, "status": "error",
                           "permissions": [], "error": None}
    manifest_path = os.path.join(plugin_dir, "plugin.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        rec["error"] = f"no/invalid plugin.json: {e}"
        return rec

    rec["name"] = manifest.get("name", name)
    rec["version"] = manifest.get("version", "?")
    rec["description"] = manifest.get("description", "")
    # Manifest-declared settings are registered even for DISABLED plugins, so the
    # UI can set their config (e.g. a bot token) BEFORE enabling them.
    _ms = manifest.get("settings")
    if isinstance(_ms, list):
        _PLUGIN_SETTINGS[rec["name"]] = [d for d in _ms if isinstance(d, dict) and d.get("key")]
    if not manifest.get("enabled", True):
        rec["status"] = "disabled"
        return rec

    perms = manifest.get("permissions", []) or []
    bad = [p for p in perms if p not in _VALID_PERMISSIONS]
    if bad:
        rec["error"] = f"unknown permissions {bad}; valid: {sorted(_VALID_PERMISSIONS)}"
        return rec
    rec["permissions"] = perms

    entry = manifest.get("entry", "plugin")
    module_path = os.path.join(plugin_dir, f"{entry}.py")
    if not os.path.exists(module_path):
        rec["error"] = f"entry module {entry}.py not found"
        return rec

    try:
        # Import as a uniquely-named module so two plugins can both have plugin.py.
        mod_name = f"odysseus_plugin_{rec['name']}".replace("-", "_")
        spec = importlib.util.spec_from_file_location(mod_name, module_path)
        module = importlib.util.module_from_spec(spec)
        # Make the plugin dir importable so the entry can do relative-ish imports.
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        rec["error"] = f"import failed: {e}"
        logger.warning("plugin %s import failed: %s", rec["name"], e, exc_info=True)
        return rec

    register = getattr(module, "register", None)
    if not callable(register):
        rec["error"] = "module has no register(api) function"
        return rec

    try:
        api = PluginAPI(rec["name"], set(perms))
        register(api)
    except Exception as e:
        rec["error"] = f"register() raised: {e}"
        logger.warning("plugin %s register() failed: %s", rec["name"], e, exc_info=True)
        return rec

    rec["status"] = "loaded"
    rec["error"] = None
    return rec


def load_all(plugins_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """Discover and load every plugin under the plugins root. Idempotent: clears
    the registry first. One bad plugin never blocks the others or startup."""
    _reset()
    try:
        if not bool(_setting("plugins_enabled", True)):
            logger.info("plugin system disabled (plugins_enabled=false)")
            return []
    except Exception:
        pass
    root = plugins_root or _plugins_root()
    if not os.path.isdir(root):
        return []
    for entry in sorted(os.listdir(root)):
        d = os.path.join(root, entry)
        if not os.path.isdir(d) or entry.startswith((".", "_")):
            continue
        if not os.path.exists(os.path.join(d, "plugin.json")):
            continue
        rec = _load_one(d)
        _PLUGINS.append(rec)
        if rec["status"] == "loaded":
            logger.info("plugin loaded: %s v%s (perms=%s)",
                        rec["name"], rec.get("version"), rec.get("permissions"))
        elif rec["status"] == "error":
            logger.warning("plugin FAILED: %s — %s", rec["name"], rec.get("error"))
    logger.info("plugins: %d loaded, %d failed, %d disabled",
                sum(1 for p in _PLUGINS if p["status"] == "loaded"),
                sum(1 for p in _PLUGINS if p["status"] == "error"),
                sum(1 for p in _PLUGINS if p["status"] == "disabled"))
    return list(_PLUGINS)


def _setting(key: str, default: Any) -> Any:
    try:
        from src.settings import get_setting
        v = get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


# ── accessors used by the host app ───────────────────────────────────────────

def list_plugins() -> List[Dict[str, Any]]:
    # Strip non-serialisable handler refs for status display.
    return [{k: v for k, v in p.items()} for p in _PLUGINS]


def has_tool(name: str) -> bool:
    return name in _TOOLS


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    return _TOOLS.get(name)


def list_tools() -> List[Dict[str, Any]]:
    return [{"name": n, "plugin": t["plugin"], "description": t["description"],
             "risk_category": t.get("risk_category")} for n, t in _TOOLS.items()]


def tool_risk_category(name: str) -> Optional[str]:
    t = _TOOLS.get(name)
    return t.get("risk_category") if t else None


async def dispatch_tool(name: str, content: str, owner: Optional[str] = None) -> Dict[str, Any]:
    """Execute a registered plugin tool. Assumes has_tool(name) is True."""
    t = _TOOLS[name]
    return await t["handler"](content, owner)


def get_cookbook_providers() -> List[Any]:
    return [p["provider"] for p in _COOKBOOK_PROVIDERS]


def get_services() -> List[Dict[str, Any]]:
    return list(_SERVICES)


def get_routers() -> List[Any]:
    return [r["router"] for r in _ROUTERS]


# ── hook execution ───────────────────────────────────────────────────────────

def run_pre_tool(tool: str, content: str, owner: Optional[str]) -> Optional[Dict[str, Any]]:
    """Run pre_tool hooks. If any returns a dict, that is treated as a veto and
    returned as the tool result (blocks execution). Hook errors are swallowed."""
    for h in _HOOKS.get("pre_tool", []):
        try:
            out = h["fn"](tool, content, owner)
            if isinstance(out, dict):
                logger.info("plugin %s pre_tool vetoed %s", h["plugin"], tool)
                return out
        except Exception as e:
            logger.debug("plugin %s pre_tool hook error: %s", h["plugin"], e)
    return None


def run_post_tool(tool: str, content: str, result: Dict[str, Any]) -> None:
    for h in _HOOKS.get("post_tool", []):
        try:
            h["fn"](tool, content, result)
        except Exception as e:
            logger.debug("plugin %s post_tool hook error: %s", h["plugin"], e)


def plugin_settings(plugin: Optional[str] = None):
    """Declared settings: one plugin's list, or {plugin: [descriptors]} for all."""
    if plugin is not None:
        return list(_PLUGIN_SETTINGS.get(plugin, []))
    return {k: list(v) for k, v in _PLUGIN_SETTINGS.items()}


def plugin_setting_keys() -> set:
    """All keys any plugin declared — used to allow them through the manage API."""
    return {d["key"] for ds in _PLUGIN_SETTINGS.values() for d in ds if d.get("key")}


def plugins_with_diagnostic() -> set:
    """Names of plugins that registered a diagnostic hook (debugger-compatible)."""
    return {h["plugin"] for h in _HOOKS.get("diagnostic", [])}


def has_repair(plugin: str) -> bool:
    return plugin in _REPAIRS


def run_repair(plugin: str, finding: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a plugin's own repair handler for a finding. Returns {ok, detail}."""
    fn = _REPAIRS.get(plugin)
    if not fn:
        return {"ok": False, "detail": f"plugin {plugin!r} has no repair handler"}
    try:
        res = fn(finding)
        if isinstance(res, dict):
            res.setdefault("ok", True)
            return res
        return {"ok": True, "detail": str(res)}
    except Exception as e:
        return {"ok": False, "detail": f"repair raised: {e}"}


def run_diagnostics() -> List[Dict[str, Any]]:
    """Run every plugin's `diagnostic` hook and collect results for the debugger.
    Each result is normalised to {area, name, status, detail, hint}. A hook that
    raises becomes an error result rather than breaking the report."""
    out: List[Dict[str, Any]] = []
    for h in _HOOKS.get("diagnostic", []):
        try:
            res = h["fn"]()
            items = res if isinstance(res, list) else [res]
            for it in items:
                if isinstance(it, dict):
                    it.setdefault("area", f"plugin:{h['plugin']}")
                    it.setdefault("name", "diagnostic")
                    it.setdefault("status", "ok")
                    out.append(it)
        except Exception as e:
            out.append({"area": f"plugin:{h['plugin']}", "name": "diagnostic",
                        "status": "error", "detail": f"diagnostic hook raised: {e}",
                        "hint": "fix the plugin's diagnostic() function"})
    return out


def apply_prompt_hooks(prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Chain build_prompt hooks; each may return a modified prompt."""
    context = context or {}
    for h in _HOOKS.get("build_prompt", []):
        try:
            out = h["fn"](prompt, context)
            if isinstance(out, str) and out:
                prompt = out
        except Exception as e:
            logger.debug("plugin %s build_prompt hook error: %s", h["plugin"], e)
    return prompt
