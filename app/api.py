"""Website API (/api), ops dashboard API, jobs runner and page routes. Uses the same services as the MCP tools."""

import json
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import and_, func, insert, select, update

from . import config, db, metrics, notify, seed
from .security import hash_password, read_token, sign_token, token_matches, verify_password
from .services import appointments as ap
from .services import blackboard as bb
from .services import patients as pt
from .services import records as rc
from .services import ref
from .services.ref import REF, doctor_card
from .util import Result, age_on, clean, human_date, human_time, mask_phone, norm_phone, parse_date, parse_dob

WEB = config.ROOT / "web"
router = APIRouter()


def out(res: Result, status_fail: int = 400):
    d = res.as_dict()
    return JSONResponse(d, status_code=200 if res.ok else (404 if res.error_code == "not_found" else
                                                           403 if res.error_code in ("not_allowed", "locked_out", "not_verified") else
                                                           409 if res.error_code in ("slot_taken", "offer_expired", "already_exists") else status_fail))


# ------------------------------------------------------------------ auth
class CurrentPatient(BaseModel):
    id: int
    phone: str
    name: str


def current_patient(authorization: str = Header(default="")) -> CurrentPatient:
    tok = authorization[7:] if authorization.startswith("Bearer ") else ""
    body = read_token(tok) if tok else None
    if not body or "pid" not in body:
        raise HTTPException(401, detail={"error_code": "not_verified", "message": "Please log in again."})
    with db.engine.connect() as c:
        p = pt.get_by_id(c, body["pid"])
    if not p:
        raise HTTPException(401, detail={"error_code": "not_verified", "message": "Please log in again."})
    return CurrentPatient(id=p["id"], phone=p["phone"], name=p["full_name"])


def ops_auth(token: str = Query(default=""), x_dashboard_token: str = Header(default="")):
    if not token_matches(token or x_dashboard_token, config.DASHBOARD_TOKEN):
        raise HTTPException(401, detail={"error_code": "not_allowed", "message": "Dashboard token required."})


class Signup(BaseModel):
    name: str = ""
    email: str
    password: str
    phone: str
    date_of_birth: str


class Login(BaseModel):
    email: str
    password: str


@router.post("/api/auth/signup")
def signup(b: Signup):
    email = clean(b.email).lower()
    if "@" not in email or len(b.password) < 8:
        return JSONResponse({"ok": False, "error_code": "invalid_input",
                             "message": "Use a valid email and a password of at least 8 characters."}, 400)
    phone, dob = norm_phone(b.phone), parse_dob(b.date_of_birth)
    if not phone or not dob:
        return JSONResponse({"ok": False, "error_code": "invalid_input",
                             "message": "Please enter a valid 10 digit mobile number and your date of birth."}, 400)
    P = db.patients
    with db.engine.begin() as c:
        if c.execute(select(P.c.id).where(P.c.web_email == email)).first():
            return JSONResponse({"ok": False, "error_code": "already_exists",
                                 "message": "An account with this email already exists. Please log in."}, 409)
        p = pt.get_by_phone(c, phone)
        if p and p["web_email"]:
            return JSONResponse({"ok": False, "error_code": "already_exists",
                                 "message": "This mobile number already has a website account. Please log in."}, 409)
        if p and not p["is_guest"] and p["date_of_birth"] != dob:
            return JSONResponse({"ok": False, "error_code": "not_verified",
                                 "message": "We couldn't match that mobile number and date of birth. Please check them."}, 403)
        h = hash_password(b.password)
        if p:   # link the existing hospital record (made by phone, chat or the front desk)
            vals = dict(web_email=email, password_hash=h, is_guest=False, date_of_birth=dob)
            if not p["email"]:
                vals["email"] = email
            if clean(b.name) and p["is_guest"]:
                vals["full_name"] = clean(b.name).title()
            c.execute(update(P).where(P.c.id == p["id"]).values(**vals))
            pid, linked = p["id"], True
        else:
            if not clean(b.name):
                return JSONResponse({"ok": False, "error_code": "invalid_input", "message": "Please enter your full name."}, 400)
            pid = c.execute(insert(P).values(patient_code=pt.random_code("PT", 6), full_name=clean(b.name).title(), phone=phone,
                                             date_of_birth=dob, email=email, web_email=email, password_hash=h,
                                             is_guest=False, created_at=config.now())).inserted_primary_key[0]
            linked = False
        pt.log(c, pid, "web_signup", None, True, "Linked website account" if linked else "New website account", "web", "web")
    return {"ok": True, "token": sign_token({"pid": pid}), "linked_existing_record": linked,
            "message": "Welcome back, we found your hospital record." if linked else "Your account is ready."}


