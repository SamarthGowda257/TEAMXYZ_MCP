# WellNest V2: what's built and how to use it

## Shape
One Python process on Render (`python server.py`):
| Path | What |
|---|---|
| `/mcp` | MCP server for Talkdesk. Same library (mcp 2.3.0), transport, path and Bearer token as V1. 34 tools. |
| `/` and pages | Patient website (React, built into `web/dist`): home, doctors, insurance, visit us, login/signup, portal (overview, book, appointments, lab reports, waitlist, profile), waitlist accept page |
| `/dashboard?token=` | Live front-desk dashboard: OPD fill, activity by channel, waitlist offers, handoffs, outbox, per-tool latency |
| `/api/...` | Website + dashboard API (same services as the tools) |
| `/jobs/run?token=` | Reminders (24 h email+SMS, 2 h call) and waitlist offer expiry |
| `/ops/reset-demo?token=` | Rebuild demo data relative to today (about 3 s) |
| `/health` | Uptime + DB check |

Database: Postgres when `DATABASE_URL` is set (Supabase), otherwise a local SQLite file. Both are seeded automatically.

## Demo personas (bot: phone + date of birth)
| Persona | Phone | DOB | Story |
|---|---|---|---|
| Shanthamma K, 67 | 98450 00001 | 1959-03-04 | Senior, Star Health, cardiology booking **WN-48213** with Dr. Rajesh Iyer, MRI Knee report pending, son Ravi as caregiver |
| Arjun Mehta, 34 | 98450 00002 | 1992-06-15 | On the waitlist for Dr. Rajesh Iyer (fully booked this week). Cancel WN-48213 → Arjun gets the offer |
| Priya Nair, 29 | 98450 00003 | 1997-01-20 | Thyroid report ready (LR-20931); asked about her MRI report 6 days ago (memory) |
| Rahul Verma, 45 | 98450 00004 | 1981-09-10 | No insurance, unpaid bill BL-55012 |
| Meera Joshi, 8 | 98450 00005 | 2018-05-12 | Child, father Sanjay as caregiver |
| Imposter | 98450 00002 | any other date | Must fail verification |

## Run locally
```bash
pip install -r requirements.txt
MCP_BEARER_TOKEN=dev python server.py            # http://localhost:8000
python -m pytest -q tests                        # unit tests
MCP_URL=http://localhost:8000/mcp MCP_BEARER_TOKEN=dev python scripts/smoke_mcp.py   # 30 acceptance checks over MCP
```
Website development: `cd frontend && npm ci && npm run dev` (proxies the API to :8000). After changes: `npm run build`
and commit `web/dist` (Render does not run Node).

## Tested (3 Nov)
- Unit tests 23/23; MCP smoke/acceptance 30/30 on SQLite **and on Postgres 16** (A1-A11, incl. parallel double booking,
  waitlist offer and accept, identity lockout, senior short replies, pre-auth fact carried into the booking reply).
- Browser end-to-end (Playwright): login, portal, booking, reports, appointments, dashboard, mobile 390 px; no console errors.
- Not testable from the build container: the live Render URL and Supabase itself (network blocked). See HUMAN_TODO step 7.

## Design
Frontend follows the taste-skill direction "One motif" (the OPD token slip as the single shape: hero, buttons, booking
IDs, call-back coupon), impeccable's craft floor and ui-ux-pro-max's accessibility checks (Atkinson Hyperlegible body text,
larger-text toggle, 44 px targets, WCAG AA). Inspector result on the home page: 0 FAIL. Skills live in `.claude/skills/`.
