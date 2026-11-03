# 09 — Frontend (website + dashboard)

## Tech choice
- **No build step.** Plain HTML + CSS + JavaScript ES modules in `web/`, served by FastAPI. Nothing to compile on Render, nothing to break on demo day.
- Supabase Auth from a pinned CDN build: `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js` (or a version you verify exists). Config from `/config.js`.
- One shared `web/js/api.js` that adds the access token to every `/api` call and handles 401 → login.
- One shared `web/css/wellnest.css` with design tokens. No CSS framework required.

## Pages
| Path | Login | Content |
|---|---|---|
| `/` | no | Hero ("Book, reschedule and get reports in under a minute, by chat, phone or web"), 3 actions (Book, Lab reports, Talk to us), departments grid, why WellNest, emergency band (call 108 / emergency 24×7) |
| `/doctors` | no | Filter by department, language, day; doctor cards (photo placeholder initials, qualification, experience, days/hours, fee, languages) → "Book" |
| `/insurance` | no | Accepted insurers, cashless vs reimbursement, documents, coverage checker (insurer + procedure → estimate) |
| `/contact` | no | Address, hours, map link (link out, no iframe), phone, emergency |
| `/login`, `/signup` | – | Supabase email + password. After signup: link step (phone + DOB) → `POST /api/me/link` |
| `/portal` | yes | Greeting, next appointment card (with assistance badges), pending/ready reports, waitlist offers, quick actions, "Ask WellNest" (opens chat) |
| `/portal/book` | yes | 3 steps: department or procedure → date + doctor + slot grid → confirm (shows fee, coverage estimate, instructions). Same service as the bot. |
| `/portal/appointments` | yes | Upcoming/past tabs; reschedule; cancel (in-page confirm step, no `confirm()`); request wheelchair/escort |
| `/portal/reports` | yes | Report list with status chips; report detail with results table and reference ranges; "Email me this" |
| `/portal/profile` | yes | Contact info, language, preferred time, caregiver + consent, mobility needs, insurer/policy |
| `/portal/waitlist` | yes | My waitlist entries, join form |
| `/waitlist/accept` | no (code + phone) | Offer details with countdown; Accept → booked; expired/taken states |
| `/checkin` | no (link token) | P2: post-visit form (pain 0–10, fever, worse?) |
| `/dashboard?token=` | ops token | Read-only operations board (below) |

## Operations dashboard (read-only, polls every 5 s)
Panels: today's schedule by department (booked/free bars), live activity feed (bookings, cancels, offers, accepts with channel badges chat/voice/web), waitlist offers with countdown, handoffs (urgent in red), outbox (email sent / SMS simulated), nurse alerts, **latency** (per-tool p50/p95, cache hit %, prefetch hit %), counts today (bookings, slots refilled from waitlist, handoffs). This is what the judges watch while the bot works, so make it clear and large.

## Talkdesk chat widget
- Snippet from `02_TALKDESK_PRIMER.md`, loaded on every page by `web/js/chat.js`.
- If `TALKDESK_TOUCHPOINT_ID` is empty: show a styled "Chat launches here" button that explains chat is being connected (no broken widget).
- Custom launcher: our own "Ask WellNest" buttons call `webchat.open()`.
- After login: `setContextParam({ patient_name, patient_phone, td_contact_person_identification: patient_phone })` on `onOpenWebchat` and `onConversationStart`; also `POST /api/session/warm`.
- On logout: `webchat.reset()`.
- Style the widget to match tokens: `chatThemeColor`, `chatTitle: "WellNest Assistant"`, `chatSubtitle: "Usually replies in seconds"`.

## Design direction
- Feel: a calm, trustworthy modern Indian hospital. Clinical clarity, warm and human, not sterile, not startup-flashy.
- Palette tokens (light; provide a dark variant too):
  - `--ink` deep blue-green `#0F2A2E` (text), `--paper` `#F6F8F7` (background), `--surface` `#FFFFFF`
  - `--care` teal `#0A7C74` (primary actions), `--care-tint` `#DDF1EE`
  - `--marigold` `#E3A21A` (highlights, senior/assist badges; a nod to Bengaluru)
  - `--alert` `#C2362F` (emergency only), `--ok` `#2E7D4F`
- Type: headings in a humanist serif or semi-serif with character (e.g. "Fraunces" or "Source Serif 4"), body in a highly legible sans with good Indic name rendering (e.g. "Noto Sans"), numbers in tabular figures. Load from Google Fonts with fallbacks.
- Layout: generous spacing, max text width ~65ch, cards only for real objects (appointment, report, doctor). Status as chips (Booked, Pending, Ready, Offered, Simulated).
- **Larger text toggle** in the header (adds `data-size="lg"` → base 18px) and remembers the choice in `localStorage`.
- Emergency band always reachable on public pages: "Medical emergency? Call 108" in `--alert`.
- Accessibility: WCAG AA, focus rings, labels on all inputs, 44 px touch targets, `prefers-reduced-motion` respected.
- Mobile first: works at 360 px; bottom action bar on mobile portal (Book, Reports, Chat).
- Copy: plain words, active voice ("Book appointment", "Booked for Wed 4 Nov, 10:30 AM"). Errors say what to do.

## API used by the website (`/api`)
| Method & path | Auth | Purpose |
|---|---|---|
| `GET /config.js` | – | Public config |
| `GET /api/departments`, `/api/doctors?department=&language=&day=` | – | Lists |
| `GET /api/procedures`, `/api/insurers`, `/api/hospital-info` | – | Lists |
| `GET /api/slots?date=&department=&doctor=&procedure=&time_preference=` | – | Free slots |
| `POST /api/coverage/estimate` | – | Coverage checker |
| `POST /api/me/link` | JWT | Link account to patient (phone + DOB) |
| `GET /api/me` | JWT | Profile + snapshot |
| `PATCH /api/me/preferences` | JWT | Preferences & caregiver |
| `GET /api/me/appointments?scope=upcoming|past` | JWT | List |
| `POST /api/me/appointments` | JWT | Book (idempotency key header) |
| `POST /api/me/appointments/{code}/reschedule` | JWT | Reschedule |
| `POST /api/me/appointments/{code}/cancel` | JWT | Cancel |
| `POST /api/me/appointments/{code}/assistance` | JWT | Wheelchair etc. |
| `GET /api/me/reports`, `GET /api/me/reports/{code}` | JWT | Reports |
| `POST /api/me/reports/{code}/email` | JWT | Email report |
| `GET/POST /api/me/waitlist` | JWT | Waitlist |
| `POST /api/session/warm` | JWT | Prefetch on chat open |
| `GET /api/waitlist/offer/{code}`, `POST /api/waitlist/offer/{code}/accept` | code + phone | Accept page |
| `GET /api/ops/feed`, `/api/ops/summary`, `/api/metrics` | dashboard token | Dashboard |

Every response includes `X-Response-Time`. Errors use `{ "error_code", "message" }` with the same codes as the tools.