@router.post("/api/auth/login")
def login(b: Login):
    P = db.patients
    with db.engine.connect() as c:
        p = c.execute(select(P).where(P.c.web_email == clean(b.email).lower())).mappings().first()
    if not p or not verify_password(b.password, p["password_hash"]):
        return JSONResponse({"ok": False, "error_code": "not_verified", "message": "Email or password is incorrect."}, 401)
    return {"ok": True, "token": sign_token({"pid": p["id"]}), "name": p["full_name"]}


# ------------------------------------------------------------------ public
@router.get("/config.js")
def config_js():
    cfg = {"touchpointId": config.TALKDESK_TOUCHPOINT_ID, "region": config.TALKDESK_REGION,
           "publicBaseUrl": config.PUBLIC_BASE_URL, "hospital": config.HOSPITAL_NAME}
    return Response(f"window.CARELINE_CONFIG = {json.dumps(cfg)};", media_type="application/javascript",
                    headers={"Cache-Control": "no-cache"})


@router.get("/api/departments")
def departments():
    counts = {}
    for d in REF.doctors.values():
        counts[d["department_id"]] = counts.get(d["department_id"], 0) + 1
    return [{"code": d["code"], "name": d["name"], "floor": d["floor"], "description": d["description"],
             "doctors": counts.get(d["id"], 0)} for d in REF.departments.values()]


@router.get("/api/doctors")
def doctors(department: str = "", language: str = "", day: str = ""):
    dept = ref.find_department(department) if department else None
    res = []
    for d in REF.doctors.values():
        if dept and d["department_id"] != dept["id"]:
            continue
        if language and language.lower() not in d["languages"].lower():
            continue
        if day and day[:3].title() not in [ref.DAY_NAMES[i - 1] for i in d["days"]]:
            continue
        card = doctor_card(d)
        card.update(code=d["code"], qualification=d["qualification"], experience_years=d["experience_years"],
                    gender=d["gender"], day_codes=d["days"])
        res.append(card)
    return res


@router.get("/api/procedures")
def procedures():
    return [{"code": p["code"], "name": p["name"], "category": p["category"], "price_inr": p["price_inr"],
             "preauth_required": p["preauth_required"], "fasting_hours": p["fasting_hours"], "instructions": p["instructions"]}
            for p in REF.procedures.values()]


@router.get("/api/insurers")
def insurers():
    return [{"code": i["code"], "name": i["name"], "mode": i["mode"], "tpa": i["tpa_name"], "documents": i["documents"]}
            for i in REF.insurers.values()]


@router.get("/api/hospital-info")
def hospital_info():
    return REF.info


@router.get("/api/slots")
def slots(date: str, department: str = "", doctor: str = "", procedure: str = "", time_preference: str = ""):
    """Full slot grid for the booking page (not capped at 3 like the bot)."""
    d = parse_date(date)
    if not d or d < config.today():
        return JSONResponse({"ok": False, "error_code": "invalid_input", "message": "Please choose an upcoming date."}, 400)
    pref = ap.norm_time_pref(time_preference)
    with db.engine.connect() as c:
        if procedure:
            p = ref.find_procedure(procedure)
            if not p:
                return JSONResponse({"ok": False, "error_code": "not_found", "message": "Unknown test."}, 404)
            free = ap.free_for_procedure(c, p, d, pref)
            return {"ok": True, "date_iso": d.isoformat(), "date": human_date(d), "procedure": p["name"],
                    "price_inr": p["price_inr"], "slots": [{"time": t, "label": human_time(t)} for t, _ in free]}
        docs, dept, err = ap._pick_doctors(department, doctor)
        if err:
            return out(err)
        free = ap.free_for_doctors(c, docs, d, pref)
    return {"ok": True, "date_iso": d.isoformat(), "date": human_date(d), "doctors": [
        dict(doctor_card(x), code=x["code"], unavailable=ap.doctor_unavailable_reason(x, d),
             slots=[{"time": t, "label": human_time(t)} for t in free.get(x["id"], [])]) for x in docs]}


