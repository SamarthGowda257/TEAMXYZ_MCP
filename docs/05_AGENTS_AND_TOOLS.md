# 05 — Agents and Tools

The agents are configured by humans in Talkdesk. The tools are yours. This file is the **contract** between the two: names and inputs here must match the code exactly, because the Talkdesk team maps them by name.

## 1. The response envelope (every tool)
```json
{
  "ok": true,
  "message": "Booked. Dr. Rajesh Iyer, Wednesday 4 November at 10:30 AM, room OPD-310, fee 1,200 rupees. Your booking ID is CL-4821.",
  "data": { "booking_id": "CL-4821", "booking_id_spoken": "C L 4 8 2 1", "...": "..." },
  "related": [ { "kind": "coverage", "text": "Star Health covers this consultation with a 10% co-pay." } ],
  "error_code": null
}
```
Rules:
- `message`: complete, self-contained, speakable, ≤ 3 sentences (≤ 2 for seniors). The agent may read it verbatim. No markdown, no emojis, money as "1,200 rupees", dates as "Wednesday 4 November", times as "10:30 AM".
- `data`: only fields the agent might need next (IDs, chosen slot, flags). Lists capped at 3.
- `related`: optional, up to 3 blackboard facts the agent should know (see `07_CONTEXT_BLACKBOARD.md`). Omit when empty.
- On failure: `ok:false`, `error_code` from the shared list, and a `message` that says what to do next ("Please share your registered phone number and date of birth so I can check.").
- Total size ≤ ~1 KB. Never raise to Talkdesk.
- Senior patients (`is_senior` known from session) get the short message variant.

## 2. Agents (configured in Talkdesk)
| Agent | Purpose | Skills (≤5) |
|---|---|---|
| **Receptionist** (supervisor) | Greets, detects emergencies first, routes, combines answers. Only agent that speaks to the patient. | none |
| **Booking** | New appointments and procedures | `verify_patient`, `register_patient`, `find_available_slots`, `book_appointment`, `join_waitlist` |
| **Changes** | Existing bookings | `verify_patient`, `find_appointments`, `reschedule_appointment`, `cancel_appointment`, `accept_waitlist_offer` |
| **Records** | Lab reports, history, refills | `verify_patient`, `get_lab_report_status`, `email_lab_report`, `get_visit_history`, `request_prescription_refill` |
| **Billing & Insurance** | Coverage, bills | `verify_patient`, `get_insurance_info`, `check_coverage`, `get_bill_status`, `send_payment_link` |
| **Info** | General questions | `get_doctors`, `suggest_department`, `get_hospital_info`, `get_visit_instructions` |
| **Care Assist** | Seniors and caregivers | `verify_patient`, `get_patient_preferences`, `set_patient_preferences`, `request_assistance`, `send_caregiver_update` |
| **Support** | Emergencies, humans, memory | `request_callback`, `create_handoff`, `get_handoff_status`, `save_interaction_note`, `search_past_interactions` |
| **Aftercare** | After a visit | `verify_patient`, `record_checkin`, `flag_nurse_alert`, `submit_feedback`, `schedule_followup` |

Routing order in the Receptionist's Conditions: 1 emergency → Support, 2 new booking → Booking, 3 change/cancel → Changes, 4 reports/history → Records, 5 money/insurance → Billing, 6 senior/caregiver help → Care Assist, 7 after a visit → Aftercare, 8 everything else → Info.

**Shared Talkdesk variables** (the team creates them; your input names should match these where possible):
`patient_phone`, `date_of_birth`, `patient_name`, `patient_email`, `is_senior`, `appointment_date`, `appointment_time`, `time_preference`, `department`, `doctor_name`, `procedure`, `booking_id`, `offer_code`, `insurance_provider`, `coverage_result`, `selected_slot`, `callback_time`, `handoff_summary`, `priority`, `symptoms`.

## 3. Input conventions
- `phone`: any Indian format; normalised to E.164 `+91XXXXXXXXXX`.
- `date_of_birth`: `YYYY-MM-DD` preferred; accept `DD/MM/YYYY`, `4 March 1958`.
- `date`: `YYYY-MM-DD`, or `today`, `tomorrow`, weekday names (next occurrence), `4 Nov`. Always echo `date_iso` and `weekday` in `data`.
- `time`: `HH:MM` 24h or `10:30 AM`.
- `time_preference`: `morning` (before 12:00), `afternoon` (12:00–17:00), `evening`, `any`.
- All inputs are strings unless noted. Optional inputs may arrive as empty strings: treat `""` as missing.

## 4. Tool contracts (34)
Legend: **V** = requires phone + date_of_birth verified on the server. **W** = writes data. **(V1)** = existing tool, keep name and old params.

