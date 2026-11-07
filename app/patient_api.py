"""Patient-facing pharmacy and HealthCredits wallet for the website (/api/me/...).

These routes are a thin web skin over `services/pharmacy.py` and `services/wallet.py`: every rule stays in
the services, so the website and the Talkdesk bot behave identically. That means the Schedule X ban, the
Schedule H/H1 prescription check, cold-chain handling, stock and in-stock generic alternatives, the delivery
fee and zone, split payment with HealthCredits, the shared family wallet and its limits, top-up bonus tiers,
refunds, idempotency, notifications and the audit log are all reused, never reimplemented here.

Every response carries the house envelope, `{"ok", "message", ...}`, with a ready-to-read sentence in `message`.
Writes go back through `out(Result)` exactly like the rest of /api. The read endpoints build the envelope
themselves rather than through `Result.as_dict()`, because that caps a reply at 2 KB for the voice agent and
would silently drop most of a 32-medicine catalogue or a page of transactions.

The signed-in patient comes from the bearer token only (the same `current_patient` dependency the rest of
/api/me uses); a patient_id or phone number is never read from a request body, so a patient can only ever
reach their own catalogue, orders and wallet.

  GET  /api/me/pharmacy?q=          search the hospital pharmacy list (Schedule X is shown, never orderable)
  GET  /api/me/pharmacy/{code}      one medicine: stock, restock date, generic alternative, prescription state
  POST /api/me/pharmacy/order       quote (confirm=false) then place (confirm=true) — the same two steps as chat
  GET  /api/me/orders               this patient's medicine orders
  POST /api/me/orders/{code}/cancel cancel while it is still cancellable (credits go back to the payer)
  GET  /api/me/wallet               balance, spendable including the family pool, transactions, bonus tiers
  POST /api/me/wallet/topup         a secure payment link for a top-up (no card details ever touch this app)
  GET  /api/me/wallet/sharing       who may draw on this wallet, and whose wallet this patient may draw on
  POST /api/me/wallet/sharing       add, change or stop a family member, with per-order and daily limits
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.sql import case

from . import config, db
from .services import patients as pt
from .services import pharmacy as ph
from .services import wallet as wl
from .util import clean, fail, human_date, mask_phone, rupees

router = APIRouter(prefix="/api/me")

INV, ORD, TXN, SHARE = db.pharmacy_inventory, db.pharmacy_orders, db.health_credit_txns, db.wallet_shares
MAX_QTY = 20                      # the pharmacy service caps a line at 20 packs; say so instead of silently clamping
CANCELLABLE = ("awaiting_payment", "awaiting_stock", "confirmed")
SCHEDULE_NOTE = {
    "OTC": "No prescription needed.",
    "H": "Prescription medicine (Schedule H): we need a doctor's prescription from the last 6 months on your record.",
    "H1": "Prescription medicine (Schedule H1): we need a doctor's prescription from the last 6 months on your record.",
    "X": "Controlled medicine (Schedule X): by law it cannot be ordered by chat, phone or website. It needs an "
         "in-person consultation and a signed prescription at the hospital pharmacy.",
}


# ------------------------------------------------------------------ auth and envelope
def _me(authorization: str = Header(default="")):
    """The same patient dependency as the rest of /api/me. Imported late so there is no import cycle."""
    from .api import current_patient
    return current_patient(authorization)


Me = Depends(_me)


def _out(res, status_fail: int = 400):
    from .api import out
    return out(res, status_fail)


def _patient(c, cp) -> dict:
    return pt.get_by_id(c, cp.id)


def _dob(p: dict) -> str:
    """The signed-in patient's own date of birth, so the services' server-side identity check still runs.
    The patient proved who they are with a password; this never comes from the request."""
    return p["date_of_birth"].isoformat() if p.get("date_of_birth") else ""


# ------------------------------------------------------------------ catalogue
def _rx_on_file(c, patient_id: int, row: dict) -> bool | None:
    """None for over-the-counter medicines; otherwise whether this patient has a valid prescription on record."""
    if row["schedule_class"] == "OTC":
        return None
    return bool(ph.active_prescription(c, patient_id, row))


def _card(c, row: dict, patient_id: int, with_rx: bool = True) -> dict:
    alt = ph._alt(c, row)
    out_of_stock = row["stock_qty"] <= 0
    return {
        "code": row["medicine_code"],
        "brand": row["brand_name"],
        "generic": row["generic_name"],
        "strength": row["strength"],
        "pack": row["pack"],
        "price_inr": row["unit_price_inr"],
        "schedule": row["schedule_class"],
        "schedule_note": SCHEDULE_NOTE[row["schedule_class"]],
        "prescription_needed": row["schedule_class"] != "OTC",
        "prescription_on_file": _rx_on_file(c, patient_id, row) if with_rx else None,
        "chronic": bool(row["chronic"]),
        "cold_chain": bool(row["cold_chain"]),
        "in_stock": not out_of_stock,
        "stock_qty": row["stock_qty"],
        "restock_eta": ph._eta_text(row["restock_eta"]) if out_of_stock else None,
        "orderable": row["schedule_class"] != "X",
        "alternative": {"code": alt["medicine_code"], "brand": alt["brand_name"], "generic": alt["generic_name"],
                        "strength": alt["strength"], "pack": alt["pack"], "price_inr": alt["unit_price_inr"]} if alt else None,
    }


@router.get("/pharmacy")
def pharmacy_search(q: str = Query(default=""), cp: Any = Me):
    """The hospital pharmacy list. Schedule X medicines are listed honestly but marked not orderable."""
    terms = [t for t in re.split(r"\s+", clean(q).lower()) if t][:5]
    where = [and_(*[or_(INV.c.brand_name.ilike(f"%{t}%"), INV.c.generic_name.ilike(f"%{t}%"),
                        INV.c.strength.ilike(f"%{t}%"), INV.c.medicine_code.ilike(f"%{t}%")) for t in terms])] if terms else []
    with db.engine.connect() as c:
        rows = c.execute(select(INV).where(*where)
                         .order_by(case((INV.c.stock_qty <= 0, 1), else_=0), INV.c.brand_name).limit(60)).mappings().all()
        meds = [_card(c, dict(r), cp.id) for r in rows]
    msg = (f"I couldn't find {clean(q)} in our hospital pharmacy list. Please check the name on the prescription, "
           f"or call the pharmacy desk on {ph.PHARMACY_DESK}." if not meds else
           f"{len(meds)} medicine{'s' if len(meds) != 1 else ''} in the hospital pharmacy list"
           + (f" matching {clean(q)}." if terms else f". Free delivery from {ph.FREE_DELIVERY_FROM} rupees."))
    return {"ok": True, "message": msg, "medicines": meds, "count": len(meds),
            "free_delivery_from_inr": ph.FREE_DELIVERY_FROM, "delivery_fee_inr": ph.DELIVERY_FEE,
            "pharmacy_desk": ph.PHARMACY_DESK}


@router.get("/pharmacy/{code}")
def pharmacy_one(code: str, cp: Any = Me):
    with db.engine.connect() as c:
        r = c.execute(select(INV).where(INV.c.medicine_code == clean(code).upper())).mappings().first()
        if not r:
            return _out(fail("not_found", "I couldn't find that medicine in our hospital pharmacy list. Please check the "
                                          f"name on the prescription, or call the pharmacy desk on {ph.PHARMACY_DESK}."))
        card = _card(c, dict(r), cp.id)
    bits = [f"{card['brand']} ({card['generic']} {card['strength']}), {card['pack']}: "
            + (f"in stock at {rupees(card['price_inr'])}." if card["in_stock"]
               else f"out of stock; the next batch arrives {card['restock_eta']}.")]
    if not card["in_stock"] and card["alternative"]:
        bits.append(f"The same medicine, {card['alternative']['brand']}, is in stock now at "
                    f"{rupees(card['alternative']['price_inr'])}.")
    bits.append(card["schedule_note"])
    if card["prescription_on_file"]:
        bits.append("Your prescription on file is valid.")
    if card["cold_chain"]:
        bits.append("It travels in a cooled pouch and an adult must be at home to receive it.")
    return {"ok": True, "message": " ".join(bits), "medicine": card}


# ------------------------------------------------------------------ order
class OrderLine(BaseModel):
    code: str
    qty: int = 1


class OrderReq(BaseModel):
    items: list[OrderLine] = []
    delivery_address: str = ""
    payment_method: str = "health_credits"      # health_credits | payment_link
    confirm: bool = False
    wait_for_restock: bool = False


def _phrase(row: dict) -> str:
    """The medicine as the pharmacy service's own matcher reads it. Separators the service splits a basket on
    (comma, semicolon, plus, ampersand, 'and') are blanked, so a brand like 'Aspirin + Atorvastatin 75/10
    (Sun Pharma)' stays one line instead of becoming two."""
    return re.sub(r"\s+", " ", re.sub(r"[,;+&]|\band\b", " ", f"{row['brand_name']} {row['strength']}", flags=re.I)).strip()


