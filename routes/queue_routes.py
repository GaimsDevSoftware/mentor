"""Message-queue persistence — /api/queue/*.

The client TurnManager holds the live message queue (messages typed while a
turn is streaming). This persists a per-session MIRROR so the queue survives a
page reload. The in-memory queue stays the source of truth; these calls are
best-effort — a failure here never blocks the live queue.

Sync model: whole-list replace (PUT). The queue is tiny (a handful of
messages), so replacing it on each change is simpler and race-free compared to
per-item add/remove + id tracking. Keyed by session_id → per-window isolation
(each popup is its own session).
"""
import uuid

from fastapi import APIRouter, HTTPException, Request, Body

from core.database import get_db_session, QueuedMessage
from src.auth_helpers import get_current_user
from routes.session_routes import _verify_session_owner

MAX_QUEUE_ITEMS = 50
MAX_TEXT_LEN = 20000


def setup_queue_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/queue/{session_id}")
    async def get_queue(session_id: str, request: Request):
        """Return the persisted queue texts for a session, in FIFO order."""
        _verify_session_owner(request, session_id)
        with get_db_session() as db:
            rows = (db.query(QueuedMessage)
                      .filter(QueuedMessage.session_id == session_id)
                      .order_by(QueuedMessage.position)
                      .all())
            return {"queue": [r.text for r in rows]}

    @router.put("/api/queue/{session_id}")
    async def replace_queue(session_id: str, request: Request, payload: dict = Body(...)):
        """Replace the session's queue with the provided ordered list of texts.
        Empty list clears it. Best-effort persistence of the client queue."""
        _verify_session_owner(request, session_id)
        texts = payload.get("texts")
        if not isinstance(texts, list):
            raise HTTPException(400, "texts must be a list")
        # Sanity bounds — never let a runaway client bloat the table.
        clean = []
        for t in texts[:MAX_QUEUE_ITEMS]:
            if isinstance(t, str) and t.strip():
                clean.append(t[:MAX_TEXT_LEN])
        owner = get_current_user(request)
        with get_db_session() as db:
            db.query(QueuedMessage).filter(QueuedMessage.session_id == session_id).delete()
            for i, t in enumerate(clean):
                db.add(QueuedMessage(id=str(uuid.uuid4()), owner=owner,
                                     session_id=session_id, text=t, position=i))
        return {"ok": True, "count": len(clean)}

    return router
