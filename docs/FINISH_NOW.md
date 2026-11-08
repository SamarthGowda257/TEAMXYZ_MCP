# Finish line: where we are and what you do (8 Nov 2026)

## Where we are

| Feature | Status |
|---|---|
| Chat: identity, balance, bills, Dolo limits, "what can I order", prescription refusal, ordering, tracking, memory across chats, complaints | **Working live** (tested in the chat on 8 Nov) |
| Refund asks to confirm, "yes" completes it | **Working live**, but a bug refunded the whole balance instead of the 50 asked. **Fixed in code**, waiting for deploy (step 0) |
| "Have I ever ordered anything for my diabetes?" | Answered "no" live. **Fixed in code** (orders now listed with what each medicine is for), waiting for deploy |
| Signed-in chat knows you with no mobile number or date of birth | **Server ready** (deploy, step 0). Needs Talkdesk part A, then a live test with your sign-in (part D) |
| Booking → email | **Done, verified live 8 Nov**: Gmail API sends confirmations and lab reports |
| Booking → Google Calendar | **Done, verified live 8 Nov**: the event lands on the hospital calendar and in the patient's own Google Calendar |
| Phone call: no asking for the number | Built and on Talkdesk; not yet tested on a real call (part D) |

Every booking already queues a confirmation email with the visit details, the booking ID, a calendar invite and an
"Add to Google Calendar" link. Reschedules move the calendar event and cancellations remove it. Once part B is done,
the booking reply also says "A confirmation email with a calendar invite is on its way."

---

## 0. Let me deploy (10 seconds)
Reply **"push to main"**. The server fixes (refund amount, past orders, signed-in details) only go live then.

---

## A. Talkdesk: 3 edits (5 min)
Only these. Don't re-add skills.

### A1. Conditions box: replace (1,989 characters)
**Skip if** it already contains `Every conversation's FIRST message`.
```
1. Support Agent: FIRST CHECK. Every conversation's FIRST message, unless only a hospital information question. Re-route every new topic. Chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure, poisoning, suicidal thoughts (urgent handoff). Also: wants a person, call back or to complain; asks about past chats, a handoff, or what they ordered, booked or asked before; asks us to remember something; asks who they are; their own record with no mobile number known yet.
2. Outreach Agent: says WellNest just called, was transferred from a WellNest call, or answers a question from that call.
3. Booking Agent: NEW appointment, test or scan; if or when a doctor or department is free; new patient registration; checking details on file; joining a waitlist.
4. Changes Agent: see, cancel or reschedule an EXISTING booking; waitlist status; waitlist OFFER CODE.
5. Pharmacy and HealthCredits Agent: buy or order medicine; medicine stock or price; what their prescriptions allow; HealthCredits balance, adding credits, paying a booking or bill with credits. NOT refunds (rule 8).
6. Care Assist Agent: wheelchair, escort, interpreter or transport; sending booking details to family or caregiver; adding a caregiver; letting family use credits; language or time preferences.
7. Records Agent: lab or scan reports, emailing a report, past visits, prescription refill requests, where a medicine order is or cancelling one.
8. Billing and Insurance Agent: insurance, cashless, coverage, pre-approval, estimates, bills, payment links; ANY refund, including HealthCredits back to a bank, card or cash.
9. Aftercare Agent: after a visit or new medicine reports how they feel, wants a nurse to call, gives feedback or a rating, wants a follow-up.
10. Info Agent: non-urgent symptoms and which department; doctors' days, fees, languages; address, parking, visiting, food, facilities, room charges, hospital policies, other hospital questions; test or visit preparation.
```
Why: the first message of a signed-in chat must reach the agent that opens the record. Before, "book me a cardiologist"
went straight to Booking, which didn't know you and asked for your number.

### A2. Support Agent: replace one paragraph
In its **Instructions**, find the paragraph starting `WHO AM I:` and replace **that paragraph only** with:
```
WHO AM I: At the start of every conversation, before anything else, call open_signed_in_session. If they are signed in, greet them by first name with what it says; it returns their mobile number and date of birth, so never ask for either in this chat. If their first message also asked for something, offer it in one short question, e.g. "Shall I look for a cardiology appointment tomorrow?". On a phone call it says whose registered number is calling: ask "Am I speaking with <name>?" and for the date of birth only. If the chat isn't linked, just help; ask for the registered mobile number and date of birth only when they want something from their own record.
```

### A3. Receptionist: add one paragraph at the end
```
SIGNED IN: When the Support Agent has opened a signed-in record, pass the mobile number and date of birth it returned to every specialist, and send the patient's answer about their request (even a bare yes) to the right specialist. Never ask a signed-in patient for their mobile number or date of birth.
```

