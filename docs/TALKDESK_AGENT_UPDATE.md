# Talkdesk update: pharmacy, HealthCredits and closed-loop agents

The clicks a person must make in Talkdesk (`pesit-hackathon.mytalkdesk.com`) after this branch is on `main`. It sits on
top of `TALKDESK_SETUP.md` (§10 tuned instructions) and `OUTBOUND_CALLS.md` (Outreach Agent). Every tool and input name
below exists on the server.

**Do this only after the deploy.** A skill can only be mapped once `/mcp` lists the tool.

**Don't paste the prompts in `WELLNEST_REAL_WORLD_POLICIES_AND_AGENTS.md` as they are.** They name tools that don't exist
(`check_insurance_coverage`, `get_bill_estimate`, `get_lab_report`) and an input that doesn't exist (`handoff_summary`
on the server is `summary`, `handoff_reason` is `reason_code`). They also say "encrypted PDF" and "PDF password" (we email
a summary and a portal link instead), and name Dr. Priya Rao and Room 204 (not in the doctor list). They hard-code visiting
hours and parking that differ from the knowledge base. Also, "verify first" and "never make up answers" style rules are marked as
broken by the Instruction Adherence judge (see `TALKDESK_SETUP.md` §10). Use the additions below instead.

## 1. Refresh the MCP server
**AI Agent Platform → MCP Servers → the WellNest server → Test connection / Refresh.** Expect **47 tools** (45 plus `open_signed_in_session`, section 10, and `recognise_caller`, section 11). New since the
outbound work: `check_medicine_stock`, `order_medicine`, `track_medicine_order`, `get_health_credits_balance`,
`recharge_health_credits`, `pay_with_health_credits`, `request_credits_refund`, `set_shared_wallet`.
`request_assistance` gains two optional inputs: `off_campus` and `date_of_birth`.

## 2. New variables ({ } → + Add variable)
| Variable | Description (paste this) |
|---|---|
| `delivery_address` | The address to deliver medicines to, as the patient said it. Empty to use the address on file. |
| `medicine_quantity` | How many strips or packs, only if one medicine is ordered and the number was not said with its name. |
| `payment_method` | health_credits, or payment_link if the patient prefers a link. |
| `order_confirm` | yes only after the patient has heard the total and clearly agreed to it. Otherwise empty. |
| `wait_for_restock` | yes if the patient chooses to wait for an out-of-stock brand. Otherwise empty. |
| `order_id` | A medicine order ID like PHARM-30219, only if the patient says one. |
| `order_action` | cancel if the patient wants to cancel the medicine order. Otherwise empty. |
| `recharge_amount` | The rupees the patient wants to add to HealthCredits, e.g. 2000. |
| `payment_reference` | The booking ID (WN-48213) or bill ID (BL-55012) to pay with HealthCredits. |
| `refund_amount` | The credits to refund, as a number. Empty means the whole balance. |
| `family_phone` | The mobile number of the family member who may use the wallet. |
| `per_transaction_limit` | The most the family member can spend per order, in rupees. Empty if none was said. |
| `daily_limit` | The most the family member can spend per day, in rupees. Empty if none was said. |
| `wallet_action` | stop if the patient wants to remove the family member's access. Otherwise empty. |
| `off_campus` | yes only if a wheelchair will leave the hospital grounds. Otherwise empty. |

`medicine_name` already exists (Records Agent).

## 3. New agent: Pharmacy and HealthCredits Agent
Talkdesk allows 10 agents per level. Booking, Changes, Support, Records, Billing, Info, Care Assist, Aftercare and
Outreach make 9, so this is the last slot. **Add Agent → AI agent**; Require authentication off, Use Knowledge Management off.

