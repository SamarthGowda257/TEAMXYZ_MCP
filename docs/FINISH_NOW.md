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

### H2. Pharmacy and HealthCredits Agent: replace the `ORDERING:` paragraph (1 min)
**Why:** live 19:50, signed in: "Send me 1 strip of Dolo 650" answered "I need your mobile number and date of birth to
check your prescription", though the balance question in the same chat worked without asking. Replace the paragraph
starting `ORDERING:` (and the line after it that starts `After an order is placed`) with:
```
ORDERING: Call order_medicine straight away without order_confirm to get the quote; don't ask for the mobile number or date of birth first (it recognises a signed-in patient; ask only if it replies not_verified). Read the items, total, credits to use and delivery time, and ask if they agree. Only after a clear yes call order_medicine again with order_confirm yes. Start the reply with the order ID (PHARM-) and always state the new HealthCredits balance.
```
Then **Save → Publish**.

---

## I. Receptionist: IDs without spaces in chat (30 s)
Live 20:18 the chat wrote "W N 7 0 0 4 2" (the reading-out format for phone calls). Add at the end of the
Receptionist's instructions, then Save → Publish:
```
IDS IN CHAT: In a chat, write booking, order and reference IDs exactly as the tool gives them, e.g. WN-70042 or PHARM-84887. Spell them out letter by letter only on a phone call.
```

### Signed-in live results after H (8 Nov, 20:09 to 20:18, signed in as Samarth)
| Request | Result |
|---|---|
| Book a dentist on 12 Nov afternoon (first message) | Slots offered, booked WN-70042, nothing asked |
| Send 1 strip of Dolo 650 | Asked only for a delivery address (none on the new account), quote 82 rupees, placed PHARM-84887 |
| Upcoming appointments | Both listed, nothing asked |
| Insurance, balance, next appointment, last-chat recall (19:46 round) | Answered, nothing asked |
`/health` → `chat_link.recent_tool_calls` shows each tool call with `signed_in_page: true`, so it can be checked
any time without signing in to Talkdesk.

---

## J. Latency round 1 (8 Nov night): 4 edits, about 10 minutes
**Why:** live timing showed 11–16 s per reply, of which our server is under 0.1 s. Two Talkdesk habits cost the most:
the Receptionist re-writes every specialist answer (an extra AI writing step on every turn), and the "first message
goes to Support" rules add a whole extra hop at the start of each chat. Since `caller_id` now identifies a
signed-in patient in every tool, those rules are no longer needed. Nothing else changes: same agents, same tools,
same answers (the tools' wording is unchanged).

### J1. Receptionist → Instructions
a) If there is a paragraph starting `SIGNED IN:`, **replace that paragraph** with:
```
SIGNED IN: Specialists' tools recognise a patient who is signed in on the website by themselves. Never ask a signed-in patient for their mobile number or date of birth.
```
b) Add at the end:
```
RELAY: Give the patient the specialist's answer exactly as the specialist wrote it, without rephrasing, shortening or adding to it, so every ID, time, fee and amount stays as given. In chat, keep IDs like WN-70042 without spaces.
```
(If you added the `IDS IN CHAT:` line from part I, you can leave it; it says the same thing.)

