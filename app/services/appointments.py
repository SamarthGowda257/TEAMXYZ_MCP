"""Slots, booking, rescheduling, cancelling, waitlist offers. Shared by the bot (/mcp) and the website (/api).

Slot model: a doctor's grid comes from their schedule; a slot is free when there is no active booking
and no open waitlist offer holding it. The partial unique index on appointments is the final guard.
"""

import re
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from .. import config, db, notify
from ..util import (Result, clean, fail, human_date, human_time, in_pref, norm_code, norm_phone, norm_time_pref, ok,
                    parse_date, parse_time, rupees, short_date, spoken_code)
from .. import events
from . import blackboard as bb
from . import patients as pt
from .ref import (REF, DAY_FULL, days_text, doctor_card, doctors_in, find_department, find_doctor, find_doctors, not_found_doctor_message,
                  find_procedure, hours_text)

A, WL, WO = db.appointments, db.waitlist, db.waitlist_offers
OFFER_MINUTES = 30
LEAD_MINUTES = 30
MAX_DAYS_AHEAD = 60


# ------------------------------------------------------------------ slot grids
def grid(start: str, end: str, minutes: int) -> list[str]:
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")
    out = []
    while s + timedelta(minutes=minutes) <= e:
        out.append(s.strftime("%H:%M"))
        s += timedelta(minutes=minutes)
    return out


def doctor_unavailable_reason(doc: dict, d: date) -> str | None:
    if d.isoweekday() == 7:
        return "The outpatient clinics are closed on Sundays."
    if d.isoweekday() not in doc["days"]:
        return f"{doc['name']} does not consult on {DAY_FULL[d.isoweekday() - 1]}s. Consulting days: {days_text(doc)}."
    return None


def _cutoff(d: date) -> str | None:
    if d == config.today():
        return (config.now() + timedelta(minutes=LEAD_MINUTES)).strftime("%H:%M")
    return None


def taken_times(conn, doctor_ids: list[int], d: date, exclude_offer_id: int | None = None) -> dict[int, set]:
    """Times that are booked or held by an open offer, per doctor, in two indexed queries."""
    out: dict[int, set] = {i: set() for i in doctor_ids}
    if not doctor_ids:
        return out
    for r in conn.execute(select(A.c.doctor_id, A.c.appt_time).where(
            A.c.doctor_id.in_(doctor_ids), A.c.appt_date == d, A.c.status == "booked")):
        out[r[0]].add(r[1])
    q = select(WO.c.doctor_id, WO.c.appt_time, WO.c.id).where(
        WO.c.doctor_id.in_(doctor_ids), WO.c.appt_date == d, WO.c.status == "open", WO.c.expires_at > config.now())
    for r in conn.execute(q):
        if r[2] != exclude_offer_id:
            out[r[0]].add(r[1])
    return out


def free_for_doctors(conn, docs: list[dict], d: date, pref: str = "any") -> dict[int, list[str]]:
    usable = [x for x in docs if not doctor_unavailable_reason(x, d)]
    taken = taken_times(conn, [x["id"] for x in usable], d)
    cut = _cutoff(d)
    out = {}
    for x in usable:
        out[x["id"]] = [t for t in grid(x["start_time"], x["end_time"], x["slot_minutes"])
                        if t not in taken[x["id"]] and (not cut or t >= cut) and in_pref(t, pref)]
    return out


def proc_grid(p: dict) -> list[str]:
    step = 30 if p["duration_minutes"] > 20 else 15
    if p["category"] == "PKG":
        return ["08:00", "08:30", "09:00", "09:30", "10:00"]
    return grid("08:00", "20:00", step)


def free_for_procedure(conn, p: dict, d: date, pref: str = "any") -> list[tuple[str, int]]:
    """[(time, resource_id)] free for a procedure on a date (any machine of the right type)."""
    if d.isoweekday() == 7 and p["category"] not in ("MRI", "CT"):
        return []
    res = [r["id"] for r in REF.resources.values() if r["category"] == p["category"]]
    busy = {(r[0], r[1]) for r in conn.execute(select(A.c.resource_id, A.c.appt_time).where(
        A.c.resource_id.in_(res), A.c.appt_date == d, A.c.status == "booked"))}
    cut = _cutoff(d)
    out = []
    for t in proc_grid(p):
        if (cut and t < cut) or not in_pref(t, pref):
            continue
        free_res = next((r for r in res if (r, t) not in busy), None)
        if free_res:
            out.append((t, free_res))
    return out


_EARLIEST = re.compile(r"^\s*$|next (available|free|consulting|open)|earliest|soonest|first (available|free)|as soon as|asap|"
                       r"any ?(day|date|time)|whenever|next slot|nearest", re.I)


def _wants_earliest(text) -> bool:
    """'next available', 'earliest', 'his next consulting day', or no date at all -> search forward for a free day."""
    return bool(_EARLIEST.search(clean(text)))


def _resolve_date(text, field="date") -> tuple[date | None, Result | None]:
    d = parse_date(text)
    if not d:
        return None, fail("invalid_input", "I didn't catch the date. Please say a date like 4 November, tomorrow, or Monday.")
    if d < config.today():
        return None, fail("invalid_input", f"{human_date(d)} is in the past. Which upcoming date would you like?")
    if d > config.today() + timedelta(days=MAX_DAYS_AHEAD):
        return None, fail("invalid_input", "We take bookings up to 60 days ahead. Please choose a nearer date.")
    return d, None