- **Name:** `Pharmacy and HealthCredits Agent`
- **Description:** `Medicine stock, prices and home delivery orders, prescription rules, and the HealthCredits wallet: balance, adding credits and paying a booking or bill with credits.`
- **Instructions:**
```
Help the patient buy medicines and use their HealthCredits wallet. Pass medicine names and amounts as the patient said them.

STOCK: For "do you have" or price questions call check_medicine_stock. If a brand is out of stock, say when it arrives and offer the in-stock generic it names.

ORDERING: Call order_medicine without order_confirm to get the quote. Read the items, total, credits to use and delivery time, and ask if they agree. Only after a clear yes call order_medicine again with order_confirm yes. Read back the order ID and the new balance.

PRESCRIPTION RULES: The server decides. If it refuses because there is no prescription, say why in the patient's words and offer the General Medicine consultation it names; the Booking Agent books it. Schedule X medicines can't be ordered by chat or phone. Never suggest a medicine.

OUT OF STOCK CHOICE: If the patient prefers to wait for the brand, call order_medicine with wait_for_restock yes after they agree.

COLD CHAIN: If the reply mentions insulin or a cooled pouch, always say an adult must be home to receive it.

WALLET: get_health_credits_balance for the balance. recharge_health_credits sends a payment link. pay_with_health_credits pays a booking or bill after a clear yes. If credits are short the order tool sends a link for the rest. Never ask for or accept card or UPI details.

TOOLS: Tools that take the mobile number and date of birth check identity themselves, so call them directly. Return the tool's message in full, including amounts and IDs, and never repeat the patient's mobile number, date of birth or email. If a tool fails, return its message.
```
- **Skills (5/5):**
| Tool | Input → source |
|---|---|
| `check_medicine_stock` | medicine_name\* → `medicine_name` |
| `order_medicine` | phone\* → `patient_phone`; medicine_name\* → `medicine_name`; date_of_birth → `date_of_birth`; quantity → `medicine_quantity`; delivery_address → `delivery_address`; payment_method → `payment_method`; confirm → `order_confirm`; wait_for_restock → `wait_for_restock` |
| `get_health_credits_balance` | phone\* → `patient_phone`; date_of_birth → `date_of_birth` |
| `recharge_health_credits` | phone\* → `patient_phone`; amount_inr\* → `recharge_amount`; date_of_birth → `date_of_birth` |
| `pay_with_health_credits` | phone\* → `patient_phone`; reference\* → `payment_reference`; date_of_birth → `date_of_birth` |

## 4. Skill swaps on existing agents
The other 3 new tools have no room in the new agent. Each swap replaces `verify_patient`, which is safe because the other
tools on these agents check identity themselves.
| Agent | Remove | Add | Input → source |
|---|---|---|---|
| Records | `verify_patient` | `track_medicine_order` | phone\* → `patient_phone`; date_of_birth → `date_of_birth`; order_id → `order_id`; action → `order_action` |
| Billing & Insurance | `verify_patient` | `request_credits_refund` | phone\* → `patient_phone`; date_of_birth → `date_of_birth`; amount → `refund_amount` |
| Care Assist | `verify_patient` | `set_shared_wallet` | phone\* → `patient_phone`; family_phone\* → `family_phone`; date_of_birth → `date_of_birth`; per_transaction_limit → `per_transaction_limit`; daily_limit → `daily_limit`; action → `wallet_action` |

On Booking open `book_appointment` and map: email → `patient_email` (so a patient with no email on file still gets the confirmation).

On Care Assist also open `request_assistance` and map: off_campus → `off_campus`; date_of_birth → `date_of_birth`; notes → `conversation_summary`.

## 5. Additions to existing agents' instructions (add, don't replace)
- **Receptionist:** add `PHARMACY: Buying medicine, medicine stock or price, and HealthCredits go to the Pharmacy and HealthCredits Agent. A medicine order that is already placed goes to the Records Agent.`
- **Booking:** `If the reply asks for an email address, ask for it, then call book_appointment again with the same details and the email. Mention that the fee includes one free follow-up review within 7 days. For a senior, offer free wheelchair help and ask if a family member should get updates. Late arrival, refunds and registration charges: the Info Agent answers these from hospital policy.`
- **Changes:** `Before cancelling or moving, say it is free up to 2 hours before the visit and 150 rupees after that. Read back the cancellation reference (CN-) from the reply.`
- **Care Assist:** `For a wheelchair or escort ask which gate (Gate 1 emergency, Gate 2 main entrance or Basement P1) and the arrival time, and put both in notes. Say it is free and two-way, and read back the token (AS-). If the wheelchair will leave the campus, set off_campus yes; it holds a 1,000 credit refundable deposit. Before adding a caregiver, say they get practical updates only, and lab results stay private unless a proxy form is signed; then get a clear yes. To let family pay from the patient's wallet use set_shared_wallet; the wallet owner's mobile and date of birth are needed.`
- **Records:** `If the reply offers a medicine refill, ask if they'd like it; the Pharmacy and HealthCredits Agent orders it. Reports go only to the registered email, never another address. Never mention a PDF or password. Use track_medicine_order for where a medicine order is, or to cancel it.`
- **Billing & Insurance:** `Coverage is an estimate; the insurer gives final approval. If asked about hidden costs, get_hospital_info is on the Info Agent: non-medical items of about 850 rupees are not covered, and the TPA desk is on the ground floor, Wing B. When a patient asks for HealthCredits back, in cash or to a bank, call request_credits_refund. Say credits can't be paid as cash and that the refund goes to the original account.`
- **Aftercare:** `When record_checkin or flag_nurse_alert raises an alert, say a nurse calls within 15 minutes and read back the reference. For stable patients offer the free review through schedule_followup.`
- **Booking, Changes, Care Assist, Pharmacy and HealthCredits, Billing & Insurance:** also add `Always include any reference from the tool reply word for word: WN-, PHARM-, AS-, CN-, GRV-, RF-. If the mobile number and date of birth were already given in this conversation, use them and don't ask again.`
- **Support:** `For a complaint call create_handoff with reason_code complaint and read back the GRV reference from the reply.`