### Booking
| Tool | Inputs | Returns `data` | Notes |
|---|---|---|---|
| `verify_patient` | `phone`, `date_of_birth` | `patient_ref`, `name`, `age`, `is_senior`, `upcoming[≤3]` (booking_id, date, time, doctor), `pending_reports` count, `insurer`, `recent_notes[≤3]`, `caregiver_on_file` bool | P1 snapshot. Triggers async prefetch. Generic failure message; lockout after 5 fails/15 min. |
| `register_patient` **W** | `name`, `phone`, `date_of_birth`, `email`, `gender?`, `insurance_provider?` | `patient_ref`, `is_senior` | Rejects duplicate phone with `already_exists` ("You're already registered…"). |
| `find_available_slots` (V1) | `date`, `department?`, `doctor_name?`, `time_preference?`, `procedure?` | `date_iso`, `weekday`, `doctors[≤3]`: name, fee, room, days, hours, languages, `free_slots[≤3]`; `notes[]` (e.g. "Dr. Kavya Reddy does not consult on Wednesdays") | Must include days/hours/fee of every doctor in the department, so the Info agent isn't needed. If nothing free: suggest the next date with slots and mention the waitlist. |
| `book_appointment` (V1) **W** | `phone`, `doctor_name`, `date`, `time`, `patient_name?`, `date_of_birth?`, `reason?`, `procedure?`, `idempotency_key?` | `booking_id`, `booking_id_spoken`, doctor, date, time, room, fee, `instructions_short` | Atomic. Same patient+slot twice → returns existing booking. Unknown phone without DOB → book as guest (V1 compatibility) and say "please register to manage it later". Queues confirmation email; writes resolution. |
| `join_waitlist` **W** | `phone`, `date_of_birth`, `department?`, `doctor_name?`, `date_from`, `date_to?`, `time_preference?` | `waitlist_id`, position | **V**. Explains they'll get an email if a slot frees up. |

### Changes
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `find_appointments` (V1) | `phone`, `date_of_birth?`, `include_past?` | `appointments[≤3]` | Without DOB: return count only and ask for DOB (privacy). With DOB: **V**, full list. |
| `reschedule_appointment` (V1) **W** | `booking_id`, `phone`, `date_of_birth`, `new_date`, `new_time` | new booking details | **V**, own booking only. Frees old slot → waitlist offer. |
| `cancel_appointment` (V1) **W** | `booking_id`, `phone`, `date_of_birth`, `reason?` | `cancelled: true`, `slot_released: true` | **V**, own booking only; others' bookings → `not_allowed` with generic message. Triggers waitlist auto-offer. |
| `accept_waitlist_offer` **W** | `offer_code`, `phone` | booking details | Code must match phone; expired/taken → clear message + next option. |

### Records
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `get_lab_report_status` | `phone`, `date_of_birth` | `reports[≤3]`: report_id, test name, status, ready_at / expected_at | **V** |
| `email_lab_report` **W** | `phone`, `date_of_birth`, `report_id?` | `sent_to` (masked email) | **V**. Only `ready` reports. Default: latest ready. Email has summary + portal link, not values. |
| `get_visit_history` | `phone`, `date_of_birth` | `visits[≤5]` | **V** |
| `request_prescription_refill` **W** | `phone`, `date_of_birth`, `medicine_name`, `doctor_name?` | `request_id`, status `pending_doctor` | **V**. Never approves itself. |

### Billing & Insurance
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `get_insurance_info` | `insurance_provider?` | accepted, mode (cashless/reimbursement), documents, TPA desk hours | No verification needed. Without provider: list top 5 accepted. |
| `check_coverage` | `insurance_provider?`, `procedure?`, `department?`, `phone?`, `date_of_birth?` | `covered` (yes/partial/no), `estimated_patient_share_inr`, `preauth_required`, `preauth_turnaround` | If phone+DOB given and valid, use the patient's policy. Always say it is an estimate. Store result on blackboard. |
| `get_bill_status` | `phone`, `date_of_birth` | `bills[≤3]` | **V** |
| `send_payment_link` **W** | `phone`, `date_of_birth`, `bill_id?` | `sent_to` (masked) | **V**. Simulated link. |

### Info
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `get_doctors` (V1) | `department?`, `doctor_name?` | `doctors[≤5]`: name, department, days, hours, fee, languages, room | No hospital block unless nothing is passed (then departments list only). |
| `suggest_department` | `symptoms` | `department`, `emergency` bool, `disclaimer` | Rule-based keyword map. Red flags (chest pain, breathlessness, stroke signs, heavy bleeding, unconsciousness, suicidal thoughts) → `emergency: true` and message "This may be an emergency. Please call 108 now." |
| `get_hospital_info` | `topic?` (address, hours, parking, visiting, emergency, facilities, pharmacy) | text facts | Cached. |
| `get_visit_instructions` | `department?`, `procedure?` | fasting, documents, arrive_before_min | Cached. |