@router.post("/pharmacy/order")
def place_order(b: OrderReq, cp: Any = Me):
    """Quote first (confirm=false), place on confirm=true — the same two steps the chat and voice agents use,
    so the price, the delivery fee, the credit split and every refusal come from the pharmacy service."""
    merged: dict[str, int] = {}
    for i in b.items:
        code = clean(i.code).upper()
        if code:
            merged[code] = merged.get(code, 0) + int(i.qty or 1)
    lines = list(merged.items())
    if not lines:
        return _out(fail("invalid_input", "Which medicines would you like to order? Please add at least one to the basket."))
    if len(lines) > 8:
        return _out(fail("invalid_input", "Please order up to 8 different medicines at a time. The pharmacy desk on "
                                          f"{ph.PHARMACY_DESK} can help with a longer list."))
    if any(q < 1 or q > MAX_QTY for _, q in lines):
        return _out(fail("invalid_input", f"Please choose between 1 and {MAX_QTY} packs of each medicine."))
    with db.engine.connect() as c:
        rows = {r["medicine_code"]: dict(r) for r in
                c.execute(select(INV).where(INV.c.medicine_code.in_([x for x, _ in lines]))).mappings()}
        missing = [x for x, _ in lines if x not in rows]
        if missing:
            return _out(fail("not_found", "One of those medicines is no longer in our pharmacy list. Please refresh the "
                                          f"page, or call the pharmacy desk on {ph.PHARMACY_DESK}."))
        text = ", ".join(f"{q} x {_phrase(rows[x])}" for x, q in lines)
        # Safety net: the service resolves the basket from text, so check it reads back as exactly what was clicked.
        found, unresolved = ph._resolve(c, text, "")
        if unresolved or [(r["medicine_code"], q) for r, q in found] != lines:
            return _out(fail("invalid_input", "I couldn't match that basket exactly. Please order these medicines one at "
                                              f"a time, or call the pharmacy desk on {ph.PHARMACY_DESK}."))
        p = _patient(c, cp)
    res = ph.order(p["phone"], _dob(p), text, quantity="", delivery_address=b.delivery_address,
                   payment_method=b.payment_method, confirm="yes" if b.confirm else "",
                   wait_for_restock="yes" if b.wait_for_restock else "")
    if res.ok and not b.confirm:
        res.data["needs"] = "confirm"
    return _out(res)