class CoverageReq(BaseModel):
    insurer: str = ""
    procedure: str = ""
    department: str = ""


@router.post("/api/coverage/estimate")
def coverage(b: CoverageReq):
    return out(rc.check_coverage(b.insurer, b.procedure, b.department))


# ------------------------------------------------------------------ patient
@router.get("/api/me")
def me(cp: CurrentPatient = Depends(current_patient)):
    with db.engine.connect() as c:
        p = pt.get_by_id(c, cp.id)
        snap = pt.snapshot(c, p) if p["date_of_birth"] else {}
    ins = REF.insurers.get(p["insurer_id"]) if p["insurer_id"] else None
    return {"id": p["patient_code"], "name": p["full_name"], "phone": p["phone"], "email": p["email"],
            "date_of_birth": p["date_of_birth"].isoformat() if p["date_of_birth"] else None,
            "age": age_on(p["date_of_birth"]) if p["date_of_birth"] else None, "gender": p["gender"],
            "insurer": ins["name"] if ins else None, "insurer_code": ins["code"] if ins else None,
            "policy_number": p["policy_number"], "preferred_language": p["preferred_language"],
            "preferred_time": p["preferred_time"], "caregiver_name": p["caregiver_name"],
            "caregiver_relation": p["caregiver_relation"], "caregiver_phone": p["caregiver_phone"],
            "caregiver_email": p["caregiver_email"], "caregiver_consent": p["caregiver_consent"],
            "mobility_needs": p["mobility_needs"], "is_senior": pt.is_senior(p), "snapshot": snap}


class Prefs(BaseModel):
    preferred_language: str = ""
    preferred_time: str = ""
    caregiver_name: str = ""
    caregiver_phone: str = ""
    caregiver_email: str = ""
    caregiver_consent: str = ""
    mobility_needs: str = ""
    email: str = ""
    insurer: str = ""
    policy_number: str = ""


@router.patch("/api/me/preferences")
def set_prefs(b: Prefs, cp: CurrentPatient = Depends(current_patient)):
    extra = {}
    if clean(b.email):
        extra["email"] = clean(b.email).lower()
    if clean(b.insurer):
        i = ref.find_insurer(b.insurer)
        extra["insurer_id"] = i["id"] if i else None
    if clean(b.policy_number):
        extra["policy_number"] = clean(b.policy_number)[:30]
    if extra:
        with db.engine.begin() as c:
            c.execute(update(db.patients).where(db.patients.c.id == cp.id).values(**extra))
    has_pref = any(clean(getattr(b, k)) for k in ("preferred_language", "preferred_time", "caregiver_name", "caregiver_phone",
                                                  "caregiver_email", "caregiver_consent", "mobility_needs"))
    if not has_pref:
        bb.invalidate(cp.phone)
        return {"ok": True, "message": "Saved."}
    return out(pt.set_preferences("", "", b.preferred_language, b.preferred_time, b.caregiver_name, b.caregiver_phone,
                                  b.caregiver_email, b.caregiver_consent, b.mobility_needs, actor="web", channel="web",
                                  patient_id=cp.id))


def _appt_rows(c, pid, scope):
    A = db.appointments
    q = select(A).where(A.c.patient_id == pid)
    if scope == "past":
        q = q.where((A.c.appt_date < config.today()) | (A.c.status.in_(["completed", "no_show"]))) \
             .order_by(A.c.appt_date.desc(), A.c.appt_time.desc()).limit(30)
    else:
        q = q.where(A.c.appt_date >= config.today(), A.c.status.in_(["booked", "cancelled"])).order_by(A.c.appt_date, A.c.appt_time).limit(30)
    rows = [dict(r) for r in c.execute(q).mappings()]
    ids = [r["id"] for r in rows]
    assist = {}
    if ids:
        for r in c.execute(select(db.assistance_requests.c.appointment_id, db.assistance_requests.c.type)
                           .where(db.assistance_requests.c.appointment_id.in_(ids))):
            assist.setdefault(r[0], []).append(r[1])
    return [dict(ap._appt_view(r), channel=r["channel"], reason=r["reason"], assistance=assist.get(r["id"], []),
                 is_procedure=bool(r["procedure_id"])) for r in rows]


@router.get("/api/me/appointments")
def my_appts(scope: str = "upcoming", cp: CurrentPatient = Depends(current_patient)):
    with db.engine.connect() as c:
        return _appt_rows(c, cp.id, scope)


