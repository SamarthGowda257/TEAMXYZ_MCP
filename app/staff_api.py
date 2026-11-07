"""Clinical staff API (/api/staff/*): doctors prescribe, pharmacists check orders and uploads (Pharmacy V3).

Same signed cookie as the admin console, scoped by role:
  doctor       find a patient, see their prescriptions and safety notes, prescribe, stop a medicine
  pharmacist   the review queue (orders and uploaded prescriptions), approve or reject, the dispensing register,
               the limits table, courier events for the simulated courier, patient safety notes
  admin        everything above, plus staff accounts
A doctor's prescription is always signed as that doctor (from the session, never the request body).
Every write lands in `resolutions` with actor "staff".

Also here: POST /api/webhooks/delivery/{provider}, the courier's signed status webhook.
"""

from __future__ import annotations

import base64
import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import insert, or_, select, update

from . import config, db
from .security import hash_password
from .services import delivery as dl
from .services import patients as pt
from .services import pharmacy as ph
from .services import rx
from .services.ref import REF
from .util import clean, mask_phone, norm_phone

router = APIRouter()
ROLES = ("admin", "doctor", "pharmacist")


def need(*roles: str):
    def dep(request: Request) -> dict:
        from .api import admin_session
        s = admin_session(request)
        if not s:
            raise HTTPException(401, detail={"error_code": "not_allowed", "message": "Please sign in to the staff console."})
        if s["role"] not in roles and s["role"] != "admin":
            raise HTTPException(403, detail={"error_code": "not_allowed", "message": "Your staff role can't do this."})
        return s
    return Depends(dep)


Doctor = need("doctor")
Pharmacist = need("pharmacist")
Clinical = need("doctor", "pharmacist")
Admin = need("admin")


def _who(s: dict) -> str:
    return s.get("name") or s.get("adm") or "staff"


def _out(res):
    if res.ok:
        return res.as_dict()
    raise HTTPException(400, detail={"error_code": res.error_code, "message": res.message, **(res.data or {})})


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# ------------------------------------------------------------------ patients and formulary (doctor, pharmacist)
@router.get("/api/staff/patients")
def find_patients(q: str = Query(default=""), s: dict = Clinical):
    P = db.patients
    term = clean(q)
    if len(term) < 2:
        return {"ok": True, "patients": []}
    phone = norm_phone(term)
    cond = or_(P.c.full_name.ilike(f"%{term}%"), P.c.patient_code.ilike(f"%{term}%"),
               *( [P.c.phone == phone] if phone else []))
    with db.engine.connect() as c:
        rows = c.execute(select(P.c.id, P.c.patient_code, P.c.full_name, P.c.phone, P.c.date_of_birth, P.c.allergies)
                         .where(cond, P.c.is_guest.is_(False)).order_by(P.c.full_name).limit(20)).mappings().all()
    return {"ok": True, "patients": [{"id": r["id"], "code": r["patient_code"], "name": r["full_name"],
                                      "phone": mask_phone(r["phone"]), "dob": _iso(r["date_of_birth"]),
                                      "allergies": r["allergies"]} for r in rows]}


@router.get("/api/staff/patients/{pid}")
def patient_card(pid: int, s: dict = Clinical):
    with db.engine.begin() as c:
        p = pt.get_by_id(c, pid)
        if not p:
            raise HTTPException(404, detail={"error_code": "not_found", "message": "No such patient."})
        items = rx.patient_summary(c, pid)
        recent = c.execute(select(db.dispensations.c.medicine_code, db.dispensations.c.packs, db.dispensations.c.status,
                                  db.dispensations.c.created_at).where(db.dispensations.c.patient_id == pid)
                           .order_by(db.dispensations.c.created_at.desc()).limit(10)).mappings().all()
    return {"ok": True, "patient": {"id": p["id"], "code": p["patient_code"], "name": p["full_name"],
                                    "phone": mask_phone(p["phone"]), "dob": _iso(p["date_of_birth"]),
                                    "age": rx._age(p), "allergies": p.get("allergies") or "",
                                    "pregnant_until": _iso(p.get("pregnant_until")), "weight_kg": p.get("weight_kg")},
            "prescriptions": items, "recent_supplies": [{**dict(r), "created_at": _iso(r["created_at"])} for r in recent]}


