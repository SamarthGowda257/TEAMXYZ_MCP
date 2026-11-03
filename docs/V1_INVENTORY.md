# V1 Inventory (what is live on `main` today)

Snapshot of commit `fe2205e` (= `main`, the code Render runs and Talkdesk calls), written in Phase 0 before any change.
Facts below were checked by reading the code **and** by running it locally and listing the tools over the real MCP transport.

## 1. Files
| File | Role |
|---|---|
| `server.py` (535 lines) | Everything: config, doctor data, SQLite store + seed, 6 MCP tools, dashboard JSON API, auth middleware, entry point |
| `dashboard.html` | Live slot/booking board, served at `/` and `/dashboard` |
| `OPEN_DASHBOARD.html` | Local shortcut that redirects to `https://teamxyz-mcp.onrender.com/dashboard` |
| `requirements.txt` | `mcp[cli]==2.3.0`, `uvicorn>=0.29.0` (nothing else) |
| `.env.example` | `MCP_BEARER_TOKEN`, `PORT` |
| `.gitignore` | ignores `.env`, `hospital.db`, `*.local.html`, venvs, caches |
| `README.md` | Setup, Talkdesk notes, Render settings |
| `.claude/skills/` | 12 skills (mcp-builder, python-patterns, python-testing, verification-loop, ecc-security-review, api-design, error-handling, frontend-design, design-taste-frontend, webapp-testing, backend-patterns, pptx) |

No `render.yaml`, `Procfile`, `runtime.txt` or `.python-version`. No tests.

## 2. MCP library, transport, endpoint, auth
| Item | Value (exact) |
|---|---|
| Library | Official Python MCP SDK **`mcp` 2.3.0** (PyPI; latest release, checked). Class `mcp.server.mcpserver.MCPServer` (the 2.x successor of 1.x `FastMCP`). Requires Python ≥ 3.10. |
| Server construction | `MCPServer(name="TeamXYZ-MCP", instructions="Appointment desk for City Hospital, Bengaluru: …")` |
| Tool registration | `@mcp.tool()` on plain **sync** `def` functions returning `dict`. Docstring = tool description; Python signature = input schema. |
| Transport | Streamable HTTP: `mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True, host="0.0.0.0")` → a Starlette app. **Stateless** (no session ID needed), **JSON responses** (no SSE stream). |
| Endpoint path | **`/mcp`** (live URL `https://teamxyz-mcp.onrender.com/mcp`) |
| Protocol version negotiated | `2025-11-25` (local test with the 2.3.0 client) |
| Results on the wire | Tool `dict` is returned as **text content holding JSON** (no `structuredContent`). |
| Auth | Pure ASGI `BearerTokenMiddleware` wrapping the whole app, applies to paths starting with `/mcp`. Header **`Authorization: Bearer <token>`**. Missing/malformed header → **401** `{"error":"unauthorized"}` + `WWW-Authenticate: Bearer`. Wrong token → **403** `{"error":"forbidden"}`. Compare is `hmac.compare_digest`. |
| Env var | **`MCP_BEARER_TOKEN`** (fallback **`MCP_TOKEN`**). Process exits at import time if neither is set. `PORT` (default 8000). `DB_PATH` (default `./hospital.db`, undocumented). |
| ASGI entry | `app = BearerTokenMiddleware(mcp_app)`; `python server.py` runs `uvicorn.run(app, host="0.0.0.0", port=PORT)`. One process, one worker. |
| Local versions resolved | uvicorn 0.54.0, starlette 1.10.0, pydantic 2.14.2 (uvicorn is unpinned, `>=0.29.0`). |

Other routes are appended to the MCP Starlette router:
| Path | Auth | Returns |
|---|---|---|
| `GET /health` | none | `{"ok":true,"hospital":"City Hospital, Bengaluru","time_ist":…}` (no DB check) |
| `GET /`, `GET /dashboard` | none for the HTML | `dashboard.html` |
| `GET /api/schedule?date=…&token=…` | `?token=` = same MCP token | every doctor's slot grid for a day, with full booking rows |
| `GET /api/bookings?token=…` | `?token=` = same MCP token | last 50 `source='ai_agent'` rows + stats |

## 3. The 6 tools: exact signatures (as Talkdesk sees them)
Input schemas captured from `list_tools` on a running copy. All inputs are `string`.

