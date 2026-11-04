"""In-chat mini-pharmacy: stock, prescription rules, doorstep delivery and HealthCredits checkout.

Prescription rules (Drugs and Cosmetics Act 1940 / Rules 1945, enforced on the server, not by the agent):
  OTC        sold to any adult.
  H, H1      need a prescription for that medicine on file from the last 6 months; otherwise refused and the
             patient is offered a General Medicine consultation instead.
  X          never sold by chat or phone (in-person consultation only).
Cold-chain medicines (insulin) go in an insulated pouch and need an adult at home to receive them (OTP handover).
Delivery: within 5 km in 90 minutes, elsewhere in Bengaluru the same day; free from 500 rupees, else 50 rupees.
Orders are quoted first and placed only with confirm=yes; the same order repeated within a minute is the same order.
"""

import hashlib
import re
from datetime import datetime, time, timedelta

from sqlalchemy import insert, or_, select, update

from .. import config, db, events, notify
from ..util import Result, clean, fail, human_date, human_time, norm_code, ok, rupees, yes_no
from . import calendar as cal
from . import patients as pt
from . import wallet

INV, ORD, RX = db.pharmacy_inventory, db.pharmacy_orders, db.prescriptions
RX_VALID_DAYS = 182
FREE_DELIVERY_FROM, DELIVERY_FEE = 500, 50
ZONE1 = ("marathahalli", "kadubeesanahalli", "munnekollal", "brookefield", "bellandur")     # under 5 km: 90 minutes
ZONE2 = ("whitefield", "hsr", "koramangala", "indiranagar")                                  # 5-15 km: same day
PHARMACY_DESK = "080 4000 1240"
GP = "Dr. Anil Kumar"                      # General Medicine, 600 rupees, Monday to Saturday mornings
NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
       "nine": 9, "ten": 10, "single": 1, "couple": 2}
UNITS = r"(?:strips?|packs?|packets?|box(?:es)?|bottles?|pens?|tubes?|inhalers?|sachets?|vials?|units?|tabs?|tablets?)"
SCHEDULE_WORDS = {"OTC": "available without a prescription", "H": "a prescription medicine (Schedule H)",
                  "H1": "a prescription medicine (Schedule H1)", "X": "a controlled medicine (Schedule X)"}


# ------------------------------------------------------------------ lookup
def _tokens(text: str) -> list[str]:
    t = re.sub(r"(\d)([a-z])", r"\1 \2", clean(text).lower())
    return [w for w in re.findall(r"[a-z]+|\d+", t) if w not in ("mg", "mcg", "ml", "iu", "of", "the", "tablet", "tablets",
                                                                     "tab", "tabs", "capsule", "capsules", "medicine")]


def find(conn, text) -> dict | None:
    q = _tokens(text)
    words = [w for w in q if not w.isdigit()]
    if not words:
        return None
    best, best_score = None, 0.0
    for r in conn.execute(select(INV)).mappings():
        hay = f"{r['brand_name']} {r['generic_name']} {r['strength']}".lower()
        hay_t = set(_tokens(hay))
        hit_words = [w for w in words if w in hay_t or any(h.startswith(w) and len(w) >= 4 for h in hay_t)]
        if not hit_words:
            continue
        score = len(hit_words) + 0.5 * sum(1 for n in q if n.isdigit() and n in hay_t)
        if any(w in r["brand_name"].lower() for w in hit_words):
            score += 0.5                                     # asked for the brand: prefer it over the generic
        if r["stock_qty"] > 0:
            score += 0.1
        if score > best_score:
            best, best_score = dict(r), score
    return best


