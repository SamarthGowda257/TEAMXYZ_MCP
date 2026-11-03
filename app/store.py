"""Key-value store for the blackboard: Redis when REDIS_URL is set, in-process memory otherwise.

If Redis stops answering, calls fall back to memory for 30 seconds and then retry Redis, so a Redis
outage never fails a tool call. Values are JSON. Every key is namespaced under "wn:".
"""

import json
import logging
import threading
import time

from . import config

log = logging.getLogger("wellnest.store")
PREFIX = "wn:"


class MemoryStore:
    kind = "memory"

    def __init__(self):
        self._d: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def _live(self, key):
        v = self._d.get(key)
        if v and (v[0] == 0 or v[0] > time.time()):
            return v[1]
        self._d.pop(key, None)
        return None

    def get(self, key):
        with self._lock:
            return self._live(key)

    def set(self, key, value: str, ttl: int = 0):
        with self._lock:
            if len(self._d) > 20_000:
                self._d.clear()
            self._d[key] = (time.time() + ttl if ttl else 0, value)

    def delete(self, *keys):
        with self._lock:
            for k in keys:
                self._d.pop(k, None)

    def incr(self, key, by: int = 1, ttl: int = 0):
        with self._lock:
            cur = int(self._live(key) or 0) + by
            self._d[key] = (time.time() + ttl if ttl else 0, str(cur))
            return cur

    def scan(self, prefix: str, limit: int = 200):
        with self._lock:
            return [k for k in list(self._d) if k.startswith(prefix) and self._live(k) is not None][:limit]

    def flush(self):
        with self._lock:
            self._d.clear()


class RedisStore:
    kind = "redis"

    def __init__(self, url: str):
        import redis
        self.r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=1.5, decode_responses=True,
                                      health_check_interval=30, retry_on_timeout=False)

    def get(self, key):
        return self.r.get(key)

    def set(self, key, value: str, ttl: int = 0):
        self.r.set(key, value, ex=ttl or None)

    def delete(self, *keys):
        if keys:
            self.r.delete(*keys)

    def incr(self, key, by: int = 1, ttl: int = 0):
        p = self.r.pipeline()
        p.incrby(key, by)
        if ttl:
            p.expire(key, ttl)
        return p.execute()[0]

    def scan(self, prefix: str, limit: int = 200):
        out = []
        for k in self.r.scan_iter(match=prefix + "*", count=200):
            out.append(k)
            if len(out) >= limit:
                break
        return out

    def flush(self):
        keys = [k for k in self.r.scan_iter(match=PREFIX + "*", count=500) if not k.startswith(PREFIX + "events")]
        for i in range(0, len(keys), 500):
            self.r.delete(*keys[i:i + 500])


class Store:
    """Facade with automatic fallback. Use the module-level `store` instance."""

    def __init__(self):
        self.memory = MemoryStore()
        self.redis: RedisStore | None = None
        self._down_until = 0.0
        self.last_error: str | None = None
        self.hits = 0
        self.misses = 0
        if config.REDIS_URL:
            try:
                self.redis = RedisStore(config.REDIS_URL)
                self.redis.r.ping()
                log.info("blackboard: connected to Redis")
            except Exception as e:  # keep running on memory
                self._fail(e)

    def _fail(self, e):
        self.last_error = str(e)[:200]
        self._down_until = time.time() + 30
        log.warning("Redis unavailable, using in-process memory for 30s: %s", self.last_error)

    @property
    def backend(self):
        if self.redis and time.time() >= self._down_until:
            return self.redis
        return self.memory

    @property
    def status(self) -> str:
        if not config.REDIS_URL:
            return "not configured (in-process memory)"
        return "connected" if self.backend is self.redis else "down, using in-process memory"

    def _call(self, name, *args, **kw):
        b = self.backend
        try:
            return getattr(b, name)(*args, **kw)
        except Exception as e:
            if b is self.redis:
                self._fail(e)
                return getattr(self.memory, name)(*args, **kw)
            raise

    # JSON helpers ------------------------------------------------------------
    def get_json(self, key, count=True):
        raw = self._call("get", PREFIX + key)
        if count:
            if raw is None:
                self.misses += 1
            else:
                self.hits += 1
        return json.loads(raw) if raw else None

    def set_json(self, key, value, ttl: int = 0):
        self._call("set", PREFIX + key, json.dumps(value, default=str), ttl)

    def delete(self, *keys):
        self._call("delete", *[PREFIX + k for k in keys])

    def incr(self, key, by=1, ttl=0):
        return self._call("incr", PREFIX + key, by, ttl)

    def scan(self, prefix, limit=200):
        return [k[len(PREFIX):] for k in self._call("scan", PREFIX + prefix, limit)]

    def flush(self):
        self._call("flush")

    def hit_rate(self):
        t = self.hits + self.misses
        return round(self.hits / t, 2) if t else None


store = Store()
