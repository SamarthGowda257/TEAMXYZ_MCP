"""Admin control API (/api/admin/*) — the write half of the staff console.

Everything here needs a signed-in admin session (the cookie set by /api/admin/login); none of it is
reachable with the read-only dashboard token. The console was view-only until now: these routes let
staff actually run the hospital — add a doctor, change a fee, restock the pharmacy, adjust a wallet,
close an appointment, correct a patient record.

Every write lands in `resolutions` with actor "staff", so the audit trail shows who changed what,
next to what the AI did. Business rules that already exist (cancel, reschedule) are called through
`services/` rather than reimplemented, so the console and the bot behave identically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update

from . import config, db
from .services import appointments as ap
from .services import ref
from .services import wallet as wl
from .util import clean, mask_phone, norm_phone, parse_date

router = APIRouter(prefix="/api/admin")


def _admin(request: Request) -> dict:
    from .api import admin_session
    s = admin_session(request)
    if not s:
        raise HTTPException(401, detail={"error_code": "not_allowed", "message": "Please sign in to the admin console."})
    if s["role"] != "admin":
        raise HTTPException(403, detail={"error_code": "not_allowed", "message": "Your staff role can't open this section."})
    return s


Guard = Depends(_admin)


def _log(c, action: str, refcode: str, summary: str, patient_id: int | None = None) -> None:
    c.execute(insert(db.resolutions).values(
        patient_id=patient_id, actor="staff", action=action, ref=refcode[:20],
        ok=True, summary=summary[:300], channel="staff", created_at=config.now()))


def _row(r) -> dict:
    out = {}
    for k, v in dict(r).items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


def _one(c, table, pk: int):
    r = c.execute(select(table).where(table.c.id == pk)).mappings().first()
    if not r:
        raise HTTPException(404, detail={"error_code": "not_found", "message": "That record no longer exists."})
    return r


# ===================================================================== doctors
class DoctorIn(BaseModel):
    name: str
    department_id: int
    qualification: str = ""
    experience_years: int = 0
    languages: str = "English"
    fee_inr: int = 500
    room: str = "OPD-000"
    consult_days: str = "1,2,3,4,5"
    start_time: str = "09:00"
    end_time: str = "13:00"
    slot_minutes: int = 15
    gender: str = ""
    bio: str = ""


@router.get("/doctors", dependencies=[Guard])
def doctors_list():
    with db.engine.connect() as c:
        rows = c.execute(
            select(db.doctors, db.departments.c.name.label("department"))
            .join(db.departments, db.departments.c.id == db.doctors.c.department_id)
            .order_by(db.doctors.c.name)
        ).mappings().all()
    return {"total": len(rows), "doctors": [_row(r) for r in rows]}


@router.post("/doctors", dependencies=[Guard])
def doctor_create(body: DoctorIn):
    with db.engine.begin() as c:
        n = c.execute(select(func.count()).select_from(db.doctors)).scalar() or 0
        code = f"DOC-{n + 1:03d}"
        while c.execute(select(db.doctors.c.id).where(db.doctors.c.code == code)).first():
            n += 1
            code = f"DOC-{n + 1:03d}"
        pk = c.execute(insert(db.doctors).values(code=code, **body.model_dump())).inserted_primary_key[0]
        _log(c, "staff_doctor_added", code, f"Added {body.name} to department {body.department_id}")
    ref.load()
    return {"ok": True, "id": pk, "code": code, "message": f"{body.name} added."}


@router.patch("/doctors/{pk}", dependencies=[Guard])
def doctor_update(pk: int, body: dict):
    allowed = {"name", "department_id", "qualification", "experience_years", "languages", "fee_inr",
               "room", "consult_days", "start_time", "end_time", "slot_minutes", "gender", "bio"}
    vals = {k: v for k, v in body.items() if k in allowed}
    if not vals:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Nothing to change."})
    with db.engine.begin() as c:
        d = _one(c, db.doctors, pk)
        c.execute(update(db.doctors).where(db.doctors.c.id == pk).values(**vals))
        _log(c, "staff_doctor_updated", d["code"], f"Updated {d['name']}: {', '.join(vals)}")
    ref.load()
    return {"ok": True, "message": f"{d['name']} updated."}


@router.delete("/doctors/{pk}", dependencies=[Guard])
def doctor_delete(pk: int):
    with db.engine.begin() as c:
        d = _one(c, db.doctors, pk)
        booked = c.execute(select(func.count()).select_from(db.appointments).where(
            db.appointments.c.doctor_id == pk, db.appointments.c.status == "booked",
            db.appointments.c.appt_date >= config.today())).scalar() or 0
        if booked:
            raise HTTPException(400, detail={
                "error_code": "not_allowed",
                "message": f"{d['name']} has {booked} upcoming bookings. Move or cancel those first."})
        c.execute(delete(db.doctors).where(db.doctors.c.id == pk))
        _log(c, "staff_doctor_removed", d["code"], f"Removed {d['name']}")
    ref.load()
    return {"ok": True, "message": f"{d['name']} removed."}


# ===================================================================== departments
class DeptIn(BaseModel):
    code: str
    name: str
    floor: str = ""
    description: str = ""


@router.get("/departments", dependencies=[Guard])
def depts_list():
    with db.engine.connect() as c:
        rows = c.execute(
            select(db.departments, func.count(db.doctors.c.id).label("doctors"))
            .outerjoin(db.doctors, db.doctors.c.department_id == db.departments.c.id)
            .group_by(db.departments.c.id).order_by(db.departments.c.name)
        ).mappings().all()
    return {"total": len(rows), "departments": [_row(r) for r in rows]}


@router.post("/departments", dependencies=[Guard])
def dept_create(body: DeptIn):
    with db.engine.begin() as c:
        if c.execute(select(db.departments.c.id).where(db.departments.c.name == body.name)).first():
            raise HTTPException(400, detail={"error_code": "already_exists", "message": "That department already exists."})
        pk = c.execute(insert(db.departments).values(**body.model_dump())).inserted_primary_key[0]
        _log(c, "staff_department_added", body.code, f"Added department {body.name}")
    ref.load()
    return {"ok": True, "id": pk, "message": f"{body.name} added."}


@router.patch("/departments/{pk}", dependencies=[Guard])
def dept_update(pk: int, body: dict):
    vals = {k: v for k, v in body.items() if k in {"name", "floor", "description", "code"}}
    with db.engine.begin() as c:
        d = _one(c, db.departments, pk)
        c.execute(update(db.departments).where(db.departments.c.id == pk).values(**vals))
        _log(c, "staff_department_updated", d["code"], f"Updated {d['name']}")
    ref.load()
    return {"ok": True, "message": f"{d['name']} updated."}


@router.delete("/departments/{pk}", dependencies=[Guard])
def dept_delete(pk: int):
    with db.engine.begin() as c:
        d = _one(c, db.departments, pk)
        n = c.execute(select(func.count()).select_from(db.doctors).where(db.doctors.c.department_id == pk)).scalar() or 0
        if n:
            raise HTTPException(400, detail={"error_code": "not_allowed",
                                             "message": f"{d['name']} still has {n} doctors. Move them first."})
        c.execute(delete(db.departments).where(db.departments.c.id == pk))
        _log(c, "staff_department_removed", d["code"], f"Removed {d['name']}")
    ref.load()
    return {"ok": True, "message": f"{d['name']} removed."}


# ===================================================================== pharmacy
class MedicineIn(BaseModel):
    brand_name: str
    generic_name: str
    strength: str = ""
    pack: str = "strip of 10 tablets"
    schedule_class: str = "OTC"          # OTC | H | H1 | X
    unit_price_inr: int = 0
    stock_qty: int = 0
    chronic: bool = False
    cold_chain: bool = False
    alternative_code: str = ""


@router.get("/pharmacy", dependencies=[Guard])
def pharmacy_list(q: str = ""):
    inv = db.pharmacy_inventory
    stmt = select(inv).order_by(inv.c.brand_name)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(inv.c.brand_name.ilike(like) | inv.c.generic_name.ilike(like))
    with db.engine.connect() as c:
        rows = c.execute(stmt).mappings().all()
    return {"total": len(rows), "medicines": [_row(r) for r in rows]}


@router.post("/pharmacy", dependencies=[Guard])
def medicine_create(body: MedicineIn):
    vals = body.model_dump()
    with db.engine.begin() as c:
        n = (c.execute(select(func.count()).select_from(db.pharmacy_inventory)).scalar() or 0) + 1
        code = f"MED-{n:04d}"
        while c.execute(select(db.pharmacy_inventory.c.id)
                        .where(db.pharmacy_inventory.c.medicine_code == code)).first():
            n += 1
            code = f"MED-{n:04d}"
        pk = c.execute(insert(db.pharmacy_inventory)
                       .values(medicine_code=code, updated_at=config.now(), **vals)).inserted_primary_key[0]
        _log(c, "staff_medicine_added", code,
             f"Added {body.brand_name} ({body.generic_name}) to the pharmacy, stock {body.stock_qty}")
    return {"ok": True, "id": pk, "code": code, "message": f"{body.brand_name} added."}


@router.patch("/pharmacy/{pk}", dependencies=[Guard])
def medicine_update(pk: int, body: dict):
    cols = {col.name for col in db.pharmacy_inventory.columns} - {"id", "medicine_code"}
    vals = {k: v for k, v in body.items() if k in cols}
    if not vals:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Nothing to change."})
    vals["updated_at"] = config.now()
    with db.engine.begin() as c:
        m = _one(c, db.pharmacy_inventory, pk)
        c.execute(update(db.pharmacy_inventory).where(db.pharmacy_inventory.c.id == pk).values(**vals))
        what = f"restocked to {vals['stock_qty']}" if "stock_qty" in vals \
            else ", ".join(k for k in vals if k != "updated_at")
        _log(c, "staff_medicine_updated", m["medicine_code"], f"{m['brand_name']}: {what}")
    return {"ok": True, "message": f"{m['brand_name']} updated."}


@router.delete("/pharmacy/{pk}", dependencies=[Guard])
def medicine_delete(pk: int):
    with db.engine.begin() as c:
        m = _one(c, db.pharmacy_inventory, pk)
        c.execute(delete(db.pharmacy_inventory).where(db.pharmacy_inventory.c.id == pk))
        _log(c, "staff_medicine_removed", m["medicine_code"], f"Removed {m['brand_name']} from the pharmacy")
    return {"ok": True, "message": f"{m['brand_name']} removed."}


@router.get("/orders", dependencies=[Guard])
def orders_list(status: str = "", limit: int = Query(default=80, le=300)):
    o, p = db.pharmacy_orders, db.patients
    stmt = select(o, p.c.full_name, p.c.phone).join(p, p.c.id == o.c.patient_id).order_by(o.c.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(o.c.status == status)
    with db.engine.connect() as c:
        rows = c.execute(stmt).mappings().all()
    return {"total": len(rows), "orders": [{**_row(r), "phone": mask_phone(r["phone"])} for r in rows]}


ORDER_STATES = {"awaiting_payment", "awaiting_stock", "awaiting_review", "confirmed", "dispatched", "delivered",
                "ready_for_pickup", "cancelled"}


@router.post("/orders/{pk}/status", dependencies=[Guard])
def order_status(pk: int, body: dict):
    new = clean(body.get("status", ""))
    if new not in ORDER_STATES:
        raise HTTPException(400, detail={"error_code": "invalid_input",
                                         "message": f"Status must be one of: {', '.join(sorted(ORDER_STATES))}."})
    if new == "cancelled":                     # a staff cancel gives back credits, stock and prescription days
        from .services import pharmacy as ph
        res = ph.reject(pk, clean(body.get("reason", "")) or "Cancelled by the hospital", "staff console")
        if not res.ok:
            raise HTTPException(400, detail={"error_code": res.error_code, "message": res.message})
        return {"ok": True, "message": res.message}
    with db.engine.begin() as c:
        o = _one(c, db.pharmacy_orders, pk)
        if new in ("confirmed", "dispatched", "delivered") and o["verification"] == "pending_pharmacist":
            raise HTTPException(400, detail={"error_code": "not_allowed",
                                             "message": "A pharmacist must check this order first (Pharmacist desk)."})
        c.execute(update(db.pharmacy_orders).where(db.pharmacy_orders.c.id == pk).values(status=new))
        _log(c, "staff_order_status", o["order_code"], f"Order {o['order_code']} marked {new}", o["patient_id"])
    return {"ok": True, "message": f"Order {o['order_code']} is now {new}."}


# ===================================================================== wallet
@router.get("/wallets", dependencies=[Guard])
def wallets_list(limit: int = Query(default=60, le=200)):
    w, p = db.health_credit_wallets, db.patients
    with db.engine.connect() as c:
        rows = c.execute(select(w, p.c.full_name, p.c.phone, p.c.id.label("pid"))
                         .join(p, p.c.id == w.c.patient_id)
                         .order_by(w.c.balance.desc()).limit(limit)).mappings().all()
    return {"total": len(rows), "wallets": [{**_row(r), "phone": mask_phone(r["phone"])} for r in rows]}


@router.post("/wallets/{patient_id}/adjust", dependencies=[Guard])
def wallet_adjust(patient_id: int, body: dict):
    """Credit or debit a wallet by hand — a goodwill refund, a counter top-up, a correction."""
    try:
        amount = int(body.get("amount", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Amount must be a whole number."})
    reason = clean(body.get("reason", "")) or "Staff adjustment"
    if not amount:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Enter a non-zero amount."})
    # one idempotency key per adjustment, so a double-submit cannot move the balance twice
    key = f"staff-adj:{patient_id}:{config.now().isoformat(timespec='seconds')}:{amount}"
    with db.engine.begin() as c:
        p = _one(c, db.patients, patient_id)
        bal = wl.balance(c, patient_id)
        if amount > 0:
            wl.credit(c, patient_id, amount, "bonus", reason[:40], key)
        else:
            ok, why = wl.debit(c, patient_id, -amount, "bill", reason[:40], key)
            if not ok:
                raise HTTPException(400, detail={
                    "error_code": "not_allowed",
                    "message": f"{p['full_name']} has {bal:,} credits; that debit would go below zero."})
        new_bal = wl.balance(c, patient_id)
        _log(c, "staff_wallet_adjust", p["patient_code"],
             f"{'Credited' if amount > 0 else 'Debited'} {abs(amount):,} credits: {reason}", patient_id)
    return {"ok": True, "balance": new_bal,
            "message": f"{p['full_name']}'s balance is now {new_bal:,} credits."}


# ===================================================================== appointments
@router.post("/appointments/{code}/status", dependencies=[Guard])
def appointment_status(code: str, body: dict):
    """Mark a visit completed or a no-show. Cancelling goes through the service so the
    waitlist offer still fires exactly as it does for the bot."""
    new = clean(body.get("status", ""))
    a_t = db.appointments
    with db.engine.begin() as c:
        a = c.execute(select(a_t).where(a_t.c.booking_code == code.upper())).mappings().first()
        if not a:
            raise HTTPException(404, detail={"error_code": "not_found", "message": "No booking with that ID."})
    if new == "cancelled":
        p = None
        with db.engine.connect() as c:
            p = c.execute(select(db.patients).where(db.patients.c.id == a["patient_id"])).mappings().first()
        res = ap.cancel(code, p["phone"], p["date_of_birth"].isoformat() if p["date_of_birth"] else "",
                        reason="Cancelled at the front desk", actor="staff", channel="staff")
        out = res.as_dict() if hasattr(res, "as_dict") else res
        return out
    if new not in {"completed", "no_show", "booked"}:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Unknown appointment status."})
    with db.engine.begin() as c:
        c.execute(update(a_t).where(a_t.c.id == a["id"]).values(status=new, updated_at=config.now()))
        _log(c, "staff_appointment_status", code.upper(), f"Booking {code.upper()} marked {new}", a["patient_id"])
    return {"ok": True, "message": f"Booking {code.upper()} marked {new.replace('_', ' ')}."}


# ===================================================================== patients
@router.patch("/patients/{pk}", dependencies=[Guard])
def patient_update(pk: int, body: dict):
    allowed = {"full_name", "email", "address", "preferred_language", "preferred_time",
               "caregiver_name", "caregiver_relation", "caregiver_phone", "caregiver_email",
               "caregiver_consent", "mobility_needs", "policy_number", "insurer_id",
               "allergies", "weight_kg"}
    vals = {k: v for k, v in body.items() if k in allowed}
    if "caregiver_phone" in vals and vals["caregiver_phone"]:
        vals["caregiver_phone"] = norm_phone(vals["caregiver_phone"]) or vals["caregiver_phone"]
    if not vals:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Nothing to change."})
    with db.engine.begin() as c:
        p = _one(c, db.patients, pk)
        c.execute(update(db.patients).where(db.patients.c.id == pk).values(**vals))
        _log(c, "staff_patient_updated", p["patient_code"], f"Updated {p['full_name']}: {', '.join(vals)}", pk)
    return {"ok": True, "message": f"{p['full_name']} updated."}


# ===================================================================== one patient, end to end
@router.get("/patients/{pk}/timeline", dependencies=[Guard])
def patient_timeline(pk: int):
    """
    Everything this hospital knows about one person, in one call: profile, wallet, bookings,
    reports, orders, escalations, the conversation summaries the AI saved, and the full audit
    trail of tool calls.

    Honest limit: WellNest never receives verbatim chat or call transcripts — Talkdesk does not
    send them. What is real and complete here is every ACTION the AI took (`resolutions`) plus the
    summary it wrote at the end of each conversation (`interaction_notes`).
    """
    with db.engine.connect() as c:
        p = _one(c, db.patients, pk)
        notes = c.execute(select(db.interaction_notes)
                          .where(db.interaction_notes.c.patient_id == pk)
                          .order_by(db.interaction_notes.c.created_at.desc()).limit(40)).mappings().all()
        trail = c.execute(select(db.resolutions)
                          .where(db.resolutions.c.patient_id == pk)
                          .order_by(db.resolutions.c.created_at.desc()).limit(60)).mappings().all()
        appts = c.execute(select(db.appointments)
                          .where(db.appointments.c.patient_id == pk)
                          .order_by(db.appointments.c.appt_date.desc()).limit(25)).mappings().all()
        reports = c.execute(select(db.lab_reports)
                            .where(db.lab_reports.c.patient_id == pk)
                            .order_by(db.lab_reports.c.ordered_at.desc()).limit(15)).mappings().all()
        bills = c.execute(select(db.bills).where(db.bills.c.patient_id == pk)
                          .order_by(db.bills.c.id.desc()).limit(15)).mappings().all()
        orders = c.execute(select(db.pharmacy_orders).where(db.pharmacy_orders.c.patient_id == pk)
                           .order_by(db.pharmacy_orders.c.id.desc()).limit(15)).mappings().all()
        hos = c.execute(select(db.handoffs).where(db.handoffs.c.patient_id == pk)
                        .order_by(db.handoffs.c.id.desc()).limit(10)).mappings().all()
        bal = wl.balance(c, pk)
        dept = {d["id"]: d["name"] for d in c.execute(select(db.departments)).mappings().all()}
        docs = {d["id"]: d["name"] for d in c.execute(select(db.doctors)).mappings().all()}

    prof = _row(p)
    prof["phone_masked"] = mask_phone(p["phone"])
    prof.pop("password_hash", None)
    return {
        "patient": prof,
        "credits": bal,
        "conversations": [_row(n) for n in notes],
        "trail": [_row(t) for t in trail],
        "appointments": [{**_row(a), "doctor": docs.get(a["doctor_id"], "—")} for a in appts],
        "reports": [_row(r) for r in reports],
        "bills": [_row(b) for b in bills],
        "orders": [_row(o) for o in orders],
        "handoffs": [_row(h) for h in hos],
        "departments": dept,
        "transcripts_available": False,
        "transcript_note": "Talkdesk does not send transcripts to WellNest. Every action the AI "
                           "took is recorded below; the wording of each conversation lives in Talkdesk.",
    }


# ===================================================================== insurers
@router.get("/insurers", dependencies=[Guard])
def insurers_list():
    with db.engine.connect() as c:
        rows = c.execute(select(db.insurers).order_by(db.insurers.c.name)).mappings().all()
    return {"total": len(rows), "insurers": [_row(r) for r in rows]}


@router.patch("/insurers/{pk}", dependencies=[Guard])
def insurer_update(pk: int, body: dict):
    vals = {k: v for k, v in body.items() if k in {"name", "mode", "tpa_name", "documents", "notes"}}
    with db.engine.begin() as c:
        i = _one(c, db.insurers, pk)
        c.execute(update(db.insurers).where(db.insurers.c.id == pk).values(**vals))
        _log(c, "staff_insurer_updated", i["code"], f"Updated {i['name']}")
    ref.load()
    return {"ok": True, "message": f"{i['name']} updated."}