def _parse_items(text: str, quantity) -> list[tuple[str, int]]:
    parts = [x.strip() for x in re.split(r",|;|\band\b|\+|&|\bplus\b", clean(text), flags=re.I) if x.strip()]
    out = []
    for part in parts or [clean(text)]:
        qty = None
        m = re.match(rf"^\s*(\d+|{'|'.join(NUM)})\b\s*(?:x\s*)?(?:{UNITS}\s*(?:of\s+)?)?", part, flags=re.I)
        if m and m.group(0).strip():
            n = m.group(1).lower()
            qty, part = (int(n) if n.isdigit() else NUM[n]), part[m.end():]
        m2 = re.search(r"\s+x\s*(\d+)\s*$", part, flags=re.I)
        if m2:
            qty, part = int(m2.group(1)), part[:m2.start()]
        out.append((part.strip(), qty))
    single = len(out) == 1
    try:
        q_param = int(float(clean(quantity))) if clean(quantity) else None
    except ValueError:
        q_param = None
    return [(name, max(1, min(20, (q_param if single and q_param else None) or qty or 1))) for name, qty in out]


def _resolve(conn, text, quantity) -> tuple[list[tuple[dict, int]], list[str]]:
    items = _parse_items(text, quantity)
    found, missing = [], []
    for name, qty in items:
        row = find(conn, name)
        (found.append((row, qty)) if row else missing.append(name))
    if missing and len(items) > 1:                      # "Amoxicillin and Clavulanate" is one medicine, not two
        whole = find(conn, text)
        if whole:
            return [(whole, items[0][1])], []
    return found, missing


def _eta_text(dt: datetime | None) -> str:
    if not dt:
        return "soon"
    day = "today" if dt.date() == config.today() else ("tomorrow" if dt.date() == config.today() + timedelta(days=1) else human_date(dt.date()))
    return f"{day} at {human_time(dt.strftime('%H:%M'))}"


def _alt(conn, row) -> dict | None:
    if not row.get("alternative_code"):
        return None
    a = conn.execute(select(INV).where(INV.c.medicine_code == row["alternative_code"])).mappings().first()
    return dict(a) if a and a["stock_qty"] > 0 else None


def _label(r: dict) -> str:
    return f"{r['brand_name']} ({r['generic_name']} {r['strength']})"


def describe(conn, row: dict, qty: int = 1) -> dict:
    alt = _alt(conn, row)
    return {"medicine": _label(row), "code": row["medicine_code"], "pack": row["pack"], "price_inr": row["unit_price_inr"],
            "in_stock": row["stock_qty"] >= qty, "stock_qty": row["stock_qty"], "schedule": row["schedule_class"],
            "prescription_needed": row["schedule_class"] != "OTC", "cold_chain": row["cold_chain"],
            "restock_eta": _eta_text(row["restock_eta"]) if row["stock_qty"] < qty else None,
            "generic_alternative": f"{_label(alt)} at {alt['unit_price_inr']} rupees" if alt else None}


def check_stock(medicine_name) -> Result:
    if not clean(medicine_name):
        return fail("invalid_input", "Which medicine would you like me to check?")
    with db.engine.connect() as c:
        rows, missing = _resolve(c, medicine_name, "")
        if not rows:
            return fail("not_found", f"I couldn't find {clean(medicine_name)} in our hospital pharmacy list. Please check the "
                                     f"name on the prescription, or call the pharmacy desk on {PHARMACY_DESK}.")
        info = [describe(c, r, q) for r, q in rows]
        lines = []
        for (r, q), d in zip(rows, info):
            if r["schedule_class"] == "X":
                lines.append(f"{d['medicine']} is a controlled medicine (Schedule X). It can't be ordered by chat or phone; "
                             "it needs an in-person consultation and a signed prescription.")
                continue
            line = (f"{d['medicine']}, {r['pack']}: {'in stock' if d['in_stock'] else 'out of stock'} at "
                    f"{r['unit_price_inr']} rupees.")
            if not d["in_stock"]:
                line += f" The next batch arrives {d['restock_eta']}."
                if d["generic_alternative"]:
                    line += f" The same medicine, {d['generic_alternative']}, is in stock right now."
            line += f" It is {SCHEDULE_WORDS[r['schedule_class']]}"
            line += "." if r["schedule_class"] == "OTC" else ", so we need a doctor's prescription from the last 6 months on file."
            if r["cold_chain"]:
                line += " It travels in a cooled pouch and an adult must be home to receive it."
            lines.append(line)
        if missing:
            lines.append(f"I couldn't find {', '.join(missing)} in our list.")
    return ok(" ".join(lines) + " Would you like me to order it for home delivery?", medicines=info)


