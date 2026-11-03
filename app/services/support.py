"""Human handoff, callbacks, conversation memory, caregiver updates and aftercare."""

from datetime import timedelta

from sqlalchemy import insert, or_, select

from .. import config, db, notify
from ..util import (Result, clean, fail, human_date, human_time, mask_email, norm_code, norm_phone, ok, split_list,
                    yes_no)
from .. import events
from . import blackboard as bb
from . import patients as pt
from .ref import REF

EMERGENCY_SAY = ("Please call 108 now if this is an emergency, or go to the nearest emergency department. "
                 "Our emergency entrance B is open 24 hours. I'm connecting you to a team member right away; please stay on the line.")


def create_handoff(summary, priority="normal", phone="", reason_code="", channel="chat") -> Result:
    summ = clean(summary)[:600] or "Patient asked for a person."
    pr = "urgent" if clean(priority).lower() in ("urgent", "high", "emergency", "critical") or clean(reason_code).lower() == "emergency" else "normal"
    rc = clean(reason_code).lower() or ("emergency" if pr == "urgent" else "requested_human")
    p_norm = norm_phone(phone)
    with db.engine.begin() as c:
        p = pt.get_by_phone(c, p_norm) if p_norm else None
        code = pt.random_code("HO")
        c.execute(insert(db.handoffs).values(handoff_code=code, patient_id=p["id"] if p else None, phone=p_norm, priority=pr,
                                             reason_code=rc[:20], summary=summ, status="open", created_at=config.now()))
        pt.log(c, p["id"] if p else None, "create_handoff", code, True, f"{pr} handoff: {summ[:120]}", "agent", channel)
    events.publish("handoff.created", priority=pr, handoff_id=code)
    if p_norm:
        bb.add(p_norm, "handoff", f"{'Urgent' if pr == 'urgent' else 'A'} handoff to a person is open ({code}); do not continue with bookings.", 0, code)
    if pr == "urgent":
        return ok(EMERGENCY_SAY, handoff_id=code, priority=pr, say=EMERGENCY_SAY, transfer=True)
    say = "I'm passing you to a team member now with a summary, so you won't need to repeat yourself. Please hold for a moment."
    return ok(say, handoff_id=code, priority=pr, say=say, transfer=True)


def handoff_status(handoff_id) -> Result:
    code = norm_code(handoff_id, "HO")
    with db.engine.connect() as c:
        h = c.execute(select(db.handoffs).where(db.handoffs.c.handoff_code == code)).mappings().first() if code else None
    if not h:
        return fail("not_found", "I couldn't find that handoff reference.")
    st = {"open": "waiting for the next team member", "assigned": f"with {h['assigned_to'] or 'a team member'}", "closed": "closed"}[h["status"]]
    return ok(f"Handoff {h['handoff_code']} is {st}.", handoff_id=h["handoff_code"], status=h["status"], assigned=h["assigned_to"])


def request_callback(phone, preferred_time, reason, channel="chat") -> Result:
    p_norm = norm_phone(phone)
    if not p_norm:
        return fail("invalid_input", "Which mobile number should we call back?")
    pref = clean(preferred_time)[:60] or "as soon as possible"
    with db.engine.begin() as c:
        p = pt.get_by_phone(c, p_norm)
        code = pt.random_code("CB")
        c.execute(insert(db.callbacks).values(callback_code=code, patient_id=p["id"] if p else None, phone=p_norm,
                                              preferred_time=pref, reason=clean(reason)[:200] or None, status="queued",
                                              created_at=config.now()))
        notify.queue(c, patient_id=p["id"] if p else None, channel="voice_call", template="callback", to=p_norm,
                     body=f"Call back {pref}: {clean(reason)[:120]}")
        pt.log(c, p["id"] if p else None, "request_callback", code, True, f"Callback {pref}", "agent", channel)
    return ok(f"Done. Our team will call you back {pref}. Your reference is {code}.", callback_id=code, preferred_time=pref)


def save_note(phone, summary, topics="", outcome="", channel="chat") -> Result:
    p_norm = norm_phone(phone)
    s = clean(summary)
    if not p_norm or not s:
        return fail("invalid_input", "I need the patient's mobile number and a short summary to save a note.")
    with db.engine.begin() as c:
        p = pt.get_by_phone(c, p_norm)
        nid = c.execute(insert(db.interaction_notes).values(patient_id=p["id"] if p else None, phone=p_norm,
                                                            channel=clean(channel)[:10] or "chat", summary=s[:500],
                                                            topics=pt.topics_text(topics) or None,
                                                            outcome=clean(outcome)[:120] or None,
                                                            created_at=config.now())).inserted_primary_key[0]
    bb.invalidate(p_norm, "p1", "p3")
    events.publish("interaction.noted", patient_id=p["id"] if p else None)
    return ok("Noted for next time.", note_id=f"NT-{10000 + nid}")


