# WellNest Hospitals — Frontend Redesign Brief (for Claude Code)

> **How to use:** open the `TEAMXYZ_MCP` repo in Claude Code and paste this whole file as the task. Attach the hospital policy / info document alongside it.

---

## 0. Read this first: hard rules (do not break these)

WellNest is LIVE and connected to Talkdesk (voice number, website chat, AI orchestration `WellNest_TeamXYZ`, Studio flows, MCP server). The demo is **today at 2 PM**. Breaking the backend or Talkdesk = no demo.

1. **Backend features are frozen.** Do NOT change, rename, remove or re-sign any MCP tool, its parameters, its docstring, or its return format. Talkdesk agents depend on these exactly as they are.
2. **Do NOT change existing API routes or their response shapes.** The `/mcp` endpoint, `/health`, auth, booking logic, notifications, Redis workers, waitlist and aftercare stay untouched.
3. **Allowed backend changes are additive only, and only to serve the new frontend:**
   - New **read-only** REST routes (e.g. list conversations, list handoffs, admin stats).
   - New DB tables/columns (e.g. `admin_users`, `hospital_content`), added by a new migration. Never drop, rename or alter existing tables/columns.
   - If an existing endpoint already provides the data, use it. Don't duplicate.
4. **Talkdesk must keep working as it does now:**
   - The website chat must still go through the **same Talkdesk chat touchpoint** (same widget script, same touchpoint/channel ID). Do not replace Talkdesk chat with a different chat backend or a direct LLM call.
   - Don't change the voice number env var (`TALKDESK_VOICE_NUMBER`) or anything Studio flows call.
5. **Secrets:** never put the Bearer token, Supabase keys, OAuth secrets or admin passwords in frontend code or in Git. Use env vars on Render.
6. **Git:** work on a branch `frontend-v3`. Merge to `main` only after the full checklist in section 9 passes (Render auto-deploys `main`). Commits must be authored by the repo owner's git identity: **no "Co-Authored-By: Claude" trailers, no AI attribution in commit messages.**
7. **Before writing code:** explore the repo and write a short plan listing (a) the current frontend stack and files, (b) how the Talkdesk chat widget is embedded today, (c) which existing endpoints the frontend uses, (d) existing DB tables. Keep the **same frontend stack and deploy method** unless it truly can't meet this brief. Don't introduce a build step that breaks the current Render deploy.

---

## 1. Goal

Turn the WellNest website into a polished, production-quality hospital site with three parts:
1. A **public website** (landing + info pages) that feels like a real, trustworthy hospital brand.
2. A **patient portal** with easy login, plus a great **WellNest AI** chat experience.
3. An **admin console** that tracks everything: appointments, all conversations, escalations to humans, reminders. Clean and well organised, never messy.

All data comes from the existing backend. Only the presentation changes, plus the additive pieces in rule 3.

---

## 2. Brand & design direction

- **Name:** WellNest Hospitals. **AI assistant name:** **WellNest AI** (short label: "WellNest AI Assistant").
- **Feel:** calm, warm, clinical-clean, trustworthy. Avoid generic template looks and stock "AI gradient" styling.
- **Palette (CSS variables, light + dark mode):** deep teal primary (`#0F5E63`-ish), soft mint accent, warm off-white background, slate text, one coral colour reserved for urgent/emergency states only. Check WCAG AA contrast.
- **Type:** one humanist sans for UI (e.g. Inter / Plus Jakarta Sans via Google Fonts) and optionally a soft serif for large headings.
- **Components:** consistent spacing scale, rounded cards (12–16px), subtle shadows, clear focus states, skeleton loaders, empty states with helpful text, toast notifications.
- **Responsive:** must look right at 360px phone width and on a laptop. No horizontal scroll.
- **Images:** no photos of real people. Use original illustrations, icons (e.g. Lucide) or abstract shapes.
- **WellNest AI avatar:** create an **original** SVG avatar (e.g. a friendly rounded nest/leaf shape with a subtle face or pulse line) in the brand colours. Use it in the chat header, on every bot message, on the floating launcher, and on the landing hero. Add a small "online" dot and a typing animation.

---

## 3. Public website pages

