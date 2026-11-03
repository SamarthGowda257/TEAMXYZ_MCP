"""Blackboard: shared working memory for the Talkdesk agents (docs/07).

Stored in Redis when REDIS_URL is set (shared by every server instance), otherwise in process memory.
Keys never contain phone numbers: a patient is identified by a keyed hash of the phone.

Levels
  P0  live session facts (slots just offered, coverage result, handoff, booking made)   15 min
  P1  patient snapshot (identity, upcoming visits, reports, insurer, notes)             30 min
  P2  stable profile (language, preferred time, insurer, caregiver, mobility)            6 hours
  P3  memory digest (last conversation summaries)                                        7 days
Registry  per patient: for each context item its state (READY, LOADING, MISSING, ERROR), level,
          source, fetched_at, expires_at and version, so agents and the dashboard see what is known.

Facts travel to agents inside normal tool replies (`related`, top 3), so the blackboard adds no extra
agent hops or tool calls in Talkdesk.
"""

import hashlib
import heapq
import hmac
import time

from .. import config
from ..store import store
from ..util import norm_phone

TTL = {"P0": 900, "P1": 1800, "P2": 6 * 3600, "P3": 7 * 24 * 3600}
FACT_TTL = TTL["P0"]
ITEMS = {"snapshot": "P1", "profile": "P2", "memory": "P3", "coverage": "P0", "slots_offered": "P0", "booking": "P0",
         "waitlist_offer": "P0", "handoff": "P0", "preauth": "P0", "assistance": "P0"}


def ref_for(phone) -> str | None:
    p = norm_phone(phone)
    if not p:
        return None
    return hmac.new(config.SECRET_KEY.encode(), p.encode(), hashlib.sha256).hexdigest()[:20]


def _k(ref: str, part: str) -> str:
    return f"patient:{ref}:{part}"


# ------------------------------------------------------------------ registry
def mark(phone_or_ref, item: str, state: str, source: str = "", ttl: int | None = None, ref: str | None = None) -> None:
    r = ref or (phone_or_ref if phone_or_ref and len(str(phone_or_ref)) == 20 and not str(phone_or_ref).startswith("+") else ref_for(phone_or_ref))
    if not r:
        return
    level = ITEMS.get(item, "P0")
    ttl = ttl or TTL[level]
    reg = store.get_json(_k(r, "registry"), count=False) or {}
    now = time.time()
    prev = reg.get(item, {})
    reg[item] = {"state": state, "level": level, "source": source or prev.get("source", ""), "fetched_at": int(now),
                 "expires_at": int(now + ttl), "version": int(prev.get("version", 0)) + (1 if state == "READY" else 0)}
    store.set_json(_k(r, "registry"), reg, TTL["P3"])


def registry(phone_or_ref) -> dict:
    r = phone_or_ref if phone_or_ref and len(str(phone_or_ref)) == 20 else ref_for(phone_or_ref)
    if not r:
        return {}
    reg = store.get_json(_k(r, "registry"), count=False) or {}
    now = time.time()
    for v in reg.values():          # expired READY items are MISSING again
        if v.get("state") == "READY" and v.get("expires_at", 0) < now:
            v["state"] = "MISSING"
    return reg


# ------------------------------------------------------------------ P0 facts
def add(phone, kind: str, text: str, priority: int = 5, ref: str | None = None, ttl: int = FACT_TTL) -> None:
    r = ref_for(phone)
    if not r:
        return
    now = time.time()
    facts = [f for f in (store.get_json(_k(r, "p0"), count=False) or [])
             if f["expires_at"] > now and not (f["kind"] == kind and f.get("ref") == ref)]
    facts.append({"kind": kind, "text": text, "priority": priority, "ref": ref, "created_at": now, "expires_at": now + ttl})
    store.set_json(_k(r, "p0"), facts[-30:], max(ttl, 60))
    mark(None, kind, "READY", "tool", ttl, ref=r)


def related(phone, ref: str | None = None, skip_kinds: tuple = (), k: int = 3) -> list[dict]:
    r = ref_for(phone)
    if not r:
        return []
    now = time.time()
    live = [f for f in (store.get_json(_k(r, "p0")) or []) if f["expires_at"] > now and f["kind"] not in skip_kinds]
    best = heapq.nsmallest(k, live, key=lambda f: (f["priority"], 0 if (ref and f.get("ref") == ref) else 1, -f["created_at"]))
    return [{"kind": f["kind"], "text": f["text"]} for f in best]


# ------------------------------------------------------------------ P1 snapshot, P2 profile, P3 memory
def put_snapshot(phone, snap: dict, source: str = "database") -> None:
    r = ref_for(phone)
    if r:
        store.set_json(_k(r, "p1"), snap, TTL["P1"])
        mark(None, "snapshot", "READY", source, ref=r)


def get_snapshot(phone) -> dict | None:
    r = ref_for(phone)
    return store.get_json(_k(r, "p1")) if r else None


def put_profile(phone, profile: dict, source: str = "preloader") -> None:
    r = ref_for(phone)
    if r:
        store.set_json(_k(r, "p2"), profile, TTL["P2"])
        mark(None, "profile", "READY", source, ref=r)


def get_profile(phone) -> dict | None:
    r = ref_for(phone)
    return store.get_json(_k(r, "p2")) if r else None


def put_memory(phone, notes: list[str], source: str = "memory-worker") -> None:
    r = ref_for(phone)
    if r:
        store.set_json(_k(r, "p3"), notes, TTL["P3"])
        mark(None, "memory", "READY", source, ref=r)


def get_memory(phone) -> list[str] | None:
    r = ref_for(phone)
    return store.get_json(_k(r, "p3")) if r else None


def invalidate(phone, *parts: str) -> None:
    """A write for this patient happened: drop cached context so the next read is fresh."""
    r = ref_for(phone)
    if not r:
        return
    parts = parts or ("p1",)
    store.delete(*[_k(r, p) for p in parts])
    for p in parts:
        item = {"p1": "snapshot", "p2": "profile", "p3": "memory"}.get(p)
        if item:
            mark(None, item, "MISSING", "invalidated", ref=r)


def clear_all() -> None:
    store.flush()


def stats() -> dict:
    keys = store.scan("patient:", 2000)
    patients = {k.split(":")[1] for k in keys}
    return {"backend": store.status, "patients_in_memory": len(patients), "cache_hit_rate": store.hit_rate(),
            "hits": store.hits, "misses": store.misses, "last_error": store.last_error if config.REDIS_URL else None}