### A4. MCP Servers → WellNest_TeamXYZ_MCP → Refresh, then top **Save → Publish**
(after step 0 is deployed; the refund `amount` description changed, no new inputs)

---

## B. Gmail + Google Calendar
Pick **one**. Option 1 is what you asked for: the visit appears in the patient's Google Calendar by itself.

### Option 1: hospital Google account (Gmail sends + real calendar events), about 15 min
Use one Gmail account as "the hospital" (it sends the emails and owns the events). Patients get invited as guests.

1. Open https://console.cloud.google.com, signed in as the hospital Gmail → top bar project picker → **New project** →
   name `WellNest` → **Create**, then select it.
2. **APIs & Services → Library** → search **Gmail API** → **Enable**. Back → search **Google Calendar API** → **Enable**
   (both are required: without the Calendar API every event fails with a 403 that `/health` shows under `outbox`).
3. **APIs & Services → OAuth consent screen** (may be called **Google Auth Platform**) → **Get started**:
   app name `WellNest Hospitals`, support email = the hospital Gmail → **External** → contact email → **Create**.
4. **Audience** → **Publish app** → **Confirm** (status must read **In production**). If it still says "Testing",
   Google blocks the sign-in with "Error 403: access_denied", and a token made in Testing stops working after 7 days.
   If Publish isn't offered, add the hospital Gmail under **Audience → Test users → + Add users** instead, and redo step 6
   every 7 days.
5. **Clients** (or **Credentials → Create credentials → OAuth client ID**) → type **Desktop app** → name `WellNest` →
   **Create**. Keep the **Client ID** and **Client secret** on screen.
6. On your Mac, in Terminal, in this repo folder, run this (paste your two values in place of the dots):
   ```bash
   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python3 scripts/google_connect.py
   ```
   A browser opens → sign in as the **hospital Gmail** → "Google hasn't verified this app" → **Advanced** →
   **Go to WellNest Hospitals** → tick both boxes (Calendar, Gmail) → **Continue**. The Terminal prints a long
   refresh token. Don't paste it in chat.
7. **Render → your service → Environment → Edit** → add:

   | Key | Value |
   |---|---|
   | `GOOGLE_CLIENT_ID` | from step 5 |
   | `GOOGLE_CLIENT_SECRET` | from step 5 |
   | `GOOGLE_REFRESH_TOKEN` | from step 6 |
   | `GOOGLE_CALENDAR_ID` | `primary` |
   | `EMAIL_FROM_ADDRESS` | the hospital Gmail address |
   | `DEMO_PERSONA_EMAILS` | `{"rahul": "your-own@gmail.com"}` (a **different** Gmail from the hospital one; add `"shanthamma"`, `"arjun"`, `"priya"`, `"meera"` the same way if you demo them) |

   **Save, rebuild and deploy**.
8. Open https://teamxyz-mcp.onrender.com/health. It should say `"email": "gmail_api"` and `"calendar": "google"`.

On the patient side: the booking shows up in their Google Calendar right away. If it shows only as an email
invitation, open **Google Calendar → Settings → Event settings → Add invitations to my calendar → From everyone**.

### Option 2: Gmail app password only, about 5 min
Email works; the calendar comes as an invite attached to the email (Gmail shows "Add to calendar"; Apple Mail and
Outlook too). It's not added by itself.
1. https://myaccount.google.com/security, signed in as the hospital Gmail → turn on **2-Step Verification**.
2. https://myaccount.google.com/apppasswords → name `WellNest` → **Create** → copy the 16-letter password.
3. Render → Environment: `SMTP_HOST`=`smtp.gmail.com`, `SMTP_PORT`=`587`, `SMTP_USER`=the Gmail,
   `SMTP_PASSWORD`=the 16 letters (no spaces), `EMAIL_FROM_ADDRESS`=the Gmail, and `DEMO_PERSONA_EMAILS` as in step 7.
4. `/health` should say `"email": "smtp"` and `"calendar": "ics_invite"`.

You can do option 2 now and option 1 later. With both set, option 1 is used.

---

## C. Put Rahul's credits back (1 min)
The refund bug refunded all 1,454 of Rahul's credits (reference RF-69473). Admin → **Wallets** (or Patients → Rahul
Verma) → **Adjust** → `+1454`, reason `Test refund reversed`.

---