| Route | Content |
|---|---|
| `/` Landing | Hero ("Care that answers 24/7"), WellNest AI CTA ("Chat with WellNest AI" + "Call +1 218 443 7744"), departments grid, how it works (Book → Remind → Visit → Aftercare), doctor highlights, trust signals (timings, emergency 108 note), FAQ, footer |
| `/departments` | All departments, from existing doctor data |
| `/doctors` | Doctor cards: department, days, hours, fee, languages, room. "Book" button → login or chat |
| `/about` | Hospital story, location, OPD timings, contact |
| `/policies` | **From the attached hospital policy document**: appointments, cancellation/rescheduling, payments & insurance, visitor rules, privacy, emergency policy. Each in an accordion with an anchor link |
| `/contact` | Address, phone, email, map placeholder, emergency banner |
| `/assistant` | **Full-page WellNest AI chat** (see section 5) |

Put the hospital information in **one structured content source** (e.g. `content/hospital.json` or a `hospital_content` table) built from the attached document, so pages don't hard-code text in many places. Keep facts consistent with the backend's doctor data and the info the Talkdesk agents use. Don't invent policies that aren't in the document.

Global: sticky header nav, "Login" button, persistent **emergency banner** ("Medical emergency? Call 108"), floating WellNest AI launcher on every public/patient page.

---

## 4. Login & patient portal

- **One login screen** with two tabs: **Patient** and **Staff/Admin**. Reuse the existing patient auth if there is one. Keep it to the fewest steps possible (phone/email + password or OTP, whatever already exists).
- Patient portal pages: **My appointments** (upcoming / past, status chips, reschedule & cancel buttons that call the *existing* endpoints), **My reports** (if lab-report endpoints exist), **Profile**, and a **Chat with WellNest AI** shortcut.
- Clear error messages, loading states, and a logout button.

---

## 5. WellNest AI chat (the big upgrade)

The current chat looks bad. Rebuild the experience **around the existing Talkdesk chat** (rule 4):

1. **Full page `/assistant`:** two-column layout on desktop. Left: the chat. Right: helpful panel with suggested prompts ("Book a skin doctor", "Reschedule my appointment", "Lab report status", "Talk to a person"), hospital hours, emergency note. Single column on mobile.
2. **Big pop-up:** the floating launcher (avatar bubble) opens a large modal/side sheet (~420×680px desktop, full-screen on mobile) with the same chat, an "Open full page" link and a close button.
3. **Branding:** header shows the WellNest AI avatar, name, "Usually replies in seconds" and an online dot.
4. **How to integrate:** first find how the Talkdesk widget is embedded today.
   - Keep the **same widget script and touchpoint ID**. Mount/open it inside your branded container (page and modal) using the widget's supported options or JS API.
   - Restyle what the widget allows (colours, launcher, size, position). Bot name/avatar *inside* the widget are set in the Talkdesk chat touchpoint settings. Write the exact settings the team must change in Talkdesk into `docs/TALKDESK_CHAT_BRANDING.md` instead of guessing in code.
   - Only if the widget officially supports a headless/custom-UI mode should you build a fully custom message UI. Otherwise wrap the widget. **A working Talkdesk chat beats a prettier broken one.**
5. **Human handoff in chat:** when the conversation escalates, the patient keeps chatting in the same window. Show a small banner "You're now connected to WellNest reception" if the widget exposes that event. If it doesn't, skip the banner.

---

## 6. Admin console (`/admin`, admin role only)

Layout: left sidebar + top bar (search, admin name, logout). Every list has search, filters, pagination, and empty/loading states.

| Page | What it shows |
|---|---|
| **Overview** | KPI cards: today's appointments, AI-handled conversations, escalations waiting, reminders sent/confirmed. Small charts (bookings per day, conversations by intent/channel). Live activity feed |
| **Appointments** | Table of all appointments: patient, doctor, dept, date/time, status (booked / confirmed / rescheduled / cancelled / completed), channel (voice / chat / web). Row → detail drawer with full history. Doctor × time schedule grid view (keep the existing dashboard grid idea, restyled) |
| **Conversations** | All past AI conversations (voice + chat) from the existing conversation/memory store: patient, channel, time, intent, outcome, escalated yes/no. Click → transcript view as chat bubbles, with tool calls shown as compact "action" chips (e.g. "Booked WN-10234"). Read-only |
| **Escalations (Human Handoff Console)** | Dedicated interface for patients who asked for a human. Left: live queue of open handoff tickets (`create_handoff` data), sorted by urgency, emergencies pinned in coral. Right: selected ticket with patient profile, reason, AI summary, recent transcript, upcoming appointments, and buttons **"Open in Talkdesk Conversations"** (link to the sandbox Conversations app), **"Mark in progress"** and **"Resolve"** (writes ticket status). Auto-refresh every 3–4 s with a sound/visual cue on new tickets. Note: the human's actual replies happen in Talkdesk Conversations, because that's where Talkdesk routes the chat/call. This console is the context + tracking screen beside it |
| **Reminders & follow-ups** | Outbound reminder/follow-up calls and emails: scheduled, sent, confirmed (press 1), reschedule requested (press 2), no answer. "Send reminder call" button per appointment **only if** a backend trigger for it already exists. Otherwise show the button disabled with "coming soon" |
| **Patients** | Patient list → profile: contact, appointments, conversations, handoffs |
| **Doctors** | Doctors, schedules, leave days (read-only unless edit endpoints exist) |