class BookReq(BaseModel):
    date: str
    time: str
    doctor: str = ""
    department: str = ""
    procedure: str = ""
    reason: str = ""


@router.post("/api/me/appointments")
def book(b: BookReq, cp: CurrentPatient = Depends(current_patient), idempotency_key: str = Header(default="")):
    return out(ap.book(cp.phone, b.date, b.time, b.doctor, b.department, reason=b.reason, procedure=b.procedure,
                       idempotency_key=idempotency_key, channel="web", actor="web", patient_id=cp.id))


class Resched(BaseModel):
    date: str
    time: str


@router.post("/api/me/appointments/{code}/reschedule")
def resched(code: str, b: Resched, cp: CurrentPatient = Depends(current_patient)):
    return out(ap.reschedule(code, b.date, b.time, channel="web", actor="web", patient_id=cp.id))


class CancelReq(BaseModel):
    reason: str = ""


@router.post("/api/me/appointments/{code}/cancel")
def cancel(code: str, b: CancelReq, cp: CurrentPatient = Depends(current_patient)):
    return out(ap.cancel(code, reason=b.reason, channel="web", actor="web", patient_id=cp.id))


class AssistReq(BaseModel):
    type: str
    notes: str = ""


@router.post("/api/me/appointments/{code}/assistance")
def assist(code: str, b: AssistReq, cp: CurrentPatient = Depends(current_patient)):
    return out(ap.request_assistance(code, cp.phone, b.type, b.notes, channel="web", actor="web", patient_id=cp.id))


@router.get("/api/me/reports")
def my_reports(cp: CurrentPatient = Depends(current_patient)):
    LR = db.lab_reports
    with db.engine.connect() as c:
        rows = c.execute(select(LR).where(LR.c.patient_id == cp.id).order_by(LR.c.ordered_at.desc()).limit(30)).mappings().all()
    return [{"report_id": r["report_code"], "test": r["test_name"], "status": r["status"],
             "ordered": human_date(r["ordered_at"].date()), "ready_at": r["ready_at"].isoformat() if r["ready_at"] else None,
             "expected_at": r["expected_at"].isoformat() if r["expected_at"] else None,
             "doctor": REF.doctors[r["doctor_id"]]["name"] if r["doctor_id"] else None} for r in rows]


@router.get("/api/me/reports/{code}")
def my_report(code: str, cp: CurrentPatient = Depends(current_patient)):
    LR = db.lab_reports
    with db.engine.connect() as c:
        r = c.execute(select(LR).where(LR.c.report_code == code.upper(), LR.c.patient_id == cp.id)).mappings().first()
    if not r:
        return JSONResponse({"ok": False, "error_code": "not_found", "message": "Report not found."}, 404)
    return {"report_id": r["report_code"], "test": r["test_name"], "status": r["status"], "summary": r["summary"],
            "results": r["results"] if r["status"] != "pending" else None, "ordered": human_date(r["ordered_at"].date()),
            "ready_at": r["ready_at"].isoformat() if r["ready_at"] else None,
            "expected_at": r["expected_at"].isoformat() if r["expected_at"] else None,
            "doctor": REF.doctors[r["doctor_id"]]["name"] if r["doctor_id"] else None}


@router.post("/api/me/reports/{code}/email")
def email_report(code: str, cp: CurrentPatient = Depends(current_patient)):
    return out(rc.email_report("", "", code, patient_id=cp.id, actor="web", channel="web"))


@router.get("/api/me/waitlist")
def my_waitlist(cp: CurrentPatient = Depends(current_patient)):
    WL, WO = db.waitlist, db.waitlist_offers
    with db.engine.connect() as c:
        rows = c.execute(select(WL).where(WL.c.patient_id == cp.id).order_by(WL.c.created_at.desc()).limit(10)).mappings().all()
        offers = c.execute(select(WO).join(WL, WL.c.id == WO.c.waitlist_id).where(
            WL.c.patient_id == cp.id, WO.c.status == "open", WO.c.expires_at > config.now())).mappings().all()
    return {"entries": [{"id": r["code"], "status": r["status"],
                         "for": REF.doctors[r["doctor_id"]]["name"] if r["doctor_id"] else REF.departments[r["department_id"]]["name"],
                         "from": r["date_from"].isoformat(), "to": r["date_to"].isoformat(), "time_preference": r["time_preference"]}
                        for r in rows],
            "offers": [ap.get_offer(o["offer_code"]) | {"_phone": None} for o in offers]}


