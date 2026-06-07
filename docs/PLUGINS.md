# Odysseus plugins

In-process, developer-installed plugins with broad freedom — but each plugin
**declares the surfaces it touches** in a manifest, and any tool it registers
still flows through the Aegis firewall and the normal `execute_tool_block` gates.
Freedom with traceability.

## Layout

```
plugins/
  my_plugin/
    plugin.json     # manifest
    plugin.py       # exposes register(api)
    ...             # anything else your plugin needs
```

## Manifest (`plugin.json`)

```json
{
  "name": "my_plugin",
  "version": "0.1.0",
  "description": "What it does.",
  "permissions": ["tools", "hooks", "cookbook", "services", "routes"],
  "entry": "plugin",
  "enabled": true
}
```

`permissions` is enforced: calling an API for a surface you didn't declare
raises `PermissionError`. List only what you use.

## Surfaces

| Permission | API | What it does |
|---|---|---|
| `tools`    | `api.register_tool(name, handler, *, description, risk_category, schema)` | New agent tool. `handler(content, owner)->dict`. Dispatched after Aegis + admin/public gates. `risk_category` ∈ exec/system-write/external/data-write/read tunes Aegis scoring. |
| `hooks`    | `api.register_hook(event, fn)` | `pre_tool(tool, content, owner)->None\|dict` (dict = veto), `post_tool(tool, content, result)`, `build_prompt(prompt, context)->str`, `diagnostic()->dict\|list` (self-check for the debugger). Also `api.register_repair(fn)` → `repair(finding)->{ok,detail}` for one-click self-heal. |
| `cookbook` | `api.register_cookbook_provider(provider)` | Object with optional `catalog()`, `profiles()`, `score(model, system)`. Consumed via `plugin_system.get_cookbook_providers()`. |
| `services` | `api.register_service(factory)` | `factory()` returns a coroutine launched as a background task at startup. |
| `routes`   | `api.register_router(router)` | A FastAPI `APIRouter`, mounted into the app at load. |

Conveniences: `api.get_setting(key, default)`, `api.data_dir()`, `api.logger`.

## Minimal example

```python
# plugins/hello/plugin.py
async def _ping(content, owner):
    return {"response": "pong", "exit_code": 0}

def register(api):
    api.register_tool("ping", _ping, description="Health check.", risk_category="read")
```

```json
{ "name": "hello", "version": "0.1.0", "permissions": ["tools"], "entry": "plugin", "enabled": true }
```

See `plugins/odysseus_local/` for a full reference using tools + hooks +
cookbook + routes.

## Model-source plugins (add your own providers)

To add a model provider (an OpenAI-compatible API-key source, or an OAuth/CLI one),
don't hand-roll it — declare a `ModelSource` and call `.mount(api)`. You get, for
free: login/status/models/recommend routes (`/api/plugins/<slug>/…`), a `<slug>_models`
tool, a **Cookbook section** (the source's models, appearing once you log in), a
debugger diagnostic + one-click reconnect, and registration of an Odysseus
ModelEndpoint so the models are usable as `model@<Name>`. Copilot can then recommend
role→model over them via `/api/plugins/<slug>/recommend`.

```python
# plugins/openrouter/plugin.py   (permissions: routes, hooks, tools, cookbook)
from src.model_source import ModelSource
SOURCE = ModelSource(name="OpenRouter", slug="openrouter",
                     base_url="https://openrouter.ai/api/v1",
                     env_var="OPENROUTER_API_KEY")
def register(api):
    SOURCE.mount(api)
```

For OAuth / CLI-backed sources, pass `resolve=fn(pasted)->(credential, source)`
(e.g. read a token file or shell out) and, if needed, `auth_header=fn(cred)->dict`.
See `plugins/opencode/` for the reference (OpenCode Zen).

## Debugger compatibility (required)

Every plugin SHOULD register a `diagnostic` hook so the Cookbook debugger can see
its health — the debugger flags plugins that don't as not-compatible. Optionally
register a `repair` handler: the debugger's one-click fix calls your `repair(finding)`
first; if you don't have one and the plugin failed to load, Copilot rewrites your
`plugin.py` (scoped to `plugins/<name>/`, never the core app) and verifies by reload.

```python
def _diagnostic():
    return {"name": "health", "status": "ok", "detail": "all good", "hint": ""}

def _repair(finding):
    # reset state / re-enable / recreate a file …
    return {"ok": True, "detail": "reset to defaults"}

def register(api):
    api.register_hook("diagnostic", _diagnostic)
    api.register_repair(_repair)
```

## Lifecycle & safety

- Loaded at startup by `src/plugin_system.load_all()`. One bad plugin is isolated
  (logged, skipped) and never blocks the others or app startup.
- Disable everything with the `plugins_enabled` setting; disable one plugin with
  `"enabled": false` in its manifest.
- Plugins are **trusted, in-process Python** — they run with the app's full
  privileges. Only install plugins you trust. Aegis (`aegis_mode`) gates the
  *tool calls* they expose, not arbitrary code they run, so review plugin source.