def _words(q: str) -> list[str]:
    stop = {"did", "i", "you", "me", "my", "ask", "asked", "about", "the", "a", "an", "last", "week", "what", "when", "was",
            "is", "of", "to", "for", "on", "in", "we", "talk", "talked", "tell", "told", "any", "previous", "before"}
    return [w for w in "".join(ch if ch.isalnum() else " " for ch in q.lower()).split() if w not in stop and len(w) > 2]


def search_interactions(phone, dob, query) -> Result:
    N, R = db.interaction_notes, db.resolutions
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        words = _words(clean(query))
        notes = [dict(r) for r in c.execute(select(N.c.summary, N.c.topics, N.c.created_at).where(N.c.patient_id == p["id"])
                                            .order_by(N.c.created_at.desc()).limit(50)).mappings()]
        res = [dict(r) for r in c.execute(select(R.c.summary, R.c.action, R.c.created_at).where(R.c.patient_id == p["id"])
                                          .order_by(R.c.created_at.desc()).limit(50)).mappings()]
    items = [{"date": n["created_at"], "text": n["summary"], "hay": f"{n['summary']} {n['topics'] or ''}".lower()} for n in notes]
    items += [{"date": r["created_at"], "text": f"{r['action'].replace('_', ' ')}: {r['summary']}",
               "hay": f"{r['action']} {r['summary']}".lower()} for r in res]
    scored = []
    for it in items:
        score = sum(1 for w in words if w in it["hay"] or (len(w) > 4 and w[:-1] in it["hay"]))
        if score or not words:
            scored.append((score, it["date"], it))
    scored.sort(key=lambda x: (-x[0], -x[1].timestamp()))
    top = [x[2] for x in scored[:3]]
    if not top:
        return ok("I don't see an earlier conversation about that on your record.", matches=[])
    m = top[0]
    days = (config.today() - m["date"].date()).days
    when = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago, on {human_date(m['date'].date())}"
    return ok(f"Yes. {when[0].upper() + when[1:]}: {m['text']}", matches=[{"date": x["date"].date().isoformat(), "summary": x["text"]} for x in top])


def caregiver_update(phone, dob, booking_id="") -> Result:
    A = db.appointments
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        if not p["caregiver_name"] or not (p["caregiver_email"] or p["caregiver_phone"]):
            return fail("not_found", "There's no caregiver on file yet. I can add one if you tell me their name and mobile number.")
        if not p["caregiver_consent"]:
            return fail("not_allowed", f"Updates to {p['caregiver_name']} are switched off. Shall I switch them on?")
        q = select(A).where(A.c.patient_id == p["id"], A.c.status == "booked", A.c.appt_date >= config.today())
        if clean(booking_id):
            q = q.where(A.c.booking_code == norm_code(booking_id, "WN"))
        a = c.execute(q.order_by(A.c.appt_date, A.c.appt_time).limit(1)).mappings().first()
        if not a:
            return fail("not_found", "I couldn't find an upcoming booking to share.")
        who = REF.doctors[a["doctor_id"]]["name"] if a["doctor_id"] else REF.procedures[a["procedure_id"]]["name"]
        text = (f"{p['full_name']} has a visit with {who} on {human_date(a['appt_date'])} at {human_time(a['appt_time'])} "
                f"(booking {a['booking_code']}) at WellNest Hospitals, Marathahalli.")
        if p["caregiver_email"]:
            notify.queue(c, patient_id=p["id"], channel="email", template="caregiver_update", to=p["caregiver_email"],
                         subject=f"Visit details for {p['full_name']}", body=f"Hello {p['caregiver_name']},\n\n{text}\n\nWellNest Hospitals")
        if p["caregiver_phone"]:
            notify.queue(c, patient_id=p["id"], channel="sms", template="caregiver_update", to=p["caregiver_phone"], body="WellNest: " + text)
        pt.log(c, p["id"], "send_caregiver_update", a["booking_code"], True, f"Update to {p['caregiver_name']}")
    sent = mask_email(p["caregiver_email"]) if p["caregiver_email"] else "their mobile"
    return ok(f"Done. I've sent the visit details to {p['caregiver_name']} at {sent}.", sent_to=sent, caregiver=p["caregiver_name"])


# ------------------------------------------------------------------ aftercare
def flag_nurse_alert(phone, reason, patient=None, conn=None) -> Result:
    p_norm = norm_phone(phone)
    def _do(c):
        p = patient or (pt.get_by_phone(c, p_norm) if p_norm else None)
        aid = c.execute(insert(db.nurse_alerts).values(patient_id=p["id"] if p else None, phone=p_norm, reason=clean(reason)[:300] or "Follow-up needed",
                                                       status="open", created_at=config.now())).inserted_primary_key[0]
        pt.log(c, p["id"] if p else None, "flag_nurse_alert", f"NA-{10000 + aid}", True, clean(reason)[:200])
        return aid
    if conn is not None:
        aid = _do(conn)
    else:
        with db.engine.begin() as c:
            aid = _do(c)
    return ok("I've alerted our nurse team; a nurse will call you shortly. If you feel worse, call 108.",
              alert_id=f"NA-{10000 + aid}")


