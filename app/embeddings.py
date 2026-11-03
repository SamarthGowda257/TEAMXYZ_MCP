"""Text embeddings for the meaning leg of hybrid search.

Providers:
  gemini  Google Gemini API (gemini-embedding-001, 768 dimensions, free tier in Google AI Studio). Needs EMBEDDINGS_API_KEY.
  hash    Local feature hashing of words and character trigrams. NOT semantic: only for tests and CI without a key.
  none    Meaning leg off; search runs on keyword + fuzzy only.

Rules (docs/08_LATENCY.md): documents are embedded in the background, never in a live call. The one network call in
a live call is the query embedding: it has a hard timeout, a 7-day cache, and a circuit breaker so an outage costs one
timeout per minute at most. Any failure returns None and search silently runs without the meaning leg.
"""

import hashlib
import logging
import math
import re
import threading
import time

from . import config

log = logging.getLogger("wellnest.embeddings")

GEMINI = "https://generativelanguage.googleapis.com/v1beta"
BATCH = 100                     # Gemini batchEmbedContents limit
STATS = {"doc_calls": 0, "docs_embedded": 0, "query_calls": 0, "query_cache_hits": 0, "errors": 0,
         "last_error": None, "last_ok": None}
_breaker_until = 0.0
_lock = threading.Lock()


def provider() -> str:
    p = config.EMBEDDINGS_PROVIDER
    if p == "gemini" and not config.EMBEDDINGS_API_KEY:
        return "none"
    return p if p in ("gemini", "hash") else "none"


def enabled() -> bool:
    return provider() != "none"


def model_id() -> str:
    """Stored with each cached embedding so a model change never mixes vector spaces."""
    p = provider()
    return f"{config.EMBEDDINGS_MODEL}@{config.EMBEDDINGS_DIM}" if p == "gemini" else f"{p}@{config.EMBEDDINGS_DIM}"


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]       # Gemini vectors below 3072 dims are not normalised; cosine needs consistency


def _hash_embed(t: str) -> list[float]:
    dim = config.EMBEDDINGS_DIM
    v = [0.0] * dim
    words = re.findall(r"[a-z0-9]+", t.lower())
    feats = words + [w[i:i + 3] for w in words if len(w) > 3 for i in range(len(w) - 2)]
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 64) & 1 else -1.0
    return _unit(v)


def _breaker_open() -> bool:
    return time.monotonic() < _breaker_until


def _trip(err: str, seconds: float = 60.0) -> None:
    global _breaker_until
    with _lock:
        _breaker_until = time.monotonic() + seconds
        STATS["errors"] += 1
        STATS["last_error"] = err[:200]
    log.warning("embeddings unavailable for %.0fs: %s", seconds, err[:200])


def _gemini(texts: list[str], task: str, timeout: float) -> list[list[float]]:
    import httpx          # imported here: a missing package must never stop the server from starting
    m = config.EMBEDDINGS_MODEL
    body = {"requests": [{"model": f"models/{m}", "content": {"parts": [{"text": t[:6000]}]}, "taskType": task,
                          "outputDimensionality": config.EMBEDDINGS_DIM} for t in texts]}
    r = httpx.post(f"{GEMINI}/models/{m}:batchEmbedContents", json=body, timeout=timeout,
                   headers={"x-goog-api-key": config.EMBEDDINGS_API_KEY, "content-type": "application/json"})
    if r.status_code != 200:
        msg = r.text[:300]
        try:
            msg = r.json().get("error", {}).get("message", msg)
        except ValueError:
            pass
        raise RuntimeError(f"HTTP {r.status_code}: {msg}")
    out = [_unit(e["values"]) for e in r.json()["embeddings"]]
    if len(out) != len(texts) or any(len(v) != config.EMBEDDINGS_DIM for v in out):
        raise RuntimeError("unexpected embedding shape")
    return out


def budget_left() -> int:
    """Background embeddings still allowed today (shared across restarts through the store)."""
    from .store import store
    try:
        used = store.get_json(f"emb:budget:{config.today().isoformat()}", count=False) or 0
    except Exception:
        used = 0
    return max(0, config.EMBED_DAILY_BUDGET - int(used))


def _spend(n: int) -> None:
    from .store import store
    try:
        key = f"emb:budget:{config.today().isoformat()}"
        used = store.get_json(key, count=False) or 0
        store.set_json(key, int(used) + n, ttl=2 * 24 * 3600)
    except Exception:
        pass


def embed_documents(texts: list[str]) -> list[list[float]] | None:
    """Background use only. Returns one unit vector per text, or None if the provider is off or failing."""
    p = provider()
    if p == "none" or not texts or _breaker_open():
        return None
    if p == "hash":
        STATS["docs_embedded"] += len(texts)
        return [_hash_embed(t) for t in texts]
    if budget_left() < len(texts):
        return None
    out: list[list[float]] = []
    try:
        for i in range(0, len(texts), BATCH):
            out += _gemini(texts[i:i + BATCH], "RETRIEVAL_DOCUMENT", timeout=30)
            STATS["doc_calls"] += 1
    except Exception as e:
        # 429 = free-tier quota: back off longer so the background backfill doesn't hammer it
        _trip(f"documents: {e}", 300 if "429" in str(e) else 60)
        return None
    STATS["docs_embedded"] += len(out)
    STATS["last_ok"] = config.now().isoformat()
    _spend(len(out))
    return out


def embed_query(q: str) -> list[float] | None:
    """Live-call use. Cached for 7 days; hard timeout; never raises."""
    p = provider()
    q = " ".join(q.split())[:500]
    if p == "none" or not q:
        return None
    if p == "hash":
        return _hash_embed(q)
    from .store import store
    key = f"emb:q:{hashlib.sha1((model_id() + '|' + q.lower()).encode()).hexdigest()}"
    try:
        hit = store.get_json(key, count=False)
        if hit:
            STATS["query_cache_hits"] += 1
            return hit
    except Exception:
        pass
    if _breaker_open():
        return None
    try:
        v = _gemini([q], "RETRIEVAL_QUERY", timeout=config.EMBEDDINGS_TIMEOUT)[0]
    except Exception as e:
        _trip(f"query: {e}")
        return None
    STATS["query_calls"] += 1
    STATS["last_ok"] = config.now().isoformat()
    try:
        store.set_json(key, [round(x, 6) for x in v], ttl=7 * 24 * 3600)
    except Exception:
        pass
    return v


def status() -> dict:
    return {"provider": provider(), "model": model_id() if enabled() else None, "breaker_open": _breaker_open(),
            "daily_budget_left": budget_left() if provider() == "gemini" else None, **STATS}