class SafetyIn(BaseModel):
    allergies: str | None = None
    pregnant_until: str | None = None
    weight_kg: float | None = None


@router.post("/api/staff/patients/{pid}/safety")
def set_safety(pid: int, body: SafetyIn, s: dict = Clinical):
    vals: dict[str, Any] = {}
    if body.allergies is not None:
        vals["allergies"] = clean(body.allergies)[:200] or None
    if body.pregnant_until is not None:
        try:
            vals["pregnant_until"] = date.fromisoformat(body.pregnant_until) if clean(body.pregnant_until) else None
        except ValueError:
            raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Use a date like 2027-03-01."})
    if body.weight_kg is not None:
        if not 0 < body.weight_kg < 300:
            raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Weight must be in kilograms."})
        vals["weight_kg"] = body.weight_kg
    if not vals:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Nothing to change."})
    with db.engine.begin() as c:
        p = pt.get_by_id(c, pid)
        if not p:
            raise HTTPException(404, detail={"error_code": "not_found", "message": "No such patient."})
        c.execute(update(db.patients).where(db.patients.c.id == pid).values(**vals))
        pt.log(c, pid, "safety_updated", p["patient_code"], True, f"{_who(s)} updated {', '.join(vals)}", actor="staff", channel="staff")
    return {"ok": True, "message": "Saved."}


@router.get("/api/staff/formulary")
def formulary(s: dict = Clinical):
    with db.engine.begin() as c:
        rx.ensure_reference(c)
        rows = c.execute(select(db.pharmacy_inventory).order_by(db.pharmacy_inventory.c.brand_name)).mappings().all()
        rules = {r["ingredient"]: r for r in c.execute(select(db.drug_rules)).mappings().all()}
    return {"ok": True, "medicines": [{"code": r["medicine_code"], "brand": r["brand_name"], "generic": r["generic_name"],
                                       "strength": r["strength"], "strength_mg": r["strength_mg"], "pack": r["pack"],
                                       "schedule": r["schedule_class"], "ingredient": r["ingredient"],
                                       "max_daily_mg": (rules.get(r["ingredient"]) or {}).get("max_daily_mg_adult")}
                                      for r in rows if r["schedule_class"] != "X"]}


# ------------------------------------------------------------------ prescribing (doctor)
class RxIn(BaseModel):
    patient_id: int
    items: list[dict]
    valid_days: int = rx.VALID_DAYS
    appointment_id: int | None = None
    doctor_id: int | None = None          # admin only; a doctor always signs as themselves


@router.post("/api/staff/prescriptions")
def prescribe(body: RxIn, s: dict = Doctor):
    doctor_id = s.get("doc") if s["role"] == "doctor" else body.doctor_id
    if s["role"] == "doctor" and not doctor_id:
        raise HTTPException(403, detail={"error_code": "not_allowed", "message": "This account isn't linked to a doctor."})
    name = REF.doctors.get(doctor_id, {}).get("name") if doctor_id else None
    res = rx.prescribe(body.patient_id, doctor_id, body.items, signed_by=name or _who(s), valid_days=body.valid_days,
                       appointment_id=body.appointment_id)
    return _out(res) | {"rx_code": res.data["rx_code"]}


class StopIn(BaseModel):
    reason: str = ""


@router.post("/api/staff/prescription-items/{item_id}/stop")
def stop(item_id: int, body: StopIn, s: dict = Doctor):
    if not clean(body.reason):
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Say why it's stopped (the pharmacist and patient see it)."})
    return _out(rx.stop_item(item_id, body.reason, _who(s)))


