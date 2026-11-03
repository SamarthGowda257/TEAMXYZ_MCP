"""Rolling per-tool latency metrics (in-process) + one JSON log line per tool call."""

import json
import logging
import threading
import time
from collections import defaultdict, deque

log = logging.getLogger("careline")
_lock = threading.Lock()
_calls: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
_counts: dict[str, int] = defaultdict(int)
_errors: dict[str, int] = defaultdict(int)
_recent: deque = deque(maxlen=60)
_cache = {"hit": 0, "miss": 0}
STARTED = time.time()


def record(tool: str, ms: float, ok: bool, error_code: str | None, who: str = "") -> None:
    with _lock:
        _calls[tool].append(ms)
        _counts[tool] += 1
        if not ok:
            _errors[tool] += 1
        _recent.appendleft({"tool": tool, "ms": round(ms, 1), "ok": ok, "error_code": error_code,
                            "at": time.strftime("%H:%M:%S", time.localtime())})
    log.info(json.dumps({"tool": tool, "ms": round(ms, 1), "ok": ok, "error_code": error_code, "who": who}))


def cache(hit: bool) -> None:
    with _lock:
        _cache["hit" if hit else "miss"] += 1


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(round(p * (len(s) - 1))))], 1)


def snapshot() -> dict:
    with _lock:
        tools = []
        for name, vals in _calls.items():
            v = list(vals)
            tools.append({"tool": name, "count": _counts[name], "errors": _errors[name],
                          "p50_ms": _pct(v, 0.5), "p95_ms": _pct(v, 0.95)})
        tools.sort(key=lambda x: -x["count"])
        total = _cache["hit"] + _cache["miss"]
        all_ms = [m for vals in _calls.values() for m in vals]
        return {"uptime_s": int(time.time() - STARTED), "tools": tools, "recent": list(_recent)[:20],
                "total_calls": sum(_counts.values()), "p50_ms": _pct(all_ms, 0.5), "p95_ms": _pct(all_ms, 0.95),
                "cache_hit_rate": round(_cache["hit"] / total, 2) if total else None}
