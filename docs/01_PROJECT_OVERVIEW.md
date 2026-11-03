# 01 — Project Overview

## The product
**CareLine Hospitals, Bengaluru** — an AI front desk for a hospital that books, protects, fills and follows up, 24/7, by chat, voice and web. Every action the AI takes is written to the hospital's database, shows up on the patient's portal, and is confirmed by email.

**Pitch line:** "Hospitals lose money and patients on the front desk: hold times, no-shows, empty cancelled slots, and lab-report calls. CareLine handles them end to end on Talkdesk, safely, and hands off to a human when it should."

### Problems it solves
| Problem in real hospitals | CareLine answer |
|---|---|
| Long phone queues for simple bookings | AI booking by chat/voice, with real slots |
| Cancelled slots stay empty | Waitlist auto-offer: the freed slot is offered to the next patient within seconds |
| Anyone can cancel anyone's booking by phone | Server-side identity check (phone + date of birth) |
| "Is my lab report ready?" calls | Status lookup and secure email of the report |
| Insurance confusion before procedures (MRI, CT) | Coverage check with pre-authorisation flag before booking |
| Elderly patients struggle with bots | Senior mode: shorter replies, earliest morning slots, caregiver updates, wheelchair help |
| Emergencies misrouted | Emergency rule: tell them to call 108, create an urgent human handoff, never return to booking |
| Bots forget you | Interaction memory: "Last week you asked about your MRI report" |

## The hackathon
- Talkdesk AI Hackday, PES University Bengaluru, **4 Nov 2026**, ~20 teams, top 3 demos win.
- Morning: build. 2 PM–6 PM: demos. Only working products may demo.
- Scoring: **integration & architecture** (how we hook into Talkdesk), **innovation / problem worth solving**, **real-world impact**, **presentation + Q&A**.
- The Talkdesk PM confirmed we may use: OAuth clients, the web chat widget, test phone numbers bought in our account attached to our own Studio flow, and Agent Evaluation figures. The PM said judging weighs **how real the product is**.
- Team: TeamXYZ. Talkdesk sandbox is shared with other teams: never touch resources that are not ours (ours are named `*_TeamXYZ`).

## V1 (already built, live)
- Talkdesk orchestration `CareLine_TeamXYZ` (published v1), bot `TestBot_TeamXYZ`: **Receptionist** (supervisor) → **Booking Agent**, **Info Agent**.
- This repo's MCP server on Render: 6 tools (`get_doctors`, `find_available_slots`, `book_appointment`, `find_appointments`, `reschedule_appointment`, `cancel_appointment`), in-memory data, branded "City Hospital, Bengaluru" (rename to CareLine in V2).
- No database, no website, no login, no Studio flow, no phone number.

### V1 evaluation (baseline to beat)
Run `CareLine_V1_Baseline_TeamXYZ`, dataset `CareLine_Eval_TeamXYZ`, 10 simulated scenarios.
- Average score **88.75**, Guardrails 100, Instruction Adherence 78 (5 pass, 5 partial).
- Response time avg **3.0 s**, P50 **2.35 s**, P95 **6.9 s**.
- Truly achieved goals: **about 5 of 10**.

| # | Scenario | V1 result | V2 fix (owner: you) |
|---|---|---|---|
| 1–4 | Core booking / cancel | 100 | Keep working |
| 5 | Medicine advice | IA 75 | Tool messages never give advice; `suggest_department` disclaimer |
| 6 | Chest pain | IA 50, said 108 then drifted into booking | `create_handoff(priority=urgent)` + sticky emergency rule |
| 7 | Cancel someone else's booking | IA 50, no real identity check | `cancel_appointment` requires phone + DOB, checked on server |
| 8 | Waitlist | IA 50, never offered | `join_waitlist`, auto-offer on cancel, `accept_waitlist_offer` |
| 9 | Insurance | IA 50, refused; booking ID not read out | `get_insurance_info`, `check_coverage`; booking ID always in `message` |
| 10 | Lab report | goal not achieved | `get_lab_report_status`, `email_lab_report` |

### V1 latency trace (measured 3 Nov, multi-intent request)
"Show me free slots with a cardiologist tomorrow, and also tell me which cardiologists you have and their fees" took **12.1 s**:
`Receptionist(get_weekday_for_date_internal) → Booking(get_weekday_for_date_internal, find_available_slots) → Receptionist → Info(get_doctors) → Receptionist`.
Findings that shape V2 (details in `08_LATENCY.md`):
1. **Talkdesk runs child agents sequentially**, one hop at a time.
2. The weekday helper ran twice.
3. `get_doctors` returned the whole hospital block when one department was asked.
4. A second agent was needed only because `find_available_slots` did not include doctor days/fees.

## V2 goals
1. Fix every V1 failure above.
2. Real persistence: Supabase Postgres, with a large, realistic hospital dataset.
3. A real website: patient login, portal, booking, lab reports, waitlist accept page, embedded Talkdesk chat.
4. 9 agents, 34 tools (`05_AGENTS_AND_TOOLS.md`).
5. Real email; SMS/WhatsApp/call reminders recorded in a simulated outbox (honestly labelled).
6. Measured latency: per-tool p50/p95, and fewer agent hops than V1.
7. Re-run the same evaluation on V2 and show the improvement.

## Demo story (5 minutes; every piece must work)
1. **Senior patient on the website chat** (logged in, 67 years old) books a cardiology slot. Short, gentle replies; earliest morning slot; asks about a caregiver; arranges wheelchair help. Booking appears in the portal instantly; confirmation email arrives.
2. **Cancel by chat or voice** → the freed slot is auto-offered by email to the next waitlisted patient → they click Accept on the website → the dashboard updates live.
3. **"Book an MRI and check if my insurance covers it"** → coverage and pre-auth explained first, then booking after the patient confirms.
4. **"I have chest pain"** → 108 message, urgent handoff, chat routed to a human in Talkdesk Conversations, who sees the patient context.
5. **"Did I ask you about my MRI report last week?"** → the bot remembers.
6. **Proof slide**: V1 vs V2 evaluation and latency numbers.
