# Talkdesk: only what's left to do (8 Nov 2026)

Everything else from earlier rounds is already done on your side: the agents, skill swaps, Studio flow, signed-in chat,
caller ID on `open_signed_in_session`, the refund `confirm` input, the Receptionist PHONE CALLS / NAMES paragraphs.
**Don't delete or re-add anything that isn't listed here.**

Each item says where to click, what to do, and **skip if** (so you can tell in two seconds whether it's already done).
Total: about 15 minutes. Do them in order, then **Save → Publish** once at the end.

`TALKDESK_AGENT_UPDATE.md` stays as the full reference of how everything should look; you don't need to work through it.

---

## 1. Refresh the MCP server (1 min)
**AI Agent Platform → MCP Servers → WellNest_TeamXYZ_MCP → Refresh.** Still 47 tools. This makes the new inputs on
`check_medicine_stock` visible (needed for item 4).

## 2. Conditions box: replace the text (1 min)
**Skip if** your box already contains the words `what their prescriptions allow`.

Click the **Conditions** box → select all → delete → paste (1,954 characters, fits the 2,000 limit):
```
1. Support Agent: FIRST CHECK. Route EVERY new message again; a new topic goes to its own agent, not the current one. Chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure, poisoning, suicidal thoughts (urgent handoff). Also: wants a person, call back or to complain; asks about past chats or a handoff; asks us to remember something; asks who they are or if we know them; asks about their own record without giving a mobile number.
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
Why: refunds were going to the Pharmacy agent, and a second topic in the same chat got "Sorry, I cannot handle your request".

## 3. Receptionist: add one paragraph (1 min)
**Skip if** its instructions already contain `Route every new message again`.

Click **Receptionist** → **Instructions** → paste this at the end:
```
ROUTING: Route every new message again, even in the middle of a conversation: a new topic goes to its own specialist, never back to the previous one.
```

## 4. Pharmacy and HealthCredits Agent (4 min)
**a. Re-add one skill** (it gained two inputs; this is the only re-add in this list).
**Skip if** clicking `check_medicine_stock` already shows **phone** and **date_of_birth** mapped.
Remove `check_medicine_stock` → **+ Add Skill → MCP → WellNest_TeamXYZ_MCP → check_medicine_stock** → map:

| Input | Source |
|---|---|
| medicine_name\* | Variables → `medicine_name` |
| phone | Variables → `patient_phone` |
| date_of_birth | Variables → `date_of_birth` |

**b. Description:** replace with
```
Medicine stock, prices, what a patient's prescriptions allow, home delivery orders, and the HealthCredits wallet: balance, adding credits and paying a booking or bill with credits. Not refunds.
```

**c. Instructions:** find the paragraph that starts `PRESCRIPTION RULES:` and **replace that one paragraph** with:
```
PRESCRIPTIONS: For "do you have", a price or "what can I order", call check_medicine_stock with the mobile number when known; it says how much they may order. For "my prescriptions" pass medicine_name "my prescriptions". The server decides: if order_medicine refuses with a limit, offer the number of packs it allows. No prescription: offer the consultation it names (the Booking Agent books it) or uploading a prescription on the website. Refill too early, used up or expired: offer a refill request to the doctor (Records Agent). An allergy: offer a person (Support Agent). Schedule X can't be ordered by chat or phone. Prescription medicines are checked by a pharmacist before dispatch: say so, and read back the order ID (PHARM-) and the new balance. Refunds are for the Billing and Insurance Agent. Never suggest a medicine.
```
**Skip c if** the instructions already contain `what can I order`.

## 5. Every specialist agent: add two lines (5 min)
**Skip an agent if** its instructions already contain `OUT OF SCOPE:`.

Agents: Booking, Changes, Support, Records, Billing and Insurance, Info, Care Assist, Aftercare, Outreach, Pharmacy and
HealthCredits. In each, paste this at the end of **Instructions** → panel **Save**:
```
OUT OF SCOPE: If the patient asks for something none of your tools can do, don't refuse and don't send them to another department; say "Let me get the right team for that" so the request is routed again, keeping the mobile number.
IDENTITY: The mobile number and date of birth are enough. Never ask for the full name to verify.
```
Why: agents were answering "I cannot answer this question" for a new topic, and asked for the full name before
answering.

## 6. Outreach Agent: one sentence (1 min)
**Skip if** its instructions already contain `Is this your registered mobile number`.

In the Outreach Agent's instructions, find rule 1 (it starts `1. CONTEXT FIRST: If you do not have the patient's
mobile number, ask for it.`) and replace **only its first sentence** with:
```
1. CONTEXT FIRST: If you do not have the patient's mobile number, ask "Is this your registered mobile number?" and use the number they confirm.
```
Why: on a WellNest call the agent asked the patient to type their number again.

## 7. One variable description (30 s)
**{ } → `medicine_name`** → description:
```
The medicine as the patient said it, e.g. Dolo 650 or 2 strips of Metformin 500; "my prescriptions" when they ask what they can order.
```

## 8. Save and publish (30 s)
Top **Save** → **Publish**.

---

## 9. On the website (not Talkdesk, 5 min)
1. Open `https://teamxyz-mcp.onrender.com/admin`, sign in with the admin ID and password from Render.
2. Left menu **Staff accounts → New account**:
   - Role **Doctor**, pick **Dr. Anil Kumar**, username e.g. `dr.anil`, a 10+ character password.
   - Role **Pharmacist**, username e.g. `pharmacist`, a 10+ character password.
3. Sign out, sign in as the pharmacist: you should land on **Pharmacist desk**. As the doctor: **Prescribe**.
4. Before real patients: pharmacist → **Pharmacist desk → Limits** → check each number → **Save and sign off**.

## Then tell me
Say "done" and I'll run the live chat tests: memory across chats, the refund, Dolo limits, "what can I order",
an antibiotic without a prescription, and an order going through the pharmacist desk.