def _order_view(o: dict) -> dict:
    link = o["payment_link_code"]
    return {"order_id": o["order_code"], "items": o["items"], "subtotal_inr": o["subtotal_inr"],
            "delivery_fee_inr": o["delivery_fee_inr"], "total_inr": o["total_inr"], "credits_used": o["credits_used"],
            "amount_due_inr": o["amount_due_inr"], "status": o["status"], "cold_chain": bool(o["cold_chain"]),
            "delivery_address": o["delivery_address"], "zone": o["zone"], "eta": ph._eta_text(o["eta"]),
            "placed": human_date(o["created_at"].date()) if o["created_at"] else None,
            "cancellable": o["status"] in CANCELLABLE,
            "payment_url": f"{config.PUBLIC_BASE_URL}/pay/{link}" if link and o["amount_due_inr"] else None,
            "tracking_url": f"{config.PUBLIC_BASE_URL}/track/{o['order_code']}"}


@router.get("/orders")
def my_orders(cp: Any = Me):
    with db.engine.connect() as c:
        rows = c.execute(select(ORD).where(ORD.c.patient_id == cp.id)
                         .order_by(ORD.c.created_at.desc(), ORD.c.id.desc()).limit(20)).mappings().all()
    orders = [_order_view(dict(r)) for r in rows]
    live = [o for o in orders if o["status"] not in ("delivered", "cancelled")]
    msg = ("You have no medicine orders yet." if not orders else
           f"{len(live)} order{'s' if len(live) != 1 else ''} on the way." if live else
           "All your medicine orders are closed.")
    return {"ok": True, "message": msg, "orders": orders, "count": len(orders)}


