# 10 — Build Plan

Timeline: build Tue 3 Nov → **code freeze Wed 4 Nov 12:30 IST**. Demos 2 PM. Work top to bottom; each phase leaves the live server working.

## Phase 0 — Understand and protect (30 min)
- [ ] Read all docs and any skills in the repo.
- [ ] Inspect `server.py` etc. Write `docs/V1_INVENTORY.md`: MCP library + version, transport, endpoint path, auth header + env var name, existing tool signatures, data structures, how the dashboard works, deploy config.
- [ ] `git tag v1-baseline && git push origin v1-baseline`. Create branch `v2`.
- [ ] Create `docs/HUMAN_TODO.md` (template below).
- **Done when:** inventory written, tag pushed, nothing changed in behaviour.

## Phase 1 — Skeleton without breaking V1 (1–1.5 h)
- [ ] Restructure into `app/` (or keep `server.py` as the entry that imports `app`) so the MCP endpoint path, transport and auth are identical.
- [ ] `config.py`, `db.py` (pool), `util/normalize.py` (+ tests), `util/envelope.py`, `metrics.py`, `@timed_tool`, `/health`.
- [ ] Re-implement the 6 V1 tools on top of an in-memory repository first (same behaviour), returning the new envelope. Rename branding to WellNest Hospitals.
- [ ] `scripts/smoke_mcp.py` calling all tools through the real MCP transport with the bearer token (URL + token from env).
- **Done when:** smoke test passes locally against the in-memory repo; V1 tool inputs still accepted.

## Phase 2 — Database (2 h)
- [ ] `db/schema.sql`, `db/seed/generate.py` → `seed.sql`, `db/reset.sh`, `PERSONAS.md`.
- [ ] `repo/` with asyncpg queries for slots, appointments, patients, waitlist, reports, insurance.
- [ ] Switch the 6 tools to Postgres. Booking transaction + unique index guard.
- [ ] Test against local Postgres if possible (see `00` environment notes).
- **Human:** create Supabase project (Singapore), run `reset.sh` with the pooler URL, set `DATABASE_URL` on Render.
- **Done when:** seed loads in < 30 s; booking the same slot twice concurrently gives one success and one `slot_taken`.

## Phase 3 — P0 tools (2–3 h)
- [ ] `verify_patient` (+ lockout), identity checks in cancel/reschedule.
- [ ] Waitlist: `join_waitlist`, auto-offer on cancel/reschedule (slot held 30 min), `accept_waitlist_offer`, `/waitlist/accept` page.
- [ ] `get_lab_report_status`, `email_lab_report`.
- [ ] `get_insurance_info`, `check_coverage`.
- [ ] `create_handoff`; `get_doctors` trimmed; `find_available_slots` enriched with doctor days/fees/notes.
- [ ] Outbox + background email sender (SMTP or simulated). `resolutions` on every write.
- [ ] Blackboard v1: P1 snapshot cache + P2 facts + `related` top-3.
- **Done when:** the acceptance tests A1–A8 below pass.
- **Human:** refresh MCP server in Talkdesk; map new skills (see `05`).

## Phase 4 — Website core (3 h)
- [ ] `web/` pages: home, doctors, login/signup/link, portal, book, appointments, reports, waitlist accept, profile.
- [ ] `/api` routes + Supabase JWT verification (JWKS or HS256).
- [ ] Chat widget loader with placeholder when no touchpoint ID; context params; session warm.
- [ ] Read-only dashboard with metrics.
- **Human:** Supabase Auth email provider on, site URL set; Render env vars; Talkdesk touchpoint ID when created.
- **Done when:** a persona can sign up, link, book on the web, and see the booking the bot made (and vice versa).

