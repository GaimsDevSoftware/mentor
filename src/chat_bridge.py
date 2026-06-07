"""ChatBridge — talk to your Odysseus assistant (FULL AGENT) from a chat client.

Reusable core for "use a chat app (Telegram, …) as a front-end" — like OpenClaw's
mobile connectors. A platform plugin handles TRANSPORT (receive a message, send a
reply); this handles the shared logic: an allowlist (only YOU can talk to the bot),
a per-chat session, and generating a reply.

Two modes (setting via the bridge):
  • "agent" (default) — runs the REAL agent loop: tools, memory, skills, the works,
    exactly like the web UI. The bot can actually DO things from your phone.
  • "chat"            — plain model conversation (no tools). Lighter / fallback.

Both inherit our anti-truncation continuation and history handling, so long
answers aren't cut off on a small screen.
"""
from __future__ import annotations

import json
import logging
from collections import deque
from typing import Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM = ("You are the user's personal Odysseus assistant, reached from a "
                   "mobile chat app. Be concise and helpful; this is a small screen.")


class ChatBridge:
    def __init__(self, name: str, *, owner: str = "admin", allowed_ids=None,
                 system_prompt: Optional[str] = None, max_history: int = 12,
                 mode: str = "agent"):
        self.name = name
        self.owner = owner or "admin"
        self.allowed_ids = {str(x) for x in (allowed_ids or [])}
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM
        self.max_history = max_history
        self.mode = mode if mode in ("agent", "chat") else "agent"
        self._history: Dict[str, Deque[dict]] = {}

    def is_allowed(self, user_id) -> bool:
        # Empty allowlist = locked down (respond to NOBODY) — fail safe, so an
        # unconfigured bot never answers strangers.
        return bool(self.allowed_ids) and str(user_id) in self.allowed_ids

    def reset(self, chat_id) -> None:
        self._history.pop(str(chat_id), None)

    def _hist(self, chat_id) -> Deque[dict]:
        cid = str(chat_id)
        if cid not in self._history:
            self._history[cid] = deque(maxlen=self.max_history)
        return self._history[cid]

    async def reply(self, chat_id, user_text: str) -> str:
        text = (user_text or "").strip()
        if not text:
            return ""
        if text.lower() in ("/reset", "/clear", "/new"):
            self.reset(chat_id)
            return "🧹 Conversation reset."

        hist = self._hist(chat_id)
        try:
            from src.endpoint_resolver import resolve_endpoint
            url, model, headers = resolve_endpoint("default", owner=self.owner)
            if not url or not model:
                return ("⚠️ No default model is configured in Odysseus yet. Set one in "
                        "Settings → Models, then try again.")
            convo = list(hist) + [{"role": "user", "content": text}]
            if self.mode == "agent":
                reply = await self._agent_reply(url, model, headers, convo, chat_id)
            else:
                reply = await self._chat_reply(url, model, headers, convo)
        except Exception as e:
            logger.warning("chat bridge reply failed: %s", e)
            return f"⚠️ Sorry, I hit an error: {e}"

        reply = (reply or "").strip() or "(no response)"
        hist.append({"role": "user", "content": text})
        hist.append({"role": "assistant", "content": reply})
        return reply

    async def _chat_reply(self, url, model, headers, convo) -> str:
        from src.llm_core import complete_with_continuation
        messages = [{"role": "system", "content": self.system_prompt}] + convo
        return await complete_with_continuation(
            url, model, messages, headers=headers or {}, timeout=180, max_rounds=3)

    async def _agent_reply(self, url, model, headers, convo, chat_id) -> str:
        """Run the FULL agent loop and accumulate its text output. Tools, memory,
        skills all run server-side exactly as in the web UI."""
        from src.agent_loop import stream_agent_loop
        from src.model_context import get_context_length
        parts: List[str] = []
        try:
            ctx = get_context_length(url, model)
        except Exception:
            ctx = 0
        async for chunk in stream_agent_loop(
            url, model, convo, headers=headers or {},
            context_length=ctx, session_id=f"{self.name}-{chat_id}", owner=self.owner,
        ):
            if not isinstance(chunk, str) or not chunk.startswith("data:"):
                continue
            payload = chunk[5:].strip()
            if payload == "[DONE]":
                break
            if not payload.startswith("{"):
                continue
            try:
                j = json.loads(payload)
            except (ValueError, TypeError):
                continue
            # text deltas only — skip thinking + tool/metric events
            if isinstance(j, dict) and j.get("delta") and not j.get("thinking"):
                parts.append(j["delta"])
        return "".join(parts)