@router.post("/orders/{code}/cancel")
def cancel_order(code: str, cp: Any = Me):
    """Cancels through the pharmacy service, so stock goes back on the shelf, credits go back to whoever paid
    (including a family wallet), the payment link expires and the delivery leaves the calendar."""
    with db.engine.connect() as c:
        p = _patient(c, cp)
        mine = c.execute(select(ORD.c.order_code).where(ORD.c.patient_id == cp.id,
                                                        ORD.c.order_code == clean(code).upper())).first()
    if not mine:
        return _out(fail("not_found", "I couldn't find that order on your record. Please check the order number."))
    return _out(ph.track(p["phone"], _dob(p), order_id=mine[0], action="cancel"))


# ------------------------------------------------------------------ wallet
def _txn_view(t: dict) -> dict:
    return {"txn": t["txn_code"], "direction": t["direction"], "amount": t["amount"],
            "balance_after": t["balance_after"], "service": t["service"], "reference": t["reference"],
            "on": t["created_at"].isoformat() if t["created_at"] else None,
            "on_text": t["created_at"].strftime("%d %b %Y, %H:%M") if t["created_at"] else ""}


@router.get("/wallet")
def my_wallet(cp: Any = Me):
    with db.engine.connect() as c:
        p = _patient(c, cp)
        bal = wl.balance(c, cp.id)
        owner_id, room = wl.pool_available(c, cp.id)
        spendable = wl.spendable(c, p)
        owner = pt.get_by_id(c, owner_id) if owner_id else None
        share = c.execute(select(SHARE).where(SHARE.c.member_patient_id == cp.id,
                                              SHARE.c.active.is_(True))).mappings().first() if owner_id else None
        txns = c.execute(select(TXN).where(TXN.c.patient_id == cp.id)
                         .order_by(TXN.c.created_at.desc(), TXN.c.id.desc()).limit(25)).mappings().all()
    pool = ({"owner_name": owner["full_name"].split()[0], "owner_phone": mask_phone(owner["phone"]),
             "available_credits": room, "per_txn_limit": share["per_txn_limit"] if share else None,
             "daily_limit": share["daily_limit"] if share else None} if owner_id and owner else None)
    msg = f"You have {bal:,} HealthCredits, worth {rupees(bal)}."
    if pool and room:
        msg += f" You can also use up to {room:,} credits from {pool['owner_name']}'s wallet, so {spendable:,} in total."
    if wl.minor(p):
        msg += " As this account belongs to a child, spending needs the parent or guardian's approval."
    return {"ok": True, "message": msg, "balance_credits": bal, "spendable_credits": spendable,
            "pool_credits": room, "pool": pool, "is_minor": wl.minor(p),
            "transactions": [_txn_view(dict(t)) for t in txns],
            "bonus_tiers": [{"from_inr": floor, "percent": pct} for floor, pct in wl.BONUS_TIERS],
            "topup_min_inr": 100, "topup_max_inr": 50000}


class TopupReq(BaseModel):
    amount_inr: int = 0


@router.post("/wallet/topup")
def topup(b: TopupReq, cp: Any = Me):
    """Creates the same secure payment link the chat sends. WellNest never collects card details itself."""
    with db.engine.connect() as c:
        p = _patient(c, cp)
    return _out(wl.recharge(p["phone"], str(b.amount_inr or ""), _dob(p)))


