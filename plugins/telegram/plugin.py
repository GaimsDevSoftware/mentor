"""telegram — use Telegram as a mobile front-end to your Odysseus assistant.

A background SERVICE long-polls the Telegram Bot API (getUpdates); each message
from an ALLOWLISTED user is run through the full agent (ChatBridge, mode "agent":
tools/memory/skills) and the reply is sent back. Long-polling needs no public
webhook, so it works behind a home NAT. Disabled by default; needs a bot token
(from @BotFather) + your Telegram numeric user id.

Settings: telegram_bot_token, telegram_allowed_user_ids (list of ints/strings),
telegram_owner (Odysseus owner whose model/data to use), telegram_mode (agent|chat).
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)
_api = None
API = "https://api.telegram.org/bot{token}/{method}"
TG_LIMIT = 4096  # Telegram message length cap


def _cfg(key, default):
    try:
        return _api.get_setting(key, default)
    except Exception:
        return default


def _build_bridge():
    from src.chat_bridge import ChatBridge
    return ChatBridge(
        "telegram",
        owner=str(_cfg("telegram_owner", "admin") or "admin"),
        allowed_ids=_cfg("telegram_allowed_user_ids", []) or [],
        mode=str(_cfg("telegram_mode", "agent") or "agent"),
        model_spec=str(_cfg("telegram_model", "") or ""),
    )


async def _api_call(client, token, method, **params):
    r = await client.post(API.format(token=token, method=method), json=params, timeout=45)
    r.raise_for_status()
    return r.json()


async def _send(client, token, chat_id, text):
    text = text or "(no response)"
    # Telegram caps messages at 4096 chars — chunk long agent answers.
    for i in range(0, len(text), TG_LIMIT):
        try:
            await _api_call(client, token, "sendMessage", chat_id=chat_id,
                            text=text[i:i + TG_LIMIT])
        except Exception as e:
            logger.warning("telegram send failed: %s", e)
            break


async def _service():
    """Long-poll Telegram and dispatch messages. Idles (no spam) until a token is
    configured; survives errors with backoff; never raises out."""
    import httpx
    offset = 0
    bridge = None
    logger.info("telegram service started (idle until token configured)")
    async with httpx.AsyncClient() as client:
        while True:
            token = (_cfg("telegram_bot_token", "") or "").strip()
            if not token:
                await asyncio.sleep(20)
                continue
            try:
                if bridge is None:
                    bridge = _build_bridge()
                resp = await _api_call(client, token, "getUpdates", offset=offset,
                                       timeout=30, allowed_updates=["message"])
                for upd in resp.get("result", []):
                    offset = max(offset, upd.get("update_id", 0) + 1)
                    msg = upd.get("message") or upd.get("edited_message")
                    if not msg:
                        continue
                    chat_id = msg.get("chat", {}).get("id")
                    user_id = (msg.get("from") or {}).get("id")
                    text = msg.get("text", "")
                    if chat_id is None or not text:
                        continue
                    # refresh config each message (cheap) so settings changes apply live
                    bridge.owner = str(_cfg("telegram_owner", "admin") or "admin")
                    bridge.allowed_ids = {str(x) for x in (_cfg("telegram_allowed_user_ids", []) or [])}
                    bridge.mode = str(_cfg("telegram_mode", "agent") or "agent")
                    bridge.model_spec = (str(_cfg("telegram_model", "") or "")).strip() or None
                    if not bridge.is_allowed(user_id):
                        await _send(client, token, chat_id,
                                    "⛔ This is a private assistant. Your Telegram id "
                                    f"({user_id}) is not on its allowlist.")
                        logger.info("telegram: rejected non-allowlisted user %s", user_id)
                        continue
                    try:
                        await _api_call(client, token, "sendChatAction",
                                        chat_id=chat_id, action="typing")
                    except Exception:
                        pass
                    reply = await bridge.reply(chat_id, text)
                    await _send(client, token, chat_id, reply)
            except httpx.HTTPStatusError as e:
                # 409 = another getUpdates poller / webhook conflict; 401 = bad token
                logger.warning("telegram poll HTTP error: %s", e)
                await asyncio.sleep(10)
            except Exception as e:
                logger.warning("telegram poll error: %s", e)
                await asyncio.sleep(5)


async def _verify_token(token: str) -> dict:
    import httpx
    async with httpx.AsyncClient() as client:
        return await _api_call(client, token, "getMe")


def _diagnostic():
    token = (_cfg("telegram_bot_token", "") or "").strip()
    allow = _cfg("telegram_allowed_user_ids", []) or []
    if not token:
        return {"name": "telegram", "status": "warn", "detail": "no bot token set",
                "hint": "create a bot with @BotFather, set telegram_bot_token, then enable the plugin"}
    if not allow:
        return {"name": "telegram", "status": "warn",
                "detail": "token set but allowlist empty — the bot will answer NOBODY (fail-safe)",
                "hint": "set telegram_allowed_user_ids to your numeric Telegram id (get it from @userinfobot)"}
    return {"name": "telegram", "status": "ok",
            "detail": f"token set, {len(allow)} allowed user(s), mode={_cfg('telegram_mode','agent')}"}


def register(api):
    global _api
    _api = api
    api.register_service(_service)
    api.register_hook("diagnostic", _diagnostic)
    api.register_settings([
        {"key": "telegram_bot_token", "label": "Bot token (@BotFather)", "type": "text",
         "default": "", "secret": True},
        {"key": "telegram_allowed_user_ids", "label": "Allowed user ids (comma-sep)",
         "type": "text", "default": []},
        {"key": "telegram_mode", "label": "Mode", "type": "select",
         "options": ["agent", "chat"], "default": "agent"},
        {"key": "telegram_model", "label": "Model", "type": "select",
         "suggest_url": "/api/manage/teacher-model-options", "default": "",
         "desc": "Which model this bot replies with. Blank = your default work model. "
                 "Pick a small/fast model for quick phone replies, or a capable one for real "
                 "work; use the filter chips or ✦ AI pick to choose."},
        {"key": "telegram_owner", "label": "Odysseus owner", "type": "text", "default": "admin"},
    ])

    try:
        from fastapi import APIRouter, Depends
        from core.middleware import require_admin
        router = APIRouter()

        @router.get("/api/plugins/telegram/status")
        async def telegram_status(admin: str = Depends(require_admin)):
            token = (_cfg("telegram_bot_token", "") or "").strip()
            out = {"configured": bool(token),
                   "allowed_users": len(_cfg("telegram_allowed_user_ids", []) or []),
                   "mode": _cfg("telegram_mode", "agent")}
            if token:
                try:
                    me = await _verify_token(token)
                    out["bot"] = (me.get("result") or {}).get("username")
                    out["token_valid"] = me.get("ok", False)
                except Exception as e:
                    out["token_valid"] = False
                    out["error"] = str(e)
            return out

        api.register_router(router)
    except Exception as e:
        api.logger.debug("telegram routes skipped: %s", e)
