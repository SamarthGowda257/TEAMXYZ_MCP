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
| The chat **hosted inside** a branded page and a big pop-up | Talkdesk's own panel, opened by our inline buttons | Two reasons, both found by testing against the live touchpoint. Re-parenting `#tdWebchat` moves an **iframe**, and browsers reload an iframe's content when it is re-parented — that would drop a live conversation mid-sentence. And the widget's own launcher iframe owns the pointer events in the bottom-right corner, so a second launcher of ours underneath it could not be clicked (Playwright reported `subtree intercepts pointer events`). The site now does what it did before: Talkdesk's bubble opens the panel, and our branding lives on the header button, the `/assistant` prompts and the calls to action |

## Still to do

- `/admin/doctors` is in the allowlist but has no page yet; the nav does not link to it.
- The Overview's "conversations by intent" chart is a channel breakdown only.
- Appointments has status filters but no date filter in the UI (the API accepts `?day=`).
- Section 9 of the brief still needs the three live Talkdesk checks (chat booking, chat → human, voice call)
  against the deployed branch before this merges to `main`.


---

## Update — the staff console as the hospital reference

Added after the first pass, on the instruction that the console should cover the whole hospital. The sidebar
now has two groups: **Operations** (Overview, Escalations, Appointments, Conversations, Reminders, Patients)
and **The hospital**:

| Page | Source | Verified rows |
|---|---|---|
| Doctors | `GET /api/doctors` | 45, with a seven-initial week strip, fee, room and languages; filter by department, search by name/language/room |
| Departments | `GET /api/departments` | 14, with floor, doctor count and what each covers |
| Tests & scans | `GET /api/procedures` | 35, with price, fasting hours, pre-auth flag and the preparation text |
| Insurance | `GET /api/insurers` | 10, with cashless mode, TPA and documents to bring |
| Knowledge base | `GET /api/ops/kb?full=true` | **111 passages**, filterable by kind (Departments 14, FAQs 28, Hospital information 8, Insurers 10, Policies 16, Tests and scans 35) and searchable across full text |

Every one of these reads an endpoint that already existed — **no new backend route was added for them**. The point
is that staff read the exact sentences the Info agent speaks, so the desk and the phone line cannot drift apart.

Shared console pieces moved to `frontend/src/pages/adminKit.tsx` (`useOps`, `Panel`, `Chip`, `Empty`, `Loading`,
`statusKind`) so the operations pages and the reference pages behave identically.

New SPA routes added to the `PAGES` allowlist: `/admin/departments`, `/admin/tests`, `/admin/insurance`,
`/admin/knowledge` (`/admin/doctors` was already there and now has a page).

### The patient chat no longer appears in the console
`loadChat()` is skipped on `/admin`, and CSS hides `#tdWebchat` under `.ad-shell` / `.ad-login` for the case
where a staff member navigates in from a patient page. Verified: widget present on the site, hidden in the
console, and back again after navigating out.

## Answering calls and continuing chats — where that actually happens

This console **cannot** answer a call or type a reply, and that is not a gap we can close:

- Talkdesk routes the voice leg to the agent's **browser softphone**, which is WebRTC inside Talkdesk's own
  agent app. There is no public API or embed for it.
- Embedding Conversations in an iframe does not work either: `https://pesit-hackathon.mytalkdesk.com/atlas/apps/conversations`
  answers **302** to its OAuth login, so it needs the agent's own Talkdesk session and refuses to be framed.

So the division of labour is: **Talkdesk Conversations is where the human talks**; this console is the context
and tracking beside it — who is waiting, how urgent, what the AI already learned, the patient's file and recent
actions, and a one-click link into Conversations. That is also why the Escalations detail panel says so in
plain words rather than implying a reply box.

## Verified in this pass

| Check | Result |
|---|---|
| `pytest tests/` | **60 passed** (up from 58: the merged outreach work adds two) |
| `npm run build` | clean |
| Live Talkdesk widget with the real touchpoint `1332…b213` | iframe `v2.0.68` loads, `window.webchat` created, **0 console errors** |
| Header "Chat to book" | calls `window.webchat.open()`; the real panel opens and greets |
| Chat on `/admin` | hidden; restored after navigating back to the site |
| 5 reference pages | 45 / 14 / 35 / 10 / 111 rows, no horizontal overflow, 0 page errors |
| `git diff main -- app/mcp_tools.py app/services/ app/db.py app/main.py app/talkdesk.py` | empty |