# ------------------------------------------------------------------ prescription check
def active_prescription(conn, patient_id, row) -> dict | None:
    """A prescription for this medicine (any of its active ingredients) signed in the last 6 months."""
    names = [w for w in re.findall(r"[a-z]+", row["generic_name"].lower()) if len(w) >= 5 and w not in ("human", "glargine")]
    names = names or [row["generic_name"].lower().split()[0]]
    since = config.today() - timedelta(days=RX_VALID_DAYS)
    q = select(RX).where(RX.c.patient_id == patient_id, or_(*[RX.c.medicine_name.ilike(f"%{n}%") for n in names]),
                         or_(RX.c.start_date >= since, RX.c.end_date >= config.today()))
    r = conn.execute(q.order_by(RX.c.start_date.desc())).mappings().first()
    return dict(r) if r else None


def _zone(address: str) -> tuple[str, datetime]:
    a, now = address.lower(), config.now()
    if any(z in a for z in ZONE1):
        return "express", now + timedelta(minutes=90)
    if any(z in a for z in ZONE2) or now.hour < 17:
        return "same_day", datetime.combine(now.date(), time(21)) if now.hour < 17 else now + timedelta(hours=4)
    return "next_day", datetime.combine(now.date() + timedelta(days=1), time(12))


# ------------------------------------------------------------------ order
def order(phone, dob, medicine_name, quantity="", delivery_address="", payment_method="health_credits", confirm="",
          wait_for_restock="") -> Result:
    if not clean(medicine_name):
        return fail("invalid_input", "Which medicine would you like to order, and how many strips?")
    go, wait = yes_no(confirm) is True, yes_no(wait_for_restock) is True
    method = "payment_link" if "link" in clean(payment_method).lower() or "upi" in clean(payment_method).lower() else "health_credits"
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        rows, missing = _resolve(c, medicine_name, quantity)
        if missing or not rows:
            return fail("not_found", f"I couldn't find {', '.join(missing) or clean(medicine_name)} in our pharmacy list. "
                                     f"Please check the name, or call the pharmacy desk on {PHARMACY_DESK}.")
        # 1. controlled medicines: never by chat or phone
        x = [r for r, _ in rows if r["schedule_class"] == "X"]
        if x:
            return fail("not_allowed", f"{_label(x[0])} is a controlled medicine (Schedule X). By law it can't be ordered by "
                                       "chat or phone; it needs an in-person consultation and a signed prescription at the "
                                       "hospital. I can book that consultation for you.", next_step="book_consultation")
        # 2. prescription medicines need a valid prescription on file
        no_rx = [r for r, _ in rows if r["schedule_class"] in ("H", "H1") and not active_prescription(c, p["id"], r)]
        if no_rx:
            r = no_rx[0]
            kind = "an antibiotic" if any(w in r["generic_name"].lower() for w in ("amoxicillin", "azithromycin", "cef", "cipro", "doxy")) else "a prescription medicine"
            otc = [x for x, _ in rows if x["schedule_class"] == "OTC"]
            return fail("prescription_required",
                        f"{_label(r)} is {kind} under Schedule {r['schedule_class']}, and I can't find a prescription for it "
                        "from the last 6 months on your record, so by law our pharmacy can't send it. I can book a quick "
                        f"consultation with {GP} in General Medicine, 600 rupees, so a doctor can review it and prescribe "
                        f"the right treatment. Shall I check his slots?"
                        + (f" The other items ({', '.join(x['brand_name'] for x in otc)}) don't need a prescription; I can "
                           "order those on their own." if otc else ""),
                        next_step="book_consultation", department="General Medicine", doctor=GP)
        # 3. stock
        short = [(r, q) for r, q in rows if r["stock_qty"] < q]
        if short and not wait:
            r, q = short[0]
            alt = _alt(c, r)
            msg = f"{_label(r)} is out of stock; the next batch arrives {_eta_text(r['restock_eta'])}."
            if alt:
                msg += (f" The same medicine, {_label(alt)}, is in stock now at {alt['unit_price_inr']} rupees "
                        f"(the brand is {r['unit_price_inr']}). Shall I send that instead, or reserve {r['brand_name']} for "
                        "when it arrives?")
            else:
                msg += " Shall I reserve it so it's sent as soon as it arrives?"
            return fail("out_of_stock", msg, alternative=_label(alt) if alt else None, restock_eta=_eta_text(r["restock_eta"]))
        # 4. price, delivery and payment plan
        items = [{"code": r["medicine_code"], "name": _label(r), "pack": r["pack"], "qty": q, "unit_price": r["unit_price_inr"],
                  "line_total": r["unit_price_inr"] * q, "schedule": r["schedule_class"], "chronic": bool(r["chronic"]),
                  "backorder": r["stock_qty"] < q} for r, q in rows]
        subtotal = sum(i["line_total"] for i in items)
        fee = 0 if subtotal >= FREE_DELIVERY_FROM else DELIVERY_FEE
        total = subtotal + fee
        address = clean(delivery_address) or (p.get("address") or "")
        if not address:
            return fail("invalid_input", "Which address should we deliver to?")
        zone, eta = _zone(address)
        backorder = any(i["backorder"] for i in items)
        if backorder:
            eta = max([r["restock_eta"] for r, q in rows if r["stock_qty"] < q and r["restock_eta"]] + [eta]) + timedelta(minutes=30)
        cold = any(r["cold_chain"] for r, _ in rows)
        bal = wallet.balance(c, p["id"])
        child = wallet.minor(p)
        credits = 0 if (method == "payment_link" or child) else min(bal, total)
        due = total - credits
        summary = ", ".join(f"{i['qty']} x {i['name'].split(' (')[0]}" for i in items)
        cold_note = (" Insulin and other cold-chain medicines travel in an insulated ice-pack pouch; please make sure an "
                     "adult is at home to receive them and put them in the fridge straight away. We can't leave them at a "
                     "gate or doorstep." if cold else "")
        if not go:
            pay_line = (f"You have {bal:,} HealthCredits. Shall I use {credits:,} credits"
                        + (f" and send a payment link for the remaining {rupees(due)}?" if due else
                           f"? Your balance would then be {bal - credits:,}.")
                        if credits else
                        ("As this is a child's account, the payment link will go to the parent or guardian. Shall I place it?"
                         if child else f"I'll send a secure payment link for {rupees(total)}. Shall I place the order?"))
            when = "within 90 minutes" if zone == "express" and not backorder else _eta_text(eta)
            return ok(f"{summary}: {rupees(subtotal)}"
                      + (f", plus {rupees(fee)} delivery (free from 500 rupees)" if fee else ", with free delivery")
                      + f", total {rupees(total)}. Delivery to {address} {when}. {pay_line}{cold_note}",
                      quote={"items": items, "subtotal_inr": subtotal, "delivery_fee_inr": fee, "total_inr": total,
                             "credits_to_use": credits, "amount_by_link_inr": due, "balance_credits": bal},
                      needs="confirm")
        # 5. place it (idempotent: the same order in the same minute is the same order)
        key = hashlib.sha256(f"{p['id']}|{sorted((i['code'], i['qty']) for i in items)}|{total}|{address}|"
                             f"{config.now().strftime('%Y%m%d%H%M')}".encode()).hexdigest()[:40]
        dup = c.execute(select(ORD).where(ORD.c.idempotency_key == key)).mappings().first()
        if dup:
            return ok(f"That order is already placed: {dup['order_code']}, total {rupees(dup['total_inr'])}.",
                      order_id=dup["order_code"], status=dup["status"], duplicate=True)
        code = _new_code(c)
        status = "awaiting_payment" if due else ("awaiting_stock" if backorder else "confirmed")
        c.execute(insert(ORD).values(order_code=code, patient_id=p["id"], items=items, subtotal_inr=subtotal,
                                     delivery_fee_inr=fee, total_inr=total, credits_used=credits, amount_due_inr=due,
                                     delivery_address=address[:200], zone=zone, status=status, cold_chain=cold, eta=eta,
                                     idempotency_key=key, created_at=config.now(), updated_at=config.now()))
        if credits:
            good, txn = wallet.debit(c, p["id"], credits, "pharmacy", code, f"order:{code}")
            if not good:
                raise RuntimeError("balance changed")      # rolls the order back; the guard returns a retry message
        link = None
        if due:
            link = wallet.new_link(c, p, "pharmacy", code, due)
            c.execute(update(ORD).where(ORD.c.order_code == code).values(payment_link_code=link["code"]))
        for r, q in rows:
            if r["stock_qty"] >= q:
                c.execute(update(INV).where(INV.c.id == r["id"]).values(stock_qty=INV.c.stock_qty - q, updated_at=config.now()))
        new_bal = wallet.balance(c, p["id"])
        pt.log(c, p["id"], "order_medicine", code, True, f"{summary}; total {total}; credits {credits}; due {due}")
        _order_messages(c, p, code, items, subtotal, fee, total, credits, new_bal, due, link, address, eta, zone, cold,
                        backorder, child)
    events.publish("pharmacy.ordered", patient_id=p["id"], order_id=code)
    parts = [f"Done. Order {code}: {summary}, total {rupees(total)}."]
    if credits:
        parts.append(f"{credits:,} HealthCredits used; your balance is now {new_bal:,}.")
    if due:
        to = "your parent or guardian" if child else "your phone and email"
        parts.append(f"I've sent a payment link for {rupees(due)} to {to}; the order is sent as soon as it's paid.")
    if backorder:
        parts.append(f"It's reserved and will be sent when the stock arrives, around {_eta_text(eta)}.")
    elif not due:
        parts.append("Our rider will deliver it " + ("within 90 minutes" if zone == "express" else _eta_text(eta)) +
                     f" to {address}. You'll get an SMS with the tracking link.")
    return ok(" ".join(parts) + cold_note, order_id=code, total_inr=total, credits_used=credits, balance_credits=new_bal,
              amount_by_link_inr=due, payment_url=link["url"] if link else None, delivery_eta=_eta_text(eta), status=status,
              tracking_url=f"{config.PUBLIC_BASE_URL}/track/{code}")