## 6. Conditions: replace the whole box
The box holds 2,000 characters, so this is the shortened text that fits (1,797).
```
1. Support Agent: FIRST CHECK. Route EVERY new message again; a new topic goes to its own agent, not the current one. Chest pain, breathing difficulty, stroke signs, heavy bleeding, unconsciousness, seizure, poisoning, suicidal thoughts (urgent handoff). Also: wants a person, call back or to complain; asks about past chats or a handoff; asks us to remember something; asks who they are or if we know them; asks about their own record without giving a mobile number.
2. Outreach Agent: says WellNest just called, was transferred from a WellNest call, or answers a question from that call.
3. Booking Agent: NEW appointment, test or scan; if or when a doctor or department is free; new patient registration; checking details on file; joining a waitlist.
4. Changes Agent: see, cancel or reschedule an EXISTING booking; waitlist status; waitlist OFFER CODE.
5. Pharmacy and HealthCredits Agent: buy or order medicine; medicine stock or price; HealthCredits balance, adding credits, paying a booking or bill with credits. NOT refunds (rule 8).
6. Care Assist Agent: wheelchair, escort, interpreter or transport; sending booking details to family or caregiver; adding a caregiver; letting family use credits; language or time preferences.
7. Records Agent: lab or scan reports, emailing a report, past visits, prescription refill requests, where a medicine order is or cancelling one.
8. Billing and Insurance Agent: insurance, cashless, coverage, pre-approval, estimates, bills, payment links; ANY refund, including HealthCredits back to a bank, card or cash.
9. Aftercare Agent: after a visit or new medicine reports how they feel, wants a nurse to call, gives feedback or a rating, wants a follow-up.
10. Info Agent: non-urgent symptoms and which department; doctors' days, fees, languages; address, parking, visiting, food, facilities, room charges, hospital policies, other hospital questions; test or visit preparation.
```
Then panel **Save**, top **Save**, and **Publish** once the team agrees.

## 7. Outreach flow: nothing to change
The new `caregiver_update` call uses the same flow. Its only keys are 1 and 3, and the flow already handles other keys.

## 8. Test script (Test → Chat, restart between tests, keep Insight open)
| # | Say | Expected |
|---|---|---|
| 1 | "Do you have Telma 40?" | Out of stock, restock time, Cipla generic at 75 rupees |
| 2 | "I'm Rahul, 9845000004, born 10 September 1981. Send 2 strips of Metformin 500 and a strip of Dolo 650 to Bellandur." | Quote 178 rupees, 1,800 credits. Say yes → PHARM- ID, balance 1,622, within 90 minutes |
| 3 | "Send me Azithromycin 500" (Rahul) | Refused, offers Dr. Anil Kumar, 600 rupees |
| 4 | "Send me Alprax" (Rahul) | Refused: in-person only |
| 5 | "5 Gelusil" (Priya, 9845000003, born 20 January 1997) | 400 credits plus link for 200 |
| 6 | "Order a Lantus pen" (Shanthamma, 9845000001, born 4 March 1959) | Refused: no insulin prescription on file |
| 7 | "Where is my medicine order?" (Rahul, after 2) | Records Agent: status and tracking link |
| 8 | "Add 2000 rupees to my HealthCredits" | Link, 2,100 credits |
| 9 | "I want my credits back in cash" | Refund to source account, not cash |
| 10 | "Wheelchair for WN-48213 at Gate 2 at 9:40" (Shanthamma) | Free, two-way, AS- token |
| 11 | "Cancel WN-48213" (Shanthamma + DOB) | CN- reference |
| 12 | "I want to complain, I was charged twice" | GRV- reference and transfer |
| 13 | "Is my lipid report ready?" (Rahul + DOB) | Ready, then the refill offer for his medicine |
| 14 | "How much is a private room?" | 7,800 rupees a day |

