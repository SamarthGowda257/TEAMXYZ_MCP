"""Latency benchmark for the read tools over the real MCP transport (client-side round trip).

Usage:
  MCP_URL=https://teamxyz-mcp.onrender.com/mcp MCP_BEARER_TOKEN=... python scripts/bench_tools.py [runs]

Prints a Markdown table (p50 / p95 in ms) to paste into docs/LATENCY_RESULTS.md.
Server-side timings are also on the dashboard (/dashboard -> Tool latency).
"""

import asyncio
import os
import statistics
import sys
import time

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")
TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 50

CALLS = [
    ("find_available_slots", {"date": "tomorrow", "department": "Cardiology"}),
    ("get_doctors", {"department": "Dermatology"}),
    ("verify_patient", {"phone": "9845000003", "date_of_birth": "1997-01-20"}),
    ("find_appointments", {"phone": "9845000001", "date_of_birth": "1959-03-04"}),
    ("get_lab_report_status", {"phone": "9845000003", "date_of_birth": "1997-01-20"}),
    ("check_coverage", {"insurance_provider": "Star Health", "procedure": "MRI Knee"}),
    ("get_insurance_info", {"insurance_provider": "HDFC ERGO"}),
    ("get_hospital_info", {"topic": "parking"}),
    ("suggest_department", {"symptoms": "knee pain for two weeks"}),
]


def pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


async def main():
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60) as hc, \
            streamable_http_client(URL, http_client=hc) as streams:
        async with ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            await s.call_tool("get_hospital_info", {"topic": "hours"})  # warm up
            print(f"Round-trip latency over MCP, {RUNS} calls each, {URL}\n")
            print("| Tool | p50 ms | p95 ms | size bytes |\n|---|---:|---:|---:|")
            for name, args in CALLS:
                times, size = [], 0
                for _ in range(RUNS):
                    t0 = time.perf_counter()
                    r = await s.call_tool(name, args)
                    times.append((time.perf_counter() - t0) * 1000)
                    size = len(r.content[0].text.encode())
                print(f"| `{name}` | {statistics.median(times):.0f} | {pct(times, 0.95):.0f} | {size} |")


if __name__ == "__main__":
    asyncio.run(main())
