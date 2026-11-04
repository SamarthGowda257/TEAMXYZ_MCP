"""WellNest HealthCredits: a closed-loop prepaid wallet per patient (1 credit = 1 rupee).

Spendable only on WellNest services (pharmacy, consultations, tests, bills); never cashed out at a counter
(RBI closed-loop PPI rules): unused credits are refunded to the source account on request.

Every debit carries an idempotency key, unique in the database, so a repeated request (double click, voice
lag, retried tool call) returns the first result and never debits twice. Balance updates are a single
conditional UPDATE (balance >= amount), so two concurrent debits can't overdraw the wallet.
Payment links: Razorpay Payment Links when RAZORPAY_KEY_ID/SECRET are set, otherwise a demo payment page on
this server (/pay/<code>), labelled as such.
"""

import logging
from datetime import timedelta

import httpx
from sqlalchemy import insert, select, update

from .. import config, db, events, notify
from ..util import Result, age_on, clean, fail, norm_code, ok, rupees
from . import patients as pt

log = logging.getLogger("wellnest.wallet")
W, T, L = db.health_credit_wallets, db.health_credit_txns, db.payment_links
# Top-up bonus tiers (credits added per rupee deposited): 5,000 or more -> 7%, 2,000 or more -> 5%.
BONUS_TIERS = [(5000, 7), (2000, 5)]
LATE_CANCEL_FEE = 150          # cancelled within 2 hours of the slot (or no-show)


def bonus_for(amount: int) -> int:
    for floor, pct in BONUS_TIERS:
        if amount >= floor:
            return amount * pct // 100
    return 0


def balance(conn, patient_id) -> int:
    return int(conn.execute(select(W.c.balance).where(W.c.patient_id == patient_id)).scalar() or 0)


def _ensure(conn, patient_id) -> None:
    if conn.execute(select(W.c.patient_id).where(W.c.patient_id == patient_id)).first() is None:
        conn.execute(insert(W).values(patient_id=patient_id, balance=0, updated_at=config.now()))


def _txn(conn, patient_id, direction, amount, service, reference, key) -> str:
    code = pt.random_code("HC", 6)
    conn.execute(insert(T).values(txn_code=code, patient_id=patient_id, direction=direction, amount=amount,
                                  balance_after=balance(conn, patient_id), service=service, reference=reference,
                                  idempotency_key=key, created_at=config.now()))
    return code


def prior(conn, key) -> dict | None:
    r = conn.execute(select(T).where(T.c.idempotency_key == key)).mappings().first()
    return dict(r) if r else None


def debit(conn, patient_id, amount: int, service: str, reference: str, key: str) -> tuple[bool, str]:
    """Atomic debit inside the caller's transaction. Returns (ok, txn_code or reason). Idempotent on key."""
    if amount <= 0:
        return True, ""
    done = prior(conn, key)
    if done:
        return True, done["txn_code"]
    _ensure(conn, patient_id)
    res = conn.execute(update(W).where(W.c.patient_id == patient_id, W.c.balance >= amount)
                       .values(balance=W.c.balance - amount, updated_at=config.now()))
    if res.rowcount != 1:
        return False, "insufficient"
    return True, _txn(conn, patient_id, "debit", amount, service, reference, key)


def credit(conn, patient_id, amount: int, service: str, reference: str, key: str) -> str:
    if amount <= 0:
        return ""
    done = prior(conn, key)
    if done:
        return done["txn_code"]
    _ensure(conn, patient_id)
    conn.execute(update(W).where(W.c.patient_id == patient_id).values(balance=W.c.balance + amount, updated_at=config.now()))
    return _txn(conn, patient_id, "credit", amount, service, reference, key)


def minor(p: dict) -> bool:
    return bool(p.get("date_of_birth") and age_on(p["date_of_birth"]) < 18)


# ------------------------------------------------------------------ payment links (Razorpay or demo page)
def new_link(conn, p: dict, purpose: str, reference: str, amount: int, credits_to_add: int = 0) -> dict:
    code = pt.random_code("PL", 6)
    conn.execute(insert(L).values(link_code=code, patient_id=p["id"], purpose=purpose, reference=reference,
                                  amount_inr=amount, credits_to_add=credits_to_add, status="created",
                                  provider="razorpay" if razorpay_on() else "demo", created_at=config.now()))
    return {"code": code, "url": f"{config.PUBLIC_BASE_URL}/pay/{code}", "amount_inr": amount}


