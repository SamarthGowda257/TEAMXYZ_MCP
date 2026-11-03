---
title: "WellNest Hospitals — Complete Technical Documentation"
subtitle: "AI front desk on Talkdesk · MCP server · website · data platform (TeamXYZ, Talkdesk AI Hackday)"
date: "3 November 2026"
---

# 1. Summary

**WellNest** is an AI front desk for a fictional multi-speciality hospital, *WellNest Hospitals, Bengaluru*. Patients talk
to it by **website chat** or **phone**; both run on **Talkdesk's AI Agent Platform**. Talkdesk's agents understand the
patient and decide what to do; our **MCP server** does the actual work (bookings, waitlist, reports, insurance, memory)
safely against a real database, and a **website + patient portal + staff dashboard** sits on the same backend.

| Item | Value |
|---|---|
| Live server | `https://teamxyz-mcp.onrender.com` (Render, deploys automatically from `main`) |
| MCP endpoint (Talkdesk connects here) | `https://teamxyz-mcp.onrender.com/mcp` (Streamable HTTP, bearer token) |
| Repository | `SamarthGowda257/TEAMXYZ_MCP` (branches `main` = live, `v2` = development) |
| Talkdesk resources | Orchestration `WellNest_TeamXYZ`, MCP connection `TeamXYZ_MCP`, bot `TestBot_TeamXYZ` |
| Size | 34 MCP tools · 27 database tables · 20 website pages · ~6,100 lines of Python · React/TypeScript frontend |
| Quality gates | 44 unit tests · 34 end-to-end MCP checks · 26-question search evaluation · load test · CI on every push |
| Cost | ₹0: every service runs on a free tier |

**Status at a glance**

| Area | Status |
|---|---|
| MCP server (34 tools), database, cache, events, jobs, search, website, dashboard | **Built, tested, live** |
| Talkdesk V1 agents (Receptionist, Booking, Info) | **Live** (connected to this server) |
| Talkdesk V2 agents (8 specialists + new routing) | **Designed; build sheet ready** (`docs/TALKDESK_SETUP.md`); to be clicked together in Talkdesk |
| Real email | Built; switches on when Gmail SMTP settings are added to Render |
| SMS, WhatsApp, reminder calls | Built as a **simulated outbox** (recorded and shown, not sent) |
| Website chat widget / "Call to book" | Built; switch on when the Talkdesk touchpoint ID and voice number are added to Render |

---

# 2. Architecture

## 2.1 The picture

```
  PATIENTS                    TALKDESK (AI Agent Platform)                 WELLNEST BACKEND (Render, Python)
 ┌─────────────┐   chat   ┌──────────────────────────────────────┐      ┌──────────────────────────────────────┐
 │ Website chat├─────────►│ Receptionist (supervisor)            │ MCP  │  /mcp  MCP gateway (34 tools)        │
 │ Phone call  ├─────────►│  └─ routes to ONE specialist:        ├─────►│        bearer auth, rate limit,      │
 └─────────────┘   voice  │     Booking · Changes · Support ·    │ HTTPS│        envelope {ok,message,data}    │
 ┌─────────────┐          │     Records · Billing & Insurance ·  │      │                 │                    │
 │ Website /   │  HTTPS   │     Info · Care Assist · Aftercare   │      │  Services (one set of business rules)│
 │ portal      ├──────────┼──────────────────────────────────────┼─────►│  /api  website + portal + dashboard  │
 └─────────────┘          │ Human handoff → Talkdesk Conversations│      │  /jobs cron: reminders, offers, ...  │
                          └──────────────────────────────────────┘      └───────┬──────────┬──────────┬────────┘
                                                                                 │          │          │
                                        ┌────────────────────────────────────────┘          │          │
                                        ▼                                                   ▼          ▼
                          ┌──────────────────────────────┐   ┌─────────────────────────┐  ┌──────────────────┐
                          │ Supabase Postgres             │   │ Redis (Render Key Value)│  │ Google Gemini    │
                          │ source of truth, 27 tables    │   │ blackboard (P0–P3)      │  │ embeddings API   │
                          │ + pgvector + pg_trgm (search) │   │ event stream + workers  │  │ (meaning search) │
                          │ Row Level Security on         │   │ query-embedding cache   │  └──────────────────┘
                          └──────────────────────────────┘   └─────────────────────────┘
                                                                         Gmail SMTP (email outbox, optional)
```

## 2.2 Design principles

1. **Talkdesk thinks, our server does.** Talkdesk agents handle language, routing and conversation. Every rule that
   matters (identity, double booking, waitlist order, emergency wording) is enforced on our server, so a confused
   agent cannot break it.
2. **One set of rules for every channel.** The bot (MCP tools), the website (`/api`), and the background jobs call the
   same service functions in `app/services/`. A booking made by voice appears in the portal instantly and vice versa.
3. **Ready-to-speak replies.** Every tool returns `{ok, message, data, related, error_code}`. `message` is a sentence
   the agent can read out as-is (short enough for voice). Tools never raise errors at Talkdesk and stay under 2 KB.
