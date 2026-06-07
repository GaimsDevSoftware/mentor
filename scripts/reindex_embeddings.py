#!/usr/bin/env python3
"""Reindex all ChromaDB collections after an embedding-model change.

Switching the embedding model changes the vector DIMENSION (e.g. all-MiniLM 384
→ jina-embeddings-v3 1024). ChromaDB collections are fixed-dimension, so old
vectors become unusable and new writes raise a dimension-mismatch — the silent
breakage the upstream community hit (PR #1444). This script rebuilds every
collection: it reads the stored documents, re-embeds them with the CURRENT
embedding client, and recreates the collection at the new dimension.

Safe by default:
  • DRY-RUN unless you pass --apply (prints what would change, touches nothing).
  • --backup dumps each collection to data/embedding_backup_<ts>/ before delete.
  • Documents are the source of truth (collections store `documents=`), so
    re-embedding is lossless for anything that has its text stored.

Usage:
  python scripts/reindex_embeddings.py             # dry-run report
  python scripts/reindex_embeddings.py --backup --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Make `src` importable when run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BATCH = 64


def _state_path() -> str:
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "embedding_state.json")


def _write_state(model: str, dim: int) -> None:
    from core.atomic_io import atomic_write_json
    atomic_write_json(_state_path(), {"model": model, "dim": dim, "ts": time.time()}, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually rebuild (default: dry-run)")
    ap.add_argument("--backup", action="store_true", help="dump collections to JSON before delete")
    args = ap.parse_args()

    from src.embeddings import get_embedding_client
    from src.chroma_client import get_chroma_client

    client = get_embedding_client()
    if client is None:
        print("ERROR: no embedding client available (HTTP endpoint down and fastembed missing).")
        return 2
    dim = client.get_sentence_embedding_dimension()
    model = getattr(client, "model", "?")
    print(f"Active embedding model: {model}  (dim={dim})")

    try:
        chroma = get_chroma_client()
    except Exception as e:
        print(f"ERROR: ChromaDB not reachable: {e}")
        print("Start ChromaDB (the app's chromadb service) and re-run.")
        return 2

    cols = chroma.list_collections()
    if not cols:
        print("No collections found — nothing to reindex.")
        if args.apply:
            _write_state(model, dim)
            print(f"Recorded embedding state ({model}, dim={dim}).")
        return 0

    backup_dir = None
    if args.backup and args.apply:
        from src.constants import DATA_DIR
        backup_dir = os.path.join(DATA_DIR, f"embedding_backup_{int(time.time())}")
        os.makedirs(backup_dir, exist_ok=True)
        print(f"Backups → {backup_dir}")

    total_reembedded = 0
    for col in cols:
        name = col.name
        c = chroma.get_collection(name)
        data = c.get(include=["documents", "metadatas"])
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or [None] * len(ids)
        have_text = sum(1 for d in docs if d)
        print(f"\nCollection '{name}': {len(ids)} items, {have_text} with stored text")
        if len(ids) != have_text:
            print(f"  ! {len(ids)-have_text} item(s) have no stored text and CANNOT be re-embedded (will be dropped).")

        if not args.apply:
            print("  [dry-run] would: backup (if --backup) → delete → recreate → re-embed "
                  f"{have_text} item(s) at dim={dim}")
            continue

        if backup_dir is not None:
            with open(os.path.join(backup_dir, f"{name}.json"), "w", encoding="utf-8") as f:
                json.dump({"ids": ids, "documents": docs, "metadatas": metas}, f, ensure_ascii=False)

        # Keep only items that have text to re-embed.
        keep = [(i, d, m) for i, d, m in zip(ids, docs, metas) if d]
        chroma.delete_collection(name)
        new = chroma.get_or_create_collection(name=name)
        for s in range(0, len(keep), BATCH):
            chunk = keep[s:s + BATCH]
            b_ids = [x[0] for x in chunk]
            b_docs = [x[1] for x in chunk]
            b_meta = [x[2] for x in chunk]
            vecs = client.encode(b_docs, normalize_embeddings=True).tolist()
            add_kw = {"ids": b_ids, "embeddings": vecs, "documents": b_docs}
            if any(m for m in b_meta):
                add_kw["metadatas"] = [m or {} for m in b_meta]
            new.add(**add_kw)
            total_reembedded += len(chunk)
            print(f"  re-embedded {min(s+BATCH, len(keep))}/{len(keep)}")

    if args.apply:
        _write_state(model, dim)
        print(f"\nDone. Re-embedded {total_reembedded} item(s). State recorded ({model}, dim={dim}).")
    else:
        print("\nDry-run only. Re-run with --apply (and optionally --backup) to execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
