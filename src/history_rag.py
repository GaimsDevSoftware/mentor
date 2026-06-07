"""RAG over conversation history — never lose an old detail on a small window.

Compaction summarizes old turns, but summaries DRIFT (each pass loses low-frequency
detail). This keeps the FULL TEXT of every turn in a vector store and RETRIEVES the
few old turns relevant to the current question — so the model can recall an exact
detail from early in a long chat even after it scrolled out of the window.

Defensive by design: if ChromaDB or embeddings are unavailable it silently no-ops
(the chat still works, just without long-range recall). Indexing is fire-and-forget;
retrieval is best-effort and never raises.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COLLECTION = "odysseus_conversation_history"
_MIN_CHARS = 40          # don't index trivial turns ("ok", "thanks")
_MAX_DOC = 2000          # cap stored/queried text


class _HistoryRAG:
    def __init__(self):
        self._c = None
        self._model = None
        self._ok = False
        self._init()

    def _init(self):
        try:
            from src.chroma_client import get_chroma_client
            from src.embeddings import get_embedding_client
            self._model = get_embedding_client()
            if self._model is None:
                return
            self._c = get_chroma_client().get_or_create_collection(
                name=COLLECTION, metadata={"hnsw:space": "cosine"})
            self._ok = True
        except Exception as e:
            logger.debug("history_rag unavailable (degrades to no recall): %s", e)

    def index(self, session_id: str, role: str, text: str, ts: Optional[float]) -> None:
        if not self._ok or not text or len(text) < _MIN_CHARS:
            return
        try:
            ts = ts or time.time()
            doc = text[:_MAX_DOC]
            tid = hashlib.sha256(f"{session_id}|{role}|{doc[:80]}".encode("utf-8")).hexdigest()[:24]
            if self._c.get(ids=[tid]).get("ids"):
                return
            vec = self._model.encode([doc], normalize_embeddings=True).tolist()
            self._c.add(ids=[tid], embeddings=vec, documents=[doc],
                        metadatas=[{"session_id": session_id or "", "role": role,
                                    "ts": float(ts)}])
        except Exception as e:
            logger.debug("history_rag index skipped: %s", e)

    def retrieve(self, session_id: str, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if not self._ok or not query:
            return []
        try:
            if self._c.count() == 0:
                return []
            vec = self._model.encode([query[:_MAX_DOC]], normalize_embeddings=True).tolist()
            where = {"session_id": session_id} if session_id else None
            res = self._c.query(query_embeddings=vec, n_results=min(k, self._c.count()),
                                where=where)
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            out = []
            for i, doc in enumerate(docs):
                out.append({"text": doc, "role": metas[i].get("role"),
                            "ts": metas[i].get("ts"), "score": round(1 - dists[i], 3)})
            return out
        except Exception as e:
            logger.debug("history_rag retrieve skipped: %s", e)
            return []


_inst: Optional[_HistoryRAG] = None


def _store() -> _HistoryRAG:
    global _inst
    if _inst is None:
        _inst = _HistoryRAG()
    return _inst


def index_turn(session_id: str, role: str, text: str, ts: Optional[float] = None) -> None:
    try:
        _store().index(session_id, role, text, ts)
    except Exception:
        pass


def retrieve(session_id: str, query: str, k: int = 3) -> List[Dict[str, Any]]:
    try:
        return _store().retrieve(session_id, query, k)
    except Exception:
        return []


def context_block(session_id: str, query: str, *, k: int = 3, min_score: float = 0.35,
                  already_present: str = "") -> str:
    """A compact system-message block of relevant EARLIER turns, or "" if none.
    Skips low-relevance hits and anything whose text is already in the live
    context (so it never duplicates recent turns)."""
    hits = retrieve(session_id, query, k=k)
    lines = []
    for h in hits:
        t = (h.get("text") or "").strip()
        if not t or h.get("score", 0) < min_score:
            continue
        if t[:120] in already_present:   # already in the live window
            continue
        lines.append(f"- ({h.get('role', '?')}) {t[:600]}")
    if not lines:
        return ""
    return ("## Relevant earlier context (retrieved from this conversation)\n"
            "These older messages may matter for the current request:\n" + "\n".join(lines))