### Care Assist
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `get_patient_preferences` | `phone`, `date_of_birth` | language, preferred time, caregiver (masked), consent, mobility | **V** |
| `set_patient_preferences` **W** | `phone`, `date_of_birth`, `preferred_language?`, `preferred_time?`, `caregiver_name?`, `caregiver_phone?`, `caregiver_email?`, `caregiver_consent?` (yes/no), `mobility_needs?` | updated prefs | **V** |
| `request_assistance` **W** | `booking_id`, `phone`, `assistance_type` (wheelchair, escort, interpreter, transport_desk), `notes?` | `assistance_id` | Must be the patient's own booking. |
| `send_caregiver_update` **W** | `phone`, `date_of_birth`, `booking_id?` | `sent_to` (masked) | **V**. Requires consent = yes. |

### Support
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `request_callback` **W** | `phone`, `preferred_time`, `reason` | `callback_id`, slot confirmed | No DOB needed. |
| `create_handoff` **W** | `summary`, `priority` (urgent/normal), `phone?`, `reason_code?` (emergency, complaint, complex, requested_human) | `handoff_id`, `say` | urgent → message starts "Please call 108 now if this is an emergency." and asks them to stay on while a team member joins. Shows on dashboard instantly. |
| `get_handoff_status` | `handoff_id` | status, assigned | |
| `save_interaction_note` **W** | `phone`, `summary`, `topics?` (comma list), `outcome?` | `note_id` | The agent calls this at the end of a meaningful conversation. Max 500 chars summary. No DOB required (write-only, cannot leak). |
| `search_past_interactions` | `phone`, `date_of_birth`, `query` | `matches[≤3]`: date, summary | **V**. Full-text over notes + resolutions; vector search when enabled. |

### Aftercare
| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `record_checkin` **W** | `phone`, `date_of_birth`, `booking_id?`, `pain_score?` (0–10), `fever?` (yes/no), `symptoms_worse?` (yes/no), `notes?` | `checkin_id`, `alert_raised` | **V**. Warning answers auto-call `flag_nurse_alert` logic. |
| `flag_nurse_alert` **W** | `phone`, `reason` | `alert_id` | Shows on dashboard. |
| `submit_feedback` **W** | `phone`, `rating` (1–5), `comment?`, `booking_id?` | `feedback_id` | |
| `schedule_followup` **W** | `phone`, `date_of_birth`, `doctor_name?`, `within_days?` | suggested slots or booking | **V**. Reuses booking service. |

### Legacy
- `get_weekday_for_date_internal`: if it exists in `server.py`, keep it unchanged.

## 5. Tool descriptions (write them like this)
```
find_available_slots:
  "Find free appointment slots for a date, by department, doctor or procedure.
   Also returns each doctor's consulting days, hours, fee and room, so you do not
   need get_doctors for the same question. Use before book_appointment."
  inputs:
    date: "Date as YYYY-MM-DD, or words like 'tomorrow' or 'Monday' (Asia/Kolkata)."
    department: "Optional. e.g. Cardiology, Orthopaedics."
    doctor_name: "Optional. e.g. Dr. Rajesh Iyer."
    time_preference: "Optional. morning, afternoon, evening or any."
    procedure: "Optional. e.g. MRI Brain, CT Chest, X-Ray."
```

## 6. Example runs (expected agent paths)
**A. "Book an MRI next week and check if Star Health covers it"**
```
Receptionist → Booking: verify_patient → find_available_slots(procedure=MRI Brain)
Receptionist → Billing: check_coverage(Star Health, MRI Brain)   (result stored on blackboard)
Receptionist: "Star Health covers it with pre-approval (about 24 hours). Free slots: Tuesday 10 AM, Wednesday 2 PM. Which one?"
Patient: "Tuesday" → Booking: book_appointment → response.related includes the coverage fact
```
**B. Cancel → waitlist**
```
Changes: verify_patient → cancel_appointment → backend frees slot → offer emailed to next waitlisted patient
Other patient: accept link on website (or accept_waitlist_offer by chat) → booked → dashboard updates
```
**C. "I have chest pain"** → Support: `create_handoff(priority=urgent, reason_code=emergency)` → 108 message → Studio escalates to a human.

**D. "Did I ask you about my MRI report last week?"** → Records/Booking `verify_patient` returns `recent_notes`; if not there → Support `search_past_interactions(query="MRI report")`.
