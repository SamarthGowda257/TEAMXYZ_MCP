# Latency results

Budget (docs/08): reads p50 ≤ 80 ms, p95 ≤ 250 ms; responses ≤ ~1 KB typical, 2 KB hard cap.

## Local, Postgres 16 (3 Nov, build container, 30 calls each, MCP round trip)
Same machine as the database, so this is server + database time without internet distance.

| Tool | p50 ms | p95 ms | size bytes |
|---|---:|---:|---:|
| `find_available_slots` | 12 | 20 | 1787 |
| `get_doctors` | 8 | 9 | 1205 |
| `verify_patient` | 21 | 27 | 568 |
| `find_appointments` | 16 | 19 | 706 |
| `get_lab_report_status` | 16 | 20 | 493 |
| `check_coverage` | 7 | 9 | 441 |
| `get_insurance_info` | 7 | 8 | 410 |
| `get_hospital_info` | 6 | 7 | 196 |
| `suggest_department` | 6 | 8 | 317 |

## Live (Render + Supabase, Singapore)
To fill in on demo morning (needs a laptop; the build container can't reach Render):
```bash
MCP_URL=https://teamxyz-mcp.onrender.com/mcp MCP_BEARER_TOKEN=... python scripts/bench_tools.py 50
```
The dashboard's "Tool latency" panel shows server-side p50/p95 for real Talkdesk calls.

## Agent hops (the bigger win)
V1 needed Receptionist → Booking → Receptionist → Info → Receptionist (12.1 s) for "free cardiology slots tomorrow and
the doctors' fees". In V2 `find_available_slots` returns each doctor's days, hours, fee, room and languages, plus the
resolved date and weekday, so one specialist answers it.
