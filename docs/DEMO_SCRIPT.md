# WellNest demo video: "Ask once."

**Length:** 7 to 8 minutes. **Story:** one patient's day, told across every channel, with the hospital's own
screens shown only when something the patient did shows up there. The site's line is "Ask once. We take it from
there." Every scene proves that line: the patient never repeats themselves, and nothing is retyped between chat,
phone, email, calendar and the staff desks.

**Cast**
- **Rahul Verma** (demo patient, diabetic, Marathahalli). The hero. You sign in as him or use 9845000004 / 10-9-1981.
- **Shanthamma K** (67, Kannada, son Ravi abroad). One short scene for language and family.
- **Dr. Anil Kumar** (doctor account) and **the pharmacist** (pharmacist account). The hospital side.

**Screen layout that makes it look good:** browser on the left two-thirds (website + chat), your phone mirrored on
the right third (QuickTime → New Movie Recording → choose the iPhone, or any phone-mirroring app) with Gmail and
Google Calendar open on samarthgowda257. When the chat says "Booked", the phone buzzes in the same shot. That
moment is the money shot of the video; give it a second of silence.

---

## Before you record (10 min, do it every time)

1. Open https://teamxyz-mcp.onrender.com/health a minute before. Render sleeps; the first request is slow.
   It should say `"email": "gmail_api"`, `"calendar": "google"`.
2. Admin → Wallets → Rahul Verma: at least 1,500 credits (top up if needed).
3. Cancel Rahul's test bookings from today (WN-83093, WN-59330) in Admin → Appointments, so his slots look clean.
4. Phone: Gmail and Google Calendar for samarthgowda257 open, notifications on, Do Not Disturb off.
5. Three browser windows signed in: the website as Rahul, admin as the pharmacist, admin as Dr. Anil Kumar.
6. **Do not** run "reset demo" (`/ops/reset-demo`): it deletes everything, including your own account.
7. Record each scene separately and **speed up the waiting** in editing (Talkdesk replies take 10–20 s; show them at
   4x with a small "AI thinking" caption, then normal speed when the answer lands).

Creative touches to add in editing:
- A small counter in the corner: **"Times Rahul repeated himself: 0"**. It never moves.
- When a reply arrives, a thin caption under it naming what happened behind it, e.g. *"find_available_slots → real
  OPD schedule"*, *"server checked the prescription, not the AI"*. Judges love seeing that it's real.
- Chapter cards between scenes using the site's own fonts and teal: "8:02 AM · Rahul wakes up with a question".

---

## Scene 1. Cold open (0:00–0:25)
**Show:** black screen, the sound of hold music and "Press 1 for appointments…". Cut to the WellNest home page,
"Ask once. We take it from there." fades in.
**Voice-over:** "Indian hospitals make you repeat your phone number, your date of birth and your problem to every
desk. WellNest's assistant asks once, on chat or on the phone, and takes it from there."

## Scene 2. "It already knows me" (0:25–1:10)
**Show:** Rahul signs in on the website → opens the chat.
**Type:** `Hi`
**Expect:** "Hello Rahul, you're signed in…", his upcoming visit or "no upcoming bookings", and that he won't need to
give his number or date of birth.
**Type:** `When is my next appointment?` → answered with no questions asked.
**Caption:** "Signed in on the website = known in the chat. A one-time code, checked on the server. The browser can't
fake it."
**Status:** server tested; rehearse once after your Talkdesk part A.

## Scene 3. Booking, then the phone buzzes (1:10–2:30)
**Type:** `I need a general medicine doctor tomorrow morning`
**Expect:** up to 3 real free times with Dr. Anil Kumar and the fee (600 rupees).
**Type:** `9:15 please`
**Expect:** "Booked. Your booking ID is WN-…, room OPD-101… A confirmation email with a calendar invite is on its way."
**Cut to phone:** Gmail notification "Confirmed: Dr. Anil Kumar on …", then the Google Calendar event appears with
reminders. Open the email for one second: booking ID, room, fee, policy, "Add to Google Calendar".
**Type:** `Can you move it to 10:30?` → it explains it's free up to 2 hours before, asks "Shall I go ahead?" → `Yes`
**Cut to phone:** the calendar event **moves** to 10:30 by itself, and an "updated" email arrives.
**Caption:** "One booking row. The chat, the email, the patient's Google Calendar and the counter all read it."
**Status:** tested live 8 Nov (booking, reschedule, Gmail, Calendar).

## Scene 4. It remembers (2:30–3:10)
**Show:** close the chat → "Start new chat" (a brand-new conversation).
**Type:** `What did I ask you last time?` → recalls the last conversation with the date.
**Type:** `Have I ever ordered anything for my diabetes?` → "Glycomet 500 SR (for diabetes), order PHARM-…".
**Caption:** "Every conversation and action is stored and embedded (hybrid search: keyword + fuzzy + meaning). It found
'diabetes' though the order only said 'Glycomet'."
**Status:** server tested; the routing needs your Talkdesk part A.

## Scene 5. The pharmacy that says no (3:10–4:40)
The strongest "this is production, not a toy" scene. Four lines, four different server rules:
1. `Send me 4 strips of Dolo 650` → "Up to 3 strips per order for safety; shall I send 3?" *(OTC daily and weekly
   limit by ingredient, across brands)*
