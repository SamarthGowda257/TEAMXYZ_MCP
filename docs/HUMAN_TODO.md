# Things a human must do (Claude Code can't click these)

Numbered so we can refer to them ("done with 3"). Tick the box when done.

## Git
1. [ ] **Push the safety tag** (the cloud container's git proxy blocks tag pushes). From a laptop:
   ```bash
   git fetch origin && git tag v1-baseline fe2205e0ed95e66d0ba88aadf1640e990485cf76 && git push origin v1-baseline
   ```
   Until then, branch `v1-baseline-branch` is the rollback point (same commit). To roll back Render: point the service at
   that branch, or `git revert` the merge on `main`.

## Supabase (the database)
2. [ ] Create project **wellnest**, region **Southeast Asia (Singapore)**. Save the database password in a password manager.
3. [ ] Click **Connect** → **Transaction pooler** (port 6543) → copy the URI, put your password in place of `[YOUR-PASSWORD]`
   (URL-encode `@ # / : ? %` in the password, or choose one without them). Do NOT use "Direct connection" (IPv6 only).
4. [ ] Nothing else in Supabase: no SQL to run, no API keys needed. The app creates the tables and loads demo data on first start.

## Render (where the key lives)
5. [ ] Service `teamxyz-mcp` → **Environment** → add these, then **Save** (Render restarts):
   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase pooler URI from step 3 (secret) |
   | `SECRET_KEY` | any long random string (signs website logins) |
   | `DASHBOARD_TOKEN` | a new random string for the ops dashboard (so you can share it without the Talkdesk token) |
   | `JOBS_TOKEN` | a new random string for the cron job |
   | `PUBLIC_BASE_URL` | `https://teamxyz-mcp.onrender.com` |
   | `DEMO_PASSWORD` | password for the demo patients' website logins (default `WellNest@2026`) |
   | optional `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `EMAIL_FROM` | real email (Gmail + App Password works). Without them emails show as "simulated". |
   | optional `DEMO_EMAIL_OVERRIDE` | one inbox that receives every real email during the demo |
   | optional `DEMO_PERSONA_EMAILS` | `{"shanthamma":"you@gmail.com","arjun":"teammate@gmail.com"}` so persona emails reach real inboxes |
   | `TALKDESK_TOUCHPOINT_ID`, `TALKDESK_REGION` | once the chat touchpoint exists (step 12) |
   Keep `MCP_BEARER_TOKEN` exactly as it is.
6. [ ] Settings → **Health Check Path** = `/health`.
7. [ ] **Check it worked**: open `https://teamxyz-mcp.onrender.com/health`. Expect `"db": true, "db_kind": "postgres"`.
   `sqlite` = `DATABASE_URL` missing; `"db": false` = wrong URL or password.
8. [ ] Demo morning: reset the data so dates are relative to that day:
   `curl -X POST "https://teamxyz-mcp.onrender.com/ops/reset-demo?token=<JOBS_TOKEN>"`

## Uptime / cron (cron-job.org or UptimeRobot, free)
9. [ ] GET `https://teamxyz-mcp.onrender.com/health` every 5 min (stops Render sleeping).
10. [x] POST `https://teamxyz-mcp.onrender.com/jobs/run?token=<JOBS_TOKEN>` every 1 min (reminders, waitlist offer expiry, visit close-out, aftercare check-ins). Done: returns `{"ok":true,...}`.

## Talkdesk (V2 changes that affect the existing bot)
> Full copy-paste build sheet: **docs/TALKDESK_SETUP.md** (agents, instructions, conditions, skill mappings, variables, test script).
11. [ ] AI Agent Platform → MCP Servers → `TeamXYZ_MCP` → refresh / Test connection, so the 34 tools appear. URL and token are unchanged.
12. [ ] **Changed behaviour, update the bot:**
   - `cancel_appointment` and `reschedule_appointment` now **require date of birth** (server-side identity check). Create a
     variable `date_of_birth` ("Patient's date of birth, e.g. 1958-03-04") and map it to the new `date_of_birth` input of
     both skills, plus `phone` → `patient_phone` on reschedule. Without it the tool asks the patient for it (no error).
   - Booking IDs are now like **WN-48213** (old CH IDs are gone). Update the `booking_id` variable description to
     "Booking ID like WN-48213".
   - `find_appointments` with phone only now returns a count and asks for date of birth (privacy). Map `date_of_birth` there too.
13. [ ] Add the new agents and skills from `docs/05_AGENTS_AND_TOOLS.md` (max 5 skills per agent). Highest value first:
   Support agent with `create_handoff` (emergency), `verify_patient` on Booking/Changes, `join_waitlist`, `accept_waitlist_offer`,
   Records agent (`get_lab_report_status`, `email_lab_report`), Billing agent (`get_insurance_info`, `check_coverage`).
14. [ ] Create the chat touchpoint (Digital Engagement) → give `TALKDESK_TOUCHPOINT_ID` + region to Render (step 5).

## Hybrid search: the meaning leg (about 10 minutes, free)
Keyword and typo search already work on the live server with nothing to set up. These steps switch on search by meaning.
15. [ ] **Get a Gemini API key**: open https://aistudio.google.com/app/apikey, sign in with a Google account, click
    **Create API key** (if asked for a project, let it create one). Copy the key (starts with `AIza`). Do not paste it in
    chat or screenshots. No billing or card needed: leave the project on the free tier.
16. [ ] **Render** → `teamxyz-mcp` → **Environment** → add `EMBEDDINGS_API_KEY` = the key → **Save** (Render redeploys).
17. [ ] **GitHub** → repository **Settings** → **Secrets and variables** → **Actions** → **New repository secret** →
    name `EMBEDDINGS_API_KEY`. Use a key from a **separate Google project** (AI Studio → Create API key → *Create API
    key in new project*): free quotas are per project, so test runs never eat the live server's daily quota. This lets the "Search eval (real embeddings)" workflow measure
    quality with the real model (Claude can start it and read the results; the key never leaves GitHub).
18. [ ] **Check it worked** (2–5 minutes after the deploy): `https://teamxyz-mcp.onrender.com/health` shows
    `"search":"hybrid"`. Detail: `/api/ops/system?token=<DASHBOARD_TOKEN>` → `search.kb_embedded` reaches `kb_total` (95);
    patients' notes are embedded when that patient is verified. `embeddings.last_quota` names any Google limit hit.
    Try it: `/api/ops/search?token=<DASHBOARD_TOKEN>&q=where can I grab a bite to eat` should return `kb:faq:food`.
19. [ ] Supabase: nothing to click. The server enables the `vector` and `pg_trgm` extensions itself (schema `extensions`).
    Only if `/api/ops/system` shows a `setup_error` about an extension: Supabase → **Database** → **Extensions** →
    enable **vector** and **pg_trgm** → Render → **Manual Deploy** → **Restart service**.

## Demo logins (website)
- Shanthamma K (67, senior): `shanthamma.demo@example.com` · Arjun Mehta: `arjun.demo@example.com` ·
  Priya Nair: `priya.demo@example.com` · password = `DEMO_PASSWORD`. Phone/DOB for the bot: see `docs/V2_GUIDE.md`.
- Ops dashboard: `https://teamxyz-mcp.onrender.com/dashboard?token=<DASHBOARD_TOKEN>`