## 9. Render settings
| Variable | For |
|---|---|
| `ADMIN_PASSWORD` | Staff console. Set a real one |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` | Real Google Calendar invites and Gmail. Run `scripts/google_connect.py` for the token. Without them: `.ics` invites over SMTP, or simulated |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Real payment links. Without them: the labelled demo payment page |
| `DEMO_PERSONA_EMAILS` | So invites reach a real inbox: demo addresses at example.com are never emailed |

## 10. Signed-in chat, memory and the refund fix (7 Nov)
**Why:** the AI never knew who was signed in on the website. The page now gets a random session code from the server
(`POST /api/chat/session`) and passes only that code to the chat widget as `wellnest_session`. A browser can forge a
phone number but not a live code; logging out revokes it. The code reaches the AI as the **Application Input** system
variable, and `open_signed_in_session` turns it into the patient's record.

### Studio (the chat flow on the website touchpoint)
1. **Studio** → open the chat flow → **Incoming Message** node → **Arguments** → add argument `wellnest_session`,
   mapped to a new flow variable `wellnest_session`.
2. **Connect to Autopilot Digital** node → **Preferences** → **Agents availability** → choose `wellnest_session`.
3. **Publish** the flow.

### Orchestration
1. **MCP Servers → Refresh**: 46 tools.
2. **Support Agent:** remove `get_handoff_status` (`search_past_interactions` now answers `HO-` IDs) and add
   `open_signed_in_session`: session_code → System variable **Application Input**; interaction_id → **Interaction ID**.
3. **Support Agent:** delete and re-add `save_interaction_note` (it has two new inputs). phone\* → `patient_phone`;
   summary\* → `conversation_summary`; topics → `conversation_topics`; last_message → **Last Received Message**;
   interaction_id → **Interaction ID**.
4. **Support Agent instructions**, add:
   `SIGNED IN: When the patient asks who they are, says they're signed in, or asks about their own record without giving a mobile number, call open_signed_in_session first. If it works, greet them by first name, use the mobile number it returns as patient_phone for every later tool and don't ask for their date of birth. If it says the chat isn't linked, ask for the registered mobile number and date of birth. For a handoff ID (HO-), call search_past_interactions with the ID.`
5. **Receptionist instructions**, replace the IDENTITY paragraph with:
   `IDENTITY: If the patient asks who they are, or asks about their own bookings, reports, bills or credits without giving a mobile number, send them to the Support Agent first: it can open their signed-in record. Otherwise the specialist needs the registered mobile number and date of birth; ask for both if not given.`