# ------------------------------------------------------------------ pharmacist
@router.get("/api/staff/pharmacist/queue")
def queue(s: dict = Pharmacist):
    O, U, D = db.pharmacy_orders, db.prescription_uploads, db.deliveries
    with db.engine.connect() as c:
        orders = c.execute(select(O, db.patients.c.full_name, db.patients.c.allergies).join(db.patients, db.patients.c.id == O.c.patient_id)
                           .where(O.c.verification == "pending_pharmacist", O.c.status != "cancelled")
                           .order_by(O.c.created_at)).mappings().all()
        uploads = c.execute(select(U.c.id, U.c.upload_code, U.c.patient_id, U.c.file_name, U.c.content_type, U.c.note,
                                   U.c.created_at, db.patients.c.full_name).join(db.patients, db.patients.c.id == U.c.patient_id)
                            .where(U.c.status == "pending").order_by(U.c.created_at)).mappings().all()
        out = []
        for o in orders:
            lines = []
            for i in o["items"]:
                d = c.execute(select(db.dispensations.c.rx_item_id, db.dispensations.c.days_supply).where(
                    db.dispensations.c.order_id == o["id"], db.dispensations.c.medicine_code == i["code"])).first()
                rxc = None
                if d and d[0]:
                    rxc = c.execute(select(db.prescriptions.c.rx_code, db.prescriptions.c.signed_by)
                                    .join(db.prescription_items, db.prescription_items.c.rx_id == db.prescriptions.c.id)
                                    .where(db.prescription_items.c.id == d[0])).first()
                lines.append({"name": i["name"], "qty": i["qty"], "schedule": i["schedule"],
                              "days": round(d[1], 1) if d else None, "rx": rxc[0] if rxc else None,
                              "prescriber": rxc[1] if rxc else None})
            out.append({"id": o["id"], "order_code": o["order_code"], "patient_id": o["patient_id"], "patient": o["full_name"],
                        "allergies": o["allergies"], "status": o["status"], "lines": lines, "notes": o["review_notes"],
                        "total_inr": o["total_inr"], "created_at": _iso(o["created_at"])})
        live = c.execute(select(D, O.c.order_code).join(O, O.c.id == D.c.order_id)
                         .where(D.c.status.in_(("booked", "picked_up", "failed_attempt"))).order_by(D.c.id.desc()).limit(30)).mappings().all()
    return {"ok": True, "orders": out,
            "uploads": [{**dict(u), "created_at": _iso(u["created_at"])} for u in uploads],
            "deliveries": [{"id": d["id"], "order_code": d["order_code"], "provider": d["provider"], "job_id": d["provider_job_id"],
                            "status": d["status"], "attempts": d["attempts"], "needs_code": bool(d["otp_hash"])} for d in live],
            "simulated_courier": dl.PROVIDER == "simulated"}


class ReviewIn(BaseModel):
    reason: str = ""
    notes: str = ""


@router.post("/api/staff/pharmacist/orders/{oid}/approve")
def approve(oid: int, body: ReviewIn, s: dict = Pharmacist):
    return _out(ph.approve(oid, _who(s), body.notes))


@router.post("/api/staff/pharmacist/orders/{oid}/reject")
def reject(oid: int, body: ReviewIn, s: dict = Pharmacist):
    return _out(ph.reject(oid, body.reason, _who(s)))


@router.get("/api/staff/pharmacist/uploads/{uid}/file")
def upload_file(uid: int, s: dict = Pharmacist):
    U = db.prescription_uploads
    with db.engine.connect() as c:
        u = c.execute(select(U.c.data, U.c.content_type, U.c.file_name).where(U.c.id == uid)).first()
    if not u:
        raise HTTPException(404, detail={"error_code": "not_found", "message": "No such upload."})
    return Response(u[0], media_type=u[1], headers={"Content-Disposition": "inline", "Cache-Control": "no-store",
                                                    "X-Content-Type-Options": "nosniff"})


