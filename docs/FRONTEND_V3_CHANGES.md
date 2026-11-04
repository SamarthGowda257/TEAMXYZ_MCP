# frontend-v3 — what changed

Branch `frontend-v3`, built 4 Nov 2026. Everything here is **additive**. No MCP tool, no existing API route and
no existing response shape was changed.

## Proof the frozen surfaces are untouched

```bash
git diff --stat main -- app/mcp_tools.py app/services/ app/db.py app/main.py app/talkdesk.py
# empty: tools, services, schema, ASGI assembly and the Talkdesk client are unchanged
git diff --name-only main -- app/
# app/api.py  app/config.py   <- only these two
```

Verified locally against a SQLite copy of the schema:

| Check | Result |
|---|---|
| `/health` | 200, `db: true` |
| `python -m pytest tests/ -q` | **58 passed** |
| `npm run build` (tsc + vite) | clean, `web/dist` rebuilt |
| `/mcp` without a Bearer token | 401 |
| Admin/ops endpoints with no session | 401 on all five |
| Admin login, wrong password | 401 |
| Admin login, correct password | 200, `wn_admin` cookie set, all six endpoints 200 |
| `/api/ops/summary?token=<DASHBOARD_TOKEN>` | 200 — the old `/dashboard` keeps working |
| New SPA routes on hard refresh | 200 for all 10 |

## New backend routes (`app/api.py`)

| Route | Auth | Why it was needed |
|---|---|---|
| `POST /api/admin/login` | public, rate-limited | An admin ID + password instead of a token in the URL |
| `POST /api/admin/logout` | cookie | Clears the session |
| `GET /api/admin/me` | cookie | Lets the console decide whether to show the login screen |
| `GET /api/ops/handoffs` | admin session **or** dashboard token | The Escalations queue. Nothing existing exposed `create_handoff` rows |
| `POST /api/ops/handoffs/{code}/status` | admin session only | "Mark in progress" / "Resolve". The only write added |
| `GET /api/ops/conversations` | session or token | Conversation list from `interaction_notes` |
| `GET /api/ops/conversations/{id}` | session or token | One conversation plus that patient's recorded actions |
| `GET /api/ops/appointments` | session or token | Hospital-wide list. `/api/me/appointments` is one patient's own |
| `GET /api/ops/patients` | session or token | Patient directory, phones masked |
| `GET /api/policies` | **public** | The 16 `kb:policy` passages, for the `/policies` page |

`ops_auth` now accepts **either** the existing dashboard token **or** a signed admin cookie, so every pre-existing
ops endpoint keeps its old behaviour and also works for a signed-in admin.

## Database

**No migration. No new table. No new column.** Two things the brief expected to add already existed:

- `handoffs.status` and `handoffs.assigned_to` are in the schema already (`app/db.py`), so the Escalations
  console writes to columns that were always there.
- Admin credentials come from env vars, so `admin_users` was not needed.

`handoffs.resolved_at` was **not** added — `status` plus `assigned_to` carry everything the console shows.

## New env vars (Render)

| Variable | Default | Notes |
|---|---|---|
| `ADMIN_USER` | `admin` | The admin ID typed on `/admin` |
| `ADMIN_PASSWORD` | falls back to `DASHBOARD_TOKEN` | **Set this to a real password before the demo.** Until it is set, the dashboard token doubles as the admin password so the console works with no Render change |

Nothing else changes. `MCP_BEARER_TOKEN`, `TALKDESK_*` and the rest are untouched.

## New frontend

| File | What |
|---|---|
`frontend/src/components/WellNestAI.tsx` | The WellNest AI mark (original SVG), the floating launcher, the side sheet, the branded chat frame, the suggested-prompt rail
`frontend/src/pages/Assistant.tsx` | `/assistant` — full-page chat, two columns on desktop
`frontend/src/pages/Policies.tsx` | `/policies` — accordion with anchor links, fed by `/api/policies`
`frontend/src/pages/Admin.tsx` | `/admin` — login, shell, Overview, Escalations, Appointments, Conversations, Reminders, Patients
`frontend/src/styles/ai.css` | Chat surfaces and the policies page
`frontend/src/styles/admin.css` | The staff console
`frontend/src/lib/chat.ts` | **Extended, not replaced:** `hostChat` / `unhostChat` move the live widget into our frame

New routes, all added to the `PAGES` allowlist in `app/api.py` so a hard refresh works:
`/assistant`, `/policies`, `/departments`, `/admin`, `/admin/escalations`, `/admin/appointments`,
`/admin/conversations`, `/admin/reminders`, `/admin/patients`.

## Also fixed on the way

The top bar and the footer showed a hardcoded `080 4000 1234`. Both now use `voiceNumber()`, so they show the
number that actually reaches the AI receptionist. This was item 3 of the open-fixes list.

## Decisions that differ from the brief

| Brief said | What shipped | Why |
|---|---|---|
| Deep teal `#0F5E63` + light **and dark** mode | Clinical hospital look, medical blue `#0b5cad`, **light only** | Repo owner's instruction |
| Inter / Plus Jakarta Sans **via Google Fonts** | Manrope + DM Serif Display, self-hosted via `@fontsource` | The CSP in `app/api.py` allows styles and scripts only from `'self'` and `*.talkdesk(app).com`. A Google Fonts link is blocked and would silently fail |
| `admin_users` table | Env-var credentials + signed cookie | No migration on demo day for no visible gain |
| Conversations as **chat bubbles** with tool-call chips | A reconstructed **activity timeline** | `interaction_notes` stores summaries, topics and outcomes — not turn-by-turn messages. The verbatim transcript exists only inside Talkdesk. Rendering invented bubbles would be a fabricated transcript |

## Still to do

- `/admin/doctors` is in the allowlist but has no page yet; the nav does not link to it.
- The Overview's "conversations by intent" chart is a channel breakdown only.
- Appointments has status filters but no date filter in the UI (the API accepts `?day=`).
- Section 9 of the brief still needs the three live Talkdesk checks (chat booking, chat → human, voice call)
  against the deployed branch before this merges to `main`.
