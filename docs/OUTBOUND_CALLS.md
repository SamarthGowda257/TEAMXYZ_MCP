# Autonomous outbound calls (reminders and post-visit follow-ups)

## What it does
WellNest calls patients by itself. Nobody presses a button:

| Call | When | Patient can |
|---|---|---|
| **Appointment reminder** | the day before a booked visit (2–26 h ahead) | 1 confirm · 2 change (text with link + call back) · 3 talk to the AI assistant · 9 stop calls |
| **Post-visit follow-up** | the day after a completed doctor visit | 1 feeling better (check-in saved) · 2 problem (nurse alert) · 3 AI assistant · 9 stop calls |

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

### 1. Talkdesk: OAuth client (5 min)
Builder → **OAuth Clients** → Create: name `WellNest_Outbound_TeamXYZ`, grant type **Client Credentials**, scope
**`flows-interactions:start`**. Copy the client ID and secret (straight into Render, never into chat).

### 2. Talkdesk: Builder connection for the webhook (10 min)
Builder → **Connections** → Create `WellNest_TeamXYZ`, base URL `https://teamxyz-mcp.onrender.com`, header
`X-Outbound-Token: <OUTBOUND_WEBHOOK_TOKEN>`. Add action **`outbound_event`**: `POST /api/outbound/event`, JSON body
`{"call_id": "<string>", "event": "<string>", "choice": "<string>"}`, outputs `say` (string), `action` (string),
`outcome` (string).

### 3. Talkdesk: Studio flow `WellNest_Outreach_TeamXYZ` (20 min)
Studio → Create flow → **API request** trigger.
1. **API request** input arguments (all strings, each to a flow variable of the same name): `call_id`,
   `patient_phone`, `patient_name`, `call_type`, `prompt`, `booking_id`.
2. **Make Outbound Call**: caller ID = our Talkdesk number; destination = `patient_phone`; ring time 30 s.
   - *No answer* → Execute Action `outbound_event` (call_id=`call_id`, event=`no_answer`) → End Flow.
     Do the same for *Busy* (`busy`) and *Invalid number* (`invalid_number`).
   - *Answered* → Execute Action `outbound_event` (event=`answered`) → next step.
3. **Input IVR** (or **Voice IVR** for spoken answers), message (text-to-speech): `%{current_flow.prompt}`.
   Options 1, 2, 3, 9; no input → repeat once → End Flow.
4. For each option N: **Execute Action** `outbound_event` (call_id=`call_id`, event=`choice`, choice=`N`, output
   `say` → flow variable `say`) → **Play Audio** text-to-speech `%{current_flow.say}` → End Flow.
   For option **3**: after Play Audio → **Forward to External Number** = the AI voice number (the Studio voice flow
   that connects to Autopilot).
5. Save → **Publish**. Open **Request details** on the flow and copy the **flow ID**.

### 4. Talkdesk: Outreach agent (10 min)
Add agent **Outreach Agent** next to the others.
- **Description:** `Continues WellNest's outbound reminder and follow-up calls: knows why we called, confirms or changes the appointment, takes how the patient feels, and records the outcome.`
- **Instructions:**
```
The patient was just called by WellNest (an appointment reminder or a check after a visit) and chose to talk to you.
1. Ask for their mobile number if you do not have it, then call get_call_context to learn why we called. Say its message.
2. Reminder: if they will come, call confirm_appointment with the booking ID and mobile number. If they want another time, ask for their date of birth and the new day and time, then call reschedule_appointment.
3. Follow-up: ask about pain (0 to 10), fever and whether they feel worse, then call record_checkin with their mobile number and date of birth. Warning answers alert a nurse. If it sounds like an emergency, tell them to call 108 now.
4. At the end call record_call_outcome once with the outcome (confirmed, rescheduled, reschedule_requested, feeling_well, needs_help, opted_out, wrong_person, call_back_later or question_answered) and a one-sentence summary. If they say "stop calling me", use opted_out.
Return each tool's message in full. Never repeat the patient's mobile number or date of birth.
```
- **Skills (5):** `get_call_context` (phone → `patient_phone`, call_id → leave empty), `confirm_appointment`
  (booking_id → `booking_id`, phone → `patient_phone`, date_of_birth → `date_of_birth`), `record_call_outcome`
  (phone → `patient_phone`, outcome → new variable `call_outcome` "how the call ended: confirmed, rescheduled,
  reschedule_requested, feeling_well, needs_help, opted_out, wrong_person, call_back_later or question_answered",
  summary → `conversation_summary`), `reschedule_appointment` (as on the Changes agent), `record_checkin` (as on
  the Aftercare agent).
- **Conditions:** add as line 2 (after Support):
  `2. Outreach Agent: the caller says WellNest just called them, was transferred from a WellNest reminder or follow-up call, or wants to confirm an appointment we called about.`
- Refresh the MCP server `TeamXYZ_MCP` first so the 3 new tools appear (37 in total).

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
