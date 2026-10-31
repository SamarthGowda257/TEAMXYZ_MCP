# TeamXYZ-MCP: City Hospital Appointment Desk

> **Practice / test project** for the Talkdesk AI Hackday (4 Nov 2026). The hospital, doctors and patients are mock data.
> This repo is the **team's main folder**: all code and docs live here, and every update is pushed here.

A remotely deployable **Model Context Protocol (MCP) server** that gives a **Talkdesk AI Agent** real tools to run a
hospital's appointment desk (find slots, book, reschedule, cancel), plus a **live dashboard** to watch every slot and booking.

- **Live server:** `https://teamxyz-mcp.onrender.com` (Render, auto-deploys on every push to `main`)
- **Stack:** Python MCP SDK 2.x (`MCPServer`), Streamable HTTP, Bearer-token auth, SQLite
- **Talkdesk:** connected as MCP server **`TeamXYZ_MCP`**, used by orchestration **`TestBot_TeamXYZ`**

---

## Project structure

```
TEAMXYZ_MCP/
├── server.py               # MCP server: 6 hospital tools + dashboard API + auth
├── dashboard.html          # Live dashboard page (served at /dashboard)
├── OPEN_DASHBOARD.html     # Double-click to open the live dashboard
├── requirements.txt        # mcp 2.x + uvicorn
├── .env.example            # Environment variable template
├── docs/
│   └── TALKDESK_HACKATHON_GUIDE.md   # Beginner guide: Talkdesk, sandbox, building agents
└── README.md
```

Local-only files (never committed, see `.gitignore`): `.env`, `hospital.db`, `*.local.html`.

---

## How it fits together

```
Caller ──► Talkdesk: Receptionist ──(Condition)──► Booking Agent
                                                     │ skills = MCP tools
                                                     │ HTTP POST /mcp  Authorization: Bearer <token>
                                                     ▼
                             BearerTokenMiddleware (401 no token · 403 wrong token)
                                                     ▼
                         TeamXYZ-MCP tools ──► SQLite (hospital.db) ◄── /dashboard (live view)
```

Talkdesk is the **brain and voice** (understands and talks). This server is the **hands and memory**
(checks and saves real data).

---

## Tools

| Tool | What the AI agent uses it for | In Talkdesk bot? |
|------|------|:--:|
| `find_available_slots(date, department?, doctor_name?, time_preference?)` | Free slots. Understands "skin", "heart", "tomorrow", "Monday", "morning" | ✅ Booking Agent |
| `book_appointment(patient_name, phone, date, time, department?/doctor_name?, reason?)` | Books and returns an ID like `CH1234`, or suggests alternatives | ✅ Booking Agent |
| `find_appointments(phone? / booking_id?)` | Look up a caller's appointments | ⏳ to add |
| `reschedule_appointment(booking_id, new_date, new_time)` | Move a booking (same doctor) | ⏳ to add |
| `cancel_appointment(booking_id, phone?)` | Cancel (phone must match if given) | ⏳ to add |
| `get_doctors(department?)` | Doctors, days, hours, fees, languages, hospital info | ⏳ to add (Receptionist / Info Agent) |

**Mock data:** 10 doctors in 8 departments with their own days, hours, slot length, fee, room and languages.
OPD runs Mon–Sat with lunch 1–2 PM, closed Sundays. Some doctors are on leave and past times are blocked (IST).
About 35% of the coming week is pre-booked. The data is created automatically on first start.
> Render's free tier forgets data on every redeploy or restart, and the server sleeps after ~15 min idle
> (the first request then takes 30–60 s).

---

## Live dashboard

**Easiest:** double-click **`OPEN_DASHBOARD.html`** (or `dashboard.html`). Either opens
`https://teamxyz-mcp.onrender.com/dashboard`.

- **First time** it asks for the token (= `MCP_BEARER_TOKEN` set in Render) and **remembers it in that browser**.
- Pick a day and filter by department. Slots are coloured **free / booked / booked by AI** (purple) / **past**.
  Hover a slot for patient details.
- The side panel shows the AI receptionist's activity and stats, refreshing every 4 s.

Optional one-click shortcut with the token built in: create `OPEN_DASHBOARD.local.html` (git-ignored) containing
`<meta http-equiv="refresh" content="0; url=https://teamxyz-mcp.onrender.com/dashboard?token=YOUR_TOKEN">`.

| Path | Auth | Purpose |
|------|------|---------|
| `/mcp` | `Authorization: Bearer <token>` | MCP endpoint for Talkdesk |
| `/dashboard` | token asked on the page | Live slots + bookings |
| `/api/schedule?date=…` · `/api/bookings` | `?token=<token>` | JSON used by the dashboard |
| `/health` | none | Uptime check, also wakes the server |

