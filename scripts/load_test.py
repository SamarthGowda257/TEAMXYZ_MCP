"""Load and concurrency test over the real MCP transport.

Scenario A, the race: N patients try to book the SAME slot at the same instant.
  Expected: exactly 1 booking, N-1 polite "slot taken" replies, 0 errors, 0 double bookings.
Scenario B, a busy hospital: U simulated patients run a normal conversation in parallel
  (verify -> find slots -> doctors -> lab reports -> coverage -> appointments), R rounds each.
  Reports per-tool p50 / p95 / max and errors.

Usage:
  MCP_URL=http://localhost:8000/mcp MCP_BEARER_TOKEN=... python scripts/load_test.py [--race 50] [--users 25] [--rounds 4]
It writes test bookings (fake phones 98000xxxxx); run /ops/reset-demo afterwards on a shared server.
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from collections import defaultdict

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")
TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
PERSONAS = [("9845000001", "1959-03-04"), ("9845000002", "1992-06-15"), ("9845000003", "1997-01-20"), ("9845000004", "1981-09-10")]


def pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))] if s else 0


async def call(s, name, args, timings, errors):
    t0 = time.perf_counter()
    try:
        r = await s.call_tool(name, args)
        body = json.loads(r.content[0].text)
    except Exception as e:  # transport-level failure
        errors[name] += 1
        timings[name].append((time.perf_counter() - t0) * 1000)
        return {"ok": False, "error_code": f"transport: {e}"}
    timings[name].append((time.perf_counter() - t0) * 1000)
    if body.get("error_code") == "service_unavailable":
        errors[name] += 1
    return body


async def main(a):
    timings, errors = defaultdict(list), defaultdict(int)
    limits = httpx2.Limits(max_connections=200, max_keepalive_connections=100) if hasattr(httpx2, "Limits") else None
    kw = {"headers": {"Authorization": f"Bearer {TOKEN}"}, "timeout": 60}
    if limits:
        kw["limits"] = limits
    async with httpx2.AsyncClient(**kw) as hc, streamable_http_client(URL, http_client=hc) as streams:
        async with ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            print(f"Target: {URL}\n")

            # ---------------- Scenario A: the race for one slot
            slots = None
            for day in ("tomorrow", "day after tomorrow", "in 3 days", "in 4 days"):
                r = await call(s, "find_available_slots", {"date": day, "department": "General Medicine"}, timings, errors)
                docs = [d for d in r.get("data", {}).get("doctors", []) if d.get("free_slots")]
                if docs:
                    slots = (r["data"]["date_iso"], docs[0]["name"], docs[0]["free_slots"][0])
                    break
            date_iso, doctor, slot = slots
            race = [dict(phone=f"98000{n:05d}", patient_name=f"Load Test {n}", date=date_iso, time=slot, doctor_name=doctor)
                    for n in range(a.race)]
            t0 = time.perf_counter()
            results = await asyncio.gather(*(call(s, "book_appointment", x, timings, errors) for x in race))
            race_ms = (time.perf_counter() - t0) * 1000
            ok = [x for x in results if x.get("ok")]
            taken = [x for x in results if x.get("error_code") == "slot_taken"]
            other = [x for x in results if not x.get("ok") and x.get("error_code") != "slot_taken"]
            after = await call(s, "find_available_slots", {"date": date_iso, "doctor_name": doctor}, timings, errors)
            still_free = any(slot in d.get("free_slots", []) for d in after.get("data", {}).get("doctors", []))
            print(f"A) {a.race} simultaneous bookings for {doctor}, {date_iso} {slot}")
            print(f"   booked: {len(ok)} · slot taken: {len(taken)} · other: {len(other)} · slot still offered as free: {still_free}"
                  f" · all {a.race} answered in {race_ms:.0f} ms")
            race_pass = len(ok) == 1 and len(taken) == a.race - 1 and not other and not still_free
            print(f"   RESULT: {'PASS, no double booking' if race_pass else 'FAIL'}\n")

            # ---------------- Scenario B: busy hospital
            async def patient(i):
                phone, dob = PERSONAS[i % len(PERSONAS)]
                for _ in range(a.rounds):
                    await call(s, "verify_patient", {"phone": phone, "date_of_birth": dob}, timings, errors)
                    await call(s, "find_available_slots", {"date": "tomorrow", "department": ["Cardiology", "Orthopaedics", "Dermatology", "ENT"][i % 4]}, timings, errors)
                    await call(s, "get_doctors", {"department": ["Neurology", "Paediatrics", "General Medicine"][i % 3]}, timings, errors)
                    await call(s, "get_lab_report_status", {"phone": phone, "date_of_birth": dob}, timings, errors)
                    await call(s, "check_coverage", {"insurance_provider": "Star Health", "procedure": "MRI Knee", "phone": phone}, timings, errors)
                    await call(s, "find_appointments", {"phone": phone, "date_of_birth": dob}, timings, errors)
            for k in list(timings):
                timings[k].clear()
            t0 = time.perf_counter()
            await asyncio.gather(*(patient(i) for i in range(a.users)))
            wall = time.perf_counter() - t0
            total = sum(len(v) for v in timings.values())
            print(f"B) {a.users} patients in parallel x {a.rounds} conversations: {total} tool calls in {wall:.1f} s "
                  f"({total / wall:.0f} calls/s), errors: {sum(errors.values())}\n")
            print("| Tool | Calls | p50 ms | p95 ms | max ms |\n|---|---:|---:|---:|---:|")
            allv = []
            for name, v in sorted(timings.items()):
                if not v:
                    continue
                allv += v
                print(f"| `{name}` | {len(v)} | {statistics.median(v):.0f} | {pct(v, 0.95):.0f} | {max(v):.0f} |")
            print(f"| **all** | {len(allv)} | {statistics.median(allv):.0f} | {pct(allv, 0.95):.0f} | {max(allv):.0f} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--race", type=int, default=50)
    ap.add_argument("--users", type=int, default=25)
    ap.add_argument("--rounds", type=int, default=4)
    asyncio.run(main(ap.parse_args()))
