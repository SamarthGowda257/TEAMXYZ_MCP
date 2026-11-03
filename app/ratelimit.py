"""Small in-process rate limiter (sliding window per client IP and bucket). No external service.

Render sits behind a proxy, so the client IP is the first X-Forwarded-For entry.
With one server instance this is exact; with several, move the counters to Redis.
"""

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)

# bucket -> (max requests, window seconds)
LIMITS = {
    "login": (10, 60),
    "signup": (5, 600),
    "callback": (5, 600),
    "accept": (20, 600),
    "coverage": (60, 60),
    "mcp_bad_token": (20, 600),
}


def client_ip(headers: dict, fallback: str = "unknown") -> str:
    xff = headers.get("x-forwarded-for") or headers.get(b"x-forwarded-for")
    if isinstance(xff, bytes):
        xff = xff.decode(errors="ignore")
    return (xff.split(",")[0].strip() if xff else "") or fallback


def hit(bucket: str, ip: str) -> bool:
    """Record a request. Returns False when the client is over the limit."""
    limit, window = LIMITS[bucket]
    now = time.time()
    with _lock:
        q = _hits[(bucket, ip)]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(_hits) > 50_000:      # bound memory under attack
            _hits.clear()
        return True


def over(bucket: str, ip: str) -> bool:
    """True if the client is already over the limit (without recording a hit)."""
    limit, window = LIMITS[bucket]
    now = time.time()
    with _lock:
        q = _hits.get((bucket, ip))
        return bool(q) and len([t for t in q if t > now - window]) >= limit
