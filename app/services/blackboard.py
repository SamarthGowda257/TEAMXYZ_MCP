"""Per-patient working memory for the current conversation (see docs/07).

Tools write facts here; every response carries the top 3 relevant facts in `related`,
so facts travel between Talkdesk agents with zero extra agent hops.
"""

import heapq
import threading
import time
from dataclasses import dataclass

from ..util import norm_phone

FACT_TTL = 1800
SNAP_TTL = 600


@dataclass
class Fact:
    kind: str
    text: str
    priority: int        # 0 critical ... 9 nice to know
    ref: str | None
    created_at: float
    expires_at: float


_lock = threading.Lock()
_facts: dict[str, list[Fact]] = {}
_snapshots: dict[str, tuple[float, dict]] = {}


def _key(phone) -> str | None:
    return norm_phone(phone)


def add(phone, kind: str, text: str, priority: int = 5, ref: str | None = None, ttl: int = FACT_TTL) -> None:
    k = _key(phone)
    if not k:
        return
    now = time.time()
    with _lock:
        lst = [f for f in _facts.get(k, []) if f.expires_at > now and not (f.kind == kind and f.ref == ref)]
        lst.append(Fact(kind, text, priority, ref, now, now + ttl))
        _facts[k] = lst[-30:]


def related(phone, ref: str | None = None, skip_kinds: tuple = (), k: int = 3) -> list[dict]:
    key = _key(phone)
    if not key:
        return []
    now = time.time()
    with _lock:
        live = [f for f in _facts.get(key, []) if f.expires_at > now and f.kind not in skip_kinds]
        _facts[key] = live
    best = heapq.nsmallest(k, live, key=lambda f: (f.priority, 0 if (ref and f.ref == ref) else 1, -f.created_at))
    return [{"kind": f.kind, "text": f.text} for f in best]


def put_snapshot(phone, snap: dict) -> None:
    k = _key(phone)
    if k:
        with _lock:
            _snapshots[k] = (time.time() + SNAP_TTL, snap)


def get_snapshot(phone) -> dict | None:
    k = _key(phone)
    with _lock:
        v = _snapshots.get(k) if k else None
    return v[1] if v and v[0] > time.time() else None


def invalidate(phone) -> None:
    k = _key(phone)
    if k:
        with _lock:
            _snapshots.pop(k, None)


def clear_all() -> None:
    with _lock:
        _facts.clear()
        _snapshots.clear()