| Tool | Required | Optional (default) |
|---|---|---|
| `get_doctors` | – | `department=""` |
| `find_available_slots` | `date` | `department=""`, `doctor_name=""`, `time_preference="any"` |
| `book_appointment` | `patient_name`, `phone`, `date`, `time` | `department=""`, `doctor_name=""`, `reason=""` |
| `find_appointments` | – | `phone=""`, `booking_id=""` |
| `reschedule_appointment` | `booking_id`, `new_date`, `new_time` | – |
| `cancel_appointment` | `booking_id` | `phone=""` |

```python
def get_doctors(department: str = "") -> dict
def find_available_slots(date: str, department: str = "", doctor_name: str = "", time_preference: str = "any") -> dict
def book_appointment(patient_name: str, phone: str, date: str, time: str, department: str = "", doctor_name: str = "", reason: str = "") -> dict
def find_appointments(phone: str = "", booking_id: str = "") -> dict
def reschedule_appointment(booking_id: str, new_date: str, new_time: str) -> dict
def cancel_appointment(booking_id: str, phone: str = "") -> dict
```

### Behaviour and output shapes (no shared envelope today)
| Tool | Success shape | Failure shape | Notes |
|---|---|---|---|
| `get_doctors` | `{hospital{name,address,opd_hours,emergency}, departments[8], doctors[{name,department,days,hours,fee_inr,languages}]}` | none (unknown dept → all doctors) | **Always** includes the hospital block and all departments (the V1 latency finding). No room. |
| `find_available_slots` | `{date:"Wednesday, 04 November 2026", date_iso, department, availability[{doctor,fee_inr,room,free_slots[≤6],total_free}], notes?, suggestion?}` | `{error, departments?/doctors?}` | Up to **6** slots per doctor, all doctors in dept. No days/hours/languages, no separate `weekday` field (weekday only inside `date` text). |
| `book_appointment` | `{message, status:"booked", booking_id:"CH1234", patient_name, doctor, department, date, time, room, fee_inr, instructions}` | `{status:"failed", reason, alternatives_same_day?, notes?, departments?}` | With department only, picks the first doctor free at that time. `instructions` claims "An SMS confirmation has been sent" (it is not). |
| `find_appointments` | `{appointments[{booking_id,patient_name,doctor,department,date,time,status}]}` or `{appointments:[], message}` | `{error}` | By `booking_id`: returns that booking (any date, any status) with **no identity check**. By phone: all upcoming, unlimited. |
| `reschedule_appointment` | `{message, status:"rescheduled", booking_id, doctor, date, time, room, fee_inr}` | `{status:"failed", reason, free_slots?, note?}` | Same doctor only. **No identity check at all.** Updates the row in place (old slot freed implicitly). |
| `cancel_appointment` | `{message, status:"cancelled", booking_id, doctor, date, time}`; already cancelled → `status:"already_cancelled"` | `{status:"failed", reason}` | Phone checked **only if supplied**: anyone with a booking ID can cancel (V1 eval scenario 7). |

Input parsing helpers (reusable ideas for V2 `normalize.py`):
- `parse_date`: today/now, tomorrow (+typos), "day after tomorrow", weekday names incl. "next/this" (next occurrence, never today), `%Y-%m-%d`, `%d-%m-%Y`, `%d/%m/%Y`, `4 Nov [2026]`, `4 November`.
- `parse_time`: `10:30`, `10.30`, `10:30AM`, `10AM`, `10` → `HH:MM`.
- `clean_phone`: strips non-digits, drops `91`/`0` prefix → **10-digit** string starting 6–9 (not E.164).
- `norm_dept`: alias table (skin, heart, bone, child, ear, women…) with substring fallback.
- `find_doctor`: matches id, full name, a single name token **or any substring** (`"a"` matches the first doctor; `"Mehta"` → Dr. Priya Mehta).

### `get_weekday_for_date_internal`
**Not ours.** It does not exist in `server.py` or anywhere in the git history (searched all commits). It is a Talkdesk-provided internal/system skill. Nothing to keep on our side; V2 just returns `date_iso` + `weekday` so agents need it less.

## 4. Data model
**Reference data is hard-coded in Python** (`DOCTORS`, `HOSPITAL`, `ALIASES`). **Bookings are in SQLite** (`hospital.db`), not in memory as the docs say.