@router.get("/wallet/sharing")
def sharing(cp: Any = Me):
    P = db.patients
    with db.engine.connect() as c:
        rows = c.execute(select(SHARE, P.c.full_name, P.c.phone, P.c.patient_code)
                         .join(P, P.c.id == SHARE.c.member_patient_id)
                         .where(SHARE.c.owner_patient_id == cp.id).order_by(SHARE.c.id)).mappings().all()
        members = []
        for r in rows:
            _, room = wl.pool_available(c, r["member_patient_id"])
            members.append({"name": r["full_name"], "patient_id": r["patient_code"], "phone": mask_phone(r["phone"]),
                            "per_txn_limit": r["per_txn_limit"], "daily_limit": r["daily_limit"],
                            "active": bool(r["active"]), "available_credits": room if r["active"] else 0})
        owner_id, room = wl.pool_available(c, cp.id)
        owner = pt.get_by_id(c, owner_id) if owner_id else None
    active = [m for m in members if m["active"]]
    msg = (f"{len(active)} family member{'s' if len(active) != 1 else ''} can pay from your HealthCredits. "
           "You get an SMS every time they do." if active else
           "Nobody else can use your HealthCredits. You can let a registered family member pay from your wallet, "
           "with a limit per order and a limit each day.")
    return {"ok": True, "message": msg, "members": members,
            "drawing_from": {"owner_name": owner["full_name"].split()[0], "available_credits": room} if owner else None}


class ShareReq(BaseModel):
    phone: str = ""
    per_txn_limit: int | None = None
    daily_limit: int | None = None
    action: str = ""                 # "" to add or change, "stop" to end it


@router.post("/wallet/sharing")
def set_sharing(b: ShareReq, cp: Any = Me):
    """Adds, changes or stops a family member. The limits and the owner's SMS alert are the wallet service's."""
    if not clean(b.phone):
        return _out(fail("invalid_input", "Please enter the family member's 10 digit mobile number. They need to be "
                                          "registered at WellNest first."))
    with db.engine.connect() as c:
        p = _patient(c, cp)
    return _out(wl.set_share(p["phone"], _dob(p), b.phone,
                             "" if b.per_txn_limit in (None, 0) else str(b.per_txn_limit),
                             "" if b.daily_limit in (None, 0) else str(b.daily_limit),
                             action=clean(b.action)))


# ------------------------------------------------------------------ prescriptions (Pharmacy V3)
@router.get("/prescriptions")
def my_prescriptions(cp: Any = Me):
    """What this patient can order: active items, days left, next refill date; and their uploads under review."""
    from .services import rx
    U = db.prescription_uploads
    with db.engine.begin() as c:
        items = rx.patient_summary(c, cp.id)
        ups = c.execute(select(U.c.upload_code, U.c.file_name, U.c.status, U.c.reason, U.c.created_at)
                        .where(U.c.patient_id == cp.id).order_by(U.c.created_at.desc()).limit(10)).mappings().all()
    return {"ok": True, "message": rx.summary_sentence(items), "prescriptions": items,
            "uploads": [{**dict(u), "created_at": u["created_at"].isoformat()} for u in ups]}


class UploadIn(BaseModel):
    file_name: str = ""
    content_type: str
    data: str                     # base64; images or PDF, 4 MB at most
    note: str = ""


@router.post("/prescriptions/upload")
def upload_prescription(body: UploadIn, cp: Any = Me):
    import base64
    import binascii
    from .services import rx
    if len(body.data) > rx.MAX_UPLOAD * 4 // 3 + 8:
        return _out(fail("invalid_input", "The file must be under 4 MB."))
    try:
        raw = base64.b64decode(body.data, validate=True)
    except (binascii.Error, ValueError):
        return _out(fail("invalid_input", "That file couldn't be read. Please try again."))
    sniff = {b"\xff\xd8": "image/jpeg", b"\x89P": "image/png", b"%P": "application/pdf", b"RI": "image/webp"}
    if sniff.get(raw[:2]) != body.content_type:   # the bytes must really be the type they claim
        return _out(fail("invalid_input", "Please upload a photo (JPG, PNG or WebP) or a PDF of the prescription."))
    res = rx.upload(cp.id, body.file_name, body.content_type, raw, body.note)
    if not res.ok:
        return _out(res)
    return {"ok": True, "message": res.message, "upload_code": res.data["upload_code"]}
