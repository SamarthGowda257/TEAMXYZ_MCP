# Pharmacy V3: prescription-controlled medicine ordering (plan)

Status: proposal, 7 Nov 2026. Nothing here is built yet. It extends what V2 already has.

## 1. What already works (V2) and what's missing

| Area | V2 today | Gap this plan closes |
|---|---|---|
| Medicine classes | `schedule_class` OTC / H / H1 / X; X is refused by chat and phone | none |
| Prescription check | any prescription row whose name matches, signed in the last 6 months | no quantity, dose or refill limit: one 5-day antibiotic script can be reordered for 6 months |
| OTC limits | none | Dolo 650 can be ordered 20 strips at a time, every hour |
| Max dose | none | no daily-dose ceiling, no sum across brands (Dolo + Crocin are both paracetamol) |
| Who writes prescriptions | seed data only | doctors need a screen to prescribe; outside prescriptions need upload and pharmacist review |
| Payment | quote → confirm → credits debited at once, rest by link | money is taken before a pharmacist checks; rejected or failed deliveries need automatic refunds |
| Delivery | simulated zones and ETAs | no real courier, no failed-delivery handling, no ID or OTP check for H1 |
| Safety | none | allergies, duplicates, age limits, early-refill and abuse patterns |

## 2. Rules (the order the server checks them, for every line of an order)

1. **Known medicine:** found in the formulary. Otherwise suggest the closest match or the pharmacy desk.
2. **Schedule X:** never by chat or phone (as today).
3. **Patient fit:** below the medicine's minimum age → refuse and offer a paediatric consult. Listed allergy to an
   ingredient → refuse and hand off to a pharmacist. Pregnancy flag with a medicine marked unsafe → pharmacist.
4. **Prescription (H, H1):** must be covered by an **active prescription item**:
   - issued by a registered doctor, not cancelled, before its `valid_until`;
   - quantity left: `units_prescribed × (1 + refills_allowed) − units_dispensed` ≥ units ordered;
   - **too-early refill:** blocked until 80% of the previous supply's days have passed
     (days supply = units ÷ (dose per intake × times per day));
   - at most 30 days' supply per order for chronic medicines; the doctor's full course for short ones;
   - a dose change by the doctor ends the old item. A stopped medicine can't be ordered.
5. **OTC limits (per patient, from the pharmacist-set table):**
   - per order, e.g. Dolo 650 at most 2 strips;
   - per rolling 7 days, e.g. 4 strips;
   - **ingredient daily ceiling summed across brands**: paracetamol from Dolo + Crocin + any paracetamol on a
     prescription can't exceed the adult daily maximum over the days the order covers.
   - Hitting a limit gives a clear reason and offers a doctor, not just "no".
6. **Duplicate therapy:** two brands of the same ingredient in one order, or one already delivered in the last few
   days → ask "you already have Crocin from 3 November; do you want both?" and flag to the pharmacist.
7. **Stock:** as today (reserve, alternative generic, restock date). Substitution only if the prescription allows it.
8. **Delivery:** address serviceable; cold-chain and H1 need an adult present with OTP (H1 also a photo ID).
9. **Payment:** HealthCredits first (own wallet, then family wallet within its limits), remainder by payment link.

All limits live in the database, not in code, and are set by the hospital pharmacist. Clinical numbers (daily
maximums, age limits) must be signed off by the pharmacist and doctor before go-live. This plan doesn't supply them.

## 3. Database changes

New or changed tables (SQLAlchemy in `app/db.py`, additive migrations, seeds in `app/seed.py`):

- **`drug_rules`** (one row per active ingredient): `ingredient`, `max_daily_mg_adult`, `min_age_years`,
  `pregnancy_caution`, `otc_max_units_per_order`, `otc_max_units_per_7d`, `early_refill_pct` (default 80),
  `requires_pharmacist` (always review).
- **`pharmacy_inventory`** gains: `ingredient`, `strength_mg` (number, for dose sums), `units_per_pack`, `returnable`.
- **`prescriptions`** becomes a header: `rx_code` (RX-…), `patient_id`, `doctor_id`, `appointment_id`, `source`
  (`in_house` / `external_upload`), `status` (`active`, `pending_review`, `cancelled`, `expired`), `issued_at`,
  `valid_until`, `signed_by`, `signature_hash`, `cancel_reason`. Existing rows migrate as one item each.
- **`prescription_items`**: `rx_id`, `medicine_code` or `ingredient`, `strength_mg`, `dose_units`, `times_per_day`,
  `duration_days`, `units_prescribed`, `refills_allowed`, `units_dispensed`, `substitution_allowed`, `instructions`,
  `stopped_at`.
- **`dispensations`** (the Schedule H1 register and the source of "units dispensed"): `order_id`, `rx_item_id`,
  `medicine_code`, `units`, `pharmacist_id`, `verified_at`, `batch_no`, `expiry_date`.
- **`prescription_uploads`**: `patient_id`, `file_ref` (private storage), `status`, `reviewer_id`, `reason`,
  `created_rx_id`.
- **`patients`** gains `allergies` (ingredient list), `pregnant_until` (optional), `weight_kg` (children).
- **`pharmacy_orders`** gains `verification` (`auto`, `pending_pharmacist`, `approved`, `rejected`),
  `credits_held`, `delivery_id`, `rejection_reason`.
- **`deliveries`**: `order_id`, `provider`, `provider_job_id`, `status`, `attempts`, `rider_name`, `otp_hash`,
  `proof_url`, `last_event_at`, plus a `delivery_events` log of raw webhooks.

