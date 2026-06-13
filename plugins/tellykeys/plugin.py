"""tellykeys — Fjernkontroll for Google TV / Android TV.

Plugin wraps the tellykeys library and registers agent tools for discovering,
pairing, and controlling a TV from the chat.  Includes a high-level
``tellykeys_play`` tool that chains connect → launch → search → select in one
step so the AI can handle "play X on Netflix" autonomously.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

_TELLYKEYS_ROOT = Path(__file__).resolve().parent.parent.parent / "tellykeys" / "src"
if str(_TELLYKEYS_ROOT) not in sys.path:
    sys.path.insert(0, str(_TELLYKEYS_ROOT))

from tellykeys.remote import TellyKeysRemote, TvStatus

logger = logging.getLogger(__name__)

_config = {"host": "10.0.0.2"}

APP_PACKAGES = {
    "netflix": "com.netflix.ninja",
    "youtube": "com.google.android.youtube.tv",
    "disney+": "com.disney.disneyplus",
    "disney plus": "com.disney.disneyplus",
    "hbo": "com.hbo.hbonow",
    "hbo max": "com.hbo.hbonow",
    "prime video": "com.amazon.amazonvideo.livingroom",
    "amazon prime": "com.amazon.amazonvideo.livingroom",
    "spotify": "com.spotify.tv.android",
    "nrk": "no.nrk.tv",
    "tv2 play": "no.tv2.tv2play",
    "viaplay": "com.viaplay.android",
    "plex": "com.plexapp.android",
    "kodi": "org.xbmc.kodi",
    "twitch": "tv.twitch.android.app",
    "apple tv": "com.apple.atve.androidtv.appletv",
}

# Singleton remote and connection state.
_remote: TellyKeysRemote | None = None
_connected = False


def _get_remote() -> TellyKeysRemote:
    global _remote
    if _remote is None:
        _remote = TellyKeysRemote()
    return _remote


async def _ensure_connected(host: str | None = None) -> TellyKeysRemote:
    global _connected
    remote = _get_remote()
    target = (host or _config["host"]).strip()
    if _connected and remote.host == target:
        return remote
    await remote.prepare(target)
    await remote.connect()
    _connected = True
    return remote


def _parse(content: str) -> dict:
    if not content or not content.strip():
        return {}
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {}


def _resolve_app(name: str) -> str | None:
    key = name.lower().strip()
    if key in APP_PACKAGES:
        return APP_PACKAGES[key]
    for k, v in APP_PACKAGES.items():
        if key in k or k in key:
            return v
    if "." in name:
        return name
    return None


# ------------------------------------------------------------------
#  TOOL HANDLERS — all async, signature: (content: str, owner) -> dict
# ------------------------------------------------------------------

async def _tool_discover(content: str, owner) -> dict:
    args = _parse(content)
    timeout = int(args.get("timeout", 5))
    try:
        from tellykeys.discovery import discover_android_tvs
        devices = await asyncio.to_thread(discover_android_tvs, timeout_s=timeout)
    except Exception as exc:
        return {"response": f"Kunne ikke oppdage TV-er: {exc}"}
    if not devices:
        return {"response": "Ingen TV-er funnet. Sjekk at TV-en er på og koblet til samme nettverk."}
    lines = [f"  {i}. {d.name} — {d.host}:{d.port}" for i, d in enumerate(devices, 1)]
    return {"response": "Oppdagede TV-er:\n" + "\n".join(lines)}


async def _tool_status(content: str, owner) -> dict:
    try:
        remote = await _ensure_connected()
        st = remote.status()
        return {"response": json.dumps({
            "name": st.name, "is_on": st.is_on,
            "current_app": st.current_app, "volume": st.volume,
        }, ensure_ascii=False)}
    except Exception as exc:
        return {"response": f"Kunne ikke hente status: {exc}"}


async def _tool_send_key(content: str, owner) -> dict:
    args = _parse(content)
    key = (args.get("key") or "").upper()
    if not key:
        return {"response": "Mangler 'key'."}
    try:
        remote = await _ensure_connected()
        remote.key(key)
        return {"response": f"Sendte {key} til TV-en."}
    except Exception as exc:
        return {"response": f"Feil: {exc}"}


async def _tool_send_text(content: str, owner) -> dict:
    args = _parse(content)
    text = args.get("text", "")
    if not text:
        return {"response": "Mangler 'text'."}
    try:
        remote = await _ensure_connected()
        method = remote.text(text)
        return {"response": f"Sendte tekst via {method or 'remote_ime'}: \"{text}\""}
    except Exception as exc:
        return {"response": f"Feil: {exc}"}


async def _tool_launch_app(content: str, owner) -> dict:
    args = _parse(content)
    package = args.get("package", "")
    resolved = _resolve_app(package) if package else None
    if not resolved:
        return {"response": f"Ukjent app: {package!r}. Oppgi pakkenavn (f.eks. com.netflix.ninja)."}
    try:
        remote = await _ensure_connected()
        remote.launch(resolved)
        await asyncio.sleep(3)
        st = remote.status()
        return {"response": f"Startet {resolved}. Aktiv app: {st.current_app}"}
    except Exception as exc:
        return {"response": f"Feil: {exc}"}


async def _tool_disconnect(content: str, owner) -> dict:
    global _connected, _remote
    try:
        if _remote:
            _remote.disconnect()
        _remote = None
        _connected = False
        return {"response": "Koblet fra TV-en."}
    except Exception as exc:
        return {"response": f"Feil: {exc}"}


async def _tool_play(content: str, owner) -> dict:
    """High-level: play <title> on <app>.

    Connects to the TV, launches the app, waits for it to load, types the
    search query, and navigates to play the first result.
    """
    args = _parse(content)
    title = (args.get("title") or args.get("query") or "").strip()
    app_name = (args.get("app") or "netflix").strip()
    if not title:
        return {"response": "Mangler 'title' — hva vil du se?"}

    package = _resolve_app(app_name)
    if not package:
        return {"response": f"Ukjent app: {app_name!r}"}

    steps = []
    try:
        remote = await _ensure_connected()
        steps.append("connected")

        # 1 — launch app
        remote.launch(package)
        steps.append(f"launched {package}")
        await asyncio.sleep(4)

        st = remote.status()
        if st.current_app != package:
            await asyncio.sleep(3)
            st = remote.status()
        steps.append(f"app active: {st.current_app}")

        # 2 — open search  (Netflix: magnifying glass is top-left; send KEY_SEARCH or navigate)
        if package == "com.netflix.ninja":
            remote.key("KEY_SEARCH")
            await asyncio.sleep(2)

            # Try ADB text first (most reliable for Netflix)
            diag = remote.text_diagnostics()
            if diag.adb_installed and diag.adb_authorized:
                method = remote.text(title)
                steps.append(f"searched via {method}")
            else:
                # Netflix opens with search highlighted after KEY_SEARCH;
                # the virtual keyboard should be up — try remote IME
                remote.text(title)
                steps.append("searched via remote_ime")

            await asyncio.sleep(3)

            # 3 — select first result: go down from search to results, then enter
            remote.key("DPAD_DOWN")
            await asyncio.sleep(0.5)
            remote.key("DPAD_DOWN")
            await asyncio.sleep(0.5)
            remote.key("ENTER")
            steps.append("selected first result")
            await asyncio.sleep(2)

            # 4 — press play (or Enter on the show's main screen)
            remote.key("ENTER")
            steps.append("pressed play")

        elif package == "com.google.android.youtube.tv":
            # YouTube: can use contextual search URL
            from urllib.parse import quote_plus
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(title)}"
            remote.launch(search_url)
            steps.append("youtube search via URL")
            await asyncio.sleep(4)
            remote.key("ENTER")
            steps.append("selected first result")

        else:
            # Generic: try KEY_SEARCH, type, navigate
            remote.key("KEY_SEARCH")
            await asyncio.sleep(2)
            remote.text(title)
            steps.append("searched")
            await asyncio.sleep(3)
            remote.key("DPAD_DOWN")
            await asyncio.sleep(0.5)
            remote.key("ENTER")
            steps.append("selected first result")
            await asyncio.sleep(2)
            remote.key("ENTER")
            steps.append("pressed play")

        return {"response": f"Spiller av \"{title}\" på {app_name}. Steg: {', '.join(steps)}"}

    except Exception as exc:
        return {"response": f"Feil under avspilling: {exc}. Kom til: {', '.join(steps)}"}


async def _tool_text_diagnostics(content: str, owner) -> dict:
    try:
        remote = await _ensure_connected()
        diag = remote.text_diagnostics()
        return {"response": json.dumps({
            "adb_installed": diag.adb_installed,
            "adb_authorized": diag.adb_authorized,
            "adb_target": diag.adb_target,
            "ime_field_counter": diag.ime_field_counter,
            "current_app": diag.current_app,
            "bluetooth_enabled": diag.bluetooth_enabled,
            "bluetooth_keyboard_connected": diag.bluetooth_keyboard_connected,
        }, ensure_ascii=False)}
    except Exception as exc:
        return {"response": f"Feil: {exc}"}


# ------------------------------------------------------------------
#  REGISTER
# ------------------------------------------------------------------

def register(api):
    logger.info("tellykeys plugin loaded")

    host = api.get_setting("tellykeys_default_host", _config["host"])
    if host:
        _config["host"] = host

    api.register_tool(
        "tellykeys_play", _tool_play,
        description=(
            "Play a show/movie/video on the TV. JSON args: "
            "{\"title\": \"Gabby's Dollhouse\", \"app\": \"netflix\"}. "
            "Auto-connects, launches the app, searches, and starts playback. "
            "Supported apps: netflix, youtube, disney+, hbo, prime video, "
            "spotify, nrk, plex, apple tv, and any Android package name."
        ),
        risk_category="external",
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Show, movie, or video to search for"},
                "app": {"type": "string", "description": "App name or Android package (default: netflix)"},
            },
            "required": ["title"],
        },
    )

    api.register_tool(
        "tellykeys_send_key", _tool_send_key,
        description=(
            "Send a remote-control key to the TV. JSON: {\"key\": \"DPAD_UP\"}. "
            "Keys: DPAD_UP/DOWN/LEFT/RIGHT, ENTER, BACK, HOME, KEY_SEARCH, "
            "VOLUME_UP/DOWN, MUTE, POWER, MEDIA_PLAY/PAUSE/STOP, 0-9."
        ),
        risk_category="external",
        schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key code to send"},
            },
            "required": ["key"],
        },
    )

    api.register_tool(
        "tellykeys_send_text", _tool_send_text,
        description="Type text on the TV (search fields, etc). JSON: {\"text\": \"...\"}.",
        risk_category="external",
        schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type"},
            },
            "required": ["text"],
        },
    )

    api.register_tool(
        "tellykeys_launch_app", _tool_launch_app,
        description=(
            "Launch an app on the TV. JSON: {\"package\": \"netflix\"} or "
            "{\"package\": \"com.netflix.ninja\"}. Accepts friendly names."
        ),
        risk_category="external",
        schema={
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "App name or Android package"},
            },
            "required": ["package"],
        },
    )

    api.register_tool(
        "tellykeys_status", _tool_status,
        description="Get TV status: power, current app, volume, device name.",
        risk_category="read",
    )

    api.register_tool(
        "tellykeys_discover", _tool_discover,
        description="Discover Android TV / Google TV devices on the local network via mDNS.",
        risk_category="read",
        schema={
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "description": "Seconds to scan (default 5)"},
            },
        },
    )

    api.register_tool(
        "tellykeys_text_diagnostics", _tool_text_diagnostics,
        description="Check text-input health: ADB status, IME state, Bluetooth keyboard.",
        risk_category="read",
    )

    api.register_tool(
        "tellykeys_disconnect", _tool_disconnect,
        description="Disconnect from the TV.",
        risk_category="read",
    )

    # Hook: inject TV awareness into the prompt when relevant.
    def _prompt_hook(prompt, context):
        return None

    api.register_hook("build_prompt", _prompt_hook)

    # Diagnostic for health_watch.
    def _diagnostic():
        findings = []
        if not Path(_TELLYKEYS_ROOT / "tellykeys" / "remote.py").exists():
            findings.append({
                "name": "tellykeys-lib",
                "status": "error",
                "detail": f"tellykeys library not found at {_TELLYKEYS_ROOT}",
                "hint": "Clone the tellykeys repo as a sibling of odysseus.",
            })
        cert = Path.home() / ".config" / "tellykeys" / "devices" / _config["host"] / "cert.pem"
        if not cert.exists():
            findings.append({
                "name": "tellykeys-pairing",
                "status": "warn",
                "detail": f'No pairing certificate for {_config["host"]}',
                "hint": "Use tellykeys_discover + pair from the TV.",
            })
        if not findings:
            findings.append({
                "name": "tellykeys",
                "status": "ok",
                "detail": f'Paired with {_config["host"]}, ready',
            })
        return findings

    api.register_hook("diagnostic", _diagnostic)

    try:
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/api/plugins/tellykeys/tools")
        async def route_tools():
            return {"tools": [
                "tellykeys_play", "tellykeys_send_key", "tellykeys_send_text",
                "tellykeys_launch_app", "tellykeys_status", "tellykeys_discover",
                "tellykeys_text_diagnostics", "tellykeys_disconnect",
            ]}

        api.register_router(router)
    except Exception:
        pass

    return {"ok": True, "plugin": "tellykeys"}