def _pick_doctors(department, doctor_name) -> tuple[list[dict], dict | None, Result | None]:
    """Resolve doctor_name / department into a doctor list. Returns (docs, dept, error)."""
    if clean(doctor_name):
        m = find_doctors(doctor_name)
        if len(m) == 1:
            return m, REF.departments[m[0]["department_id"]], None
        if len(m) > 1:
            names = ", ".join(x["name"] for x in m[:3])
            return [], None, fail("invalid_input", f"I found more than one doctor with that name: {names}. Which one?",
                                  doctors=[x["name"] for x in m[:3]])
        dept = find_department(doctor_name)
        if not dept:
            msg, sug = not_found_doctor_message(doctor_name)
            return [], None, fail("not_found", msg, did_you_mean=sug)
        return doctors_in(dept["id"]), dept, None
    dept = find_department(department)
    if not dept:
        if clean(department):
            return [], None, fail("not_found", f"I couldn't match {clean(department)} to a department. We have "
                                  "Cardiology, Orthopaedics, General Medicine, Paediatrics, Dermatology and more.")
        return [], None, fail("invalid_input", "Which department or doctor would you like? For example Cardiology or Dr. Rajesh Iyer.")
    return doctors_in(dept["id"]), dept, None


# ------------------------------------------------------------------ find slots
def find_slots(date_text, department="", doctor_name="", time_preference="", procedure="", phone="") -> Result:
    pref = norm_time_pref(time_preference)
    with db.engine.connect() as c:
        patient = pt.get_by_phone(c, phone) if clean(phone) else None
        if not clean(time_preference) and patient and pt.is_senior(patient):
            pref = "morning"
        proc = find_procedure(procedure) if clean(procedure) else None
        if clean(procedure) and not proc:
            return fail("not_found", f"I couldn't find a test called {clean(procedure)}. We do MRI, CT, X-Ray, ultrasound, ECG, echo and lab tests.")
        earliest = _wants_earliest(date_text)
        if earliest:
            d = config.today() if config.now().hour < 19 else config.today() + timedelta(days=1)
        else:
            d, err = _resolve_date(date_text)
            if err:
                return err
        docs, dept = [], None
        if not proc:
            docs, dept, err = _pick_doctors(department, doctor_name)
            if err:
                return err
        if earliest:                       # jump to the first day that actually has a free slot
            if proc:
                for k in range(14):
                    if free_for_procedure(c, proc, d + timedelta(days=k), pref):
                        d = d + timedelta(days=k)
                        break
            else:
                nxt = next_available(c, docs, d, pref)
                if nxt:
                    d = nxt[0]
        base = {"date_iso": d.isoformat(), "weekday": DAY_FULL[d.isoweekday() - 1], "time_preference": pref}
        if proc:
            return _proc_slots(c, proc, d, pref, base)
        free = free_for_doctors(c, docs, d, pref)
        notes = [r for x in docs if (r := doctor_unavailable_reason(x, d))]
        out_docs = []
        for x in sorted(docs, key=lambda x: -len(free.get(x["id"], []))):
            card = doctor_card(x)
            card["free_slots"] = [human_time(t) for t in free.get(x["id"], [])[:3]]
            card["free_count"] = len(free.get(x["id"], []))
            out_docs.append(card)
        out_docs = out_docs[:3]
        any_free = [x for x in out_docs if x["free_slots"]]
        data = dict(base, department=dept["name"] if dept else None, doctors=out_docs, notes=notes[:3])
        if any_free:
            parts = [f"{x['name']} at {', '.join(x['free_slots'])}" for x in any_free[:2]]
            day = human_date(d)
            msg = f"On {day}, free slots: " + "; ".join(parts) + "."
            fees = {x['fee_inr'] for x in any_free[:2]}
            msg += f" The fee is {rupees(fees.pop())}." if len(fees) == 1 else ""
            short = f"On {day}, {any_free[0]['name']} is free at {', '.join(any_free[0]['free_slots'][:2])}."
            return Result(True, pt.say(patient, msg, short), data, related=bb.related(phone))
        nxt = next_available(c, docs, d + timedelta(days=1), pref)
        who = docs[0]["name"] if len(docs) == 1 else (dept["name"] if dept else "this department")
        reason = notes[0] + " " if len(notes) == len(docs) and len(docs) == 1 else ""
        if nxt:
            nd, ndoc, nslots = nxt
            data["next_available"] = {"date_iso": nd.isoformat(), "weekday": DAY_FULL[nd.isoweekday() - 1],
                                      "doctor": ndoc["name"], "free_slots": [human_time(t) for t in nslots[:3]]}
            msg = (f"{reason}No free slots with {who} on {human_date(d)}. The next free slots are on {human_date(nd)} "
                   f"with {ndoc['name']} at {', '.join(human_time(t) for t in nslots[:3])}. "
                   "I can also add you to the waitlist for your preferred date.")
        else:
            msg = f"{reason}{who} is fully booked for the next two weeks. I can add you to the waitlist and we'll email you if a slot opens."
        data["waitlist_available"] = True
        return Result(True, msg, data, related=bb.related(phone))