class WaitReq(BaseModel):
    department: str = ""
    doctor: str = ""
    date_from: str = ""
    date_to: str = ""
    time_preference: str = ""


@router.post("/api/me/waitlist")
def join_wait(b: WaitReq, cp: CurrentPatient = Depends(current_patient)):
    return out(ap.join_waitlist("", "", b.department, b.doctor, b.date_from, b.date_to, b.time_preference,
                                channel="web", actor="web", patient_id=cp.id))


@router.get("/api/me/bills")
def my_bills(cp: CurrentPatient = Depends(current_patient)):
    B = db.bills
    with db.engine.connect() as c:
        rows = c.execute(select(B).where(B.c.patient_id == cp.id).order_by(B.c.created_at.desc()).limit(20)).mappings().all()
    return [{"bill_id": b["bill_code"], "for": b["description"], "amount_inr": b["amount_inr"],
             "insurer_paid_inr": b["insurer_paid_inr"], "status": b["status"],
             "due_date": b["due_date"].isoformat() if b["due_date"] else None} for b in rows]


@router.post("/api/session/warm")
def warm(cp: CurrentPatient = Depends(current_patient)):
    """Called when the logged-in patient opens the chat widget: pre-build their snapshot."""
    with db.engine.connect() as c:
        p = pt.get_by_id(c, cp.id)
        if p["date_of_birth"]:
            bb.put_snapshot(p["phone"], pt.snapshot(c, p))
    metrics.cache(False)
    return {"ok": True}


# ------------------------------------------------------------------ waitlist accept page
@router.get("/api/waitlist/offer/{code}")
def offer(code: str):
    o = ap.get_offer(code)
    if not o:
        return JSONResponse({"ok": False, "error_code": "not_found", "message": "We couldn't find that offer."}, 404)
    o.pop("_phone", None)
    return {"ok": True, **o}


class AcceptReq(BaseModel):
    phone: str


@router.post("/api/waitlist/offer/{code}/accept")
def accept(code: str, b: AcceptReq):
    return out(ap.accept_offer(code, b.phone, channel="web", actor="web"))


# ------------------------------------------------------------------ ops dashboard
@router.get("/api/metrics", dependencies=[Depends(ops_auth)])
def api_metrics():
    return metrics.snapshot()


@router.get("/api/ops/summary", dependencies=[Depends(ops_auth)])
def ops_summary():
    A, WO, H, N = db.appointments, db.waitlist_offers, db.handoffs, db.notifications
    t = config.today()
    start = datetime.combine(t, datetime.min.time())
    with db.engine.connect() as c:
        def cnt(q):
            return c.execute(q).scalar() or 0
        sched = {}
        for r in c.execute(select(A.c.doctor_id, A.c.status, func.count()).where(A.c.appt_date == t, A.c.doctor_id.isnot(None))
                           .group_by(A.c.doctor_id, A.c.status)):
            dname = REF.doctors[r[0]]["dept"]
            sched.setdefault(dname, {"booked": 0, "capacity": 0})
            if r[1] in ("booked", "completed"):
                sched[dname]["booked"] += r[2]
        for d in REF.doctors.values():
            if t.isoweekday() in d["days"]:
                sched.setdefault(d["dept"], {"booked": 0, "capacity": 0})
                sched[d["dept"]]["capacity"] += len(ap.grid(d["start_time"], d["end_time"], d["slot_minutes"]))
        summary = {
            "bookings_today": cnt(select(func.count()).select_from(A).where(A.c.created_at >= start, A.c.status != "cancelled")),
            "cancellations_today": cnt(select(func.count()).select_from(A).where(A.c.cancelled_at >= start)),
            "refilled_from_waitlist": cnt(select(func.count()).select_from(WO).where(WO.c.status == "accepted", WO.c.created_at >= start)),
            "open_offers": cnt(select(func.count()).select_from(WO).where(WO.c.status == "open", WO.c.expires_at > config.now())),
            "open_handoffs": cnt(select(func.count()).select_from(H).where(H.c.status == "open")),
            "urgent_handoffs_today": cnt(select(func.count()).select_from(H).where(H.c.priority == "urgent", H.c.created_at >= start)),
            "emails_sent": cnt(select(func.count()).select_from(N).where(N.c.channel == "email", N.c.status == "sent")),
            "messages_simulated": cnt(select(func.count()).select_from(N).where(N.c.status == "simulated", N.c.created_at >= start)),
            "nurse_alerts_open": cnt(select(func.count()).select_from(db.nurse_alerts).where(db.nurse_alerts.c.status == "open")),
            "patients": cnt(select(func.count()).select_from(db.patients)),
            "upcoming_bookings": cnt(select(func.count()).select_from(A).where(A.c.appt_date >= t, A.c.status == "booked")),
        }
    return {"date": human_date(t), "now": config.now().strftime("%H:%M"), "summary": summary,
            "schedule": [{"department": k, **v} for k, v in sorted(sched.items())], "email_mode": "smtp" if config.EMAIL_ENABLED else "simulated",
            "db": "postgres" if db.IS_POSTGRES else "sqlite"}


