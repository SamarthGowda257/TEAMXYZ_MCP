# TeamXYZ-MCP: City Hospital Appointment Desk

A remotely deployable **Model Context Protocol (MCP) server** for the Talkdesk AI Hackday.
It gives a **Talkdesk AI Agent** real tools to run a hospital's appointment desk
(find slots, book, reschedule, cancel), plus a **live dashboard** to watch every slot and booking.

Built with the official Python MCP SDK (2.x, `MCPServer`), Streamable HTTP transport and Bearer-token auth.
It is compatible with the **Talkdesk AI Agent Platform → MCP Servers → Custom MCP Server** integration.

---

## How it fits together

```
Caller ──► Talkdesk AI Agent (Receptionist → Booking Agent)
                  │  HTTP POST /mcp   Authorization: Bearer <MCP_BEARER_TOKEN>
                  ▼
           BearerTokenMiddleware  (401 no token · 403 wrong token)
                  ▼
           TeamXYZ-MCP tools ──► SQLite (hospital.db)  ◄── /dashboard (live view)
```

## Tools

| Tool | What the AI agent uses it for |
|------|------|
| `get_doctors(department?)` | Departments, doctors, consultation days/hours, fees, languages, hospital info |
| `find_available_slots(date, department?, doctor_name?, time_preference?)` | Free slots. Understands "skin", "heart", "tomorrow", "Monday", "morning" |
| `book_appointment(patient_name, phone, date, time, department?/doctor_name?, reason?)` | Books and returns an ID like `CH1234`, or suggests alternatives if the slot is taken |
| `find_appointments(phone? / booking_id?)` | Look up a caller's upcoming appointments |
| `reschedule_appointment(booking_id, new_date, new_time)` | Move a booking (same doctor) |
| `cancel_appointment(booking_id, phone?)` | Cancel. If a phone is given it must match the booking |

**Talkdesk allows 5 skills per agent**: put the last five on the *Booking Agent* and `get_doctors` on the *Receptionist*.

## Mock hospital data (realistic on purpose)
- 10 doctors across 8 departments, each with their own days, hours, slot length (15/20/30 min), fee, room and languages
- OPD Mon–Sat, lunch 1–2 PM, Sundays closed, some doctors on leave, past times blocked (IST)
- About 35% of the coming week is pre-booked by "existing patients", so the calendar looks busy
- Patients are identified by name + 10-digit Indian mobile

The database (`hospital.db`) is created and seeded automatically on first start.
> On Render's free tier the disk is temporary: data resets on every redeploy or restart. That's fine for demos.

## Live dashboard
`https://<your-service>.onrender.com/dashboard?token=<MCP_BEARER_TOKEN>`

- Pick a day and filter by department
- Slots are coloured: free / booked / **booked by AI** (purple, flashes when new) / past
- Hover a slot to see who booked it and why
- Side panel shows the AI receptionist's activity and stats; refreshes every 4 s

## Endpoints

| Path | Auth | Purpose |
|------|------|---------|
| `/mcp` | `Authorization: Bearer <token>` | MCP endpoint for Talkdesk |
| `/dashboard` | `?token=<token>` | Live slots + bookings page |
| `/api/schedule?date=…` · `/api/bookings` | `?token=<token>` | JSON used by the dashboard |
| `/health` | none | Uptime check |

---

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export MCP_BEARER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
#   Windows (cmd):  set MCP_BEARER_TOKEN=your-secret
python server.py
```
- MCP: `http://localhost:8000/mcp`
- Dashboard: `http://localhost:8000/dashboard?token=<your-token>`

Test with MCP Inspector: `npx @modelcontextprotocol/inspector` → Transport *Streamable HTTP*, URL `http://localhost:8000/mcp`, header `Authorization: Bearer <token>`.

## Deploying to Render

| Setting | Value |
|---------|-------|
| Environment | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Env var `MCP_BEARER_TOKEN` | your secret token |
| Env var `PORT` | leave blank (Render sets it) |

Endpoint: `https://<your-render-service-name>.onrender.com/mcp`

> Render free services sleep after ~15 min idle, and the first request then takes ~30–60 s.
> Open `/health` a minute before a demo to wake it up.

## Connecting to Talkdesk AI Agent Platform

1. **AI Agent Platform → MCP Servers → + New MCP Server → Custom**
2. URL `https://<your-render-service-name>.onrender.com/mcp` · Auth **Bearer token** = `MCP_BEARER_TOKEN`
3. **Test connection**
4. In the orchestration: agent → **+ Add Skill → MCP** → pick the server → pick one tool (1 skill = 1 tool) → Save
5. Top **Save** → **Test** → check **Insight → Agent work stream** to see the tool call, and watch it appear on `/dashboard`

## Security
- Bearer token required on `/mcp` (constant-time comparison); the server refuses to start without `MCP_BEARER_TOKEN`
- Dashboard and API require `?token=`; phone numbers are masked in the activity feed
- Never commit `.env` or real tokens. `hospital.db` is git-ignored.