def _proc_slots(c, proc, d, pref, base) -> Result:
    free = free_for_procedure(c, proc, d, pref)
    data = dict(base, procedure=proc["name"], procedure_code=proc["code"], price_inr=proc["price_inr"],
                preauth_required=proc["preauth_required"], free_slots=[human_time(t) for t, _ in free[:3]])
    note = " Most insurers need pre-approval for this test." if proc["preauth_required"] else ""
    if free:
        return ok(f"{proc['name']} on {human_date(d)} is available at {', '.join(human_time(t) for t, _ in free[:3])}. "
                  f"The price is {rupees(proc['price_inr'])}.{note}", **data)
    for k in range(1, 8):
        nd = d + timedelta(days=k)
        nf = free_for_procedure(c, proc, nd, pref)
        if nf:
            data["next_available"] = {"date_iso": nd.isoformat(), "free_slots": [human_time(t) for t, _ in nf[:3]]}
            return ok(f"{proc['name']} is full on {human_date(d)}. The next slots are on {human_date(nd)} at "
                      f"{', '.join(human_time(t) for t, _ in nf[:3])}.", **data)
    return ok(f"{proc['name']} is fully booked for the next week. I can request a call back from the radiology desk.", **data)


def next_available(c, docs, start: date, pref="any", days=14):
    for k in range(days):
        d = start + timedelta(days=k)
        free = free_for_doctors(c, docs, d, pref)
        best = max(docs, key=lambda x: len(free.get(x["id"], [])))
        if free.get(best["id"]):
            return d, best, free[best["id"]]
    return None


# ------------------------------------------------------------------ helpers
def _appt_view(a: dict) -> dict:
    if a["doctor_id"]:
        doc = REF.doctors[a["doctor_id"]]
        who, room, fee, dept = doc["name"], doc["room"], doc["fee_inr"], doc["dept"]
    else:
        pr = REF.procedures[a["procedure_id"]]
        who, room, fee, dept = pr["name"], REF.resources[a["resource_id"]]["name"], pr["price_inr"], "Radiology and Diagnostics"
    return {"booking_id": a["booking_code"], "booking_id_spoken": spoken_code(a["booking_code"]), "with": who,
            "department": dept, "date_iso": a["appt_date"].isoformat(), "date": human_date(a["appt_date"]),
            "time": human_time(a["appt_time"]), "room": room, "fee_inr": fee, "status": a["status"]}


def instructions_for(a: dict) -> str:
    if a.get("procedure_id"):
        return REF.procedures[a["procedure_id"]]["instructions"] or "Arrive 20 minutes early."
    return "Please arrive 15 minutes early with a photo ID and any old reports."


def _get_booking(conn, booking_id, lock=False) -> dict | None:
    code = norm_code(booking_id, "WN")
    if not code:
        return None
    q = select(A).where(A.c.booking_code == code)
    if lock:
        q = q.with_for_update()
    r = conn.execute(q).mappings().first()
    return dict(r) if r else None


def _confirm_email(conn, patient, view, subject_prefix="Booking confirmed", extra=""):
    body = (f"Dear {patient['full_name']},\n\n{subject_prefix}: {view['with']} ({view['department']})\n"
            f"Date: {view['date']}\nTime: {view['time']}\nRoom: {view['room']}\nFee: Rs {view['fee_inr']}\n"
            f"Booking ID: {view['booking_id']}\n\n{extra}Manage your bookings at {config.PUBLIC_BASE_URL}/portal\n\n"
            "WellNest Hospitals, 42 Outer Ring Road, Marathahalli, Bengaluru.\nFor emergencies call 108.")
    sms = f"WellNest: {subject_prefix} {view['booking_id']} {view['with']} {short_date(date.fromisoformat(view['date_iso']))} {view['time']}."
    notify.email_and_sms(conn, patient=patient, template=subject_prefix.lower().replace(" ", "_"),
                         subject=f"{subject_prefix} - {view['booking_id']}", body=body, sms=sms)
    if patient.get("caregiver_consent") and patient.get("caregiver_email"):
        notify.queue(conn, patient_id=patient["id"], channel="email", template="caregiver_update",
                     to=patient["caregiver_email"], subject=f"Update for {patient['full_name']}: {subject_prefix}",
                     body=f"Hello {patient['caregiver_name']},\n\n{patient['full_name']}: {subject_prefix.lower()} with "
                          f"{view['with']} on {view['date']} at {view['time']} (booking {view['booking_id']}).\n\nWellNest Hospitals")