def razorpay_on() -> bool:
    return bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


def provider_url(link_code: str) -> str | None:
    """Created lazily when the patient opens /pay/<code>, so no tool waits on Razorpay. Returns the checkout URL."""
    with db.engine.begin() as c:
        row = c.execute(select(L).where(L.c.link_code == link_code)).mappings().first()
        if not row or row["status"] != "created" or row["provider"] != "razorpay":
            return None
        if row["provider_url"]:
            return row["provider_url"]
        p = pt.get_by_id(c, row["patient_id"])
    body = {"amount": row["amount_inr"] * 100, "currency": "INR", "reference_id": link_code,
            "description": f"WellNest {row['purpose']} {row['reference'] or ''}".strip()[:240],
            "customer": {"name": p["full_name"], "contact": p["phone"], **({"email": p["email"]} if p.get("email") else {})},
            "notify": {"sms": False, "email": False}, "reminder_enable": False,
            "callback_url": f"{config.PUBLIC_BASE_URL}/pay/{link_code}/done", "callback_method": "get"}
    r = httpx.post("https://api.razorpay.com/v1/payment_links", json=body, timeout=15,
                   auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
    if r.status_code not in (200, 201):
        log.warning("razorpay link failed %s: %s", r.status_code, r.text[:200])
        return None
    j = r.json()
    with db.engine.begin() as c:
        c.execute(update(L).where(L.c.link_code == link_code).values(provider_id=j.get("id"), provider_url=j.get("short_url")))
    return j.get("short_url")


def razorpay_paid(link_code: str) -> bool:
    """Ask Razorpay whether this link is paid (used on the return page, so a forged redirect can't mark it paid)."""
    with db.engine.connect() as c:
        row = c.execute(select(L).where(L.c.link_code == link_code)).mappings().first()
    if not row or not row["provider_id"]:
        return False
    r = httpx.get(f"https://api.razorpay.com/v1/payment_links/{row['provider_id']}", timeout=15,
                  auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
    return r.status_code == 200 and r.json().get("status") == "paid"


def mark_paid(link_code: str) -> dict:
    """The money arrived (Razorpay webhook / verified return, or the demo page). Applies it exactly once."""
    from . import pharmacy
    with db.engine.begin() as c:
        row = c.execute(select(L).where(L.c.link_code == link_code).with_for_update()).mappings().first()
        if not row:
            return {"ok": False, "error": "unknown link"}
        if row["status"] == "paid":
            return {"ok": True, "already": True, "purpose": row["purpose"]}
        c.execute(update(L).where(L.c.id == row["id"]).values(status="paid", paid_at=config.now()))
        p = pt.get_by_id(c, row["patient_id"])
        out = {"ok": True, "purpose": row["purpose"], "amount_inr": row["amount_inr"]}
        if row["purpose"] == "topup":
            credit(c, p["id"], row["amount_inr"], "topup", link_code, f"topup:{link_code}")
            credit(c, p["id"], row["credits_to_add"] - row["amount_inr"], "bonus", link_code, f"bonus:{link_code}")
            out["balance"] = balance(c, p["id"])
            notify.email_and_sms(c, patient=p, template="credits_topup", key=f"topup:{link_code}",
                                 subject="HealthCredits added - WellNest Hospitals",
                                 body=f"Dear {p['full_name']},\n\nWe received {rupees(row['amount_inr'])}. "
                                      f"{row['credits_to_add']:,} HealthCredits were added to your wallet; the balance is now "
                                      f"{out['balance']:,} credits.\n\nHealthCredits can be used for medicines, consultations, "
                                      "tests and bills at WellNest.\n\nWellNest Hospitals",
                                 sms=f"WellNest: {row['credits_to_add']:,} HealthCredits added. Balance {out['balance']:,}.")
        elif row["purpose"] == "pharmacy":
            pharmacy.payment_received(c, row["reference"])
        elif row["purpose"] == "bill":
            c.execute(update(db.bills).where(db.bills.c.bill_code == row["reference"]).values(status="paid"))
    events.publish("payment.received", purpose=row["purpose"], link=link_code)
    return out


# ------------------------------------------------------------------ tools
def get_balance(phone, dob) -> Result:
    with db.engine.connect() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        bal = balance(c, p["id"])
        last = c.execute(select(T).where(T.c.patient_id == p["id"]).order_by(T.c.created_at.desc(), T.c.id.desc())
                         .limit(3)).mappings().all()
    recent = [{"txn": t["txn_code"], "type": t["direction"], "credits": t["amount"], "for": t["service"],
               "reference": t["reference"], "on": t["created_at"].strftime("%d %b %H:%M")} for t in last]
    msg = f"You have {bal:,} HealthCredits, worth {rupees(bal)}."
    if recent:
        t = recent[0]
        msg += f" Last transaction: {t['credits']:,} credits {'used' if t['type'] == 'debit' else 'added'} for {t['for']} on {t['on']}."
    if minor(p):
        msg += " As this account belongs to a child, spending needs the parent or guardian's approval."
    return ok(msg, balance_credits=bal, recent=recent)


def recharge(phone, amount, dob="") -> Result:
    try:
        amt = int(float(str(clean(amount)).replace(",", "").replace("rs", "").replace("₹", "").strip()))
    except ValueError:
        return fail("invalid_input", "How much would you like to add? For example 2,000 rupees.")
    if amt < 100 or amt > 50000:
        return fail("invalid_input", "You can add between 100 and 50,000 rupees at a time.")
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        bonus = bonus_for(amt)
        link = new_link(c, p, "topup", "", amt, amt + bonus)
        notify.email_and_sms(c, patient=p, template="credits_topup_link", key=f"tl:{link['code']}",
                             subject="Your HealthCredits top-up link - WellNest Hospitals",
                             body=f"Dear {p['full_name']},\n\nPay {rupees(amt)} here: {link['url']}\n"
                                  f"You will receive {amt + bonus:,} HealthCredits"
                                  f"{f' (including a {bonus:,} credit bonus)' if bonus else ''}.\n\nWellNest Hospitals",
                             sms=f"WellNest: pay {rupees(amt)} for {amt + bonus:,} HealthCredits: {link['url']}")
    tip = "" if bonus or amt >= 2000 else " Tip: adding 2,000 rupees or more gives a 5 percent bonus, and 5,000 or more gives 7 percent."
    return ok(f"I've sent a secure payment link for {rupees(amt)} to your phone and email. Once paid, "
              f"{amt + bonus:,} HealthCredits will be added{f', including a {bonus:,} credit bonus' if bonus else ''}.{tip}",
              payment_url=link["url"], amount_inr=amt, bonus_credits=bonus, total_credits=amt + bonus)


def pay(phone, reference, dob="") -> Result:
    """Pay a booking's consultation or test fee (WN-...) or a due bill (BL-...) from HealthCredits."""
    ref = clean(reference).upper()
    if not ref:
        return fail("invalid_input", "Which booking or bill would you like to pay? Please share the booking ID or bill ID.")
    from . import appointments as ap
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        if minor(p):
            return fail("not_allowed", "HealthCredits on a child's account can only be spent with the parent or guardian's "
                                       "approval. I can send a payment link to the guardian instead.")
        if ref.startswith("BL"):
            code = norm_code(ref, "BL")
            b = c.execute(select(db.bills).where(db.bills.c.bill_code == code, db.bills.c.patient_id == p["id"])).mappings().first()
            if not b:
                return fail("not_found", "I couldn't find that bill under your details.")
            if b["status"] == "paid":
                return ok(f"Bill {code} is already paid.", reference=code)
            amount, service, label = b["amount_inr"] - (b["insurer_paid_inr"] or 0), "bill", f"bill {code}"
        else:
            a = ap._get_booking(c, ref)
            if not a or a["patient_id"] != p["id"]:
                return fail("not_found", "I couldn't find that booking under your details. Please check the booking ID.")
            if a["status"] != "booked":
                return fail("not_allowed", f"Booking {a['booking_code']} is {a['status']}, so there is nothing to pay.")
            code, v = a["booking_code"], ap._appt_view(a)
            amount, service, label = v["fee_inr"], ("opd" if a["doctor_id"] else "lab"), f"your {v['with']} booking {code}"
        key = f"pay:{code}"
        if prior(c, key):
            return ok(f"{label[0].upper() + label[1:]} is already paid with HealthCredits.", reference=code,
                      balance_credits=balance(c, p["id"]))
        bal = balance(c, p["id"])
        if bal < amount:
            return fail("insufficient_credits", f"That's {rupees(amount)} and you have {bal:,} HealthCredits. I can send a "
                                                f"top-up link, or a payment link for the full amount.",
                        amount_inr=amount, balance_credits=bal)
        good, txn = debit(c, p["id"], amount, service, code, key)
        if not good:
            return fail("insufficient_credits", "Your balance changed just now. Please check it and try again.")
        if service == "bill":
            c.execute(update(db.bills).where(db.bills.c.bill_code == code).values(status="paid"))
        new_bal = balance(c, p["id"])
        pt.log(c, p["id"], "pay_with_health_credits", code, True, f"Paid {amount} credits for {label}")
        notify.email_and_sms(c, patient=p, template="credits_receipt", key=f"rcpt:{code}",
                             subject=f"Payment receipt {txn} - WellNest Hospitals",
                             body=f"Dear {p['full_name']},\n\n{amount:,} HealthCredits were used for {label}.\n"
                                  f"Transaction: {txn}\nBalance: {new_bal:,} credits\n\nThis receipt carries WellNest's PAN "
                                  "and GSTIN and is valid for Section 80D.\n\nWellNest Hospitals",
                             sms=f"WellNest: {amount:,} credits paid for {code}. Balance {new_bal:,}.")
    return ok(f"Done. {amount:,} HealthCredits paid for {label}. Your balance is now {new_bal:,} credits. Transaction {txn}.",
              reference=code, paid_credits=amount, balance_credits=new_bal, transaction=txn)


def refund_for_cancelled_booking(conn, p: dict, a: dict, starts_at) -> int:
    """If the fee was paid with HealthCredits, return it: in full when cancelled more than 2 hours ahead,
    otherwise minus the 150 rupee late fee. Returns the credits refunded."""
    paid = prior(conn, f"pay:{a['booking_code']}")
    if not paid:
        return 0
    late = (starts_at - config.now()) < timedelta(hours=2)
    amount = max(0, paid["amount"] - (LATE_CANCEL_FEE if late else 0))
    credit(conn, p["id"], amount, "refund", a["booking_code"], f"refund:{a['booking_code']}")
    return amount


def request_refund(phone, amount="", dob="") -> Result:
    """Unused credits back to the original bank account (never cash at a counter): 3 to 5 banking days."""
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        bal = balance(c, p["id"])
        try:
            amt = int(float(clean(amount).replace(",", ""))) if clean(amount) else bal
        except ValueError:
            return fail("invalid_input", "How many credits would you like refunded? Say 'all' for the full balance.")
        if bal <= 0:
            return fail("not_allowed", "There are no HealthCredits to refund on this account.")
        amt = min(max(amt, 1), bal)
        code = pt.random_code("RF", 5)
        good, _txn = debit(c, p["id"], amt, "refund_out", code, f"refund_out:{code}")
        if not good:
            return fail("insufficient_credits", "Your balance changed just now. Please try again.")
        c.execute(insert(db.credit_refunds).values(refund_code=code, patient_id=p["id"], amount=amt, status="requested",
                                                   created_at=config.now()))
        pt.log(c, p["id"], "request_credits_refund", code, True, f"Refund {amt} credits to source account")
        notify.email_and_sms(c, patient=p, template="credits_refund", key=f"rf:{code}",
                             subject=f"Refund request {code} - WellNest Hospitals",
                             body=f"Dear {p['full_name']},\n\nWe've started a refund of {rupees(amt)} (HealthCredits) to the "
                                  f"bank account or card you paid from. Reference {code}. It usually arrives in 3 to 5 "
                                  "banking days.\n\nWellNest Hospitals",
                             sms=f"WellNest: refund {code} of {rupees(amt)} started, 3-5 banking days.")
    return ok(f"I've started a refund of {rupees(amt)} to the account you originally paid from, reference {code}. "
              "Under RBI wallet rules credits can't be paid out as cash, so it goes back to the source account and "
              "usually arrives in 3 to 5 banking days.", refund_id=code, amount_inr=amt, balance_credits=bal - amt)