---

## Talkdesk setup (current state of `TestBot_TeamXYZ`)

```
Receptionist (Supervisor, talks to the caller)
   └─ Condition: "Booking Agent: use when the caller wants to book / check slots / reschedule / cancel…"
        └─ Booking Agent
             ├─ skill: find_available_slots  (MCP · TeamXYZ_MCP)
             └─ skill: book_appointment      (MCP · TeamXYZ_MCP)
```

**Key lesson:** every MCP tool input needs a source, either a fixed **Value** or a **Variable**. To let the AI fill an
input from the conversation, create a **custom variable with a clear description**, and the agent captures it during the chat.

| Variable | Description (what the AI looks for) | Used by |
|---|---|---|
| `appointment_date` | Date the caller wants: today / tomorrow / Monday / YYYY-MM-DD | date |
| `appointment_time` | Time the caller chose, e.g. 10:30 AM | time |
| `department` | Department or plain word (skin, heart…); empty if a doctor was named | department |
| `doctor_name` | Specific doctor if asked (e.g. Mehta) | doctor_name |
| `patient_name` | Caller's name | patient_name |
| `patient_phone` | 10-digit mobile | phone |
| *(fixed value)* `any` | | time_preference |

Verified end-to-end on 31 Oct: the bot checked slots, then booked **CH1234 (Ravi Kumar, Dr. Priya Mehta, Mon 10:50)**,
and the booking appeared on the live dashboard. Use **Test → Insight → Agent Tool used** to see each tool's inputs and result.

### Add a skill (tool already on the server)
1. Agent box → **+ Add Skill** → click the new *Skill Node* → **MCP** tab
2. **Select MCP Server** = `TeamXYZ_MCP` → **Select Tool**. The description fills in from the server.
3. **Inputs**: set each to **Variables** (pick or **+ Add variable** with a clear description) or a fixed **Value**.
   Required (*) inputs must be set.
4. Panel **Save** → top **Save** (not Publish) → **Test** → check Insight
5. Limit: 5 skills per agent

### Add a brand-new tool
1. Add a function in `server.py`:
   ```python
   @mcp.tool()
   def get_lab_report(booking_id: str) -> dict:
       """Get the lab report status for a booking ID like CH1234."""
       return {"booking_id": booking_id, "status": "ready"}
   ```
   The docstring is what the AI reads, so make it clear.
2. Commit and push to `main`. Render redeploys in ~2 min.
3. Add it as a skill in Talkdesk (steps above).

### Add an agent
1. **+ Add Agent** next to the *Condition* node (sibling) → fill Name / Description / Instructions → Save
2. Add a line for it in the **Condition** routing rules
3. Give it skills → top **Save** → **Test** (Agent work stream should show the route)

Rules: only the Supervisor talks to the caller · max 3 levels, 10 agents per level, 5 skills per agent ·
avoid the red 🗑 that appears when hovering over a box (it deletes the box).

### Next to do
- [ ] Booking Agent instructions: always read back **booking ID, doctor, room and fee**
- [ ] Add `find_appointments`, `reschedule_appointment`, `cancel_appointment` (+ variable `booking_id`)
- [ ] Info Agent with `get_doctors`
- [ ] Before the demo: Publish → AI Launchpad (Agentic Autopilot) → Studio flow → phone number (from organisers)

---

## Local development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export MCP_BEARER_TOKEN=your-secret     # Windows cmd: set MCP_BEARER_TOKEN=your-secret
python server.py
```
MCP: `http://localhost:8000/mcp` · Dashboard: `http://localhost:8000/dashboard`

Test with MCP Inspector: `npx @modelcontextprotocol/inspector` → Streamable HTTP, `http://localhost:8000/mcp`,
header `Authorization: Bearer <token>`.

## Deploying (Render)

| Setting | Value |
|---------|-------|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Env var `MCP_BEARER_TOKEN` | secret token (never commit it) |
| Env var `PORT` | leave blank (Render sets it) |

Every push to `main` redeploys automatically.

## Team workflow

```bash
git pull                     # get the latest first
# ...edit...
git add -A
git commit -m "Describe the change"
git push                     # Render redeploys
```

## Security
- Bearer token required on `/mcp` (constant-time compare); the server refuses to start without `MCP_BEARER_TOKEN`
- The dashboard and API need the token; phone numbers are masked in the activity feed
- **Never commit the real token**: `.env`, `*.local.html` and `hospital.db` are git-ignored