6. **Conditions:** paste the section 6 text again (rule 1 gains the signed-in cases; rule 8 now says
   "Billing and Insurance Agent", the agent's real name).
7. **Billing and Insurance Agent description:** `Insurance acceptance, coverage and pre-approval estimates, bills, payment links, and HealthCredits refunds to the original account.`
8. **Save** and **Publish**.

**Test:** sign in on the website as a demo patient, open the chat and ask "Do you know who I am?". Expect "Hello
<name>, you're signed in" and the next visit. Signed out, the same question asks for mobile and date of birth. In the
Simulator, **{ } → Application Input** takes a code too, but codes come only from a signed-in page.

### Memory (no Talkdesk step)
- Every successful patient-specific answer (reports, bills, balance, order tracking, coverage, preferences, visit
  history) is now written to that patient's memory automatically, once per 10 minutes for the same answer. Bookings,
  orders and payments were already logged. All of it is searchable by `search_past_interactions`.
- Notes and transcripts are embedded for meaning search (Gemini); action logs are matched by keyword, typo and code.

### Optional: full chat transcripts
Talkdesk can send each closed chat to us. In **Builder / Integrations**, add an automated task "When **a messaging
conversation transcription is available**" with an HTTP or webhook action, if this account has one:
- URL: `https://teamxyz-mcp.onrender.com/api/webhooks/talkdesk/transcript?token=<JOBS_TOKEN from Render>`
- Body (JSON): `{"transcript": <Conversation transcription>, "interaction_id": <Interaction ID>, "session": "{{context.wellnest_session}}"}`

A transcript is filed only under the patient its session code or linked interaction names, never under a phone number
alone. If the account offers only the Email Notifier, skip this: tool answers and notes are already remembered.

## 11. Voice callers, refund confirmation and names (7 Nov, after live chat tests)

Found in the live chat: the agent refused to say a verified patient's own name, a refund went through without asking
first, "what did I ask last chat" found nothing, and "When is my next appointment?" after a refund returned Talkdesk's
"Sorry, I cannot handle your request right now". Server fixes are in; these are the Talkdesk steps.

1. **MCP Servers → Refresh**: 47 tools (new: `recognise_caller`; `request_credits_refund` gains `confirm`).
2. **Receptionist** (the orchestrator's own instructions), add:
   ```
   PHONE CALLS: On a voice call, when the patient asks about their own record, send them to the Support Agent first; it recognises the calling number. If it names a patient, ask "Am I speaking with <name>?" and for the date of birth only; never ask for the mobile number, use the patient_phone it returns. If they say it's someone else's phone, ask for their own registered number. Pass that mobile number to every specialist.
   NAMES: Once a patient is verified or signed in, use their first name and tell them their own details (name, bookings, balance) when asked. Privacy rules are about other people, not the verified patient.
   ```
3. **Support Agent** (no new skill: the Receptionist can't hold skills and Support is at 5): delete and re-add
   `open_signed_in_session`, then map session_code → **Application Input**, interaction_id → **Interaction ID**, and
   the new **caller_id → Caller ID**. On a call it names the caller from their number; on chat it opens the signed-in
   record. (`recognise_caller` exists on its own too but isn't needed.)
4. **Billing and Insurance Agent:** delete and re-add `request_credits_refund` so the new `confirm` input appears. Leave
   `confirm` **unmapped** (the AI fills it). Add to its instructions:
   ```
   REFUNDS: Call request_credits_refund without confirm first and read back the amount. Only after the patient says yes, call it again with confirm=yes, then read out the refund reference (RF-).
   ```
5. **Save → Publish.**
6. **Find the "cannot handle" error:** Agent Observability → open the 7 Nov 16:04 chat (it starts "Can I get 200 of my
   HealthCredits refunded") → click the failed turn and screenshot the error. The message is Talkdesk's own fallback,
   so the trace shows which agent or skill failed.

**Test on a phone call:** call the WellNest number from your registered mobile and say "When is my next appointment?".
It should ask "Am I speaking with <your name>?" and for your date of birth, not your number.

## 12. Fixes from the 7 Nov evening chat test

Seen live: a refund request went to the Pharmacy and HealthCredits Agent (which can't refund); after one specialist
answered, the next new topic got "Sorry, I cannot answer this question" / "cannot handle your request"; the agent asked
for the full name before answering; and it called a past visit the "next appointment" (fixed on the server).

1. **Conditions:** section 6 now has the updated box (rule 1 re-routes every message, rule 5 excludes refunds, rule 8
   takes any refund). Paste it whole.
2. **Every specialist agent's instructions** (Booking, Changes, Pharmacy and HealthCredits, Care Assist, Records,
   Billing and Insurance, Aftercare, Info, Outreach, Support), add at the end:
   ```
   OUT OF SCOPE: If the patient asks for something none of your skills can do, never say you can't help or tell them to contact another department. Say "Let me get the right team for that" and pass the conversation back for routing, with the request and the patient's mobile number.
   IDENTITY: Mobile number and date of birth are enough. Never ask for the full name to verify.
   ```
3. **Save → Publish**, then send me a screenshot of **Agent Observability** for a chat where a second topic still fails
   (click the failed turn). The trace shows whether Talkdesk re-routes after a specialist answers. If it doesn't, the
   orchestration may have a setting for it that I couldn't confirm from the docs (support.talkdesk.com blocks
   automated reading).