## D. Then tell me "all done" and I test live
1. You sign in on the website **in my browser pane** (I can't type your password). I then chat without giving any
   number: "Hi", "When is my next appointment?", "Book me a general medicine appointment tomorrow".
2. A booking for Rahul → check that the email and calendar event arrive in the Gmail from `DEMO_PERSONA_EMAILS`.
3. Refund 50 → confirm → exactly 50 refunded. "Have I ever ordered anything for my diabetes?" → names the Glycomet order.
4. Phone call: you call the Talkdesk number from your registered mobile and ask "When is my next appointment?"; it
   should only ask "Am I speaking with …?" and the date of birth.

---

## E. Round 3 (8 Nov evening): signed-in memory and two wording slips (5 min)
Studio needs nothing: the sign-in now reaches the AI through the page address (Caller ID), not through Studio.

1. **MCP Servers → WellNest_TeamXYZ_MCP → Refresh** (tool descriptions changed; no new inputs, nothing to re-add).
2. **Support Agent → Instructions:** replace the paragraph starting `MEMORY:` with:
   ```
   MEMORY: For an earlier conversation, a past order or request, or a handoff ID (HO-): if you don't have the mobile number yet, call open_signed_in_session first and use the number it returns, then call search_past_interactions and say what it found, with the date. Ask for the mobile number and date of birth only if open_signed_in_session says the chat isn't linked.
   ```
   and add at the end:
   ```
   NEVER ASK FIRST: In a new conversation, never ask for a mobile number or date of birth before calling open_signed_in_session.
   ```
3. **Pharmacy and HealthCredits Agent → Instructions**, add at the end:
   ```
   DELIVERY: Orders go to the address on file as soon as possible. Never ask for a delivery date or time.
   ```
4. Top **Save → Publish**.

In the demo, open every new chat with a question about yourself ("Hi, do you know who I am?", "What did we talk about
last time?"). Those reach the Support agent, which runs the sign-in check. A first message that goes straight to
another team (e.g. "book me a cardiologist") can still ask for the number, because only Support has the sign-in tool.

---

## F. Signed-in chat, final (8 Nov night): 5 edits, about 8 minutes
Why: Talkdesk agents only reuse details written in the conversation. The server now gives a signed-in patient a chat
ID (`WS-` + 12 letters/digits) that every tool accepts in place of the mobile number and date of birth. These edits
make Support say it, make every agent pick it up, and send the first message to Support.

### F1. Variables ({ }): change two descriptions
`patient_phone` → description:
```
The patient's registered mobile number as they said it. If the conversation contains a chat ID (WS- followed by 12 letters and digits), put that chat ID here instead: it stands for the signed-in patient's mobile number and date of birth.
```
`date_of_birth` → description:
```
The patient's date of birth exactly as they said it, e.g. 10-2-1999 or 4 March 1959; never convert it or ask for a format. If the conversation contains a chat ID (WS- followed by 12 letters and digits), put that chat ID here instead.
```

### F2. Support Agent → Instructions
Replace the paragraph starting `WHO AM I:` with:
```
WHO AM I: At the start of every conversation, before anything else, call open_signed_in_session. If they are signed in, reply with its message in full, word for word, including the sentence with the chat ID (WS-...): the other teams can use the patient's details only once the chat ID is written in the conversation. Never ask a signed-in patient for their mobile number or date of birth. If their first message also asked for something, end by offering it, e.g. "Shall I check your insurance for the knee MRI?". On a phone call it says whose registered number is calling: ask "Am I speaking with <name>?" and for the date of birth only. If the chat isn't linked, just help; ask for the registered mobile number and date of birth only when they want something from their own record.
```
and add at the end:
```
CHAT ID: A chat ID (WS-...) is not private. Always repeat it exactly when a tool gives it.
```

### F3. Receptionist → Instructions
If there is a paragraph starting `SIGNED IN:`, replace it; otherwise add at the end:
```
SIGNED IN: In every new conversation, send the FIRST message to the Support Agent before any other team, whatever it asks (only a general hospital question may go straight to the Info Agent), so it can check the website sign-in; then send the request to the right team. Relay the Support Agent's reply in full, including any chat ID (WS-...). Once a chat ID is in the conversation, pass it to every team as both the mobile number and the date of birth, and never ask the patient for either.
```

### F4. Conditions box
**Skip if** it starts with `1. Support Agent: FIRST CHECK. Every conversation's FIRST message`. Otherwise paste the A1
text from section A above.

### F5. MCP Servers → WellNest_TeamXYZ_MCP → Refresh, then top Save → Publish.

Then tell me; I'll re-run: insurance as the first message, greeting then balance, booking a dentist, last-chat recall,
and an order, all while signed in, plus one signed-out chat to make sure nothing changed for patients who aren't.

---

## G. Signed-in chat that doesn't depend on the AI's wording (8 Nov night), about 20 minutes
**Why F wasn't enough (live tests 18:55):** the Receptionist rewrites every reply and dropped the chat ID, and it
routed "Will my insurance cover…" straight to Billing. Anything the AI has to *say* is unreliable.
**The fix:** Talkdesk fills system variables itself. For a web chat, **Caller ID** is the page address, which carries
the signed-in session. Every tool that takes a phone number now has a new optional input `caller_id`; map it to that
system variable and the server knows the patient, whichever agent is talking. `phone` is now optional on these tools.

### G1. MCP Servers → WellNest_TeamXYZ_MCP → Refresh
Still 47 tools. Each phone tool now shows an extra input `caller_id`.

### G2. In each skill below: open it (no re-add) → `caller_id` → **System variables → Caller ID** → Save
| Agent | Skills to open |
|---|---|
| Booking Agent | `verify_patient`, `book_appointment` |
| Changes Agent | `verify_patient`, `find_appointments`, `cancel_appointment`, `reschedule_appointment` |
| Support Agent | `search_past_interactions`, `save_interaction_note` |
| Records Agent | `track_medicine_order`, `get_lab_report_status`, `email_lab_report`, `get_visit_history`, `request_prescription_refill` |
| Billing and Insurance Agent | `check_coverage`, `get_bill_status`, `send_payment_link`, `request_credits_refund` |
| Pharmacy and HealthCredits Agent | `check_medicine_stock`, `order_medicine`, `get_health_credits_balance`, `pay_with_health_credits` |
| Care Assist Agent (optional) | `get_patient_preferences`, `request_assistance`, `send_caregiver_update` |
| Aftercare Agent (optional) | `record_checkin`, `schedule_followup` |

Leave `register_patient` and everything else as it is. If an opened skill doesn't show `caller_id` after the refresh,
remove that skill and add it again with its usual mappings plus `caller_id` → Caller ID (tell me which, I'll check).

### G3. Same agents (Booking, Changes, Support, Records, Billing and Insurance, Pharmacy and HealthCredits): add one line at the end of Instructions
```
SIGNED IN: Your tools recognise a patient who is signed in on the website by themselves. Call the tool straight away without asking for a mobile number or date of birth; ask for them only if the tool replies not_verified.
```

### G4. Top Save → Publish
Then tell me and I'll re-run the signed-in tests (insurance first, balance, dentist booking, recall, an order) and one
signed-out chat.

---

## H. Booking Agent instructions: replace all (2 min)
**Why:** live test 19:47: "book a dentist" while signed in still asked for the mobile number and date of birth. The
Booking Agent's instructions (an older 4,395-character version) say in step 4 "Before booking, collect the mobile
number and date of birth", "ask for identity only after they pick one" and "Pass date_of_birth to book_appointment".
Those override the SIGNED IN line at the end. Replace the whole box (select all, delete, paste):
```
Help the patient book a new doctor appointment, test or scan.
BOOKING: Call find_available_slots with the day as the patient said it ("next available" for the earliest) and offer at most 3 times. Read back doctor, date, time and fee and ask "Shall I confirm this booking?". After a clear yes call book_appointment with the actual date of the chosen slot (never "next available"). Don't ask for the mobile number or date of birth first: book_appointment recognises a patient signed in on the website by itself. Only if it replies not_verified, ask for the registered mobile number and date of birth and call it again. Read back the booking ID exactly (like WN-65604, no spaces), the room and the fee. If the reply asks for an email address, ask for it and call book_appointment again with the same details and the email. Mention that the fee includes one free review within 7 days.
WAITLIST: To join a waitlist call join_waitlist directly; no booking or offer code is needed.
DETAILS: If the patient only wants to check their details are on file, call verify_patient. If they say they are new, call register_patient (name, mobile, date of birth, email).
SENIORS: Keep it very short, prefer morning slots, offer free wheelchair help and ask if a family member should get updates.

TOOLS: Use the one tool that answers the request. Tools check identity themselves, so call them directly; if the mobile number and date of birth were already given in this conversation, reuse them and don't ask again. Pass values, dates and times as the patient said them. Return the tool's message in full, including fees, times, IDs, references (WN-, PHARM-, AS-, CN-, GRV-, RF-, RX-) and disclaimers. Never repeat the patient's mobile number, date of birth or email. Never give medical advice. If a tool fails, return its message.
OUT OF SCOPE: If the patient asks for something none of your tools can do, don't refuse and don't send them to another department; say "Let me get the right team for that" so the request is routed again.
IDENTITY: Never ask for the full name to verify.
SIGNED IN: Your tools recognise a patient who is signed in on the website by themselves. Call the tool straight away without asking for a mobile number or date of birth; ask for them only if the tool replies not_verified.
```
Then check the Booking skills `verify_patient` and `book_appointment` have `caller_id` → System variables → Caller ID,
and **Save → Publish**. (Your orchestration showed "V31 – Draft" with Publish still active at 19:50: if you changed
anything after the last publish, it isn't live until you publish again.)