2. `Send me Azithromycin 500` → refused: needs a prescription; offers a doctor consultation or uploading a
   prescription. *(Schedule H1 law, enforced by the server)*
3. `What can I order on my prescriptions?` → "Metformin, about … days left; Telmisartan, …" *(days of supply from the
   doctor's prescription; too-early refills refused)*
4. `Order 2 strips of Glycomet` → quote: price, delivery, paid from HealthCredits → `Yes` → "Order PHARM-…, a
   pharmacist will check it, new balance …"
**Cut to the pharmacist window:** Admin → **Pharmacist desk** → the order is in the queue with Rahul's prescription →
**Approve**.
**Back to chat:** `Where is my medicine order?` → "being packed" + tracking link.
**Optional 10 s:** Pharmacist desk → simulated courier → "delivered" needs the one-time delivery code (H1 and
cold-chain orders), and two failed attempts refund the credits automatically.
**Caption:** "Credits are held at order, captured only at dispatch, refunded on any rejection or cancellation."
**Status:** tested live 8 Nov (limits, refusal, prescription allowance, order, tracking). Approval on the live desk:
rehearse once.

## Scene 6. The doctor's side (4:40–5:20)
**Show:** the doctor window → Admin → **Prescribe** → patient Rahul → add Paracetamol 650, 2 tablets, 4 times a day.
**Expect:** the red line "5,200 mg a day · usual adult maximum 4,000 mg" and a required "Reason to go above the
maximum". Change it to 1 tablet → the warning clears → **Save**. Rahul gets the prescription; the chat's "what can I
order" now includes it.
**Caption:** "Doctors prescribe as themselves (signed), and every dose is checked against a ceiling."

## Scene 7. Money, with a safety catch (5:20–6:00)
- `What's my HealthCredits balance?` → balance, credits held for the medicine order, last transaction.
- `Do I have any unpaid bills?` → the bill → `Pay it from my credits` (or "send me a payment link").
- `Refund 50 credits to my bank` → "Shall I refund 50 rupees…?" → `Yes` → "RF-…, 3 to 5 banking days, credits can't be
  paid out as cash (RBI rules)".
**Caption:** "Two steps, enforced on the server: it can only refund the exact amount the patient heard."

## Scene 8. When it must stop being a chatbot (6:00–6:35)
**Type:** `I have chest pain and my left arm hurts`
**Expect:** it stops everything, says to call 108, gives the emergency entrance, and raises an urgent handoff.
**Cut to admin:** **Escalations** → the urgent case is at the top with the conversation summary.
**Type (new chat):** `I want to complain, I was charged twice` → logged, reference GRV-….
**Caption:** "Emergencies are a hard-coded path, not a judgement call. A person is always one sentence away."

## Scene 9. Same assistant, on the phone (6:35–7:20)
**Show:** call the Talkdesk number from your registered mobile, on speaker, screen recording the phone.
**Expect:** it recognises the number: "Am I speaking with Rahul?" → asks only the date of birth, never the number.
**Say:** "When is my next appointment?" → it reads back the booking made in scene 3 (same record, different channel).
**Optional:** "Book me a skin doctor on Saturday evening" by voice; the email arrives on screen while you're still
on the call.
**Then Shanthamma (10 s, if your Talkdesk voice handles Kannada):** "ನಾಳೆ ಹೃದಯ ವೈದ್ಯರ ಅಪಾಯಿಂಟ್ಮೆಂಟ್ ಬೇಕು"
("I need a heart doctor tomorrow") → replies in Kannada. Try it before the shoot; cut it if it stumbles.
**Status:** built and on Talkdesk; not yet tested on a real call. Rehearse.

## Scene 10. Behind the curtain (7:20–7:50)
Fast montage, 3–4 seconds each:
- Admin **Today**: the bookings, orders and escalations from this video, live.
- Admin **Conversations**: the chat transcript filed under Rahul.
- Admin **Outbound calls**: reminder and follow-up calls the backend plans by itself.
- `/architecture` page, then the Talkdesk AI Agent Platform: the Receptionist + 10 specialist agents, 47 MCP tools.
- `/health`: Postgres, Redis, hybrid search, Gmail, Google Calendar all green.
**Voice-over:** "Ten Talkdesk agents, forty-seven tools, one record. Every rule that matters, prescriptions, refunds,
identity, runs on the server, so the AI can't talk its way around it."

## Scene 11. Close (7:50–8:00)
Back to the home page. "Ask once. We take it from there." Team name, Talkdesk AI Hackday.

---

## If you're short on time (3-minute cut)
Scene 2 (signed in) → Scene 3 (booking + phone buzz + calendar move) → Scene 5 items 2 and 4 + approve →
Scene 8 (chest pain) → Scene 9 (phone call, 20 s) → close.

## If something goes wrong while recording
- "Sorry, I cannot handle your request": send the same message again in a new chat; it's a Talkdesk routing hiccup.
- It asks for the number while signed in: say "I'm signed in" once (that re-checks the sign-in).
- No email within a minute: open `/health` → `outbox.last_error` says why.
- Booking says the slot is taken: pick the next one; slots are real and earlier test bookings use them.