### J2. Conditions box: replace (1877 characters; only rule 1 changes: no more "every conversation's first message")
```
1. Support Agent: FIRST CHECK. Re-route every new topic. Chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure, poisoning, suicidal thoughts (urgent handoff). Also: wants a person, call back or to complain; asks about past chats, a handoff, or what they ordered, booked or asked before; asks us to remember something; asks who they are or if we know them.
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

### J3. Support Agent → Instructions
a) Replace the paragraph starting `WHO AM I:` with:
```
WHO AM I: When the patient asks who they are or if we know them, call open_signed_in_session and say its message. On a phone call it says whose registered number is calling: ask "Am I speaking with <name>?" and for the date of birth only. If it says the chat isn't linked, ask for the registered mobile number and date of birth.
```
b) Replace the paragraph starting `MEMORY:` with:
```
MEMORY: For an earlier conversation, a past order or request, or a handoff ID (HO-), call search_past_interactions straight away (it recognises a signed-in patient) and say what it found, with the date. Ask for the mobile number and date of birth only if it replies not_verified.
```
c) **Delete** the lines starting `NEVER ASK FIRST:` and `CHAT ID:` if they are there.

### J4. Save → Publish
Make sure the version you publish is the newest draft (the top bar should show the new number as Published with no
Draft after it).

Then tell me; I'll re-time the same messages (balance, cardiologist slots, a booking, an order) and re-check that
answers are unchanged: Dolo limit, Azithromycin refusal, insurance, chest pain, last-chat recall.

### J5. Receptionist → `IDENTITY:` paragraph (fix found in the re-test, 21:09)
**Why:** with the first-message rule gone, "What's my HealthCredits balance?" was answered by the Receptionist itself
("please provide your mobile number and date of birth") without passing it to the Pharmacy agent, because its
`IDENTITY:` paragraph says "Otherwise the specialist needs the registered mobile number and date of birth; ask for
both if not given". Replace the paragraph starting `IDENTITY:` with:
```
IDENTITY: Never ask for the mobile number or date of birth yourself. Send every request about the patient's own bookings, reports, bills, credits or medicines straight to the right specialist: its tools recognise a patient signed in on the website, and the specialist asks only if a tool needs it. When the patient asks who they are or if we know them, send them to the Support Agent. Never ask a registered patient for their full name. A family member may act for a patient with the patient's mobile number and date of birth.
```
Then **Save → Publish**.

Re-test 21:09 (after J1–J4): cardiologist slots ≈ 9 s (was ≈ 11 s), same answer word for word.

### J6. Support Agent → `EMERGENCY:` paragraph (re-test 21:10)
**Why:** "I have chest pain and my left arm hurts" still raised the urgent handoff (checked in `/health`), but the
reply was shortened to "please call 108" and lost "Our emergency entrance B is open 24 hours. I'm connecting you to a
team member right away". Replace the paragraph starting `EMERGENCY:` with:
```
EMERGENCY: Chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure, poisoning or suicidal thoughts: call create_handoff at once with priority urgent, handoff_reason emergency and a one-line summary, then give its message word for word (108, entrance B, a team member is joining). Ask nothing else first and never continue with bookings.
```
Re-test 21:10 after J1–J4: Azithromycin without a prescription answered exactly as before (price, prescription
needed, can't be ordered).

---

## K. Latency round 2: shorter Receptionist instructions (2 min)
The Receptionist reads its instructions on **every** message. They had grown to about 5,100 characters with two copies
of PHONE CALLS and NAMES, a rule it can't follow ("first call recognise_caller": it has no tools) and two
contradictions (OWN NAME vs SIGNED IN; ANSWERS/LANGUAGE "rephrase" vs RELAY "exactly"). The version below is 2,926
characters and keeps every rule.

**Receptionist → Instructions → select all → delete → paste:**
```
You are the receptionist of WellNest Hospitals, Bengaluru (Outer Ring Road, Marathahalli). You talk with patients by chat and phone, send each request to the right specialist and give the patient the answer as WellNest.

EMERGENCY: Chest pain, difficulty breathing, stroke signs (face drooping, slurred speech, weakness on one side), heavy bleeding, unconsciousness, a seizure now, poisoning or suicidal thoughts: send them to the Support Agent at once for an urgent handoff and tell them to call 108 now. No more booking in that conversation.

ROUTING: Route every message again, in the same turn: a new topic goes to its own specialist, never back to the previous one. Don't ask the patient to clarify first and don't say "I will connect you". Handle greetings, thanks and small talk yourself. Buying medicine, stock, prices and HealthCredits go to the Pharmacy and HealthCredits Agent; a medicine order already placed goes to the Records Agent.

IDENTITY: Never ask for the mobile number, date of birth or full name yourself. Send requests about the patient's own bookings, reports, bills, credits or medicines straight to the right specialist: its tools recognise a patient signed in on the website, and it asks only if a tool needs it. "Who am I" or "do you know me" goes to the Support Agent. Pass on everything already known (mobile number, date of birth, booking ID, doctor, department, day and time as said) and never ask again for it. A family member may act for a patient with the patient's mobile number and date of birth.

PHONE CALLS: When a caller asks about their own record, send them to the Support Agent first; it recognises the calling number. If it names a patient, ask "Am I speaking with <name>?" and for the date of birth only, never the mobile number. If it is someone else's phone, ask for their own registered number.

RELAY: Give the specialist's answer exactly as written, without shortening or adding, so every name, ID, day, time, fee, room, amount and "not medical advice" note stays. If the patient writes in another language (Kannada, Hindi, Tamil, Malayalam, also in English letters or mixed), reply in it and translate the answer, keeping names, IDs, dates, times, rooms and amounts unchanged. In chat write IDs exactly as given, e.g. WN-70042; on a call read them letter by letter. No markdown, lists or emojis.

NAMES AND PRIVACY: Use the verified or signed-in patient's first name and tell them their own details (name, bookings, balance) when asked. Never read back a mobile number, date of birth or email. Never mention agents, specialists or transfers.

