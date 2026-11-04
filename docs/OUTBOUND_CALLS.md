# Autonomous outbound calls (reminders and post-visit follow-ups)

## What it does
WellNest calls patients by itself. Nobody presses a button:

| Call | When | Patient can |
|---|---|---|
| **Appointment reminder** | the day before a booked visit (2–26 h ahead) | 1 confirm · 2 change (text with link + call back) · 3 AI assistant · 9 stop calls |
| **Post-visit follow-up** | the day after a completed doctor visit | 1 feeling better (check-in saved) · 2 problem (nurse alert) · 3 AI assistant · 9 stop calls |
| **Waitlist slot offer** | as soon as a cancelled slot is offered to the patient | 1 book it on the call · 2 decline · 3 AI assistant · 9 stop calls |
| **Lab report ready** | within 48 h of a report becoming ready | 1 email a secure link (never results) · 3 AI assistant · 9 stop calls |
| **Call back** (any of the above) | when the patient told the AI "call me tomorrow at 5" | same as the original call |

Answers can be keys or words ("confirm", "change", "better", "help", "stop") when the flow uses Voice IVR.
New call types (lab report ready, bill due, vaccination due) are one small class in `app/services/outbound.py`;
the flow, the webhook and the scheduler stay the same because the backend writes each call's words.

## How it works
```
cron-job.org ── every minute ──► POST /jobs/run
                                   └ outbound.plan()     finds due reminders / follow-ups → outbound_calls (one per event, unique key)
                                   └ outbound.dispatch() calling hours, max 2 per run, retries; claims each call atomically
                                        │  OAuth client credentials → POST /flows/{flow_id}/interactions
                                        ▼  {call_id, patient_phone, patient_name, call_type, prompt, booking_id}
Talkdesk Studio flow "WellNest_Outreach_TeamXYZ" (API request trigger)
   Make Outbound Call ──Answered──► Execute Action(event=answered) → Input IVR / Voice IVR speaking %{prompt}
        │ no answer / busy / invalid ─► Execute Action(event=no_answer…) → End      (backend schedules a retry)
        └ patient answers 1 / 2 / 9 ─► Execute Action(event=choice, choice=N) ─► Play %{say} ─► End
          patient answers 3 ────────► Execute Action(choice=3) ─► Play %{say} ─► Forward to External: AI voice number
                                                                                    │
POST /api/outbound/event (X-Outbound-Token)  ◄─────────── every Execute Action      ▼
   confirm · SMS reschedule link + call back · check-in · nurse alert · opt-out     Studio voice flow → Autopilot
   returns {"say": next sentence, "action": end|ask|repeat|transfer}               → Receptionist → Outreach Agent
                                                                                      get_call_context → confirm /
Dashboard feed: every step is a resolution (actor system, channel voice)            reschedule / check-in → record_call_outcome
```
**Why a forward to the AI number:** Talkdesk's documented components for API-request flows are Forward to External,
Input IVR, Play Audio, Standard IVR, Voice IVR, Voice Transcription, Callback, Make Outbound Call, Execute Action,
rules and End Flow. **Connect to Autopilot is not among them**, so the AI agent cannot be attached to the outbound
call directly. The flow handles the common answers itself (fast, and our backend decides what it says), and option 3
hands the patient to the AI receptionist on our inbound number, where the new Outreach agent picks up with context.
If your Studio editor does show Connect to Autopilot in the API-request flow, use it after "Answered" instead of the
forward: everything else stays the same.

## Safety built in
- **No duplicate calls:** one `dedupe_key` per event (unique in the database), atomic claim before dialling, one live
  call per booking for manual triggers.
- **Retries:** no answer, busy, a failed start or no report from the flow within 10 minutes → retry after 30 min,
  3 attempts, then `failed / unreachable`. An invalid number is not retried.
- **Consent and opt-out:** pressing 9 or telling the AI "stop calling" adds the number to `call_optouts`; planner,
  dispatcher and manual trigger all skip it. Calls only 9 AM–8 PM IST (others wait for the next morning).
