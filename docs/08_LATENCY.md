# 08 — Latency

## Where the time goes
A patient turn = Talkdesk LLM steps (one per agent hop) + our tool time + Talkdesk's own overhead. We control **our tool time** and, through tool design, **how many hops** happen.

Measured on V1 (3 Nov):
- Typical turn 2.35 s (P50), slow turn 6.9 s (P95).
- A two-part request took **12.1 s** across 5 steps: `Receptionist → Booking → Receptionist → Info → Receptionist`, with the weekday helper called twice and `get_doctors` returning the whole hospital.

**The biggest win is removing agent hops, not shaving milliseconds.** One avoided hop ≈ 2–3 s. A perfect database query saves ≈ 10 ms.

## Budgets
| Layer | Target |
|---|---|
| Tool server time, reads | p50 ≤ 80 ms, p95 ≤ 250 ms |
| Tool server time, writes | p95 ≤ 400 ms |
| Single DB query | ≤ 10 ms at seed volume |
| DB round trips per tool | ≤ 2 (reads), ≤ 3 (writes) |
| Response size | ≤ 1 KB typical, 2 KB hard cap |
| Agent hops for a common request | 1 specialist (3 steps total) |

## Rules (apply to every tool)
1. **One specialist answers common combos.** `find_available_slots` returns doctor days/hours/fee/room so "slots + which doctors + fees" never needs the Info agent. `verify_patient` returns upcoming bookings, so "what are my appointments" after verification needs no second tool.
2. **Return resolved values** (`date_iso`, `weekday`) so agents stop calling the weekday helper.
3. **Small responses.** Only what the agent needs next; lists ≤ 3; no hospital block in `get_doctors` when a department is given; no nulls or empty arrays.
4. **Ready-to-speak `message`.** The agent relays it instead of composing a long answer (fewer output tokens = faster LLM step).
5. **No outbound network in the request path.** Emails, SMS, Talkdesk APIs, embeddings: outbox + background task.
6. **One query where possible.** Use CTEs/joins for the snapshot. Never N+1 (no query per doctor in a loop).
7. **Pool and region.** asyncpg pool, min 1 / max 5, transaction pooler URL, `statement_cache_size=0`. Render and Supabase in the same region (Singapore).
8. **Cache reference data** in L1 (see `07`). Load doctors/departments/procedures/insurers at startup.
9. **Async prefetch** after `verify_patient` and on widget open.
10. **Idempotent writes** so a Talkdesk retry doesn't double-act or double-wait.
11. **Warm server.** `/health` pinged every 5 minutes by an external monitor; Render free instances sleep after ~15 min idle and cold starts take tens of seconds. On demo day the team may switch to a paid instance.
12. **uvloop + httptools** via `uvicorn[standard]`; JSON via `orjson` if convenient.
13. **Timeouts everywhere.** DB statement timeout 3 s (`SET statement_timeout`), prefetch 2 s; on timeout return `service_unavailable` with a speakable message rather than hanging the call.

## Instrumentation (build in Phase 1)
- Decorator `@timed_tool(name)` records duration, ok, error_code, cache hits for that call.
- Rolling window (last 500 calls per tool) → p50/p95 in `/api/metrics` and the dashboard.
- Log line per call: `{"tool":"book_appointment","ms":143,"ok":true,"cache":"miss","db_queries":3}`.
- Count DB queries per request (wrap the pool's `fetch*`/`execute`) to catch N+1.
- `scripts/bench_tools.py`: calls each read tool 50× against the deployed URL, prints p50/p95. Run it before and after optimisations; paste the table in `docs/LATENCY_RESULTS.md` for the slides.

## Agent-side guidance (for the Talkdesk team, already in their checklist)
- Conditions route each common intent to exactly one specialist.
- Receptionist instruction: "Relay the specialist's answer as given; don't rephrase long answers."
- Booking instruction: "If the date is already in YYYY-MM-DD, don't call the weekday helper."
- Conversation fillers on, so multi-hop turns don't feel frozen.
