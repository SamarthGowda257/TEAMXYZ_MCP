# WellNest architecture: measured, before vs after

Two kinds of numbers, from two sources you can show live:
1. **Agent side** (what the patient feels): Talkdesk's own evaluation reports, summarised by
   `python scripts/eval_report_stats.py <report.html>`.
2. **Server side** (what our architecture does per call): `GET /api/ops/benchmark?token=<DASHBOARD_TOKEN>` on the
   live server, which times a plain-MCP path and the WellNest path inside the same Render instance, against the same
   Supabase Postgres and Redis.

## 1. Agent side: V1 (plain agents + MCP) vs V2 (WellNest)

| | V1 (3 agents, 6 tools, in-memory data) | V2 (9 agents, 34 tools, blackboard) |
|---|---|---|
| Turn latency P50 | 2.35 s | **1.0 – 1.2 s** |
| Turn latency P95 | 6.9 s | 7.1 – 7.9 s |
| "Free cardiology slots tomorrow and the fees" | 12.1 s, 5 agent steps, 2 specialists, weekday helper twice | **1 specialist, 1 tool call** (slots come with fees, days, rooms) |
| Goals truly achieved | about 5 / 10 (easy set) | **63 / 75** (harder set: identity, emergencies, languages, adversarial) |
| Routed turns answered by one specialist | not measured | **98.7 %** (avg 1.01 specialist hops) |
| Identity checked on the server | no | yes, every patient-specific tool (5 tries, then 15-minute lock) |

V1 numbers: `docs/01_PROJECT_OVERVIEW.md` (V1 evaluation and latency trace, 3 Nov).
V2 numbers: report `013bc1fd` (75 scenarios, 177 patient turns).

Evaluation runs, same product, as the dataset and agent instructions were fixed:

| Run | Scenarios | Avg score | Goals achieved | Turn P50 | Date-helper calls |
|---|---:|---:|---:|---:|---:|
| `2ddac07e` (first 100-scenario set) | 100 | 74.8 | 72 | 2.3 s | 64 |
| `e9fd63ba` (v3 set) | 82 | 81.3 | 65 | 1.1 s | 22 |
| `272f5b45` (v4 set) | 75 | 80.8 | 61 | 1.0 s | 20 |
| `013bc1fd` (v4 set, knowledge lookups off) | 75 | 82 | 63 | 1.2 s | 16 |

Why the latency halved: each answer now needs one specialist and one tool call, and every tool reply is a complete,
ready-to-speak sentence, so the agents write less. An avoided agent hop saves about 1–2 s; a faster database query saves
milliseconds. The remaining P95 comes from Talkdesk's own `get_weekday_for_date_internal`, which runs on the
Receptionist and again on the specialist whenever a day is mentioned (we cannot switch it off).

## 2. Server side: plain MCP vs WellNest (measured inside the server)

`/api/ops/benchmark` runs each path `n` times (default 20) and reports p50 / p95:

| What | Plain MCP server | WellNest | Where it helps |
|---|---|---|---|
| Patient context for 5 patients | rebuild from Postgres (4 queries each) | read P1 snapshot from the **Redis blackboard** | every tool after `verify_patient`, the dashboard, the portal |
| Doctor / department lookup | query Postgres | in-process reference cache | every slot, doctor and coverage question |
| "Slots + fees" question | 2 tool calls, 2 agent hops | **1 tool call, 1 agent hop** | the V1 12.1 s case |
| Fact from one agent needed by another (pre-approval) | lost, or an extra tool call | rides in the next reply's `related` field, **0 extra calls** | MRI booking after a coverage check |

Local run (SQLite on the same disk, so database time is the *smallest* it can be):
patient context **4.6 ms → 0.05 ms** (about 90× faster), reference lookup 0.2 ms → under 0.01 ms.
On Render the database is Supabase over the network, so the gap is larger: open the URL below and paste the live
numbers here.

Live numbers (fill in on demo day): patient context ___ ms → ___ ms (×___), reference lookup ___ ms → ___ ms.

The same response also returns `blackboard_live` (backend `connected` = Redis, hits, misses, hit rate) and
`talkdesk_traffic` (server-side p50/p95 of the real Talkdesk tool calls since the last restart).

## 3. Is Redis really in use? (30-second check)
1. `https://teamxyz-mcp.onrender.com/health` → `"blackboard":"connected"` and `"events":"redis-streams"`.
   `connected` means Render Key Value (Redis); `not configured (in-process memory)` would mean it is not.
2. `/api/ops/system?token=<DASHBOARD_TOKEN>` → `blackboard.hits` / `misses` / `cache_hit_rate`, and the context
   registry (READY / LOADING / MISSING per patient) for the three demo personas.
3. Dashboard `/dashboard?token=<DASHBOARD_TOKEN>` → "Blackboard & event stream" and "Tool latency" panels.