- **Who can be called:** `OUTBOUND_ALLOWLIST` (default: the 5 demo personas) and `OUTBOUND_TEST_NUMBER` (every call
  rings this one number). Demo patients have invented numbers, so the test number is required for a real call.
- **Privacy:** the call says the doctor, date and time only (no reason or results); `confirm_appointment` without a
  birth date works only for a booking we called that number about; everything else keeps phone + date of birth.
- **No secrets in code:** credentials, flow ID, numbers and tokens come from Render environment variables.

## What you do (about 45 minutes)

Build in this order; each step can be tested on its own. Menu paths checked in the sandbox on 4 Nov.

### 1. Talkdesk: Custom Integration for the webhook (10 min)
**Builder → Integrations → Browse integrations → Custom Integration → Add.** (Another team's
"Rakshak Backend_VortexKnights" integration is the same keypress-confirm pattern, so this works in our sandbox.)
- Name `WellNest_Outbound_TeamXYZ`, host / base URL `https://teamxyz-mcp.onrender.com`.
- Authentication: an API key **header** `X-Outbound-Token` = the `OUTBOUND_WEBHOOK_TOKEN` value (if only "no auth" is
  offered, put the token in the action path instead: `/api/outbound/event?token=<OUTBOUND_WEBHOOK_TOKEN>`).
- **Add action** `outbound_event`: method **POST**, path `/api/outbound/event`, JSON body with three string inputs:
  `{"call_id": "{{call_id}}", "event": "{{event}}", "choice": "{{choice}}"}`.
  Response / outputs (strings): `say`, `action`, `outcome`.
- Test the action from the integration screen with `call_id` = any `OC-...` from `/api/ops/outbound`, `event` =
  `answered`: it should return a `say` sentence. (A wrong token returns 401.)

### 2. Talkdesk: Studio flow `WellNest_Outreach_TeamXYZ` (20 min)
**Studio → Create flow → trigger type API request** (only API-request flows can be started by the Flows API and only
they offer Make Outbound Call).
1. **API request** node → input arguments (all strings), each saved to a flow variable of the same name:
   `call_id`, `patient_phone`, `patient_name`, `call_type`, `prompt`, `booking_id`.
2. **Make Outbound Call**: outbound (caller ID) number = our Talkdesk number from Admin → Numbers; destination =
   variable `patient_phone`; ring time 30 s (allowed 10–35). Exits:
   - *No answer* → **Execute Action** `outbound_event` (call_id = `call_id`, event = `no_answer`, choice empty) → End Flow.
   - *Busy* → same with event `busy`; *Invalid number* → same with event `invalid_number`.
   - *Answered* → **Execute Action** `outbound_event` (event = `answered`) → step 3.
3. **Input IVR** (keys) or **Voice IVR** (spoken answers): message, text-to-speech: `%{current_flow.prompt}`.
   Options **1, 2, 3, 9**. No input / invalid → repeat once → End Flow.
4. For each option N: **Execute Action** `outbound_event` (call_id = `call_id`, event = `choice`, choice = `N`;
   output `say` → flow variable `say`) → **Play Audio** text-to-speech `%{current_flow.say}` → End Flow.
   Option **3** only: after Play Audio → **Forward to External Number** = the AI voice number (the Studio voice flow
   that connects to Autopilot / the WellNest orchestration).
   Execute Action *failure / timeout* exits → Play Audio "Thank you, goodbye." → End Flow.
5. **Save → Publish**. In the flow list open **Request details**: copy the **flow ID** (and check the example body
   lists the six input names above).

### 3. Talkdesk: OAuth client (5 min)
**Builder → OAuth Clients → create**: name `WellNest_Outbound_TeamXYZ`, grant type **Client Credentials**, scope
**`flows-interactions:start`**. Copy the client ID and secret straight into Render (step 5), never into chat. (If the
page shows "Thanks for your patience… Refresh", press Refresh; it loaded slowly in our sandbox.)