# ------------------------------------------------------------------ book
def book(phone, date_text, time_text, doctor_name="", department="", patient_name="", date_of_birth="", reason="",
         procedure="", idempotency_key="", channel="chat", actor="agent", patient_id=None) -> Result:
    p_norm = norm_phone(phone)
    if not patient_id and not p_norm:
        return fail("invalid_input", "Please share a valid 10 digit mobile number for the booking.")
    d, err = _resolve_date(date_text)
    if err:
        return err
    hh = parse_time(time_text)
    if not hh:
        return fail("invalid_input", "I didn't catch the time. Please say a time like 10:30 AM.")
    proc = find_procedure(procedure) if clean(procedure) else None
    if clean(procedure) and not proc:
        return fail("not_found", f"I couldn't find a test called {clean(procedure)}.")
    docs, dept = [], None
    if not proc:
        docs, dept, err = _pick_doctors(department, doctor_name)
        if err:
            return err
    key = clean(idempotency_key)[:80] or None
    try:
        with db.engine.begin() as c:
            # identify the patient
            if patient_id:
                patient = pt.get_by_id(c, patient_id)
            else:
                patient = pt.get_by_phone(c, p_norm)
                if patient and not patient["is_guest"] and clean(date_of_birth):
                    patient, err = pt.check_identity(c, p_norm, date_of_birth)
                    if err:
                        return err
                if not patient:
                    name = clean(patient_name).title()
                    if not name:
                        return fail("invalid_input", "May I have the patient's name for the booking?")
                    from ..util import parse_dob
                    dob = parse_dob(date_of_birth)
                    pid = c.execute(insert(db.patients).values(
                        patient_code=pt.random_code("PT", 6), full_name=name, phone=p_norm, date_of_birth=dob,
                        is_guest=dob is None, created_at=config.now())).inserted_primary_key[0]
                    patient = pt.get_by_id(c, pid)
            # idempotency: same key, or same patient + same slot, returns the existing booking
            if key:
                ex = c.execute(select(A).where(A.c.idempotency_key == key)).mappings().first()
                if ex:
                    return _booked_result(patient, dict(ex), repeat=True)
            q = select(A).where(A.c.patient_id == patient["id"], A.c.appt_date == d, A.c.appt_time == hh,
                                A.c.status == "booked")
            ex = c.execute(q).mappings().first()
            if ex and (not proc or ex["procedure_id"] == proc["id"]):
                return _booked_result(patient, dict(ex), repeat=True)
            # find a free doctor/machine at that time
            if proc:
                free = dict(free_for_procedure(c, proc, d))
                if hh not in free:
                    alts = [human_time(t) for t in list(free)[:3]]
                    return fail("slot_taken", f"{human_time(hh)} isn't available for {proc['name']} on {human_date(d)}."
                                + (f" Free times: {', '.join(alts)}." if alts else ""), alternatives=alts)
                vals = dict(procedure_id=proc["id"], resource_id=free[hh])
            else:
                free = free_for_doctors(c, docs, d)
                chosen = next((x for x in docs if hh in free.get(x["id"], [])), None)
                if not chosen:
                    alts = []
                    for x in docs:
                        alts += [f"{x['name']} at {human_time(t)}" for t in free.get(x["id"], [])[:3]]
                    reason_ = next((r for x in docs if (r := doctor_unavailable_reason(x, d))), None) if len(docs) == 1 else None
                    msg = (reason_ + " " if reason_ else "") + f"{human_time(hh)} on {human_date(d)} isn't available."
                    msg += f" Free: {'; '.join(alts[:3])}." if alts else " I can check another day or add you to the waitlist."
                    return fail("slot_taken", msg, alternatives=alts[:3], date_iso=d.isoformat())
                vals = dict(doctor_id=chosen["id"])
            code = new_booking_code(c)
            aid = c.execute(insert(A).values(booking_code=code, patient_id=patient["id"], appt_date=d, appt_time=hh,
                                             status="booked", reason=clean(reason)[:200] or (proc["name"] if proc else None),
                                             channel=channel, idempotency_key=key, created_at=config.now(),
                                             updated_at=config.now(), **vals)).inserted_primary_key[0]
            a = dict(c.execute(select(A).where(A.c.id == aid)).mappings().first())
            view = _appt_view(a)
            _confirm_email(c, patient, view, extra=f"Before your visit: {instructions_for(a)}\n\n")
            pt.log(c, patient["id"], "book_appointment", code, True,
                   f"Booked {view['with']} {view['date']} {view['time']}", actor, channel)
    except IntegrityError:
        return fail("slot_taken", "Sorry, that slot was just taken by someone else. Shall I check the next free time?")
    bb.invalidate(patient["phone"])
    events.publish("appointment.created", patient_id=patient["id"], booking_id=code, channel=channel)
    bb.add(patient["phone"], "booking", f"Booked {view['with']} on {view['date']} at {view['time']}, ID {code}.", 5, code)
    return _booked_result(patient, a)


def _booked_result(patient, a: dict, repeat=False) -> Result:
    v = _appt_view(a)
    ins = instructions_for(a)
    lead = "You already have this booking." if repeat else "Booked."
    msg = (f"{lead} {v['with']}, {v['date']} at {v['time']}, room {v['room']}, fee {rupees(v['fee_inr'])}. "
           f"Your booking ID is {v['booking_id']}.")
    if patient.get("is_guest"):
        msg += " Please register with us to manage this booking later."
    short = f"{lead} {v['with']}, {v['date']} at {v['time']}. Booking ID {v['booking_id']}."
    ref = REF.procedures[a["procedure_id"]]["code"] if a.get("procedure_id") else None
    rel = bb.related(patient["phone"], ref=ref, skip_kinds=("booking",))
    data = dict(v, instructions_short=ins[:160], patient_name=patient["full_name"])
    return Result(True, pt.say(patient, msg, short), data, related=rel)