def record_checkin(phone, dob, booking_id="", pain_score="", fever="", symptoms_worse="", notes="",
                   patient_id=None, appointment_id=None, channel="chat") -> Result:
    try:
        pain = int(float(clean(pain_score))) if clean(pain_score) else None
    except ValueError:
        pain = None
    if pain is not None and not 0 <= pain <= 10:
        return fail("invalid_input", "Please give the pain score from 0 to 10.")
    fev, worse = yes_no(fever), yes_no(symptoms_worse)
    alert = bool((pain is not None and pain >= 7) or fev or worse)
    A = db.appointments
    with db.engine.begin() as c:
        if patient_id:                       # website check-in link (signed token) already identifies the patient
            p = pt.get_by_id(c, patient_id)
        else:
            p, err = pt.check_identity(c, phone, dob)
            if err:
                return err
        a = (appointment_id,) if appointment_id else None
        if clean(booking_id) and not a:
            a = c.execute(select(A.c.id).where(A.c.booking_code == norm_code(booking_id, "WN"), A.c.patient_id == p["id"])).first()
        cid = c.execute(insert(db.checkins).values(patient_id=p["id"], appointment_id=a[0] if a else None, pain_score=pain,
                                                   fever=fev, symptoms_worse=worse, notes=clean(notes)[:300] or None,
                                                   alert_raised=alert, created_at=config.now())).inserted_primary_key[0]
        if alert:
            flag_nurse_alert(p["phone"], f"Check-in warning: pain {pain}, fever {fev}, worse {worse}. {clean(notes)[:150]}", p, c)
        pt.log(c, p["id"], "record_checkin", f"CI-{10000 + cid}", True, f"Check-in, alert={alert}", channel=channel)
    if alert:
        return ok("Thank you. Because of your answers, a nurse will call you shortly. If you feel much worse, call 108.",
                  checkin_id=f"CI-{10000 + cid}", alert_raised=True)
    return ok("Thank you, that's good to hear. Keep following your doctor's advice.", checkin_id=f"CI-{10000 + cid}", alert_raised=False)


def submit_feedback(phone, rating, comment="", booking_id="") -> Result:
    try:
        r = int(float(clean(rating)))
    except ValueError:
        return fail("invalid_input", "Please rate us from 1 to 5.")
    if not 1 <= r <= 5:
        return fail("invalid_input", "Please rate us from 1 to 5.")
    A = db.appointments
    with db.engine.begin() as c:
        p = pt.get_by_phone(c, phone)
        a = c.execute(select(A.c.id).where(A.c.booking_code == norm_code(booking_id, "WN"))).first() if clean(booking_id) else None
        fid = c.execute(insert(db.feedback).values(patient_id=p["id"] if p else None, appointment_id=a[0] if a else None, rating=r,
                                                   comment=clean(comment)[:500] or None, created_at=config.now())).inserted_primary_key[0]
    msg = "Thank you for the feedback." if r >= 4 else "Thank you for telling us. Our patient care team will look into it."
    if r <= 2 and p:
        create_handoff(f"Low rating {r}/5: {clean(comment)[:200]}", "normal", p["phone"], "complaint")
    return ok(msg, feedback_id=f"FB-{10000 + fid}")


def schedule_followup(phone, dob, doctor_name="", within_days="") -> Result:
    from . import appointments as ap
    from .ref import find_doctor
    A = db.appointments
    try:
        days = max(1, min(30, int(float(clean(within_days) or 7))))
    except ValueError:
        days = 7
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        doc = find_doctor(doctor_name) if clean(doctor_name) else None
        if not doc:
            last = c.execute(select(A.c.doctor_id).where(A.c.patient_id == p["id"], A.c.status == "completed", A.c.doctor_id.isnot(None))
                             .order_by(A.c.appt_date.desc()).limit(1)).first()
            doc = REF.doctors.get(last[0]) if last else None
        if not doc:
            return fail("invalid_input", "Which doctor is the follow-up with?")
        nxt = ap.next_available(c, [doc], config.today() + timedelta(days=1), "any", days)
    if not nxt:
        return ok(f"{doc['name']} has no free slots in the next {days} days. I can add you to the waitlist.", doctor=doc["name"])
    d, _, slots = nxt
    return ok(f"For your follow-up, {doc['name']} is free on {human_date(d)} at {', '.join(human_time(t) for t in slots[:3])}. "
              "Which time should I book?", doctor=doc["name"], date_iso=d.isoformat(), free_slots=[human_time(t) for t in slots[:3]])