@router.get("/api/ops/feed", dependencies=[Depends(ops_auth)])
def ops_feed():
    R, WO, WL, H, N, P = db.resolutions, db.waitlist_offers, db.waitlist, db.handoffs, db.notifications, db.patients
    with db.engine.connect() as c:
        acts = c.execute(select(R, P.c.full_name).outerjoin(P, P.c.id == R.c.patient_id)
                         .where(R.c.actor.in_(["agent", "web", "system"])).order_by(R.c.id.desc()).limit(25)).mappings().all()
        offers = c.execute(select(WO, P.c.full_name).join(WL, WL.c.id == WO.c.waitlist_id).join(P, P.c.id == WL.c.patient_id)
                           .order_by(WO.c.id.desc()).limit(8)).mappings().all()
        hos = c.execute(select(H).order_by(H.c.id.desc()).limit(8)).mappings().all()
        outbox = c.execute(select(N).order_by(N.c.id.desc()).limit(12)).mappings().all()
        alerts = c.execute(select(db.nurse_alerts).where(db.nurse_alerts.c.status == "open").order_by(db.nurse_alerts.c.id.desc()).limit(5)).mappings().all()
    now = config.now()
    return {
        "activity": [{"at": a["created_at"].strftime("%H:%M:%S"), "day": a["created_at"].date().isoformat(), "action": a["action"],
                      "ref": a["ref"], "ok": a["ok"], "summary": a["summary"], "channel": a["channel"] or a["actor"],
                      "patient": (a["full_name"] or "Guest").split()[0] + (" " + a["full_name"].split()[-1][0] + "." if a["full_name"] and len(a["full_name"].split()) > 1 else "")}
                     for a in acts],
        "offers": [{"code": o["offer_code"], "patient": o["full_name"].split()[0], "doctor": REF.doctors[o["doctor_id"]]["name"],
                    "slot": f"{o['appt_date'].strftime('%a %d %b')} {human_time(o['appt_time'])}",
                    "status": "expired" if o["status"] == "open" and o["expires_at"] <= now else o["status"],
                    "seconds_left": max(0, int((o["expires_at"] - now).total_seconds())) if o["status"] == "open" else 0} for o in offers],
        "handoffs": [{"code": h["handoff_code"], "priority": h["priority"], "status": h["status"], "summary": h["summary"][:140],
                      "phone": mask_phone(h["phone"]), "at": h["created_at"].strftime("%d %b %H:%M")} for h in hos],
        "outbox": [{"channel": n["channel"], "template": n["template"], "status": n["status"],
                    "to": mask_phone(n["to_address"]) if n["to_address"].startswith("+") else n["to_address"][:2] + "***@" + n["to_address"].split("@")[-1],
                    "at": n["created_at"].strftime("%H:%M:%S")} for n in outbox],
        "nurse_alerts": [{"reason": a["reason"][:120], "at": a["created_at"].strftime("%d %b %H:%M")} for a in alerts],
    }


# ------------------------------------------------------------------ jobs + demo reset
def _job_auth(token: str = Query(default=""), x_jobs_token: str = Header(default="")):
    if not token_matches(token or x_jobs_token, config.JOBS_TOKEN):
        raise HTTPException(401, detail={"error_code": "not_allowed", "message": "Jobs token required."})


