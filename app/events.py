"""Event backbone: Redis Streams when REDIS_URL is set, an in-process queue otherwise.

Kafka-style semantics on free infrastructure:
  - one durable stream `wn:events` (capped), a consumer group `workers`, explicit acknowledgements
  - failed events are retried (re-claimed after 30 s idle); after 3 deliveries they go to `wn:events:dlq`
  - handlers are idempotent; events carry only references (patient hash, booking code), never PHI

Tools publish after their database transaction commits and never wait for the workers.
Workers run as background threads in the web service (Render's free plan has no separate workers);
they are independent consumers and could run as separate services without code changes.

Event types
  patient.verified       -> context preloader (P1 snapshot, P2 profile, P3 memory into the blackboard)
  session.warm           -> context preloader (website chat opened by a logged-in patient)
  appointment.created / .cancelled / .rescheduled / waitlist.accepted
                         -> context updater (invalidate + refresh), analytics
  notification.queued    -> notification worker (wake the email sender)
  interaction.noted      -> memory worker (refresh the P3 memory digest)
"""

import json
import logging
import os
import queue
import socket
import threading
import time
from collections import Counter, deque

from . import config

log = logging.getLogger("wellnest.events")
STREAM, GROUP, DLQ = "wn:events", "workers", "wn:events:dlq"
MAX_DELIVERIES = 3
CONSUMER = f"{socket.gethostname()}-{os.getpid()}"

_handlers: dict[str, list] = {}
_local: queue.Queue = queue.Queue(maxsize=5000)
_stats = Counter()
_recent: deque = deque(maxlen=30)
_heartbeat = {"at": 0.0}
_redis = None
_started = False


def on(event_type: str):
    def deco(fn):
        _handlers.setdefault(event_type, []).append(fn)
        return fn
    return deco


def _r():
    global _redis
    if _redis is None and config.REDIS_URL:
        try:
            import redis
            _redis = redis.Redis.from_url(config.REDIS_URL, socket_timeout=6, socket_connect_timeout=1.5, decode_responses=True)
            _redis.ping()
            try:
                _redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
            except Exception:
                pass  # group exists
        except Exception as e:
            log.warning("event bus: Redis unavailable, using in-process queue: %s", e)
            _redis = False
    return _redis or None


def backend() -> str:
    return "redis-streams" if _r() else "in-process queue"


def publish(event_type: str, **payload) -> None:
    """Fire and forget. Never raises into the caller."""
    evt = {"type": event_type, "at": round(time.time(), 3), "payload": payload}
    _stats["published"] += 1
    _stats[f"pub:{event_type}"] += 1
    _recent.appendleft({"type": event_type, "at": time.strftime("%H:%M:%S"), "status": "published"})
    r = _r()
    try:
        if r:
            r.xadd(STREAM, {"e": json.dumps(evt, default=str)}, maxlen=10_000, approximate=True)
            return
    except Exception as e:
        log.warning("event publish to Redis failed, queued locally: %s", e)
    try:
        _local.put_nowait(evt)
    except queue.Full:
        _stats["dropped"] += 1


def _handle(evt: dict) -> None:
    for fn in _handlers.get(evt["type"], []):
        fn(evt.get("payload") or {})
    _stats["processed"] += 1
    _stats[f"done:{evt['type']}"] += 1
    lag = max(0.0, time.time() - float(evt.get("at", time.time())))
    _stats["lag_ms_last"] = int(lag * 1000)


def _loop_redis(r) -> None:
    last_claim = 0.0
    while True:
        _heartbeat["at"] = time.time()
        try:
            if time.time() - last_claim > 15:        # retry stuck events, dead-letter poison ones
                last_claim = time.time()
                for item in r.xpending_range(STREAM, GROUP, min="-", max="+", count=50):
                    if item["time_since_delivered"] < 30_000:
                        continue
                    if item["times_delivered"] >= MAX_DELIVERIES:
                        msgs = r.xrange(STREAM, item["message_id"], item["message_id"])
                        if msgs:
                            r.xadd(DLQ, msgs[0][1], maxlen=1000, approximate=True)
                        r.xack(STREAM, GROUP, item["message_id"])
                        _stats["dead_lettered"] += 1
                    else:
                        r.xclaim(STREAM, GROUP, CONSUMER, 30_000, [item["message_id"]])
                pending_mine = r.xreadgroup(GROUP, CONSUMER, {STREAM: "0"}, count=20)
                for _stream, msgs in pending_mine or []:
                    for mid, fields in msgs:
                        _process_redis(r, mid, fields)
            resp = r.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=20, block=5000)
            for _stream, msgs in resp or []:
                for mid, fields in msgs:
                    _process_redis(r, mid, fields)
        except Exception as e:
            _stats["errors"] += 1
            if "NOGROUP" in str(e):          # stream or group was deleted (e.g. Redis restarted empty): recreate
                try:
                    r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
                    continue
                except Exception:
                    pass
            log.warning("event worker (redis) error: %s", e)
            time.sleep(2)


def _process_redis(r, mid, fields) -> None:
    try:
        evt = json.loads(fields.get("e", "{}"))
        _handle(evt)
        r.xack(STREAM, GROUP, mid)
        _recent.appendleft({"type": evt.get("type"), "at": time.strftime("%H:%M:%S"), "status": "processed"})
    except Exception as e:      # left pending: retried, then dead-lettered
        _stats["failed"] += 1
        log.warning("event %s failed: %s", mid, e)


def _loop_local() -> None:
    while True:
        _heartbeat["at"] = time.time()
        try:
            evt = _local.get(timeout=5)
        except queue.Empty:
            continue
        for attempt in range(MAX_DELIVERIES):
            try:
                _handle(evt)
                _recent.appendleft({"type": evt.get("type"), "at": time.strftime("%H:%M:%S"), "status": "processed"})
                break
            except Exception as e:
                _stats["failed"] += 1
                log.warning("event %s failed (attempt %s): %s", evt.get("type"), attempt + 1, e)
                time.sleep(0.5 * (attempt + 1))
        else:
            _stats["dead_lettered"] += 1


def start_workers() -> None:
    global _started
    if _started:
        return
    _started = True
    from . import workers  # noqa: F401  (registers handlers)
    r = _r()
    threading.Thread(target=_loop_local, name="events-local", daemon=True).start()   # drains local fallback queue
    if r:
        threading.Thread(target=_loop_redis, args=(r,), name="events-redis", daemon=True).start()


def snapshot() -> dict:
    out = {"backend": backend(), "published": _stats["published"], "processed": _stats["processed"],
           "failed": _stats["failed"], "dead_lettered": _stats["dead_lettered"], "lag_ms_last": _stats["lag_ms_last"],
           "worker_alive": time.time() - _heartbeat["at"] < 15, "recent": list(_recent)[:12],
           "by_type": {k[4:]: v for k, v in _stats.items() if k.startswith("pub:")}}
    r = _r()
    if r:
        try:
            info = r.xinfo_groups(STREAM)
            g = next((x for x in info if x["name"] == GROUP), None)
            out["pending"] = g["pending"] if g else 0
            out["stream_length"] = r.xlen(STREAM)
            out["dlq_length"] = r.xlen(DLQ) if r.exists(DLQ) else 0
        except Exception as e:
            out["redis_error"] = str(e)[:120]
    else:
        out["pending"] = _local.qsize()
    return out