Doctors (10, 8 departments; `days` 0=Mon…5=Sat; lunch 13:00–14:00 removed from every grid; Sunday closed):
| ID | Name | Dept | Days | Hours | Slot | Fee | Room | Languages |
|---|---|---|---|---|---|---|---|---|
| D01 | Dr. Anil Kumar | General Medicine | Mon–Sat | 09:00–17:00 | 15 | 500 | OPD-101 | En, Kn, Hi |
| D02 | Dr. Sneha Rao | General Medicine | Mon, Wed, Fri | 10:00–16:00 | 15 | 500 | OPD-102 | En, Kn, Te |
| D03 | Dr. Priya Mehta | Dermatology | Mon, Tue, Thu, Sat | 09:30–13:00 | 20 | 800 | OPD-205 | En, Hi |
| D04 | Dr. Farhan Ali | Dermatology | Tue, Wed, Fri | 14:00–17:00 | 20 | 800 | OPD-206 | En, Hi, Ur |
| D05 | Dr. Rajesh Iyer | Cardiology | Mon, Wed, Fri | 10:00–13:00 | **30** | 1200 | OPD-310 | En, Ta |
| D06 | Dr. Kavya Reddy | Cardiology | Tue, Thu, Sat | 14:00–17:00 | **30** | 1200 | OPD-311 | En, Te, Kn |
| D07 | Dr. Kiran Shetty | Orthopaedics | Mon–Fri | 09:00–13:00 | 20 | 1000 | OPD-402 | En, Kn, Tulu |
| D08 | Dr. Lakshmi Nair | Paediatrics | Mon–Sat | 09:00–13:00 | 15 | 700 | OPD-120 | En, Ml, Kn |
| D09 | Dr. Arjun Desai | ENT | Tue, Thu, Sat | 10:00–16:00 | 20 | 700 | OPD-215 | En, Hi, Mr |
| D10 | Dr. Meera Joshi | Gynaecology | Mon, Wed, Fri, Sat | 09:30–15:30 | 20 | 900 | OPD-130 | En, Hi, Kn |

Leave (relative to today): D01 on today+3, D05 on today+2. Same-day slots need ≥30 min lead time.

SQLite table (one table, created on startup):
```sql
CREATE TABLE IF NOT EXISTS bookings (
  id TEXT PRIMARY KEY,          -- 'CH' || (1001 + COUNT(*))
  patient_name TEXT, phone TEXT,-- phone = 10 digits, no country code
  doctor_id TEXT, doctor TEXT, department TEXT,
  date TEXT, time TEXT,         -- 'YYYY-MM-DD', 'HH:MM'
  reason TEXT, status TEXT,     -- 'booked' | 'cancelled'
  source TEXT,                  -- 'existing' (seed) | 'ai_agent'
  created_at TEXT, updated_at TEXT)
```
- Seed: if the table is empty, ~35% of every slot for today..today+7 is booked with random names/phones (`random.Random(42)`). No patients table, no DOB, no email.
- Double-booking guard: a process-wide `threading.Lock` around read-then-insert. No DB constraint.
- **On Render the file is ephemeral**: every deploy, restart or free-tier sleep wipes it and re-seeds. Booking IDs like `CH1234` from earlier tests do not survive.

## 5. Dashboard
- `dashboard.html` is a single static page (no build). The token comes from `?token=` or `localStorage["td_dash_token"]`, and the page asks for it if missing. It is the **same value as `MCP_BEARER_TOKEN`**.
- It polls `/api/schedule?date=…` and `/api/bookings` every **4 s**. It shows a slot grid per doctor (free / booked / booked-by-AI / past) and an AI activity feed.
- Phones are masked **only in the browser** (`****1234`). The JSON API returns full phone numbers and names.

## 6. Deploy (Render)
From the README (no config file in the repo; I can't see the Render dashboard to confirm):
| Setting | Value |
|---|---|
| Service URL | `https://teamxyz-mcp.onrender.com` |
| Branch | `main`, auto-deploy on push |
| Build | `pip install -r requirements.txt` |
| Start | `python server.py` |
| Env | `MCP_BEARER_TOKEN` (secret); `PORT` set by Render |
| Health check path | not documented (`/health` exists) |
| Python version | not pinned. Render picks its default; **unverified which**. |
| Plan | free tier (sleeps after ~15 min idle; cold start 30–60 s) |

Talkdesk side (from README + docs): MCP server registered as **`TeamXYZ_MCP`**; bot `TestBot_TeamXYZ`; README says only `find_available_slots` and `book_appointment` were mapped as skills on 31 Oct; docs say the V1 evaluation also used cancel and `get_doctors`.

## 7. Rollback
- `main` = `fe2205e` at the time of writing. Rollback ref pushed as branch **`v1-baseline-branch`** (same commit).
- Tag `v1-baseline` was created locally but **the push was refused by this container's git proxy** (branch pushes work, tag pushes are cut off). See `HUMAN_TODO.md` item 1.