def _new_code(c) -> str:
    while True:
        code = pt.random_code("PHARM", 5)
        if not c.execute(select(ORD.c.id).where(ORD.c.order_code == code)).first():
            return code


def _order_messages(c, p, code, items, subtotal, fee, total, credits, new_bal, due, link, address, eta, zone, cold,
                    backorder, child):
    lines = "\n".join(f"  {i['qty']} x {i['name']} ({i['pack']}) @ {i['unit_price']} = {i['line_total']} rupees" for i in items)
    track = f"{config.PUBLIC_BASE_URL}/track/{code}"
    body = (f"Dear {p['full_name']},\n\nYour medicine order {code} is placed.\n\n{lines}\n  Delivery: {fee} rupees\n"
            f"  Total: {total} rupees\n  Paid with HealthCredits: {credits} (balance {new_bal})\n"
            + (f"  To pay by link: {due} rupees - {link['url']}\n" if due else "")
            + f"\nDelivery to: {address}\nExpected: {_eta_text(eta)}\nTrack: {track}\n"
            + ("\nCold-chain medicine: an adult must receive it and refrigerate it immediately (2 to 8 C).\n" if cold else "")
            + "\nDispensed medicines can't be returned once they leave the pharmacy.\nPharmacy desk: 080 4000 1240\n\n"
              "WellNest Hospitals")
    notify.email_and_sms(c, patient=p, template="pharmacy_order", key=f"ord:{code}",
                         subject=f"Medicine order {code} placed - WellNest Hospitals", body=body,
                         sms=f"WellNest: order {code} placed, {total} rupees. Track: {track}")
    if child and due and p.get("caregiver_phone"):
        notify.queue(c, patient_id=p["id"], channel="sms", template="pharmacy_guardian_pay", to=p["caregiver_phone"],
                     body=f"WellNest: please approve and pay {due} rupees for {p['full_name']}'s medicines: {link['url']}",
                     dedupe_key=f"ordg:{code}")
    # caregiver: delivery window only (operational), never the medicine list (DPDP)
    notify.to_caregiver(c, p, template="pharmacy_order", key=f"ord:{code}",
                        subject=f"Medicine delivery for {p['full_name']}",
                        body=f"Hello {p.get('caregiver_name') or ''},\n\nA WellNest pharmacy delivery ({code}) for "
                             f"{p['full_name']} is expected {_eta_text(eta)} at {address}."
                             + (" It contains cold-chain medicine: please make sure an adult is home to receive it." if cold else "")
                             + "\n\nWellNest Hospitals",
                        sms=f"WellNest: delivery {code} for {p['full_name']} expected {_eta_text(eta)}.")
    if not due and not backorder:
        cal.upsert(c, ref=code, patient=p, kind="delivery", title=f"WellNest medicine delivery ({code})", starts_at=eta - timedelta(minutes=90 if zone == "express" else 60),
                   minutes=90 if zone == "express" else 60, location=address,
                   details=f"Order {code}: {', '.join(i['name'] for i in items)}. Tracking: {track}"
                           + (". Cold chain: an adult must receive it." if cold else ""))
    for i in items:
        if i["chronic"]:
            due_day = config.today() + timedelta(days=26)
            cal.upsert(c, ref=f"refill:{p['id']}:{i['code']}", patient=p, kind="refill",
                       title=f"Refill alert: {i['name'].split(' (')[0]} 30-day supply due",
                       starts_at=datetime.combine(due_day, time(9)), minutes=0, all_day=True,
                       location="WellNest Hospitals pharmacy (24 hours), Gate 1",
                       details=f"Your 30-day supply of {i['name']} runs out in about 4 days. Reorder in the WellNest chat, "
                               f"call 080 4000 1240, or visit {config.PUBLIC_BASE_URL}.")


