"""Embeddings with cache. sentence-transformers preferred, hash fallback."""
from __future__ import annotations

import hashlib
import math
import re

_DIM = 128
_CACHE: dict[str, list[float]] = {}
_CACHE_MAX = 2000
_MODEL = None
_MODEL_NAME = ""


def _hash_embed(text: str, dim: int = _DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9+#.]+", text.lower()):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def _get_model():
    global _MODEL, _MODEL_NAME
    import os

    name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    if _MODEL is not None and _MODEL_NAME == name:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _MODEL = SentenceTransformer(name)
        _MODEL_NAME = name
        return _MODEL
    except Exception:
        _MODEL = None
        return None


def _store(key: str, v: list[float]) -> list[float]:
    # Bounded cache: evict oldest first (dicts preserve insertion order).
    if key not in _CACHE and len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = v
    return v


def embed(text: str) -> list[float]:
    key = text[:2000]
    if key in _CACHE:
        return _CACHE[key]
    model = _get_model()
    if model is not None:
        try:
            return _store(key, model.encode(key, normalize_embeddings=True).tolist())
        except Exception:
            pass
    return _store(key, _hash_embed(key))


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(-1.0, min(1.0, dot / (na * nb)))
