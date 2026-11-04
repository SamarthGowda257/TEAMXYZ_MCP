"""Hospital-wide context on the blackboard store (Redis when REDIS_URL is set, else process memory).

  hospital:profile          name, address, hours, emergency, contact, facilities, policy titles, knowledge counts
  hospital:answer:<v>:<q>   answers already found for a hospital question (24 h), keyed by knowledge version

The knowledge base in Postgres (search_docs + pgvector) stays the source of truth; this is the fast layer every
agent's get_hospital_info call reads first. A new knowledge version (any passage added or changed) starts a fresh
answer cache, so an edited policy is never answered from an old copy.
"""

import hashlib
from collections import Counter

from ..store import store
from .ref import REF

PROFILE_KEY = "hospital:profile"
ANSWER_TTL = 24 * 3600
_state = {"version": ""}


def publish(docs: list[dict]) -> dict:
    """Store the hospital profile and the current knowledge version (startup and after every re-index)."""
    _state["version"] = hashlib.md5("|".join(d["ref"] + d["body"] for d in docs).encode()).hexdigest()[:10]
    kinds = Counter(d["ref"].split(":")[1] for d in docs)
    profile = {"name": "WellNest Hospitals, Bengaluru", "kb_version": _state["version"], "passages": len(docs),
               "passages_by_kind": dict(kinds),
               **{k: REF.info.get(k) for k in ("address", "hours", "emergency", "contact", "facilities", "visiting")},
               "policies": [d["title"] for d in docs if d["ref"].startswith(("kb:policy:", "kb:doc:"))][:80]}
    store.set_json(PROFILE_KEY, profile)
    return profile


def profile() -> dict | None:
    return store.get_json(PROFILE_KEY, count=False)


def _key(question: str) -> str:
    q = " ".join(question.lower().split())
    return f"hospital:answer:{_state['version'] or 'none'}:{hashlib.md5(q.encode()).hexdigest()[:16]}"


def cached_answer(question: str) -> dict | None:
    return store.get_json(_key(question))


def remember_answer(question: str, message: str, data: dict) -> None:
    store.set_json(_key(question), {"message": message, "data": data}, ANSWER_TTL)


def cached_answers() -> int:
    return len(store.scan("hospital:answer:", 5000))