def payment_received(conn, order_code) -> None:
    o = conn.execute(select(ORD).where(ORD.c.order_code == order_code)).mappings().first()
    if not o or o["status"] != "awaiting_payment":
        return
    backorder = any(i.get("backorder") for i in o["items"])
    conn.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="awaiting_stock" if backorder else "confirmed",
                                                               amount_due_inr=0, updated_at=config.now()))


# ------------------------------------------------------------------ track / cancel
def track(phone, dob="", order_id="", action="") -> Result:
    want_cancel = "cancel" in clean(action).lower()
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        q = select(ORD).where(ORD.c.patient_id == p["id"])
        if clean(order_id):
            q = q.where(ORD.c.order_code == norm_code(order_id, "PHARM"))
        o = c.execute(q.order_by(ORD.c.created_at.desc(), ORD.c.id.desc())).mappings().first()
        if not o:
            return fail("not_found", "I couldn't find a medicine order on your record." if not clean(order_id) else
                        "I couldn't find that order under your details. Please check the order number.")
        o = dict(o)
        what = ", ".join(f"{i['qty']} x {i['name'].split(' (')[0]}" for i in o["items"])
        if want_cancel:
            if o["status"] in ("dispatched", "delivered"):
                return fail("not_allowed", f"Order {o['order_code']} has already left the pharmacy with our rider. Under our "
                                           "drug safety policy dispensed medicines can't be recalled or restocked once "
                                           "dispatched. If you refuse it at the door, the pharmacy audit team checks the "
                                           "sealed package before any partial credit refund is considered.",
                            order_id=o["order_code"], status=o["status"])
            if o["status"] == "cancelled":
                return ok(f"Order {o['order_code']} is already cancelled.", order_id=o["order_code"], status="cancelled")
            c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="cancelled", updated_at=config.now()))
            back = o["credits_used"]
            wallet.credit(c, p["id"], back, "refund", o["order_code"], f"order_refund:{o['order_code']}")
            for i in o["items"]:
                if not i.get("backorder"):
                    c.execute(update(INV).where(INV.c.medicine_code == i["code"]).values(stock_qty=INV.c.stock_qty + i["qty"]))
            if o["payment_link_code"]:
                c.execute(update(db.payment_links).where(db.payment_links.c.link_code == o["payment_link_code"],
                                                         db.payment_links.c.status == "created").values(status="expired"))
            cal.cancel(c, o["order_code"])
            pt.log(c, p["id"], "cancel_medicine_order", o["order_code"], True, f"Cancelled; refunded {back} credits")
            return ok(f"Cancelled order {o['order_code']} ({what})."
                      + (f" {back:,} HealthCredits are back in your wallet; balance {wallet.balance(c, p['id']):,}." if back else ""),
                      order_id=o["order_code"], status="cancelled", refunded_credits=back)
    st = o["status"]
    say = {"awaiting_payment": f"is waiting for the payment of {rupees(o['amount_due_inr'])} by the link we sent",
           "awaiting_stock": f"is reserved and will be sent when the stock arrives, around {_eta_text(o['eta'])}",
           "confirmed": "is being packed at the pharmacy",
           "dispatched": f"is on the way with our rider, expected {_eta_text(o['eta'])}",
           "delivered": "was delivered", "cancelled": "was cancelled"}[st]
    return ok(f"Order {o['order_code']} ({what}) {say}. Tracking: {config.PUBLIC_BASE_URL}/track/{o['order_code']}",
              order_id=o["order_code"], status=st, eta=_eta_text(o["eta"]), total_inr=o["total_inr"])