## Phase 5 — P1 features (2–3 h)
- [ ] `register_patient`, `find_appointments` privacy rule, `get_visit_history`.
- [ ] Care Assist tools; senior message variants.
- [ ] `suggest_department`, `get_hospital_info`, `get_visit_instructions`.
- [ ] `request_callback`, `save_interaction_note`, `search_past_interactions` (full-text).
- [ ] Jobs runner: reminders 24 h / 2 h, waitlist expiry. External cron set up by human.
- [ ] Async prefetch + prefetch metrics.

## Phase 6 — P2 (only if time)
- [ ] Billing tools, aftercare tools + check-in page, caregiver update, prescription refill, birthday job.
- [ ] Redis L2 (`REDIS_URL`), pgvector embeddings (`EMBEDDINGS_PROVIDER`).
- [ ] Talkdesk REST client stub (Contacts upsert) behind `TALKDESK_ENABLED`.

## Phase 7 — Harden and freeze (Wed morning)
- [ ] `scripts/bench_tools.py` → `docs/LATENCY_RESULTS.md`.
- [ ] Reset seed relative to today. Verify personas.
- [ ] Merge `v2` → `main` (with user OK), watch Render deploy, run smoke test against the live URL.
- [ ] Tag `v2-demo`.

## Acceptance tests (automate where possible; IDs map to `03_REQUIREMENTS.md`)
| ID | Scenario | Expected |
|---|---|---|
| A1 | `verify_patient` Arjun correct DOB / wrong DOB | snapshot / generic failure; 6th wrong try in 15 min → `locked_out` |
| A2 | Book same slot twice in parallel | one booking, one `slot_taken` |
| A3 | `book_appointment` twice with same idempotency key | same booking ID returned |
| A4 | Cancel Shanthamma's booking using Arjun's phone | `not_allowed`, nothing changed |
| A5 | Cancel a booking where Arjun is waitlisted for that doctor/date | slot `held`, offer created, email (or simulated) queued; Arjun accepts → booked; second accept → `offer_expired`/taken |
| A6 | Lab: Priya status → ready report; email → `sent_to` masked; pending report cannot be emailed | as stated |
| A7 | `check_coverage(Star Health, MRI Knee)` → partial/yes with `preauth_required: true`; then `book_appointment(procedure=MRI-KNEE)` → `related` contains pre-auth fact | as stated |
| A8 | `create_handoff(priority=urgent)` → message starts with 108 advice; dashboard shows it | as stated |
| A9 | Every tool: envelope present, `message` ≤ 3 sentences, size ≤ 2 KB, no exception on garbage input | as stated |
| A10 | `find_available_slots(date=tomorrow, department=Cardiology)` returns both cardiologists' days/fees in one response | no need for `get_doctors` |
| A11 | Senior persona responses are shorter than non-senior for the same tool | as stated |
| A12 | Website booking appears in `find_appointments` via MCP and vice versa | as stated |
| A13 | Tool p95 within budget on deployed URL (bench script) | see `08` |

## `docs/HUMAN_TODO.md` template (keep it updated)
```
# Things a human must do (Claude Code can't click these)
## Supabase
- [ ] Create project "wellnest" in region Singapore
- [ ] Copy transaction pooler URL → Render env DATABASE_URL
- [ ] Run: DATABASE_URL=... ./db/reset.sh   (from a laptop or Supabase SQL editor: paste schema.sql then seed.sql)
- [ ] Auth → Email provider on; Site URL = PUBLIC_BASE_URL; copy anon key + JWT settings
## Render
- [ ] Env vars: (list every new one here)
- [ ] Health check path /health
## Uptime/cron
- [ ] Ping /health every 5 min; POST /jobs/run?token=... every 1 min
## Talkdesk
- [ ] Refresh MCP server connection so new tools appear
- [ ] Map new skills to agents (table in docs/05)
- [ ] Create chat touchpoint → give TALKDESK_TOUCHPOINT_ID + region
```

## Reporting back to the user
After each phase, give a short summary: what works now, what's next, and any new items in `HUMAN_TODO.md`. Ask before merging to `main`.