4. **Fewer agent hops = faster.** Talkdesk runs agents one after another (about 1–2 s per hop), so tools answer
   combined questions in one call (slots come with each doctor's days, fee and room) and context travels inside
   replies instead of extra calls.
5. **Degrade, never die.** Postgres down → SQLite fallback. Redis down → in-process memory. Google refuses → keyword
   and typo search. SMTP missing → simulated email. `/health` always says which mode is active.
6. **Zero cost.** Free tiers only; every limit (Render sleep, Gemini quota) has a designed workaround.

## 2.3 Life of one request ("Cancel my booking WN-48213")

1. Patient types or says it. Talkdesk's **Receptionist** classifies the intent and routes to the **Changes Agent**.
2. The Changes Agent fills the tool inputs from conversation variables and calls `cancel_appointment` over MCP:
   `POST https://teamxyz-mcp.onrender.com/mcp` with `Authorization: Bearer <token>`.
3. `BearerTokenMiddleware` checks the token in constant time (401 missing, 403 wrong, IP blocked after 20 bad tokens
   in 10 minutes).
4. The tool wrapper times the call, validates inputs and calls `appointments.cancel()`.
5. The service verifies phone + date of birth against the database (5 wrong tries lock the number for 15 minutes),
   checks the booking belongs to that patient, cancels it in a transaction, records an action in `resolutions`,
   queues a cancellation email + SMS in the outbox, and **offers the freed slot to the next waitlisted patient**
   (creates an offer with a 30-minute hold, emails/SMSes them a link).
6. It publishes events (`appointment.cancelled`, `waitlist.offered`) to the Redis stream. Workers update the
   blackboard (patient snapshots), counters and the dashboard feed.
7. The tool returns e.g. `{"ok": true, "message": "Cancelled booking WN-48213.", "data": {...,"offered_to_waitlist": true}}`.
8. The agent reads the message to the patient. Total server time is typically 10–30 ms.

---

# 3. Services used (and exactly how)

| Service | Role | How we use it | Plan / cost | Configured by |
|---|---|---|---|---|
| **Talkdesk AI Agent Platform** | Conversation, routing, chat + voice channels, human handoff | Receptionist + specialist agents call our MCP tools ("skills"); variables carry phone, DOB, dates; Insight shows each tool call | Hackday sandbox | Talkdesk UI (build sheet `docs/TALKDESK_SETUP.md`) |
| **Talkdesk Digital Engagement (Chat Widget V2)** | Website chat | `frontend/src/lib/chat.ts` loads the widget with `TALKDESK_TOUCHPOINT_ID` + `TALKDESK_REGION` from `/config.js` | Sandbox | Render env vars |
| **Talkdesk voice (Studio flow number)** | Phone channel | Website shows "Call to book" with `TALKDESK_VOICE_NUMBER` | Sandbox | Render env var |
| **Render (web service)** | Hosts the Python server and the built website | `pip install -r requirements.txt` → `python server.py`; Python 3.13; health check `/health`; auto-deploy on push to `main` | Free | Render dashboard, env group `CareLine_TeamXYZ` |
| **Render Key Value (Redis 7)** | Blackboard cache, event stream, query-embedding cache, counters | `REDIS_URL`; Redis Streams consumer group `workers` | Free | Render |
| **Supabase (Postgres 16)** | Source of truth; pgvector + pg_trgm for search | `DATABASE_URL` (transaction pooler, port 6543, psycopg 3 with `prepare_threshold=None`); server creates tables, extensions, RLS itself | Free | Supabase (nothing to click) |
| **Google AI Studio / Gemini API** | Text embeddings for meaning search | Model `gemini-embedding-001`, 768 dimensions, `batchEmbedContents`; key `EMBEDDINGS_API_KEY` on Render only | Free tier (~100 texts/min) | AI Studio + Render |
| **Gmail SMTP** (optional) | Real email delivery | Background sender thread reads the outbox; `SMTP_*`, `EMAIL_FROM`, `DEMO_EMAIL_OVERRIDE` | Free | Render env vars |
| **cron-job.org** | Calls `/jobs/run` every minute; pings `/health` so Render doesn't sleep | `POST /jobs/run?token=<JOBS_TOKEN>` | Free | cron-job.org (done) |
| **GitHub Actions** | CI on every push | Postgres+pgvector and Redis service containers, unit tests, server start, search evaluation, 34 MCP checks, website build | Free | `.github/workflows/ci.yml` |
| **Unsplash / Fontsource** | Website photos and fonts | Photos by URL with fallbacks; DM Serif Display + Manrope bundled | Free | — |

**Libraries (server):** `mcp==2.3.0` (official MCP Python SDK, `MCPServer`, Streamable HTTP), FastAPI, Uvicorn,
SQLAlchemy 2.1 (Core), psycopg 3, redis-py, httpx. **Frontend:** React 18, Vite 5, TypeScript, react-router,
Lenis (smooth scroll), lucide icons.

---

# 4. Backend components (code map)

| File | What it does |
|---|---|
| `server.py` | Entry point: requires `MCP_BEARER_TOKEN`, builds the app, runs Uvicorn (1 worker) on `PORT` |
| `app/main.py` | Startup (`init_data`: schema, seed, brand migration, reference cache, search index, email sender, event workers), `BearerTokenMiddleware`, mounts `/mcp` + FastAPI |
| `app/mcp_tools.py` | The 34 MCP tools: names, input schemas, descriptions Talkdesk reads; each calls a service |
| `app/services/patients.py` | Identity check (phone + DOB, lockout), registration, patient snapshot, action log |
| `app/services/appointments.py` | Slots, booking, reschedule, cancel, waitlist, offers, follow-ups, booking codes |
| `app/services/records.py` | Lab reports, visit history, prescriptions, insurance, coverage, bills, department suggestion, hospital info, visit prep |
| `app/services/support.py` | Handoffs, callbacks, notes, memory search, preferences, assistance, caregiver updates, check-ins, nurse alerts, feedback |
| `app/services/blackboard.py` | Shared working memory P0–P3 + context registry |
| `app/services/ref.py` | Reference data cache (departments, doctors, procedures, insurers, coverage, hospital info) + fuzzy lookups |
| `app/db.py` | Schema (27 tables), engine, SQLite fallback, Row Level Security lock-down, search extensions setup |
| `app/seed.py` | Deterministic demo data generator (dates relative to today), demo reset |
| `app/api.py` | Website/portal/dashboard API, auth, jobs, check-in, health, ops search, SPA serving, security headers |
| `app/store.py` | Redis-or-memory key/value store with automatic 30 s fallback |
| `app/events.py`, `app/workers.py` | Event bus (Redis Streams or in-process queue) and the workers that react to events |
| `app/notify.py` | Notification outbox, SMTP sender thread, simulated channels |
| `app/search.py`, `app/embeddings.py`, `app/kb.py` | Hybrid search engine, Gemini client, hospital knowledge base |
| `app/security.py`, `app/ratelimit.py` | Password hashing (scrypt), signed tokens (HMAC), rate limiter |
| `frontend/` → `web/dist/` | React website source → built files served by the same server |
| `scripts/` | `smoke_mcp.py` (34 checks), `eval_search.py`, `load_test.py`, `bench_tools.py` |
| `tests/` | `test_core.py`, `test_search.py` (44 tests) |

---

# 5. The MCP server

## 5.1 Connection

* **Library:** official MCP Python SDK 2.3.0 (`MCPServer`), transport **Streamable HTTP**, path `/mcp`,
  `stateless_http=True`, `json_response=True`. Same library, path and auth scheme as V1, so Talkdesk's existing
  connection kept working through the rebuild.
* **Auth:** `Authorization: Bearer <MCP_BEARER_TOKEN>`. Missing → 401, wrong → 403 (constant-time compare). An IP that
  sends 20 wrong tokens in 10 minutes is blocked for a while. Valid callers are never rate-limited.
* **Envelope (every tool):**

```json
{ "ok": true,
  "message": "Booked. Dr. Rajesh Iyer, Wednesday 4 November at 10:30 AM, room OPD-310, fee 1,200 rupees. Your booking ID is WN-42989.",
  "data": { "booking_id": "WN-42989", "doctor": "Dr. Rajesh Iyer", "date": "2026-11-04", "time": "10:30", "room": "OPD-310", "fee_inr": 1200 },
  "related": [ { "kind": "coverage", "text": "Star Health covers this consultation with a 10% co-pay." } ],
  "error_code": null }
```

  `error_code` values: `invalid_input`, `not_verified`, `not_found`, `not_allowed`, `slot_taken`, `offer_expired`,
  `locked_out`, `service_unavailable`. Tools never throw; a crash becomes `service_unavailable` with a polite message.
* **Inputs are forgiving:** phone numbers in any Indian format (`98450 00001`, `+91-…`, `0…`), dates like `tomorrow`,
  `4 Nov`, `next Monday`, times like `10.30am`, spoken booking codes (`W N 4 8 2 1 3`), misspelt doctor/department names.
* **Every call is measured** (server time, ok/error) and shown on the dashboard's "Tool latency" panel.

## 5.2 All 34 tools

`*` = required input. "ID check" = the server verifies phone + date of birth before doing anything.

**Identity & booking**

| Tool | Inputs | What it does |
|---|---|---|
| `verify_patient` | phone\*, date_of_birth\* | Verifies identity; returns name, age, senior flag, upcoming bookings, report status, insurer, recent notes, and any **waitlist offer waiting for them**. Starts context preloading. |
| `register_patient` | name\*, phone\*, date_of_birth\*, email\*, gender, insurance_provider | Registers a new patient; rejects a phone already registered |
| `find_available_slots` *(V1)* | date\*, department, doctor_name, time_preference, procedure, phone | Free slots for a date by department, doctor or test/scan, **plus each doctor's days, hours, fee, room, languages**; suggests the next free day if full |
| `book_appointment` *(V1)* | phone\*, date\*, time\*, patient_name, department, doctor_name, reason, date_of_birth, procedure, idempotency_key | Books a doctor or test slot; returns booking ID, room, fee, preparation; database makes double booking impossible; same idempotency key = same booking |
| `join_waitlist` | phone\*, date_of_birth\*, department, doctor_name, date_from, date_to, time_preference | Adds a verified patient to the waitlist (ID check) |
| `find_appointments` *(V1)* | phone, booking_id, date_of_birth, include_past | Lists up to 3 upcoming bookings with phone + DOB; with phone only, says how many and asks for DOB (privacy) |
| `reschedule_appointment` *(V1)* | booking_id\*, new_date\*, new_time\*, phone, date_of_birth, doctor_name | Moves the patient's own booking (ID check); old slot goes to the waitlist |
| `cancel_appointment` *(V1)* | booking_id\*, phone, date_of_birth, reason | Cancels the patient's own booking (ID check); freed slot offered to the next waitlisted patient |
| `accept_waitlist_offer` | offer_code\*, phone\* | Accepts a held slot; the phone must be the one the offer was sent to |
| `schedule_followup` | phone\*, date_of_birth\*, doctor_name, within_days | Finds follow-up slots with the last (or named) doctor within N days (ID check) |

**Records**

| Tool | Inputs | What it does |
|---|---|---|
| `get_lab_report_status` | phone\*, date_of_birth\* | Pending (with expected time), ready or collected (ID check) |
| `email_lab_report` | phone\*, date_of_birth\*, report_id | Emails a summary + secure portal link, **never lab values** (ID check) |
| `get_visit_history` | phone\*, date_of_birth\* | Last 5 completed visits (ID check) |
| `request_prescription_refill` | phone\*, date_of_birth\*, medicine_name\*, doctor_name | Sends a refill request to the doctor; never auto-approved (ID check) |

**Insurance & billing**

| Tool | Inputs | What it does |
|---|---|---|
| `get_insurance_info` | insurance_provider | Accepted insurers, cashless/reimbursement, documents, desk hours |
| `check_coverage` | insurance_provider, procedure, department, phone, date_of_birth | Covered yes/partial/no, estimated patient share, pre-approval needed + turnaround; uses the patient's own policy when verified; stored on the blackboard so a later booking mentions it |
| `get_bill_status` | phone\*, date_of_birth\* | Outstanding bills, amount, due date (ID check) |
| `send_payment_link` | phone\*, date_of_birth\*, bill_id | Emails/SMSes a secure payment link (simulated payment page `/pay`); never takes card details (ID check) |

**Information**

| Tool | Inputs | What it does |
|---|---|---|
| `get_doctors` *(V1)* | department, doctor_name | Doctors with days, hours, fee, room, languages (only the department asked) |
| `suggest_department` | symptoms\* | Routing suggestion with disclaimer. Red-flag words → `emergency: true` + "call 108". Keyword rules first, then hybrid search over department descriptions |
| `get_hospital_info` | topic | Any hospital question in the caller's own words (visiting, ICU, food, Wi-Fi, payment, cashless, records, packages, parking…) answered from the knowledge base by hybrid search |
| `get_visit_instructions` | department, procedure | Fasting, documents, arrival time for a visit or test |

**Care, seniors and caregivers**

| Tool | Inputs | What it does |
|---|---|---|
| `get_patient_preferences` | phone\*, date_of_birth\* | Language, preferred time, caregiver + consent, mobility needs (ID check) |
| `set_patient_preferences` | phone\*, date_of_birth\*, preferred_language, preferred_time, caregiver_name, caregiver_phone, caregiver_email, caregiver_consent, mobility_needs | Updates only the fields given (ID check) |
| `request_assistance` | booking_id\*, phone\*, assistance_type\*, notes | Wheelchair, escort, interpreter or transport desk for the patient's own booking |
| `send_caregiver_update` | phone\*, date_of_birth\*, booking_id | Sends next booking details to the caregiver **only with consent** (ID check) |

**Support, memory and aftercare**

| Tool | Inputs | What it does |
|---|---|---|
| `create_handoff` | summary\*, priority, phone, reason_code | Hands over to a human; `urgent` messages start with the 108 advice |
| `get_handoff_status` | handoff_id\* | Status of a handoff |
| `request_callback` | phone\*, preferred_time\*, reason\* | Schedules a call back (no DOB needed) |
| `save_interaction_note` | phone\*, summary\*, topics, outcome | Saves a conversation note for next time (immediately searchable) |
| `search_past_interactions` | phone\*, date_of_birth\*, query\* | Hybrid search over **this patient's own** notes and actions ("did I ask about my MRI report?", "WN-48213") (ID check) |
| `record_checkin` | phone\*, date_of_birth\*, booking_id, pain_score, fever, symptoms_worse, notes | Post-visit check-in; pain ≥ 7, fever or "worse" → nurse alert (ID check) |
| `flag_nurse_alert` | phone\*, reason\* | Asks a nurse to call back about a worrying symptom |
| `submit_feedback` | phone\*, rating\*, comment, booking_id | Records feedback; low ratings go to the patient-care team |

The **six V1 tools** (`get_doctors`, `find_available_slots`, `book_appointment`, `find_appointments`,
`reschedule_appointment`, `cancel_appointment`) keep their names and inputs; new inputs are optional, and an
automated check guards this on every push.

---

# 6. Talkdesk agents (current and proposed)

## 6.1 Overview

Nine agents: one supervisor and eight specialists, each with **at most 5 skills** (Talkdesk's limit). The full
copy-paste build sheet (descriptions, instructions, every skill-input → variable mapping, 39 variables, conditions,
orchestrator settings, test script) is `docs/TALKDESK_SETUP.md`.

| # | Agent | Status | Handles | Skills (MCP tools) |
|---|---|---|---|---|
| 0 | **Receptionist** (supervisor) | Live (V1), V2 instructions ready | Greeting, emergency-first rule, routing, relaying answers, small talk | — (routes to specialists) |
| 1 | **Booking** | Live (V1), V2 extension ready | New appointments, tests/scans, registration, waitlist | verify_patient, find_available_slots, book_appointment, join_waitlist, register_patient |
| 2 | **Changes** | Proposed | View/cancel/reschedule existing bookings, accept waitlist offers | verify_patient, find_appointments, cancel_appointment, reschedule_appointment, accept_waitlist_offer |
| 3 | **Support** | Proposed | Emergencies + human handoff, call backs, complaints, memory | create_handoff, request_callback, search_past_interactions, save_interaction_note, get_handoff_status |
| 4 | **Records** | Proposed | Lab/scan reports, emailing reports, visit history, refills | verify_patient, get_lab_report_status, email_lab_report, get_visit_history, request_prescription_refill |
| 5 | **Billing & Insurance** | Proposed | Insurers, coverage + pre-approval, bills, payment links | get_insurance_info, check_coverage, get_bill_status, send_payment_link, verify_patient |
| 6 | **Info** | Live (V1), V2 extension ready | Doctors, symptom → department, hospital facts and FAQs, visit prep | get_doctors, suggest_department, get_hospital_info, get_visit_instructions |
| 7 | **Care Assist** | Proposed | Seniors and caregivers: preferences, caregiver updates, wheelchair/escort/interpreter | verify_patient, get_patient_preferences, set_patient_preferences, request_assistance, send_caregiver_update |
| 8 | **Aftercare** | Proposed | Post-visit check-ins, nurse alerts, feedback, follow-ups | record_checkin, flag_nurse_alert, submit_feedback, schedule_followup, verify_patient |

## 6.2 Receptionist rules (summary)

* **Emergency first:** chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure,
  poisoning or suicidal thoughts → Support Agent for an urgent handoff; tell the patient to call 108; never continue
  with booking in that conversation.
* **Style:** 1–2 sentences, plain words, no markdown or emojis (voice-friendly), reply in the patient's language.
* **Relay:** read specialists' messages as given; always read back booking IDs, doctor, date, time, room and fee;
  on voice spell booking IDs character by character ("W N 4 8 2 1 3").
* **Safety:** no medical advice, diagnoses or medicine recommendations; department suggestions only, via Info.
* **Identity:** for anything about an existing patient, ask for registered mobile number + date of birth.
* **Memory:** at the end of a meaningful conversation, ask Support to save a note.

## 6.3 Routing conditions (in order)

1. **Support** first: emergency words; wants a human/call back/complaint; asks about an earlier conversation; handoff status; saving a note.
2. **Booking:** a new appointment, test or scan; free slots; new patient; join a waitlist.
3. **Changes:** see, cancel or reschedule an existing booking; accept an offer code.
4. **Records:** lab/scan reports, emailing a report, past visits, prescription refill.
5. **Billing & Insurance:** insurance, cashless, coverage, pre-approval, estimates, bills, paying.
6. **Care Assist:** wheelchair/escort/interpreter, caregiver updates, preferences.
7. **Aftercare:** recent visit + how they feel, feedback, follow-up.
8. **Info:** anything else about the hospital.

## 6.4 Variables (39)

Conversation variables carry what the patient said into tool inputs, e.g. `patient_phone`, `date_of_birth`,
`patient_name`, `patient_email`, `appointment_date`, `appointment_time`, `time_preference`, `department`,
`doctor_name`, `procedure`, `booking_id`, `offer_code`, `insurance_provider`, `report_id`, `bill_id`, `symptoms`,
`hospital_topic`, `memory_query`, `handoff_summary`, `priority`, `callback_time`, `callback_reason`,
`preferred_language`, `caregiver_*`, `mobility_needs`, `assistance_type`, `pain_score`, `has_fever`,
`symptoms_worse`, `feedback_rating`, `feedback_comment`, `conversation_summary`, `conversation_topics` and more.
Each has a description in the build sheet; Talkdesk uses the description to decide what to fill in.

---

# 7. Data

## 7.1 Database (27 tables)

| Group | Tables |
|---|---|
| Reference | `departments`, `doctors`, `procedures`, `resources` (MRI/CT rooms), `insurers`, `coverage_rules`, `hospital_info` |
| Patients & identity | `patients`, `verification_attempts` |
| Scheduling | `appointments`, `waitlist`, `waitlist_offers`, `assistance_requests` |
| Clinical admin | `lab_reports`, `prescriptions`, `prescription_requests`, `bills` |
| Support & care | `handoffs`, `callbacks`, `checkins`, `nurse_alerts`, `feedback` |
| Memory & audit | `interaction_notes`, `resolutions` (every action any channel takes), `search_docs` (search index) |
| Messaging | `notifications` (the outbox) |
| Outside the schema | `embedding_cache` (meaning vectors; survives demo resets) |

**Integrity in the database itself:**
* `uq_doctor_slot_booked` / `uq_resource_slot_booked`: partial unique indexes (only where `status = 'booked'`) make
  double booking impossible even under concurrency.
* `uq_open_offer_per_slot`: one open waitlist offer per slot.
* Booking codes `WN-xxxxx` are generated unique (checked before insert).
* **Row Level Security** is enabled on every table with no policies, and `anon`/`authenticated` roles are revoked, so
  Supabase's public REST API sees nothing; only our server (table owner) has access.

## 7.2 Demo data (generated, deterministic, relative to today)

14 departments · 45 doctors · 35 procedures (MRI, CT, X-ray, ultrasound, cardiac tests, endoscopy, labs, health
packages) · 12 imaging resources · 10 insurers · 490 coverage rules · 600 patients · ~7,300 appointments (past and
future) · lab reports, prescriptions, bills · 804 conversation notes · ~1,850 action records · 8 hospital-info topics.

**Personas (all fictional):**

| Persona | Phone / DOB | Story |
|---|---|---|
| Shanthamma K (67, senior) | 98450 00001 / 1959-03-04 | Booking **WN-48213** with cardiologist Dr. Rajesh Iyer; son Ravi as caregiver; wheelchair needs |
| Arjun Mehta (34) | 98450 00002 / 1992-06-15 | On the waitlist for Dr. Iyer (fully booked for 7 days) |
| Priya Nair (29) | 98450 00003 / 1997-01-20 | Thyroid report **ready**; asked about her MRI report last week |
| Rahul Verma | 98450 00004 / 1981-09-10 | Outstanding bill **BL-55012** |
| Meera Joshi (child) | 98450 00005 / 2018-05-12 | Paediatrics patient |

Website logins: `shanthamma.demo@example.com`, `arjun.demo@example.com`, `priya.demo@example.com` with `DEMO_PASSWORD`.

**Reset:** `POST /ops/reset-demo?token=<JOBS_TOKEN>` rebuilds all data relative to that day in about 3 seconds
(run it on demo morning, around 11:30).

---

# 8. Security and privacy

| Control | Implementation |
|---|---|
| MCP authentication | Bearer token, constant-time comparison, 401/403, brute-force IP block |
| Patient identity | Phone + date of birth verified **on the server** for every identity-sensitive tool; generic failure message; **5 wrong tries → 15-minute lock** |
| Ownership | A patient can only see/change their own bookings, reports, bills; offers only for the phone they were sent to |
| Website accounts | scrypt password hashing; signed HMAC session tokens; rate-limited login/sign-up |
| Rate limits | Login, sign-up, call-back, waitlist accept, coverage estimate, check-in |
| Web headers | Content-Security-Policy (allows only the Talkdesk widget domains), HSTS, `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy |
| Data exposure | Row Level Security on all tables; lab values never emailed (portal link only); emails/phones masked in replies (`pr***@example.com`) |
| Cache privacy | No phone numbers in Redis: patient keys are keyed hashes (HMAC) |
| Secrets | Only in Render environment variables; `.env.example` documents names; nothing secret in the repo; testing never uses the Google key |
| Medical safety | No advice; department suggestions carry a disclaimer; emergency words always produce the 108 message and an urgent handoff |
| Signed links | Waitlist accept, payment and post-visit check-in links are signed and expire (check-in: 7 days) |

---

# 9. Context: the blackboard

A shared working memory (in Redis, falls back to process memory) so agents get patient context **inside normal tool
replies**, with no extra calls.

| Level | Content | Lifetime |
|---|---|---|
| **P0** live facts | Things just learned in this conversation: coverage result, offered slots, waitlist offer, handoff | 15 min |
| **P1** snapshot | Verified patient's summary: upcoming bookings, reports, open offer | 30 min |
| **P2** profile | Insurer, preferences, caregiver, senior flag | 6 h |
| **P3** memory digest | Latest conversation notes | 7 days |

* **Context registry:** per patient, each item is READY / LOADING / MISSING / ERROR with source and age (shown on
  the dashboard).
* **Preloading:** when a patient is verified (or opens the website portal), a worker preloads P1–P3 in the background.
* **Freshness:** booking changes invalidate the snapshot; waitlist offers are always read live from the database.
* **Related facts:** P0 facts ride along in `related` (e.g. the booking reply reminds the agent that pre-approval is
  needed, because `check_coverage` ran earlier in the call).

# 10. Events and workers

Every important change is published as an event; workers react in the background.

* **Transport:** Redis Streams (`wn:events`, consumer group `workers`), acknowledgements, automatic reclaim after
  30 s, **dead-letter stream** after 3 failed deliveries, self-repair if the stream is wiped. Without Redis an
  in-process queue does the same.
* **Events:** `patient.verified`, `session.warm`, `appointment.created/cancelled/rescheduled`, `waitlist.offered`,
  `waitlist.accepted`, `preferences.updated`, `notification.queued`, `interaction.noted`, `handoff.created`.
* **Workers:** context preloader (verified/session warm), context updater (booking and waitlist changes), notification
  waker (email sender), memory refresher (new notes), search indexer (embeds a patient's notes on verification or a new
  note), analytics counters per day.

---

# 11. Hybrid search

Used by `search_past_interactions`, `get_hospital_info` and `suggest_department`.

**Why hybrid:** embeddings alone miss exact codes (WN-48213), names and typos; keywords alone miss paraphrases. So
four "legs" run in one Postgres query and are fused:

| Leg | Technology | Catches | Example |
|---|---|---|---|
| Keyword | Postgres full-text (`tsvector`, English stemming, GIN index) | exact words and word forms | "visiting" ↔ "visits" |
| Fuzzy | `pg_trgm` whole-word trigram similarity ≥ 0.45 | typos, names | "cardiolgy" → Cardiology, "parkng" → parking |
| Code | normalised code match | booking/report/bill IDs | "wn 48213" → WN-48213 |
| Meaning | **pgvector** `vector(768)` cosine + **Gemini** `gemini-embedding-001` | paraphrases | "grab a bite to eat" → cafeteria |

* **Fusion:** Reciprocal Rank Fusion (`Σ weight / (60 + rank)`, ties share a rank).
* **Relevance gate:** a result counts only if it covers enough of the question's meaningful words, matches a code,
  or has cosine ≥ `SEARCH_MIN_SIM` (0.70). "Nothing relevant" is a real answer; filler words are ignored.
* **Scope:** patient searches are filtered to that one patient (exact scoring); the knowledge base has an HNSW index.
* **Knowledge base (95 passages):** 8 hospital-info topics, 14 departments with lay symptom words, 35 procedures with
  preparation, 10 insurers, 28 FAQs (`app/kb.py`).
* **Embedding policy (free tier):** only natural-language text is embedded; the 95 knowledge passages at startup,
  paced 25 every 20 s; a patient's notes only when that patient shows up. Vectors are cached in `embedding_cache`
  (survives resets, so restarts cost nothing). Query embeddings: 1.5 s timeout, 7-day cache, circuit breaker; a
  Google 429 is decoded (per-minute vs per-day) and the server falls back to keyword + fuzzy automatically.
* **Debug view:** `/api/ops/search?token=<DASHBOARD_TOKEN>&q=…[&phone=…][&raw=true]` shows each hit's legs and scores.

**Measured with the real Gemini model (3 Nov):** keyword 6/6, typos 3/3, codes 1/1, off-topic correctly empty 3/3,
paraphrases 6/13 (3/13 without Gemini); 26 queries, 0 errors. Correct passages scored cosine 0.61–0.80 (median 0.71).

---

# 12. Notifications, reminders and jobs

## 12.1 Outbox

Every message is written to `notifications` **in the same transaction** as the action, so no booking is ever missing
its confirmation. A background thread sends queued emails over SMTP and retries; duplicates are prevented with
dedupe keys.

| Trigger | Email | SMS / call |
|---|---|---|
| Booking confirmed / rescheduled | ✅ | SMS |
| Booking cancelled | ✅ | SMS |
| Waitlist slot offered (30-min hold, accept link) | ✅ | SMS |
| 24 h before the visit | ✅ | SMS |
| 2 h before the visit | — | voice call (simulated) |
| Lab report ready (portal link only) | ✅ | — |
| Payment link | ✅ | SMS |
| Caregiver update (with consent) | ✅ | SMS |
| Call back requested | — | call (simulated) |
| Day-2 aftercare check-in (signed 7-day link) | ✅ | — |

* **Real vs simulated:** email is real when `SMTP_*` is set, except to invented demo addresses (`@example.com`,
  `.test`). `DEMO_EMAIL_OVERRIDE` redirects all real emails to one inbox for demos. SMS, WhatsApp and calls are
  always simulated (recorded and shown on the dashboard), honestly labelled.

## 12.2 Jobs (`/jobs/run`, every minute via cron-job.org)

| Job | What it does |
|---|---|
| `expire_offers` | Expires unanswered waitlist offers and offers the slot to the next patient |
| `run_reminders` | 24 h email + SMS and 2 h call reminders (deduplicated) |
| `close_past_visits` | Marks visits whose time has passed as completed |
| `run_aftercare` | Two days after a visit, emails a signed link to the check-in form |
| search backfill | Indexes new notes/actions; embeds up to 25 knowledge passages if any are missing |
| `notify.flush` | Sends queued emails |

Reply example: `{"ok":true,"offers_expired":0,"reminders_queued":92,"visits_completed":0,"aftercare_checkins_queued":0,"emails_processed":0,"search_rows_embedded":0,"ms":561}`.

---

# 13. Website, portal and dashboard

**Design:** a real hospital site: white and medical blue, DM Serif Display + Manrope, real photos, smooth scrolling,
accessible (keyboard, contrast, larger-text toggle), responsive down to phone width. **Booking is Talkdesk-first:**
every page leads with "Chat to book" and "Call to book"; the manual booking form is the fallback.

| Page | Purpose |
|---|---|
| `/` | Home: live chat demo script, how it works, numbers, centres of excellence, why us, doctors, stories, packages, health library, emergency banner, call-back form |
| `/specialities`, `/doctors`, `/about`, `/visitors`, `/insurance`, `/contact` | Hospital information; insurance page has a live coverage checker |
| `/login`, `/signup` | Patient accounts |
| `/portal` (+ `/book`, `/appointments`, `/reports`, `/waitlist`, `/profile`) | Patient portal: book (same rules as the bot), view/cancel/reschedule, request assistance, lab reports, waitlist, profile |
| `/waitlist/accept?code=…` | One-click accept page from the offer email/SMS |
| `/pay?bill=…` | Payment page (simulated) from the payment link |
| `/checkin?t=…` | Post-visit check-in form (pain slider, fever, worse, notes) from the day-2 email; nurse alert on warning answers |
| `/architecture` | "How WellNest works": live system status, request flow, test results, safety, scale plan |
| `/dashboard?token=…` | Staff dashboard: OPD fill by department, activity by channel, waitlist offers, handoffs, outbox, blackboard & event stream, tool latency |

**API (`/api`, used by the website):** sign-up/login; public reference data (departments, doctors, procedures,
insurers, hospital info, slots, coverage estimate); patient endpoints under `/api/me/…` (appointments, reports,
waitlist, bills, assistance); `/api/session/warm`; waitlist offer view/accept; check-in; call back; ops endpoints
(`/api/metrics`, `/api/ops/summary|feed|system|search`) with the dashboard token; `/health`; `/config.js` (widget
settings).

---

# 14. Example workflows

Each workflow shows the channel, the agent route, the tool calls and what happens inside the backend.

## W1. New booking by chat
1. Patient: *"I need a heart doctor tomorrow morning."* → Receptionist → **Booking**.
2. `find_available_slots(date="tomorrow", department="heart", time_preference="morning")` → resolves "heart" to
   Cardiology, "tomorrow" to the date; returns free times **and** each doctor's fee, room, languages, so no second agent is needed.
3. Patient picks 10:00 with Dr. Farzana Begum and gives name, phone, DOB.
4. `verify_patient(...)` → identity checked; snapshot preloaded.
5. `book_appointment(phone, date, time="10:00", doctor_name="Farzana")` → transaction inserts the booking (unique
   index guarantees the slot), logs the action, queues confirmation email + SMS, publishes `appointment.created`.
6. Bot: *"Booked. Dr. Farzana Begum, Wednesday 4 November at 10:00 AM, room …, fee … Your booking ID is WN-…"*
7. The booking appears in the website portal and on the dashboard immediately.

## W2. Senior patient with caregiver and wheelchair
1. Shanthamma (67) on chat: verified → snapshot marks her **senior**; replies become shorter and morning slots are preferred.
2. *"Please tell my son Ravi"* → Care Assist → `set_patient_preferences(caregiver_name="Ravi", caregiver_phone=…, caregiver_consent=yes)` → `send_caregiver_update` emails/SMSes Ravi the booking.
3. *"I need a wheelchair"* → `request_assistance(booking_id="WN-48213", assistance_type="wheelchair")` → request recorded for the front desk.

## W3. Cancel → waitlist auto-offer → accept
1. Shanthamma: *"Cancel WN-48213"* → **Changes** → `cancel_appointment(booking_id, phone, dob)`; the server checks
   it's her booking, cancels it, and **offers the slot to Arjun**, the best waitlist match (urgent first, then seniors, then earliest to join): offer code, 30-minute
   hold, email + SMS with `/waitlist/accept?code=…`.
2. Arjun either clicks the link (website accept page) **or** calls: `verify_patient` tells him *"a slot with Dr. Rajesh
   Iyer … is held for you until 5:50 PM, offer code …. Shall I confirm it?"*
3. `accept_waitlist_offer(offer_code, phone)` → booked with a fresh unique code; dashboard "Waitlist offers" updates.
4. If he doesn't answer, `/jobs/run` expires the offer and offers the slot to the next patient.

## W4. "Book an MRI and check if my insurance covers it"
1. **Billing & Insurance** → `check_coverage(insurance_provider="Star Health", procedure="MRI Knee", phone, dob)` →
   *"Star Health covers MRI Knee in full. Pre-approval is needed first, usually within 24 hours…"*; the fact is stored on the blackboard (P0).
2. Patient confirms → **Booking** → `find_available_slots(procedure="MRI Knee")` → `book_appointment(procedure=…)` → the
   reply's `related` reminds the agent about pre-approval; preparation instructions (remove metal, arrive 30 min early) included.

## W5. Emergency
1. *"I have chest pain right now."* → Receptionist's emergency rule → **Support**.
2. `create_handoff(summary, priority="urgent", phone)` → message starts *"Please call 108 now…"*; handoff recorded and
   shown on the dashboard; conversation goes to a human in Talkdesk Conversations. No booking talk afterwards.
3. The same red-flag detection runs in `suggest_department` (deterministic word list, plus meaning search that can only escalate).

## W6. Memory: "Did I ask you about my MRI report last week?"
1. Priya + DOB → **Support** → `search_past_interactions(phone, dob, query="MRI report")`.
2. Server: identity check → index any new notes → hybrid search over **only Priya's** notes and actions.
3. *"Yes. 6 days ago, on Wednesday 28 October: Asked whether her MRI report from last month could be emailed; told it is in the portal under Lab reports."*
4. Codes work too: *"Anything about WN-48213?"* finds the booking record.

## W7. Lab report
1. *"Is my thyroid report ready?"* → **Records** → `get_lab_report_status(phone, dob)` → *"Thyroid Profile is ready…"*
2. *"Email it"* → `email_lab_report` → summary + secure portal link to `pr***@…` (values only in the portal).
3. Pending reports: *"isn't ready yet; it should be ready tomorrow by 6:00 PM. We'll email you when it is."*

## W8. Hospital question in the caller's own words
1. *"Can my son stay overnight with me in the ward?"* → **Info** → `get_hospital_info(topic="can my son stay overnight with me in the ward")`.
2. Hybrid search over 95 knowledge passages → *"Each admitted patient gets one attendant pass. The attendant can stay overnight in the ward…"*
3. *"Where can I grab a bite to eat?"* → found by meaning (Gemini) → cafeteria answer. *"What's the cricket score?"* → nothing relevant → agent offers a call back instead of guessing.

## W9. Symptom to department
1. *"I need a cardiolgy check up"* (typo) → `suggest_department` → keyword rules miss → hybrid search → **Cardiology** + disclaimer.
2. *"Always thirsty and peeing a lot"* → Endocrinology. *"Face drooping, slurred speech"* → emergency.

## W10. Bill and payment
1. Rahul → **Billing** → `get_bill_status` → outstanding BL-55012 → `send_payment_link` → email/SMS with `/pay?bill=BL-55012` (simulated payment page). Card details are never taken by chat or phone.

## W11. Reminders and aftercare (no patient action)
1. Every minute cron calls `/jobs/run`.
2. 24 h before a visit → email + SMS; 2 h before → reminder call (simulated).
3. After the visit → marked completed; two days later → email with a signed check-in link.
4. Patient opens `/checkin`, reports pain 8 → `record_checkin` → **nurse alert** raised → *"A nurse will call you."*

## W12. Website-only patient
1. Patient signs up / logs in → portal → books with the same slot rules and double-booking guard as the bot.
2. Opening the portal calls `/api/session/warm` → context preloaded, so a later call to the bot is instant.

## W13. Staff and operations
* `/dashboard?token=…` shows OPD fill, live activity by channel, offers, handoffs, outbox, cache/event health and tool latency.
* Demo morning: `curl -X POST "https://teamxyz-mcp.onrender.com/ops/reset-demo?token=JOBS_TOKEN"`.
* `/health` → `db_kind`, `blackboard`, `events`, `email`, `search` modes at a glance.

---

# 15. Testing and quality

| Layer | What | Result |
|---|---|---|
| Unit tests (`tests/`, pytest) | Normalisers, envelope, identity + lockout, double booking, waitlist, booking-code clash regression, rate limiter, headers, store fallback, blackboard, events, hybrid search fallback + isolation, Gemini client (mocked: request shape, normalisation, cache, 429 parsing, daily budget) | **44 passed** |
| End-to-end (`scripts/smoke_mcp.py`) | 34 checks over the real MCP transport: V1 tools/inputs unchanged, every tool returns the envelope on garbage input, identity, lockout, ownership, waitlist cancel→offer→accept, coverage + pre-auth fact, emergency wording, idempotency, parallel booking, memory, search | **34/34** (also with Redis killed, and with Google refusing) |
| Search evaluation (`scripts/eval_search.py`) | 26 labelled questions: keyword, typo, code, paraphrase, off-topic | Keyword/typo/code/off-topic all pass (required in CI) |
| Load (`scripts/load_test.py`) | 50 patients booking the same slot at once; 25 parallel patients × 4 conversations | **1 booked, 49 "slot taken", 0 double bookings**; **600 calls in 6.8 s, 0 errors** |
| CI (GitHub Actions) | On every push: Postgres 16 + pgvector, Redis 7, unit tests, server start (checks `postgres`, `redis-streams`, `hybrid`), search evaluation, 34 MCP checks, website type-check + build | Green on `main` |
| Browser checks (Playwright) | Pages render, no console errors, no horizontal scroll on phones | Clean |

**Bugs found and fixed by this testing (examples):** waitlist accept failed ~1 in 12 times on a booking-code clash;
public pages lost their side margins; a missing `httpx` dependency crashed one Render deploy (now CI installs exactly
what Render installs).

# 16. Performance

| Measure | Value |
|---|---|
| Typical server time per tool call | 5–30 ms (reads p50 target ≤ 80 ms) |
| Under load (25 simultaneous conversations, 1 worker) | p50 268 ms, p95 429 ms, 89 calls/s, 0 errors |
| Meaning-search query (Gemini call, first time) | ~200–250 ms; repeats served from cache |
| V1 multi-intent request | 12.1 s over 4 agent hops → V2 answers it in one tool call (`find_available_slots` includes fees/days/rooms) |
| V1 evaluation baseline | Score 88.75, ~5/10 goals truly achieved; V2 fixes each failed scenario (identity, waitlist, insurance, lab reports, emergency) |

---

# 17. Deployment and configuration

## 17.1 How it runs

* Render web service builds with `pip install -r requirements.txt` and starts `python server.py` (Python 3.13). The
  React site is pre-built into `web/dist/` and committed (Render has no Node build step).
* On start: create/upgrade tables, enable Row Level Security, enable search extensions, seed demo data if empty,
  load reference cache, start the email sender and event workers, index search documents.
* Push to `main` → Render deploys automatically.

## 17.2 Environment variables (Render)

| Variable | Purpose |
|---|---|
| `MCP_BEARER_TOKEN` | Token Talkdesk sends to `/mcp` (required) |
| `DATABASE_URL` | Supabase Postgres (transaction pooler URL) |
| `REDIS_URL` | Render Key Value (blackboard, events) |
| `DASHBOARD_TOKEN` | Staff dashboard and ops endpoints |
| `JOBS_TOKEN` | `/jobs/run` and `/ops/reset-demo` |
| `SECRET_KEY` | Signs session, offer, payment and check-in links |
| `PUBLIC_BASE_URL` | Links in emails |
| `EMBEDDINGS_API_KEY` | Google Gemini key (meaning search). Optional; without it search is keyword + fuzzy |
| `EMBEDDINGS_MODEL`, `SEARCH_MIN_SIM`, `EMBED_DAILY_BUDGET`, `EMBEDDINGS_TIMEOUT` | Search tuning (defaults are fine) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | Real email (optional) |
| `DEMO_EMAIL_OVERRIDE`, `DEMO_PERSONA_EMAILS` | Send demo emails to real inboxes |
| `TALKDESK_TOUCHPOINT_ID`, `TALKDESK_REGION` | Website chat widget |
| `TALKDESK_VOICE_NUMBER` | "Call to book" number |
| `DEMO_PASSWORD`, `AUTO_SEED`, `DB_PATH`, `PORT` | Demo/local settings |

All names are documented in `.env.example`; no secret values are in the repository.

## 17.3 Health and runbook

| Check | Expect |
|---|---|
| `GET /health` | `ok: true`, `db_kind: postgres`, `blackboard: connected`, `events: redis-streams`, `search: hybrid`, `email: smtp` or `simulated` |
| `GET /api/ops/system?token=…` → `search` | `kb_embedded` = 95; `embeddings.last_quota` empty |
| Cron | `/jobs/run` returns `{"ok":true,…}` every minute |
| Demo morning | Reset demo data; open dashboard; run the Talkdesk test script |

---

# 18. Honest limitations

* Hospital, doctors and patients are fictional; a real deployment needs consent, retention rules and DPDP Act compliance.
* SMS, WhatsApp, reminder calls and payments are simulated (recorded, not sent/charged).
* Render's free instance sleeps without traffic (prevented by the cron ping) and runs one worker.
* Gemini free tier: ~100 embeddings per minute and a daily cap; the server paces itself and falls back to keyword +
  fuzzy search if refused. Paraphrase recall with the real model was 6/13 at the current cautious threshold.
* Talkdesk V2 specialist agents are designed and documented but must be built in the Talkdesk UI by the team.

# 19. What remains (human steps)

1. **Talkdesk:** refresh `TeamXYZ_MCP` (expect 34 tools); build agents and routing from `docs/TALKDESK_SETUP.md`; run test script (16 tests); run Agent Evaluation V1 vs V2.
2. **Render env:** `TALKDESK_TOUCHPOINT_ID` + `TALKDESK_REGION` (chat widget), `TALKDESK_VOICE_NUMBER`; optional Gmail SMTP settings.
3. **GitHub:** delete the unused `EMBEDDINGS_API_KEY` secret.
4. **Demo day:** reset demo data around 11:30; check `/health` and the dashboard.
5. Talkdesk safety rules: only touch `*_TeamXYZ` resources; one editor at a time; no Publish without team agreement; don't change Admin, Numbers, Channels or the MCP token; never paste tokens in chats or screenshots.

# 20. Scale-up path

| Today | At hospital scale |
|---|---|
| One FastAPI service, one worker | Several instances behind a load balancer (blackboard already shared in Redis) |
| Workers inside the web service | Separate worker services, same code |
| Redis Streams | Kafka behind the same publish interface |
| Hybrid search in Supabase | Same design + reranker; ANN indexes already in place |
| Email by SMTP; SMS/WhatsApp/calls simulated | Talkdesk SMS and outbound voice, WhatsApp Business API |
| Demo data | Integration with HIS/EHR, lab (LIS) and billing systems |

---

*Repository documents for deeper detail:* `docs/00_START_HERE.md` … `docs/10_BUILD_PLAN.md` (design and requirements),
`docs/TALKDESK_SETUP.md` (agent build sheet), `docs/V2_GUIDE.md` (routes), `docs/HUMAN_TODO.md` (click steps),
`docs/LATENCY_RESULTS.md` (measurements), `docs/07_CONTEXT_BLACKBOARD.md` (context and search design).
