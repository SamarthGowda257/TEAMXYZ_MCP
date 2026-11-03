# 03 — Requirements

Priority: **P0** must, **P1** should, **P2** could. IDs are referenced from tests and the build plan.

## Functional requirements

### FR-A Identity & patients
| ID | Requirement | P |
|---|---|---|
| FR-A1 | `verify_patient(phone, date_of_birth)` returns a patient snapshot (P1 context: name, age, `is_senior`, upcoming appointments ≤3, pending lab reports, insurance, last 3 interaction summaries, caregiver on file) or a clear "not verified" result. | P0 |
| FR-A2 | Failed verification never reveals whether the phone exists ("I couldn't verify those details"). Lock a phone after 5 failed attempts in 15 min. | P0 |
| FR-A3 | `register_patient` creates a new patient (name, phone, DOB, email, optional gender, insurer). Rejects duplicates by phone. | P1 |
| FR-A4 | Website login via Supabase Auth (email + password). On first login the user links to their patient record with phone + DOB, or creates one. | P1 |
| FR-A5 | One role only: **patient**. A patient can only read/write their own data through `/api`. | P1 |

### FR-B Appointments
| ID | Requirement | P |
|---|---|---|
| FR-B1 | `find_available_slots` by date (+ department or doctor, + morning/afternoon/any). Returns ≤3 slots per doctor, ≤3 doctors, and for each doctor: days, hours, fee, room, languages. Includes the resolved weekday. | P0 |
| FR-B2 | `book_appointment` books a slot atomically (no double booking), returns booking ID (+ spoken form), doctor, date, time, room, fee, pre-visit instruction summary; queues a confirmation email. Idempotent for the same patient + slot. | P0 |
| FR-B3 | `find_appointments` lists a verified patient's upcoming (and optionally past) appointments. | P0 |
| FR-B4 | `reschedule_appointment` (verified) moves a booking to a new free slot atomically; old slot is freed and triggers waitlist offers. | P0 |
| FR-B5 | `cancel_appointment` (verified, own booking only) cancels, frees the slot, triggers waitlist auto-offer. | P0 |
| FR-B6 | Bookings for procedures (MRI, CT, X-ray, ultrasound, blood tests…) use the same slot model with `procedure_code`. | P1 |
| FR-B7 | Website: book from the portal with the same rules and same data. | P1 |

### FR-C Waitlist
| ID | Requirement | P |
|---|---|---|
| FR-C1 | `join_waitlist` for a department or doctor and a date range, with time preference. | P0 |
| FR-C2 | When a slot is freed, the backend finds the best matching waitlist entry (priority: urgency flag, then senior, then earliest joined), creates an offer with a code valid 30 min, emails an accept link, writes a simulated SMS. | P0 |
| FR-C3 | `accept_waitlist_offer(offer_code, phone)` and the website accept page book the slot if still free. First to accept wins; expired or taken offers return a clear message and offer the next option. | P0 |
| FR-C4 | Offer expiry is handled by the jobs runner: expired offers move to the next waitlisted patient. | P1 |

### FR-D Records
| ID | Requirement | P |
|---|---|---|
| FR-D1 | `get_lab_report_status` (verified): list recent reports with status `pending` / `ready` / `collected`, expected time for pending. | P0 |
| FR-D2 | `email_lab_report` (verified): emails a ready report (summary + "view in portal" link; no full medical values in email body) to the registered email only. | P0 |
| FR-D3 | `get_visit_history` (verified): last 5 visits (date, doctor, department). | P1 |
| FR-D4 | `request_prescription_refill` (verified): creates a request for the doctor's approval; never approves itself. | P2 |
| FR-D5 | Website: lab reports page with status and a report view. | P1 |

### FR-E Insurance & billing
| ID | Requirement | P |
|---|---|---|
| FR-E1 | `get_insurance_info(provider?)`: accepted insurers, cashless or reimbursement, documents needed, TPA desk hours. | P0 |
| FR-E2 | `check_coverage` (verified, or by provider name only): for a procedure or department, returns covered yes/no/partial, estimated patient share, pre-authorisation required and turnaround. Clearly labelled as an estimate. | P0 |
| FR-E3 | `get_bill_status` (verified): outstanding bills with amount and due date. | P2 |
| FR-E4 | `send_payment_link` (verified): emails a simulated payment link; never takes card details. | P2 |

### FR-F Information
| ID | Requirement | P |
|---|---|---|
| FR-F1 | `get_doctors(department?, doctor_name?)`: only the asked doctors; no hospital block unless asked. | P0 |
| FR-F2 | `suggest_department(symptoms)`: keyword/rule-based routing to a department with a "this is not medical advice" line; red-flag symptoms return `emergency: true`. | P1 |
| FR-F3 | `get_hospital_info(topic)`: address, hours, parking, visiting rules, facilities, emergency number. | P1 |
| FR-F4 | `get_visit_instructions(department or procedure)`: fasting, documents, arrival time. | P1 |

### FR-G Senior care
| ID | Requirement | P |
|---|---|---|
| FR-G1 | `is_senior = age >= 60`, returned by `verify_patient` and stored for the session. | P0 |
| FR-G2 | `get_patient_preferences` / `set_patient_preferences`: preferred language, preferred time of day, caregiver name/phone/email, consent to update caregiver, mobility needs. | P1 |
| FR-G3 | `request_assistance(booking_id, type)`: wheelchair, escort, interpreter, transport desk. Shown on the booking. | P1 |
| FR-G4 | `send_caregiver_update`: emails the caregiver the booking details if consent is on. | P2 |
| FR-G5 | Every tool `message` for a senior patient is shorter: one short sentence per fact, ≤3 facts, no option lists longer than 2. | P1 |