# ------------------------------------------------------------------ find appointments
def find_appointments(phone="", date_of_birth="", booking_id="", include_past="") -> Result:
    past = clean(include_past).lower() in ("yes", "true", "1", "past", "y")
    with db.engine.begin() as c:
        if clean(booking_id) and not clean(date_of_birth):
            a = _get_booking(c, booking_id)
            if not a:
                return fail("not_found", f"I couldn't find booking {norm_code(booking_id, 'CL') or clean(booking_id)}. Please check the ID.")
            v = _appt_view(a)
            st = {"booked": "is confirmed", "cancelled": "was cancelled", "completed": "was completed",
                  "no_show": "was missed"}.get(a["status"], a["status"])
            return ok(f"Booking {v['booking_id']} with {v['with']} on {v['date']} at {v['time']} {st}. "
                      "To change it I'll need the registered mobile number and date of birth.",
                      appointments=[{k: v[k] for k in ("booking_id", "with", "date", "date_iso", "time", "status")}])
        if not clean(date_of_birth):
            p = pt.get_by_phone(c, phone)
            if not norm_phone(phone):
                return fail("invalid_input", "Please share the registered mobile number, or the booking ID.")
            n = 0
            if p:
                n = c.execute(select(func.count()).select_from(A).where(
                    A.c.patient_id == p["id"], A.c.status == "booked", A.c.appt_date >= config.today())).scalar() or 0
            return ok(f"I can see {n} upcoming booking{'s' if n != 1 else ''} on this number. "
                      "For privacy, please share the date of birth so I can read out the details." if n else
                      "I can't see any upcoming bookings on this number. Please share the date of birth so I can check fully.",
                      upcoming_count=n, needs="date_of_birth")
        p, err = pt.check_identity(c, phone, date_of_birth)
        if err:
            return err
        base = select(A).where(A.c.patient_id == p["id"])
        up = [dict(r) for r in c.execute(base.where(A.c.status == "booked", A.c.appt_date >= config.today())
                                         .order_by(A.c.appt_date, A.c.appt_time).limit(3)).mappings()]
        old = [dict(r) for r in c.execute(base.where(A.c.appt_date < config.today())
                                          .order_by(A.c.appt_date.desc(), A.c.appt_time.desc()).limit(3)).mappings()] if past else []
    up_v, old_v = [_appt_view(r) for r in up], [_appt_view(r) for r in old]
    fmt = lambda v: f"{v['with']} on {v['date']} at {v['time']}, ID {v['booking_id']}"
    keys = ("booking_id", "with", "date", "date_iso", "time", "room", "status")
    data = {"appointments": [{k: v[k] for k in keys} for v in up_v]}
    if past:
        data["past_visits"] = [{k: v[k] for k in keys} for v in old_v]
    if not up_v and not old_v:
        return ok("You have no upcoming bookings and no past visits on record." if past
                  else "You have no upcoming bookings. Would you like to book one?", **data)
    bits = []
    if up_v:
        bits.append(("Your upcoming booking: " if len(up_v) == 1 else "Your upcoming bookings: ") + "; ".join(fmt(v) for v in up_v) + ".")
    elif past:
        bits.append("You have no upcoming bookings.")
    if old_v:
        bits.append("Your recent visits: " + "; ".join(fmt(v) for v in old_v) + ".")
    short = " ".join(bits) if past else bits[0]     # asked for past visits: never shorten them away
    return Result(True, pt.say(p, " ".join(bits), short), data, related=bb.related(p["phone"]))


# ------------------------------------------------------------------ cancel / reschedule
def _own_booking(c, booking_id, phone, dob, patient_id=None):
    if patient_id:
        p = pt.get_by_id(c, patient_id)
    else:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return None, None, err
    a = _get_booking(c, booking_id, lock=True)
    if not a or a["patient_id"] != p["id"]:
        return p, None, fail("not_allowed", "I couldn't find that booking under your details. Please check the booking ID.")
    return p, a, None


def cancel(booking_id, phone="", date_of_birth="", reason="", channel="chat", actor="agent", patient_id=None) -> Result:
    if not clean(booking_id):
        return fail("invalid_input", "Which booking would you like to cancel? Please share the booking ID.")
    with db.engine.begin() as c:
        p, a, err = _own_booking(c, booking_id, phone, date_of_birth, patient_id)
        if err:
            return err
        v = _appt_view(a)
        if a["status"] == "cancelled":
            return ok(f"Booking {v['booking_id']} was already cancelled.", booking_id=v["booking_id"], cancelled=True)
        if a["status"] != "booked":
            return fail("not_allowed", f"Booking {v['booking_id']} is already {a['status'].replace('_', ' ')} and can't be cancelled.")
        c.execute(update(A).where(A.c.id == a["id"]).values(status="cancelled", cancelled_at=config.now(),
                                                            cancel_reason=clean(reason)[:200] or None, updated_at=config.now()))
        pt.log(c, p["id"], "cancel_appointment", v["booking_id"], True, f"Cancelled {v['with']} {v['date']} {v['time']}",
               actor, channel)
        notify.email_and_sms(c, patient=p, template="booking_cancelled", subject=f"Booking cancelled - {v['booking_id']}",
                             body=f"Dear {p['full_name']},\n\nYour booking {v['booking_id']} with {v['with']} on {v['date']} "
                                  f"at {v['time']} is cancelled.\n\nBook again any time at {config.PUBLIC_BASE_URL}.\n\nWellNest Hospitals",
                             sms=f"WellNest: booking {v['booking_id']} cancelled.")
        offer = offer_slot(c, a["doctor_id"], a["appt_date"], a["appt_time"], exclude_patient=p["id"]) if a["doctor_id"] else None
    bb.invalidate(p["phone"])
    events.publish("appointment.cancelled", patient_id=p["id"], booking_id=v["booking_id"], channel=channel)
    if offer:
        events.publish("waitlist.offered", patient_id=offer["patient_id"], offer_code=offer["offer_code"])
    msg = f"Cancelled. Booking {v['booking_id']} with {v['with']} on {v['date']} at {v['time']} is cancelled."
    short = f"Cancelled booking {v['booking_id']}."
    if offer:
        msg += " The freed slot has been offered to the next patient on the waitlist."
    return ok(pt.say(p, msg, short), booking_id=v["booking_id"], cancelled=True, slot_released=True,
              offered_to_waitlist=bool(offer))


