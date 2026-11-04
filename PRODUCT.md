# PRODUCT.md — WellNest Hospitals

Durable product truth for the WellNest web surfaces. Written 4 Nov 2026 from `docs/FRONTEND_REDESIGN_PROMPT.md`,
the repo's own docs (`docs/00`–`docs/10`, `TALKDESK_SETUP.md`, `KNOWLEDGE_BASE.md`) and the live code, plus four
decisions the repo owner answered directly before the build. Visual decisions live in `DESIGN.md`, not here.

## Platform

web

## Stack

React 18.3 · TypeScript 5.6 · Vite 5.4 · react-router-dom 6.28 · lucide-react · Lenis (smooth scroll) ·
self-hosted fonts via `@fontsource` (Manrope Variable, DM Serif Display, Atkinson Hyperlegible).
Hand-written CSS with custom properties in `frontend/src/styles/` — no CSS framework.

The frontend builds to `web/dist`, which is **committed to git** and served directly by FastAPI
(`app/api.py`). Render runs no npm build. Every visual change therefore needs a local `npm run build`
and a committed `web/dist`. A stack change would mean re-wiring the deploy, so the stack is fixed.

Backend: one FastAPI app serving `/mcp` (34 MCP tools for Talkdesk), `/api` (website), `/jobs` (cron),
on Supabase Postgres + Redis, with hybrid search (Postgres full-text + trigram + pgvector).

## Users

1. **Patients and their families** in Marathahalli, Bengaluru. Wide range: Shanthamma, 67, booking cardiology
   by phone; Arjun, 34, taking a waitlist offer on his phone; a caregiver acting for a parent. Many are not
   fluent in English or in web forms. Phone and chat are first-class, not fallbacks.
2. **Hospital reception staff** (today: two people) who take over a chat or call when the AI escalates. They
   work inside Talkdesk Conversations; the admin console is the context and tracking screen beside it.
3. **Hackathon judges** on 4 Nov 2026, assessing integration and architecture, problem choice, real-world
   impact, and the presentation. "How real the product feels" is explicitly part of the score.

## Product Purpose

WellNest is an AI front desk for a hospital. A patient books, reschedules, cancels, joins a waitlist, checks a
lab report or checks insurance by **website chat, phone call, or the website itself** — and every one of those
paths writes to the same database and shows on the same live operations view. A human can take over any
conversation at any point without the patient repeating themselves.

The unique mechanism: **one brain, every channel.** The same nine agents and the same 34 tools answer the web
chat and the phone line, because both run through the same Talkdesk orchestration against the same MCP server.

## Positioning

Not a FAQ chatbot. Nine specialised agents that *act*: verify identity, book, refill a cancelled slot from the
waitlist, check coverage, escalate an emergency. The promise is that a freed slot never goes empty and nobody
reaches a dead end — if the AI can't help, a person picks up; if nobody is free, it takes a voicemail.

## Operating Context

- **Live and demonstrated today.** The Talkdesk voice number, the website chat touchpoint, the orchestration
  and the Studio flows all point at the deployed `main`. Breaking the backend or the chat embed means no demo.
- Render free tier: the service sleeps and is woken by an uptime ping; first load after sleep is slow.
- Usage is bursty and small (a demo), but the design must read as a real hospital under real load.
- Emergencies are a genuine path, not an edge case: chest pain must stop the booking flow and surface 108.

## Capabilities and Constraints

- **The 34 MCP tools are frozen.** Names, parameters, docstrings and return shapes cannot change; Talkdesk
  skill mappings depend on them exactly.
- **Existing API routes and response shapes are frozen.** New work is additive only: new read-only routes,
  new nullable columns, new tables.
- **The Talkdesk chat widget cannot be replaced.** Chat Widget V2 SDK, same script URL, same touchpoint ID and
  region. It renders its own UI; it has no headless mode. It can be mounted into our own container, opened by
  our own launcher, and given a title, subtitle and theme colour — nothing more. Bot name and avatar inside the
  panel are Talkdesk touchpoint settings, changed by hand.
- **A strict CSP** (`app/api.py`) allows scripts and styles only from `'self'` and `*.talkdesk(app).com`.
  **Google Fonts and every other CDN are blocked.** Fonts must stay self-hosted through `@fontsource`.
- **SPA routes are an explicit allowlist** (`PAGES` in `app/api.py`). A new route 404s on hard refresh until
  it is added there.
- Identity-sensitive actions verify phone + date of birth **on the server**. The browser session is never
  trusted for that, by design: browser data can be faked, and the same rule has to protect the phone line.
- Email is real only when SMTP env vars are set; SMS and WhatsApp are simulated rows in an outbox.

## Brand Commitments

- Name: **WellNest Hospitals**. The assistant is **WellNest AI** ("WellNest AI Assistant").
- Phone on every surface comes from `TALKDESK_VOICE_NUMBER` (+1 218 443 7744), never a hardcoded number.
- Emergency guidance is always **108**, and always visible.
- Fictional hospital; every patient, phone number and email in the data is invented.

## Evidence on Hand

- Live doctor, department, procedure, insurer and slot data through `/api/*`.
- A 111-passage knowledge base (`app/kb.py` + `data/hospital/`) that the Info agent answers from, including
  16 policy passages.
- Real operational data to show: handoffs, outbound calls, notifications outbox, tool latency, OPD fill.
- Two hospital reference manuals in `docs/hospital/` for prose the database does not hold.
- No photographs of real people may be used.

## Product Principles

1. **A working Talkdesk chat beats a prettier broken one.** Wrap the widget; never reimplement it.
2. **The live database and knowledge base are the source of truth.** Doctors, fees, hours and slots come from
   the API. The reference manuals only fill gaps. The website must never contradict what the phone agent says.
3. **Say the true thing.** Where a capability is simulated, label it. Never show a fabricated transcript.
4. **Every surface offers a way to a human**, and never promises a connection it cannot make.
5. **Additive only.** If it would change a tool signature or an existing response shape, it is out of scope.

## Accessibility & Inclusion

- WCAG AA contrast minimum; visible focus on every interactive element; full keyboard operation.
- Works at 360px with no horizontal scroll; the site already ships a larger-text mode (`data-size="lg"`) and
  Atkinson Hyperlegible is available for it.
- Many users are elderly: generous hit targets, plain language, no reliance on hover or on colour alone.
- Patients are never asked to reformat a date or a phone number, on any channel.

## Decisions taken 4 Nov 2026 (repo owner)

| Topic | Decision |
|---|---|
| Stack | Keep React + TypeScript + Vite. |
| Theme | Clinical **hospital** look, white and medical blue. **Light mode only — no dark theme.** |
| Admin auth | Real admin **ID + password** login with a server-side cookie session. |
| Conflicting facts | Live DB/KB wins; the manuals fill gaps only. |