class UploadReviewIn(BaseModel):
    approve: bool
    reason: str = ""
    doctor_name: str = ""
    items: list[dict] = []
    valid_days: int = rx.VALID_DAYS


@router.post("/api/staff/pharmacist/uploads/{uid}/review")
def review_upload(uid: int, body: UploadReviewIn, s: dict = Pharmacist):
    return _out(rx.review_upload(uid, body.approve, _who(s), body.reason, body.items, body.doctor_name, body.valid_days))


@router.get("/api/staff/pharmacist/register")
def register(schedule: str = Query(default="H1"), limit: int = Query(default=200, le=1000), s: dict = Pharmacist):
    D = db.dispensations
    with db.engine.connect() as c:
        rows = c.execute(select(D, db.patients.c.full_name, db.pharmacy_orders.c.order_code, db.pharmacy_inventory.c.brand_name)
                         .join(db.patients, db.patients.c.id == D.c.patient_id)
                         .join(db.pharmacy_orders, db.pharmacy_orders.c.id == D.c.order_id)
                         .join(db.pharmacy_inventory, db.pharmacy_inventory.c.medicine_code == D.c.medicine_code)
                         .where(D.c.status == "dispensed", *( [D.c.schedule_class == schedule.upper()] if schedule else []))
                         .order_by(D.c.verified_at.desc()).limit(limit)).mappings().all()
    return {"ok": True, "register": [{"order": r["order_code"], "patient": r["full_name"], "medicine": r["brand_name"],
                                      "schedule": r["schedule_class"], "packs": r["packs"], "units": r["units"],
                                      "pharmacist": r["pharmacist"], "verified_at": _iso(r["verified_at"]),
                                      "batch_no": r["batch_no"], "expiry_date": _iso(r["expiry_date"])} for r in rows]}


@router.get("/api/staff/drug-rules")
def rules(s: dict = Clinical):
    with db.engine.begin() as c:
        rx.ensure_reference(c)
        rows = c.execute(select(db.drug_rules).order_by(db.drug_rules.c.ingredient)).mappings().all()
    return {"ok": True, "rules": [{k: _iso(v) for k, v in dict(r).items()} for r in rows]}


RULE_FIELDS = ("max_daily_mg_adult", "min_age_years", "pregnancy_caution", "otc_max_mg_per_order", "otc_max_mg_per_7d",
               "otc_max_units_per_order", "otc_max_units_per_7d", "early_refill_pct", "max_days_per_order",
               "requires_pharmacist")


@router.post("/api/staff/drug-rules/{ingredient}")
def set_rule(ingredient: str, body: dict, s: dict = Pharmacist):
    vals = {k: body[k] for k in RULE_FIELDS if k in body}
    if "early_refill_pct" in vals and not 50 <= int(vals["early_refill_pct"] or 0) <= 100:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Early refill must be 50 to 100 percent."})
    if body.get("sign_off"):
        vals.update(signed_off_by=_who(s), signed_off_at=config.now())
    if not vals:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Nothing to change."})
    vals["updated_at"] = config.now()
    ing = clean(ingredient).lower()
    with db.engine.begin() as c:
        if c.execute(select(db.drug_rules.c.id).where(db.drug_rules.c.ingredient == ing)).first():
            c.execute(update(db.drug_rules).where(db.drug_rules.c.ingredient == ing).values(**vals))
        else:
            c.execute(insert(db.drug_rules).values(ingredient=ing, **vals))
        pt.log(c, None, "drug_rule_updated", ing[:20], True, f"{_who(s)}: {json.dumps({k: str(v) for k, v in vals.items()})}"[:300],
               actor="staff", channel="staff")
    return {"ok": True, "message": f"Saved the {ing} limits."}


class CourierIn(BaseModel):
    event: str
    otp: str = ""