def run_reminders() -> int:
    A, P = db.appointments, db.patients
    now = config.now()
    n = 0
    with db.engine.begin() as c:
        rows = c.execute(select(A, P.c.full_name, P.c.email, P.c.phone).join(P, P.c.id == A.c.patient_id).where(
            A.c.status == "booked", A.c.appt_date.in_([config.today(), config.today() + timedelta(days=1)]))).mappings().all()
        for r in rows:
            start = datetime.combine(r["appt_date"], datetime.strptime(r["appt_time"], "%H:%M").time())
            hours = (start - now).total_seconds() / 3600
            v = ap._appt_view(dict(r))
            patient = {"id": r["patient_id"], "full_name": r["full_name"], "email": r["email"], "phone": r["phone"]}
            if 20 <= hours <= 25:
                notify.email_and_sms(c, patient=patient, template="reminder_24h", key=f"r24:{r['booking_code']}",
                                     subject=f"Reminder: {v['with']} tomorrow at {v['time']}",
                                     body=f"Dear {r['full_name']},\n\nA reminder of your visit with {v['with']} on {v['date']} at "
                                          f"{v['time']}, room {v['room']}. Booking {v['booking_id']}.\n\nTo cancel or change: "
                                          f"{config.PUBLIC_BASE_URL}/portal/appointments\n\nCareLine Hospitals",
                                     sms=f"CareLine reminder: {v['with']} {v['date']} {v['time']}, {v['booking_id']}.")
                n += 1
            elif 1.5 <= hours <= 2.5:
                notify.queue(c, patient_id=r["patient_id"], channel="voice_call", template="reminder_2h", to=r["phone"],
                             body=f"Reminder call: {v['with']} at {v['time']} today.", dedupe_key=f"r2:{r['booking_code']}")
                n += 1
    return n


@router.api_route("/jobs/run", methods=["GET", "POST"], dependencies=[Depends(_job_auth)])
def jobs_run():
    t0 = time.perf_counter()
    expired = ap.expire_offers()
    reminders = run_reminders()
    sent = notify.flush(50)
    return {"ok": True, "offers_expired": expired, "reminders_queued": reminders, "emails_processed": sent,
            "ms": round((time.perf_counter() - t0) * 1000)}


@router.post("/ops/reset-demo", dependencies=[Depends(_job_auth)])
def reset_demo():
    counts = seed.reset(verbose=False)
    ref.load()
    bb.clear_all()
    return {"ok": True, "seeded": counts}


@router.get("/health")
def health():
    return {"ok": True, "service": "CareLine Hospitals MCP + web", "version": config.VERSION, "db": db.db_ok(),
            "db_kind": "postgres" if db.IS_POSTGRES else "sqlite", "time_ist": config.now().isoformat(),
            "email": "smtp" if config.EMAIL_ENABLED else "simulated"}


# ------------------------------------------------------------------ call-back form (website)
class CallbackReq(BaseModel):
    name: str = ""
    phone: str
    preferred_time: str = ""
    reason: str = ""


@router.post("/api/callback")
def web_callback(b: CallbackReq):
    from .services import support as sp
    reason = (f"{clean(b.name)}: " if clean(b.name) else "") + (clean(b.reason) or "Call back requested on the website")
    return out(sp.request_callback(b.phone, b.preferred_time, reason, channel="web"))


# ------------------------------------------------------------------ pages (React app built into web/dist)
DIST = WEB / "dist"
PAGES = ["/", "/doctors", "/insurance", "/contact", "/login", "/signup", "/portal", "/portal/book", "/portal/appointments",
         "/portal/reports", "/portal/profile", "/portal/waitlist", "/waitlist/accept", "/dashboard", "/pay"]


def spa():
    index = DIST / "index.html"
    if not index.exists():
        return PlainTextResponse("Website not built. Run: cd frontend && npm ci && npm run build", status_code=503)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


for _path in PAGES:
    router.add_api_route(_path, spa, methods=["GET"], include_in_schema=False)


def create_app() -> FastAPI:
    app = FastAPI(title="CareLine Hospitals", version=config.VERSION, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def timing(request: Request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        resp.headers["X-Response-Time"] = f"{(time.perf_counter() - t0) * 1000:.1f}ms"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp

    @app.exception_handler(HTTPException)
    async def http_err(_req, exc: HTTPException):
        body = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        return JSONResponse({"ok": False, **body}, status_code=exc.status_code)

    app.include_router(router)
    (DIST / "assets").mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    return app