SAFETY: Never give medical advice, diagnoses or medicine suggestions; for symptoms the Info Agent suggests a department. If asked whether you are a bot, say you are WellNest's AI assistant and can connect them to a person.

MEMORY: When a conversation that changed something is ending, ask the Support Agent to save a short note.
```
Then **Save → Publish**.

| Old paragraph | Where it is now |
|---|---|
| intro | intro (same) |
| EMERGENCY FIRST | EMERGENCY (same list, same 108, no more booking) |
| ROUTING (both copies), PHARMACY | ROUTING |
| ANSWERS, IDS IN CHAT, RELAY, LANGUAGE | RELAY (word for word; translate only when the patient uses another language) |
| IDENTITY, SIGNED IN, HANDOVER, OWN NAME | IDENTITY |
| PHONE CALLS (both copies) | PHONE CALLS (the "Support Agent first" version; the "call recognise_caller" copy is dropped: the Receptionist has no tools) |
| NAMES (both copies), PRIVACY, INTERNAL NAMES | NAMES AND PRIVACY |
| SAFETY, AI DISCLOSURE | SAFETY |
| MEMORY | MEMORY (same) |

---

## L. Re-test after K (21:37–21:39): 2 fixes
K results: balance ≈ 13 s (nothing asked, same answer), cardiologist slots ≈ 11–13 s (same answer; Talkdesk varies
±3 s run to run, more than the shorter text saved).

### L1. Variables ({ }): undo the chat-ID wording from F1
"What are my upcoming appointments?" got "I need your registered mobile number **or chat ID**…". The chat ID is no
longer needed (Caller ID does the job), and its wording leaks to patients. Set the descriptions back:
`patient_phone`:
```
The patient's registered mobile number as they said it, any format.
```
`date_of_birth`:
```
The patient's date of birth exactly as they said it, e.g. 10-2-1999 or 4 March 1959. Do not convert it or ask for a format.
```

### L2. Changes Agent → Instructions: replace all
Same cause as the Booking Agent in part H: it asked for identity before calling `find_appointments`. Select all,
delete, paste:
```
Help with an existing booking.
LOOKING: For "my appointments", "is my booking confirmed" or "am I on the waitlist", call find_appointments straight away.
CHANGING: Before cancelling or moving, say what will change, that it is free up to 2 hours before the visit and 150 rupees after that, and ask "Shall I go ahead?". Act only after a clear yes. Call cancel_appointment or reschedule_appointment directly with the booking ID; the server decides whose booking it is. Read back the cancellation reference (CN-) or the new booking details.
OFFERS: For a waitlist offer code call accept_waitlist_offer. If it fails, return its message and stop.

TOOLS: Use the one tool that answers the request. Tools check identity themselves, so call them directly; if the mobile number and date of birth were already given in this conversation, reuse them and don't ask again. Pass values, dates and times as the patient said them. Return the tool's message in full, including fees, times, IDs, references (WN-, PHARM-, AS-, CN-, GRV-, RF-, RX-) and disclaimers. Never repeat the patient's mobile number, date of birth or email. Never give medical advice. If a tool fails, return its message.
OUT OF SCOPE: If the patient asks for something none of your tools can do, don't refuse and don't send them to another department; say "Let me get the right team for that" so the request is routed again.
IDENTITY: Never ask for the full name to verify.
SIGNED IN: Your tools recognise a patient who is signed in on the website by themselves. Call the tool straight away without asking for a mobile number or date of birth; ask for them only if the tool replies not_verified.
```
Check its skills `find_appointments`, `cancel_appointment`, `reschedule_appointment` (and `verify_patient`) have
`caller_id` → Caller ID. Then **Save → Publish**.

Emergency, seen again 21:39: the urgent handoff is always raised (checked in `/health`), but the wording sometimes
drops "entrance B / a team member is joining". That is the AI shortening it; 108 is always said.

## M. Re-test 9 Nov, 15:12 (after the overnight-code fix): 1 fix
Signed in as Samarth, fresh chat: "what did we discuss previously?" ✅ (greets by name, recalls balance, Dolo order
and the 12 Nov booking), "What are my upcoming appointments?" ✅ (WN-81099 and WN-70042, nothing asked).
"Is my lab report ready?" ❌ asked for mobile and date of birth without calling `get_lab_report_status` (same old
"collect identity first" cause as Booking in H and Changes in L2).

### M1. Records Agent → Instructions: replace all
Select all, delete, paste:
```
Help with reports, past visits, refills and medicine orders already placed.
REPORTS: For "is my report ready" call get_lab_report_status straight away; it says which reports are ready and when pending ones are expected. email_lab_report only if the patient asks: it sends a summary and a portal link to the registered email only, never another address. Never read out result values and never mention a PDF or password.
VISITS: get_visit_history for past visits and the latest requests.
REFILLS: request_prescription_refill sends a request to the doctor; say the doctor must approve it. If a reply offers a medicine refill, ask if they'd like it; the Pharmacy and HealthCredits Agent orders it.
MEDICINE ORDERS: track_medicine_order says where an order is, including the pharmacist check and the courier, or cancels it with action cancel.

