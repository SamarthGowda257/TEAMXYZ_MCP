# Finish line: where we are and what you do (8 Nov 2026)

## Where we are

| Feature | Status |
|---|---|
| Chat: identity, balance, bills, Dolo limits, "what can I order", prescription refusal, ordering, tracking, memory across chats, complaints | **Working live** (tested in the chat on 8 Nov) |
| Refund asks to confirm, "yes" completes it | **Working live**, but a bug refunded the whole balance instead of the 50 asked. **Fixed in code**, waiting for deploy (step 0) |
| "Have I ever ordered anything for my diabetes?" | Answered "no" live. **Fixed in code** (orders now listed with what each medicine is for), waiting for deploy |
| Signed-in chat knows you with no mobile number or date of birth | **Server ready** (deploy, step 0). Needs Talkdesk part A, then a live test with your sign-in (part D) |
| Booking → email | **Built, switched off**: Render has no Gmail settings, `/health` says `"email": "simulated"`. Needs part B |
| Booking → Google Calendar | **Built, switched off**: needs part B (option 1 puts it straight in their Google Calendar) |
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
2. **APIs & Services → Library** → search **Gmail API** → **Enable**. Back → search **Google Calendar API** → **Enable**.
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