### 4. Talkdesk: Outreach agent (15 min)
First: **MCP Servers → WellNest_TeamXYZ_MCP → Test connection / refresh** (37 tools; the 3 new ones are
`get_call_context`, `confirm_appointment`, `record_call_outcome`).

**Variables** ({ } → + Add variable):
| Variable | Description |
|---|---|
| `call_id` | The WellNest call reference like OC-123456, only if the patient reads it out. Usually empty. |
| `call_outcome` | How the call ended: confirmed, rescheduled, reschedule_requested, feeling_well, needs_help, opted_out, wrong_person, call_back_later or question_answered. |

**Add Agent → AI agent → Configuration**
- **Name:** `Outreach Agent`
- **Description:** `Continues WellNest's own calls to patients: appointment reminders, checks after a visit, waitlist slots and ready lab reports. Knows why we called, confirms or changes the appointment, records how the patient feels, books call backs and saves the outcome.`
- **Agent Instructions:** see the block below.
- **Advanced settings:** Require authentication **off** · Use Knowledge Management **off**.

```
You are WellNest Hospitals' outreach assistant. WellNest calls patients by itself: appointment reminders, a check after a visit, a waitlist slot that has opened, or a lab report that is ready. You take over when the patient chooses to talk to the assistant or says "you called me".

1. CONTEXT FIRST: If you do not have the patient's mobile number, ask for it. Then call get_call_context with the mobile number and say its message. If it finds no recent call, say so and help with what they need.
2. APPOINTMENT REMINDER: If they will come, call confirm_appointment with the booking ID and mobile number. If they want another day or time, ask for their date of birth and the new day and time exactly as they say them, then call reschedule_appointment with the booking ID.
3. AFTER A VISIT: Ask about pain from 0 to 10, fever, and whether they feel worse, then call record_checkin with their mobile number and date of birth. Warning answers alert a nurse automatically. If it sounds like an emergency (chest pain, breathing trouble, heavy bleeding, fainting), tell them to call 108 now.
4. WAITLIST SLOT OR LAB REPORT: Say what get_call_context told you. If they want the slot, include the offer code in your answer so it can be booked; if they want the report, include the report ID so it can be emailed. Never read out or explain lab results.
5. NOT NOW: If they are busy or ask us to call later, call record_call_outcome with outcome call_back_later and call_back_at as they said it (for example "tomorrow at 5 pm").
6. END: Call record_call_outcome once at the end with the outcome and a one-sentence summary. If they say "stop calling me", use opted_out. If the person is not the patient, use wrong_person and share nothing.

Return each tool's message in full. Never repeat the patient's mobile number, date of birth or email. Never give medical advice. Keep replies short and natural for a phone call.
```

**Skills (5/5)** — + Add Skill → **MCP** → server `WellNest_TeamXYZ_MCP` → tool; the description fills in.
| # | Tool | Inputs → Variables |
|---|---|---|
| 1 | `get_call_context` | phone → `patient_phone` · call_id → `call_id` |
| 2 | `confirm_appointment` | booking_id\* → `booking_id` · phone\* → `patient_phone` · date_of_birth → `date_of_birth` |
| 3 | `reschedule_appointment` | booking_id\* → `booking_id` · new_date\* → `appointment_date` · new_time\* → `appointment_time` · phone → `patient_phone` · date_of_birth → `date_of_birth` · doctor_name → `doctor_name` |
| 4 | `record_checkin` | phone\* → `patient_phone` · date_of_birth\* → `date_of_birth` · booking_id → `booking_id` · pain_score → `pain_score` · fever → `has_fever` · symptoms_worse → `symptoms_worse` · notes → `conversation_summary` |
| 5 | `record_call_outcome` | phone\* → `patient_phone` · outcome\* → `call_outcome` · summary → `conversation_summary` · call_id → `call_id` · call_back_at → `callback_time` |