### FR-H Safety & human
| ID | Requirement | P |
|---|---|---|
| FR-H1 | `create_handoff(summary, priority, phone?)`: records a handoff (urgent/normal) and returns what to say. For urgent: "Please call 108 now…". | P0 |
| FR-H2 | `request_callback(phone, preferred_time, reason)`. | P1 |
| FR-H3 | `get_handoff_status(handoff_id)`. | P2 |

### FR-I Memory
| ID | Requirement | P |
|---|---|---|
| FR-I1 | Every state-changing tool writes a `resolutions` row (who, what, when, result). | P0 |
| FR-I2 | `save_interaction_note(phone, summary, topics)` stores a short summary of the conversation. | P1 |
| FR-I3 | `search_past_interactions(phone, date_of_birth, query)` searches notes + resolutions for that patient (full-text; vector search if embeddings are enabled). | P1 |
| FR-I4 | `verify_patient` includes the last 3 summaries so most memory questions need no extra call. | P1 |

### FR-J Aftercare
| ID | Requirement | P |
|---|---|---|
| FR-J1 | Jobs runner sends a day-2 post-visit check-in email with a link to a short form. | P2 |
| FR-J2 | `record_checkin`, `flag_nurse_alert` (warning answers), `submit_feedback`, `schedule_followup`. | P2 |

### FR-K Notifications & jobs
| ID | Requirement | P |
|---|---|---|
| FR-K1 | Every outbound message is a `notifications` row (channel, template, payload, status: queued/sent/failed/simulated). | P0 |
| FR-K2 | Email sender runs in the background (never inside a tool call). If SMTP env vars are missing, emails are marked `simulated`. | P0 |
| FR-K3 | `POST /jobs/run` (token protected) runs: appointment reminders (24 h and 2 h before), waitlist offer expiry, birthday wishes (P2), aftercare check-ins (P2). Safe to call every minute; idempotent. | P1 |

### FR-L Website & dashboard
| ID | Requirement | P |
|---|---|---|
| FR-L1 | Public pages: home, doctors & departments, insurance, contact. Patient pages: login/signup, portal home, book, my appointments, lab reports, profile & preferences. | P1 |
| FR-L2 | Waitlist accept page `/waitlist/accept?code=…` (no login needed; code + phone confirm). | P0 |
| FR-L3 | Read-only operations dashboard `/dashboard?token=…`: today's schedule, recent bookings/cancellations, waitlist offers, handoffs, outbox, per-tool latency. Auto-refresh every 5 s. | P1 |
| FR-L4 | Talkdesk chat widget on every page; context passed after login. | P1 |

## Non-functional requirements

### NFR-1 Latency (details: `08_LATENCY.md`)
- Tool server time (request in → response out): **p50 ≤ 80 ms, p95 ≤ 250 ms** for reads, **p95 ≤ 400 ms** for writes, measured at the app.
- No network call to email/SMS/Talkdesk APIs inside a tool request.
- Responses ≤ ~1 KB JSON (hard cap 2 KB).
- Common single-intent requests need **one** specialist agent (one hop).

### NFR-2 Correctness & concurrency
- No double booking: enforced by a database constraint, not only by code.
- Writes in transactions; idempotency keys for book/cancel/reschedule.
- All times stored as `timestamptz`; hospital timezone `Asia/Kolkata`.

### NFR-3 Security & privacy
- `/mcp`: bearer token, constant-time compare. `/api`: Supabase JWT verified on every request; patient ID always from the token. `/jobs`, `/dashboard`: separate tokens.
- Identity-sensitive tools check phone + DOB server-side; failures are generic; rate-limited.
- Never log full DOB, tokens, or report contents. Mask phones in logs (`+91******2345`).
- Emails never contain full lab values. Payment links never collect card data.
- CORS: only our own origin. HTTPS only (Render provides TLS).
- Health data in this demo is fake; the README states real deployment would need consent, retention rules and DPDP Act compliance.

### NFR-4 Reliability
- `/health` returns DB status and version; Render health check uses it.
- If the DB is unreachable, tools return `ok:false, error_code:"service_unavailable"` with a speakable apology and a suggestion to request a callback.
- Free-tier sleep is countered by an external ping every 5 min.
- Seed script restores the demo dataset in under 30 s.

### NFR-5 Observability
- Each tool call logged as one JSON line: tool, duration_ms, ok, error_code, masked patient ref.
- In-memory rolling metrics: per-tool count, p50, p95, error rate, cache hit rate → `/api/metrics` (dashboard token).
- `X-Response-Time` header on `/api` responses.

### NFR-6 Usability & accessibility
- Website works at 360 px width; WCAG AA contrast; keyboard reachable; visible focus.
- "Larger text" toggle in the header (seniors).
- Tool messages: plain English, speakable, no markdown.

### NFR-7 Maintainability
- Tools are thin: validate → call a service function → format the envelope.
- Business rules live in `services/`, shared by `/mcp` and `/api`, so the bot and the website behave the same.
- Tests: unit tests for services, a smoke script that calls every tool over the real MCP transport.