def public_status(order_code) -> dict | None:
    """For the /track page: no names, no medicines, just where the parcel is."""
    with db.engine.connect() as c:
        o = c.execute(select(ORD).where(ORD.c.order_code == norm_code(order_code, "PHARM"))).mappings().first()
    if not o:
        return None
    return {"order_id": o["order_code"], "status": o["status"].replace("_", " "), "eta": _eta_text(o["eta"]),
            "cold_chain": o["cold_chain"]}


# ------------------------------------------------------------------ background progress (jobs runner)
def advance() -> dict:
    """Restock arrived batches, send packed orders out, mark delivered, release unpaid orders after 24 hours."""
    now, n = config.now(), {"dispatched": 0, "delivered": 0, "restocked": 0, "expired": 0}
    with db.engine.begin() as c:
        res = c.execute(update(INV).where(INV.c.stock_qty == 0, INV.c.restock_eta.is_not(None), INV.c.restock_eta <= now)
                        .values(stock_qty=100, restock_eta=None, updated_at=now))
        n["restocked"] = res.rowcount or 0
        for o in c.execute(select(ORD).where(ORD.c.status == "awaiting_stock")).mappings().all():
            if all(c.execute(select(INV.c.stock_qty).where(INV.c.medicine_code == i["code"])).scalar() >= i["qty"] for i in o["items"]):
                for i in o["items"]:
                    c.execute(update(INV).where(INV.c.medicine_code == i["code"]).values(stock_qty=INV.c.stock_qty - i["qty"]))
                c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="confirmed", updated_at=now))
        for o in c.execute(select(ORD).where(ORD.c.status == "confirmed", ORD.c.updated_at <= now - timedelta(minutes=10))).mappings().all():
            eta = max(o["eta"] or now, now + timedelta(minutes=60 if o["zone"] == "express" else 120))
            c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="dispatched", dispatched_at=now, eta=eta, updated_at=now))
            p = pt.get_by_id(c, o["patient_id"])
            track_url = f"{config.PUBLIC_BASE_URL}/track/{o['order_code']}"
            notify.email_and_sms(c, patient=p, template="pharmacy_dispatched", key=f"disp:{o['order_code']}",
                                 subject=f"Dispatched: medicine order {o['order_code']} is on its way",
                                 body=f"Dear {p['full_name']},\n\nOrder {o['order_code']} has left the pharmacy and is expected "
                                      f"{_eta_text(eta)}.\nLive tracking: {track_url}\n"
                                      + ("\nCold-chain medicine: the rider will ask for an OTP; an adult must receive it.\n" if o["cold_chain"] else "")
                                      + "\nWellNest Hospitals",
                                 sms=f"WellNest: order {o['order_code']} is on its way, expected {_eta_text(eta)}. {track_url}")
            notify.to_caregiver(c, p, template="pharmacy_dispatched", key=f"disp:{o['order_code']}",
                                subject=f"Medicine delivery for {p['full_name']} is on its way",
                                body=f"Delivery {o['order_code']} for {p['full_name']} is expected {_eta_text(eta)}.",
                                sms=f"WellNest: delivery {o['order_code']} for {p['full_name']} expected {_eta_text(eta)}.")
            n["dispatched"] += 1
        res = c.execute(update(ORD).where(ORD.c.status == "dispatched", ORD.c.eta <= now).values(status="delivered", updated_at=now))
        n["delivered"] = res.rowcount or 0
        for o in c.execute(select(ORD).where(ORD.c.status == "awaiting_payment", ORD.c.created_at <= now - timedelta(hours=24))).mappings().all():
            c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="cancelled", updated_at=now))
            wallet.credit(c, o["patient_id"], o["credits_used"], "refund", o["order_code"], f"order_refund:{o['order_code']}")
            n["expired"] += 1
    return n


