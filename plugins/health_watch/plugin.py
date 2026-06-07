"""health_watch — surfaces active app health to the assistant.

The diagnostics engine (src/debugger) already knows what's wrong; this plugin
makes the chat AI actually NOTICE it. A background service refreshes a cached
health snapshot every N seconds (off the event loop), a build_prompt hook injects
a short summary of any active errors/warnings into the agent's prompt, and an
`app_health` tool lets the AI pull the full report on demand.

Read-only: it never changes anything. It only injects context when there is a
real warning or error to report, so it doesn't nag.
"""
import time

_cache = {"ts": 0.0, "data": None}


def _findings(data):
    out = []
    for area, items in (data or {}).get("groups", {}).items():
        for f in items:
            if f.get("status") in ("warn", "error"):
                out.append(f)
    return out


def register(api):
    # ── background refresher (off the event loop, never blocks chat) ──────────
    async def _watch_loop():
        import asyncio
        while True:
            ttl = 180
            try:
                ttl = max(60, int(api.get_setting("health_watch_ttl", 180) or 180))
                from src import debugger
                _cache["data"] = await asyncio.to_thread(debugger.run_all, only_failures=True)
                _cache["ts"] = time.time()
            except Exception as e:
                try:
                    api.logger.debug("health_watch refresh failed: %s", e)
                except Exception:
                    pass
            await asyncio.sleep(ttl)

    api.register_service(_watch_loop)

    # ── make the assistant aware (prompt injection, only when there's something) ─
    def _prompt_hook(prompt, context):
        if not api.get_setting("health_watch_inject", True):
            return None
        data = _cache.get("data")
        if not data:
            return None
        c = data.get("counts", {})
        errs, warns = c.get("error", 0), c.get("warn", 0)
        if not errs and not warns:
            return None
        fs = _findings(data)
        fs.sort(key=lambda f: 0 if f.get("status") == "error" else 1)  # errors first
        lines = [f"- [{f.get('status')}] {f.get('area')}/{f.get('name')}: {f.get('detail','')}"
                 for f in fs[:6]]
        return prompt + (
            "\n\n## App health (live)\n"
            f"Self-diagnostics currently report {errs} error(s) and {warns} warning(s):\n"
            + "\n".join(lines)
            + "\nIf the user asks whether everything is OK, or a request is blocked by one of these, "
            "tell them plainly and offer the fix: the Diagnostics page (/manage#diag) has one-click "
            "fixes and a 'Fix all safe issues' button, or call the `app_health` tool for the full "
            "report. Don't bring these up otherwise."
        )

    api.register_hook("build_prompt", _prompt_hook)

    # ── on-demand full check the AI can call ─────────────────────────────────
    async def _app_health(content, owner):
        try:
            from src import debugger
            import asyncio
            data = await asyncio.to_thread(debugger.run_all, only_failures=False)
        except Exception as e:
            return {"response": f"Could not read diagnostics: {e}", "exit_code": 1}
        c = data.get("counts", {})
        lines = [f"Overall: {data.get('overall')} — "
                 f"{c.get('ok',0)} ok / {c.get('warn',0)} warn / {c.get('error',0)} err"]
        for f in _findings(data):
            hint = f"  (fix: {f.get('hint')})" if f.get("hint") else ""
            lines.append(f"- [{f.get('status')}] {f.get('area')}/{f.get('name')}: {f.get('detail','')}{hint}")
        if len(lines) == 1:
            lines.append("No warnings or errors — everything healthy.")
        return {"response": "\n".join(lines), "exit_code": 0}

    api.register_tool(
        "app_health", _app_health,
        description="Check the app's own health/diagnostics (errors, warnings) across serving, "
                    "embeddings/ChromaDB, plugins, memory and the local fleet. Use when the user "
                    "asks if everything is OK or wants to troubleshoot the app itself.",
        risk_category="read",
    )

    # ── debugger-compatible self-check (reads cache; never recurses run_all) ──
    def _diagnostic():
        data = _cache.get("data")
        if data is None:
            return {"name": "health_watch", "status": "ok",
                    "detail": "active (snapshot pending)", "hint": ""}
        c = data.get("counts", {})
        age = int(time.time() - _cache.get("ts", 0))
        return {"name": "health_watch", "status": "ok",
                "detail": f"active — last snapshot {age}s ago: {c.get('error',0)} err / {c.get('warn',0)} warn",
                "hint": ""}

    api.register_hook("diagnostic", _diagnostic)