def reschedule(booking_id, new_date, new_time, phone="", date_of_birth="", doctor_name="", channel="chat",
               actor="agent", patient_id=None) -> Result:
    if not clean(booking_id):
        return fail("invalid_input", "Which booking should I move? Please share the booking ID.")
    d, err = _resolve_date(new_date)
    if err:
        return err
    hh = parse_time(new_time)
    if not hh:
        return fail("invalid_input", "I didn't catch the new time. Please say a time like 11:15 AM.")
    try:
        with db.engine.begin() as c:
            p, a, err = _own_booking(c, booking_id, phone, date_of_birth, patient_id)
            if err:
                return err
            if a["status"] != "booked":
                return fail("not_allowed", f"Booking {a['booking_code']} is {a['status']} and can't be moved. I can make a new booking instead.")
            old = (a["doctor_id"], a["appt_date"], a["appt_time"])
            if a["procedure_id"]:
                proc = REF.procedures[a["procedure_id"]]
                free = dict(free_for_procedure(c, proc, d))
                if hh not in free:
                    alts = [human_time(t) for t in list(free)[:3]]
                    return fail("slot_taken", f"{human_time(hh)} isn't free for {proc['name']} on {human_date(d)}."
                                + (f" Free: {', '.join(alts)}." if alts else ""), alternatives=alts)
                vals = dict(resource_id=free[hh])
            else:
                doc = REF.doctors[a["doctor_id"]]
                if clean(doctor_name):
                    nd = find_doctor(doctor_name)
                    if not nd:
                        return fail("not_found", f"I couldn't find {clean(doctor_name)}.")
                    doc = nd
                free = free_for_doctors(c, [doc], d).get(doc["id"], [])
                if hh not in free:
                    why = doctor_unavailable_reason(doc, d)
                    alts = [human_time(t) for t in free[:3]]
                    return fail("slot_taken", (why + " " if why else "") + f"{doc['name']} isn't free at {human_time(hh)} on {human_date(d)}."
                                + (f" Free: {', '.join(alts)}." if alts else ""), alternatives=alts)
                vals = dict(doctor_id=doc["id"])
            c.execute(update(A).where(A.c.id == a["id"]).values(appt_date=d, appt_time=hh, updated_at=config.now(), **vals))
            a2 = dict(c.execute(select(A).where(A.c.id == a["id"])).mappings().first())
            v = _appt_view(a2)
            pt.log(c, p["id"], "reschedule_appointment", v["booking_id"], True, f"Moved to {v['date']} {v['time']}", actor, channel)
            _confirm_email(c, p, v, subject_prefix="Booking rescheduled")
            offer = offer_slot(c, *old, exclude_patient=p["id"]) if old[0] else None
            moved_code = v["booking_id"]
    except IntegrityError:
        return fail("slot_taken", "Sorry, that slot was just taken. Shall I check another time?")
    bb.invalidate(p["phone"])
    events.publish("appointment.rescheduled", patient_id=p["id"], booking_id=moved_code, channel=channel)
    if offer:
        events.publish("waitlist.offered", patient_id=offer["patient_id"], offer_code=offer["offer_code"])
    msg = (f"Rescheduled. Booking {v['booking_id']} is now with {v['with']} on {v['date']} at {v['time']}, "
           f"room {v['room']}, fee {rupees(v['fee_inr'])}.")
    if offer:
        msg += " Your old slot went to the next patient on the waitlist."
    short = f"Moved. {v['with']}, {v['date']} at {v['time']}. Booking ID {v['booking_id']}."
    return ok(pt.say(p, msg, short), **v)


# ------------------------------------------------------------------ assistance
def request_assistance(booking_id, phone, assistance_type, notes="", channel="chat", actor="agent", patient_id=None) -> Result:
    t = clean(assistance_type).lower().replace(" ", "_")
    kinds = {"wheelchair": "wheelchair", "wheel_chair": "wheelchair", "escort": "escort", "interpreter": "interpreter",
             "translator": "interpreter", "transport": "transport_desk", "transport_desk": "transport_desk", "cab": "transport_desk"}
    kind = next((v for k, v in kinds.items() if k in t), None)
    if not kind:
        return fail("invalid_input", "What help do you need: wheelchair, escort, interpreter or transport desk?")
    with db.engine.begin() as c:
        a = _get_booking(c, booking_id)
        p = pt.get_by_id(c, patient_id) if patient_id else pt.get_by_phone(c, phone)
        if not a or not p or a["patient_id"] != p["id"]:
            return fail("not_allowed", "I couldn't find that booking under this mobile number. Please check the booking ID.")
        aid = c.execute(insert(db.assistance_requests).values(appointment_id=a["id"], type=kind, notes=clean(notes)[:200] or None,
                                                              created_at=config.now())).inserted_primary_key[0]
        pt.log(c, p["id"], "request_assistance", a["booking_code"], True, f"{kind} requested", actor, channel)
    v = _appt_view(a)
    label = kind.replace("_", " ")
    bb.add(p["phone"], "assistance", f"{label.capitalize()} help is arranged for booking {v['booking_id']}.", 3, v["booking_id"])
    return ok(f"Done. {label.capitalize()} help will be ready at the main entrance on {v['date']} before your {v['time']} visit.",
              assistance_id=f"AS-{10000 + aid}", booking_id=v["booking_id"], type=kind)


