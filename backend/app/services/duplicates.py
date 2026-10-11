"""Duplicate detection: exact hash match + near cosine >= 0.95."""
from __future__ import annotations

from .embeddings import cosine, embed


def find_duplicates(items: list[dict]) -> list[dict]:
    pairs: list[dict] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            # exact: shared email/phone hash
            ha = {e.get("hash") for e in (a.get("email_hash") or []) if isinstance(e, dict)}
            hb = {e.get("hash") for e in (b.get("email_hash") or []) if isinstance(e, dict)}
            if ha and ha & hb:
                pairs.append({"a": a["id"], "b": b["id"], "kind": "exact", "score": 1.0})
                continue
            try:
                s = cosine(embed((a.get("text") or "")[:2000]), embed((b.get("text") or "")[:2000]))
            except Exception:
                s = 0.0
            if s >= 0.95:
                pairs.append({"a": a["id"], "b": b["id"], "kind": "near", "score": round(s, 3)})
    return pairs