**Conditions:** replace the whole box with
```
1. Support Agent: FIRST CHECK. Chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure, poisoning or suicidal thoughts (urgent handoff). Also: wants a person, a call back or to complain; asks what they talked about with us before; asks about a handoff; asks us to remember something.
2. Outreach Agent: says WellNest just called them, was transferred from a WellNest reminder, follow-up, waitlist or lab report call, or answers a question we asked on that call.
3. Booking Agent: wants a NEW appointment, test or scan; asks if or when a doctor or department is free or next available, on any day; is a new patient to register; wants to check their details are on file; wants to JOIN or be added to a waitlist (no booking needed).
4. Changes Agent: wants to see, cancel or reschedule an EXISTING booking; asks if they are on a waitlist; has a waitlist OFFER CODE to accept.
5. Care Assist Agent: wheelchair, escort, interpreter or transport help; sending booking details to a son, daughter, caregiver or family member; adding a caregiver; language or time preferences.
6. Records Agent: lab or scan reports, emailing a report, past visits, prescription refills.
7. Billing & Insurance Agent: insurance, cashless, coverage, pre-approval, estimates, bills, paying.
8. Aftercare Agent: after a visit or new medicine reports how they feel, wants a nurse to call, gives feedback or a rating, wants a follow-up.
9. Info Agent: symptoms and which department to see (non-urgent); doctors, their days, fees and languages; address, parking, visiting, food, facilities, hospital policies and other hospital questions; preparing for a test or visit.
```
Panel **Save**, then top **Save**. Test in **Test → Chat**: "Hi, you just called me about my appointment, my number is 9845000001" (after
triggering a reminder for WN-48213 in step 6).

### 5. Render environment (5 min)
| Variable | Value |
|---|---|
| `OUTBOUND_ENABLED` | `true` |
| `TALKDESK_ACCOUNT` | `pesit-hackathon` |
| `TALKDESK_CLIENT_ID`, `TALKDESK_CLIENT_SECRET` | from step 1 |
| `TALKDESK_OUTBOUND_FLOW_ID` | from step 3 |
| `TALKDESK_REGION` | `td-us-1` |
| `OUTBOUND_TEST_NUMBER` | a teammate's real phone in E.164 (e.g. `+9198…` or a US number); every call goes there |
| `OUTBOUND_WEBHOOK_TOKEN` | a new random string, the same as in the step 2 header |

### 6. Test (5 min)
1. `https://teamxyz-mcp.onrender.com/api/ops/outbound?token=<DASHBOARD_TOKEN>` → `"mode": "talkdesk"`,
   `missing_settings: []`.
2. Call now: `curl -X POST "https://teamxyz-mcp.onrender.com/api/ops/outbound/call?token=<DASHBOARD_TOKEN>&booking_id=WN-48213"`
   (add `&kind=post_visit_followup` and a completed booking ID for a follow-up). The test phone rings.
3. Press 1 → hear the confirmation → the call shows `completed / confirmed` on `/api/ops/outbound` and in the
   dashboard activity feed. Press 3 → you are forwarded to the AI receptionist; say "you just called me about my
   appointment", give the mobile number 9845000001, and confirm by voice.
4. Autonomous: the cron job already calls `/jobs/run` every minute; it queues and places calls for any persona
   booking 2–26 hours ahead (and follow-ups the day after a visit) with no human action.

## Limits (be honest in the demo)
- **International calls:** the sandbox number is US-based; calls to Indian mobiles may be blocked or charged. Test
  one call to the test number first. If it fails, use a US number or Talkdesk's softphone as the test number.
- **AI on the outbound leg:** not available directly in API-request flows (see above); the AI joins through the
  forward on option 3. The forwarded call may reach the AI from our own number, so the Outreach agent asks for the
  mobile number before `get_call_context`.
- **Execute Action** must be able to reach our server (Builder connection). Without it, calls still go out, but
  outcomes arrive only through the AI agent; set `OUTBOUND_MAX_ATTEMPTS=1` so unreported calls are not retried.
- Talkdesk allows 2 Flows API requests per second; the dispatcher starts at most `OUTBOUND_MAX_PER_RUN` per minute.
