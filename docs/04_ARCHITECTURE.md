# 04 — Architecture

## Big picture
```
 WEBSITE (browser)                                PHONE
  portal pages ──────── /api (JWT) ─────────┐      caller
  Talkdesk chat widget ─► Talkdesk ─┐       │        │
                                    ▼       │        ▼
                    Studio chat flow / Studio voice flow ─► Autopilot ─► Orchestration
                                                                           (9 agents)
                                                                              │ /mcp (bearer)
                                                                              ▼
 ┌──────────────────────────── ONE FASTAPI APP on Render ─────────────────────────────┐
 │  /mcp   MCP tools ──┐                                                               │
 │  /api   website API ├──► services/ (business rules) ──► repo/ (SQL) ──► Postgres   │
 │  /jobs  cron runner ┘          │                │                                   │
 │  /      static website          ▼                ▼                                  │
 │                         context/ (blackboard: L1 memory, optional L2 Redis)         │
 │                         notify/  (outbox → background email sender)                 │
 │                         metrics/ (per-tool timings)                                 │
 └─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                               Supabase: Postgres (+ Auth, + pgvector optional)
```

**Key ideas**
1. **One process, one deploy.** MCP, API, website and jobs share code and the DB pool. No CORS, no service-to-service calls.
2. **Services are the single source of business rules.** A booking from the bot and a booking from the website go through the same `services.appointments.book()`.
3. **Postgres is the source of truth.** Caches are only for speed and are never trusted for writes.
4. **Side effects are async.** Tools write an outbox row in the same transaction; a background task sends it.

## Code layout (target)
Adapt names to what already exists in `server.py`; move code gradually, keeping the live server working at each commit.
```
app/
  main.py              FastAPI app; mounts MCP at the existing path; /api, /jobs, /health, static
  config.py            env vars (pydantic-settings), validated at startup
  db.py                asyncpg pool (min 1, max 5, statement_cache_size=0 for Supabase pooler)
  mcp_server.py        MCP tool registration (same library/transport as V1), one function per tool
  tools/               thin tool wrappers grouped by agent: booking.py, changes.py, records.py, ...
  api/
    routes_public.py   doctors, departments, insurance, hospital info
    routes_patient.py  /api/me, appointments, book, cancel, lab reports, preferences, session warm
    routes_waitlist.py accept page API (code + phone)
    routes_ops.py      /api/metrics, /api/ops/* (dashboard token)
    auth.py            Supabase JWT verification → CurrentPatient
  services/            patients, appointments, waitlist, records, billing, insurance,
                       info, care, support, memory, aftercare
  repo/                SQL per table group (plain SQL with asyncpg, no ORM needed)
  context/             blackboard.py (P0/P1/P2), cache.py (L1 + optional Redis L2), prefetch.py
  notify/              outbox.py, email_sender.py (aiosmtplib), templates/ (Jinja2)
  jobs/                runner.py: reminders, waitlist_expiry, birthdays, aftercare
  util/                normalize.py (phone/date/time), speak.py (spoken IDs), envelope.py, timing.py
  metrics.py           rolling p50/p95 per tool, cache hit rates
web/                   static site (see 09_FRONTEND.md)
db/
  schema.sql           tables, indexes, constraints
  seed/generate.py     deterministic large dataset generator → seed.sql
  seed.sql             generated output (committed)
  reset.sh             psql $DATABASE_URL -f schema.sql -f seed.sql
tests/                 pytest: services, normalizers, tool envelopes
scripts/smoke_mcp.py   calls every tool through the real MCP endpoint
docs/                  these files + HUMAN_TODO.md
```

## Request flows
### A) Agent tool call
1. Talkdesk → `POST /<mcp path>` with `Authorization: Bearer <MCP_BEARER_TOKEN>`.
2. Auth middleware: constant-time compare. Fail → 401.
3. Tool wrapper: start timer, normalise inputs (phone, date, time), validate.
4. Service function: read via cache/blackboard where allowed, write in a transaction, enqueue outbox rows, write `resolutions` row, update blackboard.
5. Wrapper builds the envelope (≤1 KB), records timing, returns.
6. After returning: background tasks send email and run prefetch.