@router.post("/api/staff/pharmacist/deliveries/{did}/event")
def courier_event(did: int, body: CourierIn, s: dict = Pharmacist):
    """Simulated courier only: lets staff play the rider (picked up, delivered with code, missed, no rider)."""
    if dl.PROVIDER != "simulated":
        raise HTTPException(400, detail={"error_code": "not_allowed", "message": "A real courier reports status by webhook."})
    with db.engine.connect() as c:
        d = c.execute(select(db.deliveries).where(db.deliveries.c.id == did)).mappings().first()
    if not d:
        raise HTTPException(404, detail={"error_code": "not_found", "message": "No such delivery."})
    eid = f"console:{did}:{body.event}:{config.now().isoformat()}"
    return _out(dl.apply_event(d["provider"], eid, d["provider_job_id"], body.event, {"by": _who(s)}, otp=body.otp))


# ------------------------------------------------------------------ staff accounts (admin)
class StaffIn(BaseModel):
    username: str
    full_name: str
    role: str
    password: str
    doctor_id: int | None = None


@router.get("/api/staff/accounts")
def accounts(s: dict = Admin):
    with db.engine.connect() as c:
        rows = c.execute(select(db.staff_users).order_by(db.staff_users.c.role, db.staff_users.c.username)).mappings().all()
    return {"ok": True, "accounts": [{"id": r["id"], "username": r["username"], "full_name": r["full_name"], "role": r["role"],
                                      "doctor": REF.doctors.get(r["doctor_id"], {}).get("name") if r["doctor_id"] else None,
                                      "active": r["active"], "last_login_at": _iso(r["last_login_at"])} for r in rows]}


@router.post("/api/staff/accounts")
def create_account(body: StaffIn, s: dict = Admin):
    user, role = clean(body.username).lower(), clean(body.role).lower()
    if role not in ("doctor", "pharmacist", "admin"):
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Role must be doctor, pharmacist or admin."})
    if len(body.password) < 10:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Use a password of at least 10 characters."})
    if not user.replace(".", "").replace("_", "").isalnum() or len(user) < 3:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Usernames use letters, numbers, dots and underscores."})
    if role == "doctor" and body.doctor_id not in REF.doctors:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Pick the doctor this account belongs to."})
    if user == config.ADMIN_USER.lower():
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "That username is reserved."})
    with db.engine.begin() as c:
        if c.execute(select(db.staff_users.c.id).where(db.staff_users.c.username == user)).first():
            raise HTTPException(400, detail={"error_code": "already_exists", "message": "That username is taken."})
        c.execute(insert(db.staff_users).values(username=user, full_name=clean(body.full_name)[:80] or user, role=role,
                                                doctor_id=body.doctor_id if role == "doctor" else None,
                                                password_hash=hash_password(body.password), active=True, created_at=config.now()))
        pt.log(c, None, "staff_account_created", user[:20], True, f"{_who(s)} created {role} {user}", actor="staff", channel="staff")
    return {"ok": True, "message": f"Created {role} account {user}."}


@router.post("/api/staff/accounts/{aid}/active")
def set_active(aid: int, body: dict, s: dict = Admin):
    with db.engine.begin() as c:
        c.execute(update(db.staff_users).where(db.staff_users.c.id == aid).values(active=bool(body.get("active"))))
    return {"ok": True, "message": "Saved."}


# ------------------------------------------------------------------ courier webhook
@router.post("/api/webhooks/delivery/{provider}")
async def delivery_webhook(provider: str, request: Request):
    raw = await request.body()
    if not dl.signature_ok(raw, request.headers.get("x-signature", "")):
        raise HTTPException(401, detail={"error_code": "not_allowed", "message": "Bad signature."})
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, detail={"error_code": "invalid_input", "message": "Body must be JSON."})
    res = dl.apply_event(provider, clean(body.get("event_id")), clean(body.get("job_id")), clean(body.get("event")),
                         body, otp=clean(body.get("otp")))
    return res.as_dict()