def refill_reminders() -> int:
    """4 days before a 30-day supply of a maintenance medicine runs out: email/SMS the patient (and caregiver)."""
    T, n = config.today(), 0
    with db.engine.begin() as c:
        rows = c.execute(select(RX).where(RX.c.end_date == T + timedelta(days=4))).mappings().all()
        for rx in rows:
            p = pt.get_by_id(c, rx["patient_id"])
            if not p or p["is_guest"]:
                continue
            item = find(c, rx["medicine_name"])
            if not item or not item["chronic"]:
                continue
            ends = human_date(rx["end_date"])
            notify.email_and_sms(c, patient=p, template="refill_reminder", key=f"refill:{rx['id']}:{rx['end_date']}",
                                 subject=f"Refill reminder: your {rx['medicine_name']} runs out on {ends}",
                                 body=f"Dear {p['full_name']},\n\nYour supply of {rx['medicine_name']} runs out on {ends}. "
                                      "Reply in the WellNest chat with 'refill my medicine' and we'll deliver it home (free from "
                                      f"500 rupees), or call the pharmacy on {PHARMACY_DESK}.\nIf your prescription is older than "
                                      "6 months, book a quick review with your doctor first.\n\nWellNest Hospitals",
                                 sms=f"WellNest: your {rx['medicine_name']} runs out {ends}. Reorder in chat or call {PHARMACY_DESK}.")
            notify.to_caregiver(c, p, template="refill_reminder", key=f"refill:{rx['id']}:{rx['end_date']}",
                                subject=f"Refill due for {p['full_name']}",
                                body=f"{p['full_name']}'s regular medicine runs out on {ends}. A refill can be ordered in the "
                                     "WellNest chat or by phone.", sms=f"WellNest: {p['full_name']}'s medicine refill is due by {ends}.")
            cal.upsert(c, ref=f"refill-rx:{rx['id']}", patient=p, kind="refill",
                       title=f"Refill alert: {rx['medicine_name']} runs out {ends}",
                       starts_at=datetime.combine(T, time(9)), minutes=0, all_day=True,
                       location="WellNest Hospitals pharmacy (24 hours), Gate 1",
                       details=f"Reorder {rx['medicine_name']} in the WellNest chat or call {PHARMACY_DESK}.")
            n += 1
    return n