# ------------------------------------------------------------------ waitlist
def join_waitlist(phone, date_of_birth, department="", doctor_name="", date_from="", date_to="", time_preference="",
                  channel="chat", actor="agent", patient_id=None) -> Result:
    df = parse_date(date_from) if clean(date_from) else config.today()
    if not df:
        return fail("invalid_input", "From which date should I look for a slot?")
    df = max(df, config.today())
    dt = parse_date(date_to) if clean(date_to) else df + timedelta(days=7)
    if not dt or dt < df:
        dt = df + timedelta(days=7)
    pref = norm_time_pref(time_preference)
    doc, dept = None, None
    if clean(doctor_name):
        doc = find_doctor(doctor_name)
        if not doc:
            return fail("not_found", f"I couldn't find a doctor named {clean(doctor_name)}.")
        dept = REF.departments[doc["department_id"]]
    else:
        dept = find_department(department)
        if not dept:
            return fail("invalid_input", "Which doctor or department should the waitlist be for?")
    with db.engine.begin() as c:
        if patient_id:
            p = pt.get_by_id(c, patient_id)
        else:
            p, err = pt.check_identity(c, phone, date_of_birth)
            if err:
                return err
        target = (WL.c.doctor_id == doc["id"]) if doc else and_(WL.c.doctor_id.is_(None), WL.c.department_id == dept["id"])
        dup = c.execute(select(WL).where(WL.c.patient_id == p["id"], WL.c.status.in_(["waiting", "offered"]), target)).mappings().first()
        if dup:
            return ok(f"You're already on the waitlist, reference {dup['code']}. We'll email you as soon as a slot opens.",
                      waitlist_id=dup["code"])
        code = pt.random_code("WL", 4)
        c.execute(insert(WL).values(code=code, patient_id=p["id"], department_id=dept["id"], doctor_id=doc["id"] if doc else None,
                                    date_from=df, date_to=dt, time_preference=pref, urgent=False, status="waiting",
                                    created_at=config.now()))
        ahead = c.execute(select(func.count()).select_from(WL).where(
            WL.c.status == "waiting", WL.c.code != code,
            (WL.c.doctor_id == doc["id"]) if doc else (WL.c.department_id == dept["id"]))).scalar() or 0
        pt.log(c, p["id"], "join_waitlist", code, True, f"Waitlist for {doc['name'] if doc else dept['name']}", actor, channel)
    who = doc["name"] if doc else dept["name"]
    return ok(f"You're on the waitlist for {who} between {short_date(df)} and {short_date(dt)}, reference {code}. "
              "If a slot opens we'll email you a link and hold it for 30 minutes.",
              waitlist_id=code, position=ahead + 1, date_from=df.isoformat(), date_to=dt.isoformat())


def offer_slot(c, doctor_id, d: date, hh: str, exclude_patient=None, exclude_waitlist_ids=()) -> dict | None:
    """A slot was freed: offer it to the best waitlist match (urgent, then senior, then earliest)."""
    slot_dt = datetime.combine(d, datetime.strptime(hh, "%H:%M").time())
    if slot_dt < config.now() + timedelta(minutes=LEAD_MINUTES):
        return None
    doc = REF.doctors[doctor_id]
    q = select(WL, db.patients.c.date_of_birth, db.patients.c.full_name, db.patients.c.email, db.patients.c.phone) \
        .join(db.patients, db.patients.c.id == WL.c.patient_id).where(
        WL.c.status == "waiting", WL.c.date_from <= d, WL.c.date_to >= d,
        or_(WL.c.doctor_id == doctor_id, and_(WL.c.doctor_id.is_(None), WL.c.department_id == doc["department_id"])))
    if exclude_patient:
        q = q.where(WL.c.patient_id != exclude_patient)
    if exclude_waitlist_ids:
        q = q.where(WL.c.id.notin_(list(exclude_waitlist_ids)))
    cands = [dict(r) for r in c.execute(q.with_for_update(skip_locked=True, of=WL)).mappings()]
    cands = [x for x in cands if in_pref(hh, x["time_preference"] or "any")]
    if not cands:
        return None
    from ..util import age_on
    cands.sort(key=lambda x: (not x["urgent"], not (x["date_of_birth"] and age_on(x["date_of_birth"]) >= 60), x["created_at"]))
    w = cands[0]
    code = pt.offer_code()
    expires = config.now() + timedelta(minutes=OFFER_MINUTES)
    held = c.execute(select(WO.c.id).where(WO.c.doctor_id == doctor_id, WO.c.appt_date == d, WO.c.appt_time == hh,
                                           WO.c.status == "open")).first()
    if held:
        return None   # someone already holds an offer for this slot
    c.execute(insert(WO).values(offer_code=code, waitlist_id=w["id"], doctor_id=doctor_id, appt_date=d, appt_time=hh,
                                status="open", expires_at=expires, created_at=config.now()))
    c.execute(update(WL).where(WL.c.id == w["id"]).values(status="offered"))
    link = f"{config.PUBLIC_BASE_URL}/waitlist/accept?code={code}"
    patient = {"id": w["patient_id"], "full_name": w["full_name"], "email": w["email"], "phone": w["phone"]}
    notify.email_and_sms(c, patient=patient, template="waitlist_offer",
                         subject=f"A slot opened with {doc['name']} - reply within 30 minutes",
                         body=f"Dear {w['full_name']},\n\nGood news: a slot opened with {doc['name']} ({doc['dept']}) on "
                              f"{human_date(d)} at {human_time(hh)}.\n\nWe are holding it for you until "
                              f"{human_time(expires.strftime('%H:%M'))}. Accept here: {link}\n\nOffer code: {code}\n\n"
                              "You can also reply in chat with this code.\n\nWellNest Hospitals",
                         sms=f"WellNest: slot with {doc['name']} {short_date(d)} {human_time(hh)} held 30 min. Accept: {link}",
                         key=f"offer:{code}")
    bb.invalidate(w["phone"])
    pt.log(c, w["patient_id"], "waitlist_offer", code, True, f"Offered {doc['name']} {d.isoformat()} {hh}", "system", None)
    bb.add(w["phone"], "waitlist_offer", f"A slot with {doc['name']} on {human_date(d)} at {human_time(hh)} is held for this "
           f"patient until {human_time(expires.strftime('%H:%M'))}, offer code {code}.", 2, code, ttl=OFFER_MINUTES * 60)
    return {"offer_code": code, "waitlist_code": w["code"], "patient_id": w["patient_id"]}