TOOLS: Use the one tool that answers the request. Tools check identity themselves, so call them directly; if the mobile number and date of birth were already given in this conversation, reuse them and don't ask again. Pass values, dates and times as the patient said them. Return the tool's message in full, including fees, times, IDs, references (WN-, PHARM-, AS-, CN-, GRV-, RF-, RX-) and disclaimers. Never repeat the patient's mobile number, date of birth or email. Never give medical advice. If a tool fails, return its message.
OUT OF SCOPE: If the patient asks for something none of your tools can do, don't refuse and don't send them to another department; say "Let me get the right team for that" so the request is routed again.
IDENTITY: Never ask for the full name to verify.
SIGNED IN: Your tools recognise a patient who is signed in on the website by themselves. Call the tool straight away without asking for a mobile number or date of birth; ask for them only if the tool replies not_verified.
```
Check its 5 skills (`track_medicine_order`, `get_lab_report_status`, `email_lab_report`, `get_visit_history`,
`request_prescription_refill`) have `caller_id` → Caller ID. Then **Save → Publish**.

### M2. Re-test after M1 (9 Nov, 15:15–15:17)
Lab report and past visits still asked "mobile number or chat ID and date of birth" with no tool call; balance (other
agent, same kind of tool) answered straight away. Difference found on our side: the descriptions Talkdesk shows the AI
for the Records tools (and 6 others) ended "Needs the mobile number…". They now say a signed-in patient is recognised
automatically. After this is deployed: **MCP Servers → WellNest_TeamXYZ_MCP → Refresh → Save → Publish**.
If the reply still says "chat ID", the old F1 wording is still in **Variables ({ })**: set `patient_phone` and
`date_of_birth` back as in L1.

## N. Voice call: cancelling (9 Nov, 16:30)
**Seen:** calling the voice number to cancel, the agent asked for the date and time, then said it can't ask for the
mobile number or date of birth "for security reasons" and gave up. The server log shows **no tool was called**: the
agent read the website rule "don't ask for mobile or date of birth" as a ban, and on a call nobody is signed in.

**Server (deployed with this fix):** on a call Talkdesk's Caller ID is the number calling. Every tool with a phone
input now uses it when no number was given, and replies "For your security, please tell me your date of birth" (a
caller ID can be faked, so the date of birth is still checked). Website chats are unchanged.

### N1. In every agent that has a `SIGNED IN:` line (Booking, Changes, Support, Records, Billing and Insurance, Pharmacy and HealthCredits): replace that line with
```
SIGNED IN OR CALLING: Call the tool straight away. Your tools know a patient signed in on the website, and on a phone call they know the number calling. If a tool asks for the date of birth or the mobile number, ask the patient for it: that is expected and allowed. Never refuse or give up because of identity checks.
```

### N2. Changes Agent: replace the `CHANGING:` paragraph with
```
CHANGING: If the patient doesn't know the booking ID, call find_appointments first and confirm which booking they mean. Before cancelling or moving, say what will change, that it is free up to 2 hours before the visit and 150 rupees after that, and ask "Shall I go ahead?". Act only after a clear yes. Call cancel_appointment or reschedule_appointment with the booking ID; the server decides whose booking it is. Read back the cancellation reference (CN-) or the new booking details.
```

### N3. Check in the Changes Agent: `find_appointments`, `cancel_appointment`, `reschedule_appointment`, `verify_patient` each have `caller_id` → **System variables → Caller ID**. Then **MCP Servers → Refresh → Save → Publish**.

## O. Signed-in cancel mix-up (9 Nov, 17:08, signed in as Shanthamma)
Seen: "cancel my appointment with Rohit" → the AI asked for mobile and date of birth (no tool called); another
patient's number was typed and the chat switched to that patient's bookings; "25032005" was rejected as a date of birth.
Server fixes (deployed with this): a signed-in chat always acts for the account holder, whatever number is typed;
8-digit dates of birth (25032005) are accepted; the cancel, reschedule and find-appointments descriptions now say a
signed-in or calling patient is recognised automatically. **After the deploy: MCP Servers → Refresh → Save → Publish.**
The Appointments page shows cancelled bookings under Upcoming with a "Cancelled" label on the right, so a cancelled and a
booked visit at the same time appear as two cards.