## 4. Money flow (hold, then capture)

1. Quote. Then the patient confirms.
2. **Hold:** stock reserved and credits moved to `credits_held`. Not spent yet, and the balance shows them as held.
3. **Verify:** OTC within limits is auto-approved. Any H or H1 item needs the pharmacist queue (target 15 minutes in
   opening hours). A rejection releases the hold at once, with an SMS giving the reason and a consult offer.
4. **Capture** on dispatch. **Refund** automatically if delivery finally fails or the order is cancelled before
   dispatch. After dispatch, medicines are non-returnable except wrong, damaged or expired items (pharmacist decides).
5. Payment links unpaid after 30 minutes release the reserved stock and any held credits.

## 5. Delivery partner

Make delivery a provider interface (`quote`, `create`, `cancel`, `status`, webhook) so the courier can change
without touching the order logic. Keep the current simulated provider for demos and tests.

- **Dunzo:** check before choosing it. Its delivery business largely stopped in 2024–25 and I couldn't confirm a
  working public API. Look at hyperlocal APIs such as Porter, Shadowfax or Borzo, the hospital's own riders, or
  ONDC logistics.
- Handle courier cancellations (re-book once, then tell the patient), no rider found (offer pickup at the pharmacy
  counter), patient not home (second attempt, then return to the pharmacy and refund), and OTP or ID checks for H1
  and cold-chain medicines.
- Courier webhooks must be signed and processed once each (we store event IDs).

## 6. Doctor and pharmacist screens (website staff console, not Talkdesk)

- **Doctor → Prescribe:** pick a patient from today's list. Add items from the formulary with dose, times per day,
  days and refills; the units are worked out. Sign. The patient gets an SMS: "Dr. X prescribed … You can order it on
  chat." The doctor can stop an item or change its dose.
- **Pharmacist → Queue:** orders waiting for review, uploaded prescriptions to approve or reject (with a reason),
  the dispensing register with batch and expiry, and the limits table.
- **Patient → My prescriptions:** what can be ordered, how much is left, and the next refill date. Upload an
  outside prescription (signed in).

## 7. Talkdesk changes (kept inside the 5-skill limit)

No new agent is needed. The Pharmacy and HealthCredits Agent's skills become:

| Skill | Change |
|---|---|
| `check_medicine_stock` | Optional phone. Returns stock, price, schedule, and "you can order up to N; prescription valid until …" |
| `order_medicine` | Same inputs. Messages now cover limits, duplicates, review wait, holds and reasons |
| `track_medicine_order` | Moved here from Records. Includes the pharmacist review and courier status |
| `get_health_credits_balance` | Shows held credits too |
| `pay_with_health_credits` | Unchanged |

`recharge_health_credits` moves to the Billing and Insurance Agent (swapped for something rarely used there).
New tool calls all return the usual `{ok, message, data}` with a ready-to-say reason.

## 8. Edge cases to test (each becomes a unit test)

- Dolo: 2 strips ok; a third strip in the same week refused with the reason; Dolo + Crocin together counts as
  paracetamol.
- Antibiotic course of 15 tablets: reordering after delivery is refused (no refills); reordering a chronic medicine on
  day 10 of 30 is refused as too early, and on day 25 is allowed.
- Prescription cancelled by the doctor while an order is pending → the pharmacist sees it, the order is rejected, and
  the credits come back.
- Dose changed: the old item is stopped and the new item's quantities apply.
- Outside prescription: an upload waits for review and can't be ordered until approved; a rejected upload gives the
  reason.
- Child account: age limits, weight-based items go to the pharmacist, and the payment link goes to the guardian.
- Family member ordering for a parent with shared credits: within the wallet limits, the prescription must be the
  parent's, and the delivery address is confirmed.
- Allergy listed for an ingredient → refused and handed off.
- Two orders sent at once with the same idempotency key → one order. Two different orders racing for the last strip
  → one gets an alternative or backorder.
- Credits less than the total → split with a link. An unpaid link expires and releases the hold.
- Courier cancels, no rider, patient not home, and an OTP mismatch for H1.
- Out of stock while waiting for pharmacist review → alternative offered if substitution is allowed, else backorder.
- Expired batch in stock is never dispensed (batch expiry checked at dispatch).
- Voice call: the medicine name is misheard, so the brand and strength are read back before confirming.

## 9. Build order

1. Schema, migration and seed (rules, prescription items, dispensations); old prescriptions migrated.
   *Test: existing pharmacy tests still pass.*
2. Rules engine `can_dispense()` with the checks in section 2, and the tool messages.
   *Test: every edge case in section 8.*
3. Hold, capture and refund money flow, plus pharmacist review states.
4. Doctor Prescribe screen and pharmacist queue (staff console). Patient "My prescriptions" and upload.
5. Delivery provider interface: simulated first, then the chosen courier's sandbox.
6. Talkdesk skill swap (section 7) and a live chat run of section 8.

## 10. Decisions needed from the team

1. Courier: which partner, or our own riders? This needs their API sandbox keys in Render.
2. OTC limits and daily maximums: the hospital pharmacist must give and sign off the numbers.
3. Do we accept outside prescriptions (uploads), or only WellNest doctors' prescriptions?
4. Pharmacist review hours: what happens to H or H1 orders at night (queue until morning, or refuse)?
5. Legal: online sale and delivery of prescription medicines in India sits under rules that are still in draft (the
   2018 e-pharmacy draft). Have the hospital's compliance team confirm the model before real patients use it.