def get_offer(code) -> dict | None:
    c_ = clean(code).upper().replace(" ", "")
    with db.engine.connect() as c:
        r = c.execute(select(WO, WL.c.patient_id, db.patients.c.phone, db.patients.c.full_name)
                      .join(WL, WL.c.id == WO.c.waitlist_id).join(db.patients, db.patients.c.id == WL.c.patient_id)
                      .where(WO.c.offer_code == c_)).mappings().first()
    if not r:
        return None
    r = dict(r)
    doc = REF.doctors[r["doctor_id"]]
    live = r["status"] == "open" and r["expires_at"] > config.now()
    return {"offer_code": r["offer_code"], "doctor": doc["name"], "department": doc["dept"], "room": doc["room"],
            "fee_inr": doc["fee_inr"], "date": human_date(r["appt_date"]), "date_iso": r["appt_date"].isoformat(),
            "time": human_time(r["appt_time"]), "status": r["status"] if not (r["status"] == "open" and not live) else "expired",
            "expires_at": r["expires_at"].isoformat(), "seconds_left": max(0, int((r["expires_at"] - config.now()).total_seconds())),
            "patient_first_name": r["full_name"].split()[0], "_phone": r["phone"]}


def new_booking_code(c) -> str:
    """WN-xxxxx not used by any appointment (5 digits: with ~7k bookings a blind pick would clash ~8% of the time)."""
    while True:
        code = pt.random_code("WN")
        if not c.execute(select(A.c.id).where(A.c.booking_code == code)).first():
            return code


def accept_offer(offer_code, phone, channel="chat", actor="agent") -> Result:
    code = clean(offer_code).upper().replace(" ", "").replace("-", "")
    if not code:
        return fail("invalid_input", "Please share the offer code from the email or SMS.")
    p_norm = norm_phone(phone)
    if not p_norm:
        return fail("invalid_input", "Please share the mobile number the offer was sent to.")
    try:
        with db.engine.begin() as c:
            o = c.execute(select(WO).where(WO.c.offer_code == code).with_for_update()).mappings().first()
            if not o:
                return fail("not_found", "I couldn't find that offer code. Please check the email or SMS.")
            o = dict(o)
            w = dict(c.execute(select(WL).where(WL.c.id == o["waitlist_id"])).mappings().first())
            p = pt.get_by_id(c, w["patient_id"])
            if p["phone"] != p_norm:
                return fail("not_allowed", "That offer was sent to a different mobile number.")
            doc = REF.doctors[o["doctor_id"]]
            if o["status"] == "accepted":
                a = c.execute(select(A).where(A.c.id == o["appointment_id"])).mappings().first()
                return _booked_result(p, dict(a), repeat=True)
            if o["status"] != "open" or o["expires_at"] <= config.now():
                if o["status"] == "open":
                    c.execute(update(WO).where(WO.c.id == o["id"]).values(status="expired"))
                    c.execute(update(WL).where(WL.c.id == w["id"]).values(status="waiting"))
                nxt = next_available(c, [doc], config.today())
                extra = (f" The next free slot with {doc['name']} is {human_date(nxt[0])} at {human_time(nxt[2][0])}." if nxt else
                         " You're still on the waitlist and we'll offer you the next opening.")
                return fail("offer_expired", "Sorry, that offer has expired or the slot has gone." + extra)
            code_b = new_booking_code(c)       # unique: a clash would surface as a false "slot taken"
            aid = c.execute(insert(A).values(booking_code=code_b, patient_id=p["id"], doctor_id=doc["id"], appt_date=o["appt_date"],
                                             appt_time=o["appt_time"], status="booked", reason="Waitlist booking",
                                             channel="waitlist", created_at=config.now(), updated_at=config.now())).inserted_primary_key[0]
            c.execute(update(WO).where(WO.c.id == o["id"]).values(status="accepted", appointment_id=aid))
            c.execute(update(WL).where(WL.c.id == w["id"]).values(status="booked"))
            a = dict(c.execute(select(A).where(A.c.id == aid)).mappings().first())
            v = _appt_view(a)
            _confirm_email(c, p, v, extra="Booked from the waitlist.\n\n")
            pt.log(c, p["id"], "accept_waitlist_offer", code_b, True, f"Waitlist slot {v['with']} {v['date']} {v['time']}", actor, channel)
    except IntegrityError:
        return fail("offer_expired", "Sorry, that slot has just been taken. You're still on the waitlist.")
    bb.invalidate(p["phone"])
    events.publish("waitlist.accepted", patient_id=p["id"], booking_id=code_b, channel=channel)
    return _booked_result(p, a)


def expire_offers() -> int:
    """Jobs: expired open offers move to the next waitlisted patient (or free the slot)."""
    n = 0
    with db.engine.begin() as c:
        rows = [dict(r) for r in c.execute(select(WO).where(WO.c.status == "open", WO.c.expires_at <= config.now())).mappings()]
        for o in rows:
            c.execute(update(WO).where(WO.c.id == o["id"]).values(status="expired"))
            c.execute(update(WL).where(WL.c.id == o["waitlist_id"]).values(status="waiting"))
            tried = [r[0] for r in c.execute(select(WO.c.waitlist_id).where(
                WO.c.doctor_id == o["doctor_id"], WO.c.appt_date == o["appt_date"], WO.c.appt_time == o["appt_time"]))]
            offer_slot(c, o["doctor_id"], o["appt_date"], o["appt_time"], exclude_waitlist_ids=tried)
            n += 1
    return n
