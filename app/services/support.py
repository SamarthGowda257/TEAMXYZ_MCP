"""Human handoff, callbacks, conversation memory, caregiver updates and aftercare."""

import logging
import re
from datetime import timedelta

from sqlalchemy import insert, or_, select

from .. import config, db, notify
from ..util import (Result, clean, fail, human_date, human_time, mask_email, norm_code, norm_phone, ok, split_list,
                    yes_no)
from .. import events
from . import blackboard as bb
from . import patients as pt
from .ref import REF

log = logging.getLogger("wellnest.support")

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
    say = ("I'm passing you to a team member now with a summary, so you won't need to repeat yourself. "
           "If we get disconnected, we'll call you back within 2 hours.")
    if rc == "complaint":
        grv = "GRV-" + code.split("-")[1]
        say = ("I'm sorry about this. I've logged your complaint and passed it to our patient relations team with a summary, "
               "so you won't need to repeat yourself. If we get disconnected, we'll call you back within 2 hours. "
               f"Your complaint reference is {grv}.")          # last, as its own sentence: summaries kept dropping it
        return ok(say, handoff_id=code, grievance_id=grv, priority=pr, say=say, transfer=True)
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


# Answers that change nothing, so no service logs them. Recording them is what lets a patient ask "did I check that?".
REMEMBERED_READS = {"get_lab_report_status", "get_visit_history", "get_bill_status", "get_health_credits_balance",
                    "track_medicine_order", "recharge_health_credits", "get_patient_preferences", "check_coverage"}


def remember_read(tool_name, phone, message) -> None:
    """Add a successful read to the patient's memory, once per 10 minutes for the same answer. Never raises."""
    try:
        p_norm, text = norm_phone(phone), clean(message)[:300]
        if not p_norm or not text:
            return
        R = db.resolutions
        with db.engine.begin() as c:
            p = pt.get_by_phone(c, p_norm)
            if not p:
                return
            since = config.now() - timedelta(minutes=10)
            if c.execute(select(R.c.id).where(R.c.patient_id == p["id"], R.c.action == tool_name, R.c.summary == text,
                                              R.c.created_at >= since)).first():
                return
            pt.log(c, p["id"], tool_name, None, True, text)
    except Exception:
        log.exception("remember_read failed")


def memory_touched(phone) -> None:
    """After a successful tool call, ask the workers to index and embed this patient's new memory (notes, actions,
    remembered answers), at most once every 15 seconds per patient. Never raises."""
    try:
        from .. import events
        from ..store import store
        p_norm = norm_phone(phone)
        if not p_norm:
            return
        with db.engine.connect() as c:
            p = pt.get_by_phone(c, p_norm)
        if p and not store.get_json(f"memidx:{p['id']}", count=False):
            store.set_json(f"memidx:{p['id']}", 1, ttl=15)
            events.publish("memory.touched", patient_id=p["id"])
    except Exception:
        log.exception("memory_touched failed")


def save_note(phone, summary, topics="", outcome="", channel="chat", last_message="", interaction_id="") -> Result:
    p_norm = norm_phone(phone)
    s = clean(summary)
    said = clean(last_message)
    if s and said:
        s = f'{s} Patient said: "{said[:200]}"'
    if not p_norm or not s:
        return fail("invalid_input", "I need the patient's mobile number and a short summary to save a note.")
    with db.engine.begin() as c:
        p = pt.get_by_phone(c, p_norm)
        nid = c.execute(insert(db.interaction_notes).values(patient_id=p["id"] if p else None, phone=p_norm,
                                                            channel=clean(channel)[:10] or "chat", summary=s[:500],
                                                            topics=pt.topics_text(topics) or None,
                                                            outcome=clean(outcome)[:120] or None,
                                                            created_at=config.now())).inserted_primary_key[0]
        if p:
            from .. import search
            search.sync(c, p["id"])                 # keyword-searchable at once; the meaning vector follows in the background
    bb.invalidate(p_norm, "p1", "p3")
    if p and clean(interaction_id) and pt.recently_verified(p_norm):      # later transcript of this chat finds its patient
        from . import chat_session
        chat_session.link_interaction(interaction_id, p["id"])
    events.publish("interaction.noted", patient_id=p["id"] if p else None)
    return ok("Noted for next time.", note_id=f"NT-{10000 + nid}")


# Words that ask "when" rather than "what": a query made only of these means "show me the latest".
_RECENCY_WORDS = {"last", "time", "chat", "chats", "conversation", "conversations", "before", "previous", "earlier",
                  "ask", "asked", "talk", "talked", "spoke", "discuss", "discussed", "said", "told", "did", "what", "about",
                  "recent", "recently", "history", "past", "you", "me", "my", "i", "we", "us", "the", "a", "in", "with",
                  "do", "remember", "anything", "something", "call", "message", "messages", "ago", "yesterday", "week",
                  "speak", "spoke", "spoken", "speaking", "talking", "discussion", "session", "previously", "prior", "our",
                  "was", "were", "it", "that", "this", "have", "had", "any", "all", "over", "recap", "summary",
                  "summarise", "summarize", "can", "tell", "know", "please", "everything", "go", "went", "there", "then",
                  "happened", "conversation's", "last time"}