Admin auth: credentials from env vars (hashed) or an additive `admin_users` table. Server-side session/cookie, and **every admin API route must check the admin role**. Admin pages must never be readable without login.

---

## 7. Database (additive only)

- Add only what the frontend needs: `admin_users`, `hospital_content` (if content goes in DB), `handoffs.status` / `resolved_at` (only if missing, added as new nullable columns).
- Write a new migration file. Don't edit or drop existing tables. Seed hospital content from the attached policy document.
- List every DB change in `docs/FRONTEND_V3_CHANGES.md`.

---

## 8. Quality bar

- Production feel: consistent components, no lorem ipsum, no broken links, favicon + page titles + meta description, 404 page.
- Performance: no heavy frameworks added just for looks. Lazy-load charts. Pages usable within ~2 s on Render.
- Accessibility: keyboard navigation, labels on inputs, alt text, visible focus.
- Security: input validation, no secrets client-side, admin routes protected, CORS unchanged for `/mcp`.

---

## 9. Must-pass checklist before merging to `main`

Run all of these on the deployed branch (or locally against the real backend). Fix anything that fails.

**Backend unchanged**
- [ ] `/health` returns OK (postgres, Redis, search as before).
- [ ] `git diff main -- <MCP tool file(s)>` shows **no** changes to tool names, parameters, docstrings or return shapes.

**Talkdesk still works**
- [ ] Website chat (page + modal): "Book a dermatologist tomorrow" → AI replies, MCP tools run, booking appears in admin Appointments.
- [ ] Chat: "I want to talk to a human" → Conversations app rings for the available agent → ticket shows in the Escalations console.
- [ ] Voice: call +1 218 443 7744 → AI answers → booking works → "talk to a person" reaches the agent.

**Frontend**
- [ ] All public pages load on phone and laptop width; no console errors.
- [ ] Patient login → My appointments → reschedule/cancel works via existing endpoints.
- [ ] Admin login → every admin page loads with real data; logged-out user is redirected from `/admin`.
- [ ] Conversations page shows real past transcripts.

---

## 10. Time-box (demo at 2 PM, build must work by ~1:30 PM)

Build in this order and deploy after each step so something good is always live:
1. **Design system + landing page + header/footer + WellNest AI launcher/modal** (biggest visual impact).
2. **Admin Escalations console + Appointments + Overview.**
3. **Admin Conversations transcript view.**
4. **Info pages from the policy document + login polish.**
5. Reminders page, Patients, Doctors (only if time is left).

If a step risks breaking Talkdesk or the backend, stop and report instead of forcing it.

---

## 11. Deliverables

- Redesigned frontend on branch `frontend-v3`, merged only after section 9 passes.
- `docs/FRONTEND_V3_CHANGES.md`: what changed, new routes/tables, env vars to set on Render.
- `docs/TALKDESK_CHAT_BRANDING.md`: exact Talkdesk chat touchpoint settings to change by hand (bot name "WellNest AI", avatar, colours).
- A short demo script: landing → chat with WellNest AI → booking shows in admin → "talk to a human" → Escalations console + Talkdesk Conversations.

---

## 12. Decisions taken on 4 Nov 2026 (override the brief above where they differ)

Answered by the repo owner before the build started:

| Topic | Decision |
|---|---|
| **Stack** | Keep React 18 + TypeScript + Vite. The built `web/dist` is committed and served by FastAPI; Render runs no npm build, so a stack change would mean re-wiring the deploy hours before the demo. |
| **Theme** | A clinical **hospital** look: white surfaces, medical blue, clean. **Light mode only — no dark theme.** This replaces section 2's deep-teal + dark-mode direction. |
| **Admin auth** | A real **admin ID + password** login with a server-side cookie session (credentials from Render env vars, hashed). Not a token in the URL. |
| **Conflicting facts** | The **live database and knowledge base win**. The attached manual only fills gaps. Doctors, fees, hours and slots always come from the API, never from the document. |
