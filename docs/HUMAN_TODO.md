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
10. [ ] POST `https://teamxyz-mcp.onrender.com/jobs/run?token=<JOBS_TOKEN>` every 1 min (reminders + waitlist offer expiry).

## Talkdesk (V2 changes that affect the existing bot)
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

## Demo logins (website)
- Shanthamma K (67, senior): `shanthamma.demo@example.com` · Arjun Mehta: `arjun.demo@example.com` ·
  Priya Nair: `priya.demo@example.com` · password = `DEMO_PASSWORD`. Phone/DOB for the bot: see `docs/V2_GUIDE.md`.
- Ops dashboard: `https://teamxyz-mcp.onrender.com/dashboard?token=<DASHBOARD_TOKEN>`