### B) Website call
1. Browser → `/api/...` with `Authorization: Bearer <supabase access token>`.
2. `auth.py` verifies the JWT (see below) → `auth_user_id` → `patients.auth_user_id` lookup (cached) → `CurrentPatient`.
3. Route calls the same service functions, scoped to `CurrentPatient.id`. Any `patient_id` in the request body is ignored.

### C) Jobs
External free cron (cron-job.org or UptimeRobot) → `POST /jobs/run?token=...` every minute → runs each job with a DB advisory lock so overlapping calls don't double-send.

## Authentication & authorisation
| Surface | Credential | Check |
|---|---|---|
| `/mcp` | Bearer token (existing env var name from V1) | `hmac.compare_digest` |
| `/api/*` patient routes | Supabase access token (JWT) | Verify signature + `exp` + `aud == "authenticated"`. Newer Supabase projects use asymmetric signing keys: verify with JWKS from `https://<project>.supabase.co/auth/v1/.well-known/jwks.json` (cache 10 min). Older projects use HS256 with `SUPABASE_JWT_SECRET`. Support both: pick by the token header `alg`. |
| `/api` public routes | none | read-only, cached |
| `/waitlist/accept` | offer code + phone | code unguessable (≥10 chars base32), expires 30 min |
| `/dashboard`, `/api/metrics`, `/api/ops/*` | `DASHBOARD_TOKEN` query/header | read-only, fake data |
| `/jobs/run` | `JOBS_TOKEN` | idempotent jobs |

Patient linking: after signup, `POST /api/me/link {phone, date_of_birth}` links `auth_user_id` to an existing patient (if phone+DOB match) or creates a new patient row.

## Environment variables
```
# existing (keep names from V1 server.py; example names shown)
MCP_BEARER_TOKEN=
# database
DATABASE_URL=postgresql://...pooler.supabase.com:6543/postgres   # transaction pooler
# supabase auth
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=            # public, injected into web config
SUPABASE_JWT_SECRET=          # only if project uses HS256
# website / widget
PUBLIC_BASE_URL=https://<render-app>.onrender.com
TALKDESK_TOUCHPOINT_ID=       # empty until the team creates it
TALKDESK_REGION=td-us-1       # confirm with the team
# email
SMTP_HOST= SMTP_PORT=587 SMTP_USER= SMTP_PASSWORD= EMAIL_FROM="CareLine Hospitals <...>"
# ops
DASHBOARD_TOKEN= JOBS_TOKEN=
# optional
REDIS_URL=                    # enables L2 cache (Upstash free tier works)
EMBEDDINGS_PROVIDER=none      # none | <provider>; none = full-text search only
EMBEDDINGS_API_KEY=
TALKDESK_ENABLED=false
TALKDESK_CLIENT_ID= TALKDESK_CLIENT_SECRET= TALKDESK_ACCOUNT=
DEMO_EMAIL_OVERRIDE=          # if set, all outgoing email goes here (safe demos)
TZ_NAME=Asia/Kolkata
```
`/config.js` (served by the app) exposes only public values: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `TALKDESK_TOUCHPOINT_ID`, `TALKDESK_REGION`, `PUBLIC_BASE_URL`.

## Deployment
- Render web service (existing), auto-deploys `main`. Start command e.g. `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` (one worker: in-process cache + metrics stay coherent).
- Render health check path: `/health`.
- Region: Render and Supabase both in **Singapore** if creating new resources.
- Supabase: enable the `pgvector` extension only if embeddings are used. Use the **transaction pooler** URL (port 6543) and `statement_cache_size=0`.
- Static files served by FastAPI `StaticFiles` with cache headers; HTML no-cache.
- Startup: run `schema.sql` migrations idempotently only if `AUTO_MIGRATE=true`; otherwise the human runs `db/reset.sh` once.

## Dependencies (suggested)
`fastapi`, `uvicorn[standard]`, the MCP library already used by V1, `asyncpg`, `pydantic-settings`, `python-jose[cryptography]` or `PyJWT[crypto]`, `httpx`, `aiosmtplib`, `jinja2`, `python-dateutil`, `phonenumbers`, optional `redis>=5` (asyncio), `pytest`, `pytest-asyncio`.

## Error codes (shared by tools and API)
`not_verified`, `locked_out`, `not_found`, `slot_taken`, `outside_hours`, `invalid_input`, `already_exists`, `offer_expired`, `not_allowed`, `service_unavailable`.