def search_interactions(phone, dob, query) -> Result:
    """Hybrid search (keyword + fuzzy + meaning) over this patient's own notes and actions; never across patients."""
    from .. import search
    handoff = re.search(r"\bHO[\s-]?\d{3,6}\b", clean(query), re.I)
    if handoff:
        return handoff_status(handoff.group(0))
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        search.sync(c, p["id"])                     # a note saved seconds ago is findable at once
        q = clean(query)
        topical = [w for w in search.words(q) if w not in _RECENCY_WORDS]
        top, mode, missed = [], "recent", False
        if topical or search.codes(q):
            res = search.search(q, patient_id=p["id"], k=3, conn=c)
            top, mode = res["hits"], res["mode"]
            missed = not top
        if not top:                                 # "what did I ask last time?", or nothing on that topic: newest first
            D = db.search_docs
            rows = c.execute(select(D.c.ref, D.c.kind, D.c.title, D.c.body, D.c.created_at).where(
                D.c.patient_id == p["id"], D.c.kind.in_(("note", "action"))).order_by(D.c.created_at.desc()).limit(12)).mappings().all()
            top, mode = [dict(r) for r in rows], "recent"
    if not top:
        return ok("I don't see any earlier conversation on your record yet.", matches=[], search_mode=mode)
    m = top[0]
    days = (config.today() - m["created_at"].date()).days
    when = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago, on {human_date(m['created_at'].date())}"
    matches = [{"date": x["created_at"].date().isoformat(), "summary": x["body"][:200]} for x in top[:5]]
    if mode == "recent" and not missed:
        # "what did we talk about last time": the whole last conversation (everything within an hour of the newest
        # item), not only its final line. Live, a booking made in the same chat was left out.
        session = [x for x in top if (m["created_at"] - x["created_at"]) <= timedelta(hours=1)]
        seen, parts = set(), []
        for x in reversed(session):                 # oldest first, so it reads in the order it happened
            line = _short(x["body"])
            if line.lower() not in seen:
                seen.add(line.lower())
                parts.append(line)
        parts = parts[-4:]
        if len(parts) > 1:
            return ok(f"In our last conversation, {when}: " + "; ".join(parts) + ".", search_mode=mode, matched_topic=True,
                      matches=matches, items=len(parts))
    lead = "I don't see one on that exact topic. The most recent was" if missed else "Yes. Most recently,"
    return ok(f"{lead} {when}: {m['body']}", search_mode=mode, matched_topic=not missed, matches=matches)


def _short(body: str) -> str:
    t = re.sub(r"\s+", " ", clean(body)).rstrip(". ")
    t = re.sub(r"^[a-z_ ]{3,40}: ", "", t)          # action lines start with the tool's name
    t = re.sub(r"^(Patient |The patient )", "", t)
    return t[:140] + ("..." if len(t) > 140 else "")


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
        pt.log(c, p["id"] if p else None, "flag_nurse_alert", f"ALT-{10000 + aid}", True, clean(reason)[:200])
        if p:                                # caregiver: that a nurse is calling, never the symptoms (DPDP)
            notify.to_caregiver(c, p, template="nurse_alert", key=f"alert:{aid}", subject=f"Nurse follow-up for {p['full_name']}",
                                body=f"Our nurse team is calling {p['full_name']} within 15 minutes after their check-in.",
                                sms=f"Our nurse team is calling {p['full_name']} within 15 minutes.")
            from . import outbound
            outbound.queue_caregiver_call(c, p, f"Our nurse team is calling {p['full_name']} within 15 minutes after their check-in. "
                                                "If it is an emergency, please call 108.", f"alert{aid}")
        return aid
    if conn is not None:
        aid = _do(conn)
    else:
        with db.engine.begin() as c:
            aid = _do(c)
    return ok("I've flagged this to our nurse team; a nurse will call you within 15 minutes. If you feel much worse, call 108 or come to "
              "our emergency entrance straight away.", alert_id=f"ALT-{10000 + aid}", callback_sla_minutes=15)


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
        return ok("Thank you. Because of your answers, a nurse will call you within 15 minutes. If you feel much worse, call 108.",
                  checkin_id=f"CI-{10000 + cid}", alert_raised=True)
    return ok("Thank you, that's good to hear. Keep following your doctor's advice. Your visit includes a free follow-up review "
              "within 7 days if you'd like one.", checkin_id=f"CI-{10000 + cid}", alert_raised=False)


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
    msg = ("Thank you for the feedback." if r >= 4 else
           "I'm sorry your visit wasn't better, and thank you for telling us. Our patient care team will look into it.")
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
        until = ap.free_review_until(c, p["id"], doc["id"], nxt[0]) if nxt else None
    if not nxt:
        return ok(f"{doc['name']} has no free slots in the next {days} days. I can add you to the waitlist.", doctor=doc["name"])
    d, _, slots = nxt
    free = f" This review is free if it is on or before {human_date(until)}." if until else ""
    return ok(f"For your follow-up, {doc['name']} is free on {human_date(d)} at {', '.join(human_time(t) for t in slots[:3])}.{free} "
              "Which time should I book?", doctor=doc["name"], date_iso=d.isoformat(), free_slots=[human_time(t) for t in slots[:3]],
              free_review=bool(until))
