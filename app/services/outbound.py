"""Autonomous outbound calls: the backend decides who to call and when, Talkdesk places the call.

  plan()        every minute (jobs runner): finds due events per call kind and queues one call per event
                (dedupe_key is unique, so a reminder can never be queued twice)
  dispatch()    starts due calls through the Talkdesk Flows API (or records them as simulated without credentials),
                within calling hours, a few per run, with retries for no answer / busy / failed
  handle_event  the Studio flow reports back (answered, keypress or spoken choice, no answer...); we act on it
                (confirm, reschedule link, nurse alert, opt-out...) and return the next sentence for the flow to say
  context_for / record_outcome / confirm   used by the Outreach agent's MCP tools when the patient asks to talk
                to the AI assistant, so the conversation continues with full context

A call kind is a small object: who is due, what to say, what each answer means. New kinds (lab report ready,
bill due, vaccination due...) are added to KINDS without touching the dispatcher, the flow or the webhook.
"""

import contextlib
import logging
import re
import time as _time
from datetime import datetime, timedelta

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .. import config, db, notify, talkdesk
from ..util import Result, clean, fail, human_date, human_time, mask_phone, norm_code, norm_phone, ok, parse_date
from . import patients as pt
from .ref import REF

log = logging.getLogger("wellnest")
OC, A, P = db.outbound_calls, db.appointments, db.patients
OPEN = ("scheduled", "retry")
_nullctx = contextlib.nullcontext
FINAL = ("completed", "failed", "cancelled", "simulated")


def _who(a) -> str:
    if a["doctor_id"]:
        return REF.doctors[a["doctor_id"]]["name"]
    return REF.procedures[a["procedure_id"]]["name"] if a["procedure_id"] else "your doctor"


def _start(a) -> datetime:
    hh, mm = (int(x) for x in a["appt_time"].split(":"))
    return datetime.combine(a["appt_date"], datetime.min.time()).replace(hour=hh, minute=mm)


def _log(c, patient_id, action, ref, summary, ok_=True):
    pt.log(c, patient_id, action, ref, ok_, summary, actor="system", channel="voice")


# ------------------------------------------------------------------ call kinds
class CallKind:
    name = ""
    label = ""
    options: dict[str, str] = {}
    outside: tuple = ()          # outcomes handled by another service after our transaction commits

    def due(self, c, now: datetime) -> list[dict]:
        """[{patient_id, appointment_id, due_at, dedupe_key}] for events that need a call."""
        return []

    def prompt(self, c, p: dict, a: dict | None, ref: str = "") -> str:
        return ""

    def topic(self, c, p: dict, a: dict | None, ref: str = "") -> tuple[str, str]:
        """(what we called about, what to ask) for the AI assistant."""
        return "your recent visit", "How can I help?"

    def act(self, c, call: dict, p: dict, a: dict | None, outcome: str) -> str:
        """Do what the patient's answer means; return what the flow says next."""
        return "Thank you. Goodbye."

    def act_outside(self, call: dict, p: dict, outcome: str, ref: str) -> str:
        return "Thank you. Goodbye."


def _ref(call: dict) -> str:
    """The subject a call is about, kept in its dedupe key: offer:<code>, report:<code>."""
    parts = call["dedupe_key"].split(":")
    return parts[1] if parts[0] in ("offer", "report") else ""


class AppointmentReminder(CallKind):
    name, label = "appointment_reminder", "Appointment reminder"
    options = {"1": "confirmed", "2": "reschedule_requested", "3": "transfer_to_ai", "9": "opted_out"}

    def due(self, c, now):
        rows = c.execute(select(A).where(A.c.status == "booked", A.c.appt_date >= now.date(),
                                         A.c.appt_date <= (now + timedelta(days=2)).date())).mappings().all()
        out = []
        for a in rows:
            start = _start(a)
            if now + timedelta(hours=2) <= start <= now + timedelta(hours=26):      # the day-before reminder window
                out.append({"patient_id": a["patient_id"], "appointment_id": a["id"],
                            "due_at": max(now, start - timedelta(hours=24)), "dedupe_key": f"remind:{a['booking_code']}"})
        return out

    def topic(self, c, p, a, ref=""):
        return (f"your appointment with {_who(a)} on {human_date(a['appt_date'])} at {human_time(a['appt_time'])}, "
                f"booking ID {a['booking_code']}", "Would you like to confirm it, or change the time?")

    def prompt(self, c, p, a, ref=""):
        first = p["full_name"].split()[0]
        return (f"Hello {first}, this is WellNest Hospitals with a reminder. You have an appointment with {_who(a)} on "
                f"{human_date(a['appt_date'])} at {human_time(a['appt_time'])}. To confirm, press 1 or say confirm. "
                "To change it, press 2 or say change. To talk to our assistant, press 3. "
                "To stop reminder calls, press 9.")

    def act(self, c, call, p, a, outcome):
        when = f"{_who(a)} on {human_date(a['appt_date'])} at {human_time(a['appt_time'])}" if a else "your appointment"
        if outcome == "confirmed":
            _log(c, p["id"], "confirm_appointment", a["booking_code"] if a else call["call_code"], f"Confirmed by phone: {when}")
            return f"Thank you, your appointment with {when} is confirmed. Please come 15 minutes early. Goodbye."
        if outcome == "reschedule_requested":
            link = f"{config.PUBLIC_BASE_URL}/portal/appointments"
            notify.queue(c, patient_id=p["id"], channel="sms", template="reschedule_link", to=p["phone"],
                         body=f"WellNest: to change your appointment with {when}, open {link} or reply on chat. "
                              "We will also call you back.", dedupe_key=f"reschedule_link:{call['call_code']}")
            c.execute(insert(db.callbacks).values(callback_code=pt.random_code("CB"), patient_id=p["id"], phone=p["phone"],
                                                  preferred_time="today", reason=f"Reschedule {a['booking_code'] if a else ''}",
                                                  status="queued", created_at=config.now()))
            _log(c, p["id"], "reschedule_requested", a["booking_code"] if a else call["call_code"], f"Asked to change {when}")
            return ("No problem. We have sent you a text with a link to pick a new time, and our team will call you back today. "
                    "Goodbye.")
        return "Thank you. Goodbye."


class PostVisitFollowup(CallKind):
    name, label = "post_visit_followup", "Post-visit follow-up"
    options = {"1": "feeling_well", "2": "needs_help", "3": "transfer_to_ai", "9": "opted_out"}

    def due(self, c, now):
        rows = c.execute(select(A).where(A.c.status == "completed", A.c.doctor_id.is_not(None),
                                         A.c.appt_date >= (now - timedelta(days=2)).date(),
                                         A.c.appt_date < now.date())).mappings().all()
        return [{"patient_id": a["patient_id"], "appointment_id": a["id"],
                 "due_at": max(now, _start(a) + timedelta(hours=20)), "dedupe_key": f"followup:{a['booking_code']}"}
                for a in rows]

    def topic(self, c, p, a, ref=""):
        return (f"how you are after your visit with {_who(a)} on {human_date(a['appt_date'])}",
                "How are you feeling since the visit? Are you better, or is something worrying you?")

    def prompt(self, c, p, a, ref=""):
        first = p["full_name"].split()[0]
        return (f"Hello {first}, this is WellNest Hospitals checking on you after your visit with {_who(a)} on "
                f"{human_date(a['appt_date'])}. If you are feeling better, press 1 or say better. If you have any problem "
                "or feel worse, press 2 or say help, and a nurse will call you. To talk to our assistant, press 3. "
                "To stop these calls, press 9.")

    def act(self, c, call, p, a, outcome):
        if outcome == "feeling_well":
            c.execute(insert(db.checkins).values(patient_id=p["id"], appointment_id=a["id"] if a else None, fever=False,
                                                 symptoms_worse=False, notes="Phone follow-up: feeling better",
                                                 alert_raised=False, created_at=config.now()))
            _log(c, p["id"], "record_checkin", call["call_code"], "Phone follow-up: feeling better")
            return "We are glad you are feeling better. Take care, and goodbye."
        if outcome == "needs_help":
            from . import support
            c.execute(insert(db.checkins).values(patient_id=p["id"], appointment_id=a["id"] if a else None,
                                                 symptoms_worse=True, notes="Phone follow-up: asked for help",
                                                 alert_raised=True, created_at=config.now()))
            support.flag_nurse_alert(p["phone"], f"Follow-up call after visit with {_who(a) if a else 'doctor'}: "
                                                 "patient reports a problem", patient=p, conn=c)
            return ("A nurse will call you shortly. If it is an emergency, please hang up and call 108 now. Goodbye.")
        return "Thank you. Goodbye."


class WaitlistOfferCall(CallKind):
    name, label = "waitlist_offer", "Waitlist slot offer"
    options = {"1": "offer_accepted", "2": "offer_declined", "3": "transfer_to_ai", "9": "opted_out"}
    outside = ("offer_accepted",)

    def due(self, c, now):
        WO, WL = db.waitlist_offers, db.waitlist
        rows = c.execute(select(WO.c.offer_code, WL.c.patient_id).join(WL, WL.c.id == WO.c.waitlist_id)
                         .where(WO.c.status == "open", WO.c.expires_at > now + timedelta(minutes=5),
                                WO.c.created_at >= now - timedelta(minutes=30))).all()
        return [{"patient_id": r.patient_id, "appointment_id": None, "due_at": now, "dedupe_key": f"offer:{r.offer_code}"}
                for r in rows]

    def _offer(self, c, ref):
        WO = db.waitlist_offers
        return c.execute(select(WO).where(WO.c.offer_code == ref)).mappings().first()

    def topic(self, c, p, a, ref=""):
        o = self._offer(c, ref)
        if not o:
            return "a waitlist slot", "Would you like me to check other free slots?"
        return (f"a waitlist slot with {REF.doctors[o['doctor_id']]['name']} on {human_date(o['appt_date'])} at "
                f"{human_time(o['appt_time'])}, offer code {ref}", "Would you like to take it?")

    def prompt(self, c, p, a, ref=""):
        o = self._offer(c, ref)
        mins = max(1, int((o["expires_at"] - config.now()).total_seconds() // 60)) if o else 0
        first = p["full_name"].split()[0]
        return (f"Hello {first}, good news from WellNest Hospitals. A slot with {REF.doctors[o['doctor_id']]['name']} on "
                f"{human_date(o['appt_date'])} at {human_time(o['appt_time'])} has opened from the waitlist and is held for you "
                f"for {mins} minutes. To book it, press 1 or say book. If you don't want it, press 2. To talk to our "
                "assistant, press 3. To stop these calls, press 9.") if o else ""

    def act(self, c, call, p, a, outcome):
        if outcome == "offer_declined":
            _log(c, p["id"], "waitlist_offer_declined", _ref(call), "Declined the offered slot by phone")
            return "No problem. You stay on the waitlist and we will let you know about other slots. Goodbye."
        return "Thank you. Goodbye."

    def act_outside(self, call, p, outcome, ref):
        from . import appointments as ap
        r = ap.accept_offer(ref, p["phone"], channel="voice", actor="system")
        return r.message + " Goodbye."


class LabReportReady(CallKind):
    name, label = "lab_report_ready", "Lab report ready"
    options = {"1": "report_emailed", "3": "transfer_to_ai", "9": "opted_out"}
    outside = ("report_emailed",)

    def due(self, c, now):
        LR = db.lab_reports
        rows = c.execute(select(LR.c.report_code, LR.c.patient_id).where(
            LR.c.status == "ready", LR.c.ready_at >= now - timedelta(hours=48), LR.c.ready_at <= now)).all()
        return [{"patient_id": r.patient_id, "appointment_id": None, "due_at": now, "dedupe_key": f"report:{r.report_code}"}
                for r in rows]

    def _test(self, c, ref):
        r = c.execute(select(db.lab_reports.c.test_name).where(db.lab_reports.c.report_code == ref)).first()
        return r[0] if r else "lab"

    def topic(self, c, p, a, ref=""):
        return f"your {self._test(c, ref)} report, which is ready", "Would you like a secure link to it by email?"

    def prompt(self, c, p, a, ref=""):
        first = p["full_name"].split()[0]
        return (f"Hello {first}, this is WellNest Hospitals. Your {self._test(c, ref)} report is ready. We never read results "
                "over the phone. To get a secure link by email, press 1 or say email. To talk to our assistant, press 3. "
                "To stop these calls, press 9.")

    def act_outside(self, call, p, outcome, ref):
        from . import records
        r = records.email_report("", "", ref, patient_id=p["id"], actor="system", channel="voice")
        return r.message + " Goodbye."


KINDS: dict[str, CallKind] = {k.name: k for k in (AppointmentReminder(), PostVisitFollowup(), WaitlistOfferCall(),
                                                  LabReportReady())}
SPOKEN = {"confirm": "1", "yes": "1", "book": "1", "email": "1", "better": "1", "fine": "1", "good": "1",
          "change": "2", "reschedule": "2", "help": "2", "worse": "2", "problem": "2", "decline": "2",
          "assistant": "3", "agent": "3", "talk": "3", "stop": "9"}


# ------------------------------------------------------------------ guards
def _allowed(phone: str) -> bool:
    return "*" in config.OUTBOUND_ALLOWLIST or phone in config.OUTBOUND_ALLOWLIST


def _opted_out(c, phone: str) -> bool:
    return c.execute(select(db.call_optouts.c.phone).where(db.call_optouts.c.phone == phone)).first() is not None


def _in_hours(now: datetime) -> bool:
    start, end = config.OUTBOUND_CALL_HOURS
    return start <= now.hour < end


def _next_open(now: datetime) -> datetime:
    start, end = config.OUTBOUND_CALL_HOURS
    if now.hour < start:
        return now.replace(hour=start, minute=0, second=0, microsecond=0)
    return (now + timedelta(days=1)).replace(hour=start, minute=0, second=0, microsecond=0)


def mode() -> str:
    return "talkdesk" if talkdesk.configured() else "simulated"


# ------------------------------------------------------------------ planning and dispatch (jobs runner)
def _queue(c, kind: str, item: dict, p: dict) -> dict | None:
    if c.execute(select(OC.c.id).where(OC.c.dedupe_key == item["dedupe_key"][:80])).first():
        return None                                        # already queued once: never call twice for one event
    try:
        with (c.begin_nested() if db.IS_POSTGRES else _nullctx()):     # the unique key is the final guard
            cid = c.execute(insert(OC).values(
                call_code=_new_code(c), kind=kind, patient_id=p["id"], appointment_id=item.get("appointment_id"),
                to_number=config.OUTBOUND_TEST_NUMBER or p["phone"], dedupe_key=item["dedupe_key"][:80], status="scheduled",
                due_at=item["due_at"], next_attempt_at=item["due_at"], attempts=0, created_at=config.now(),
                updated_at=config.now())).inserted_primary_key[0]
    except IntegrityError:
        return None
    return dict(c.execute(select(OC).where(OC.c.id == cid)).mappings().first())


def _new_code(c) -> str:
    while True:
        code = pt.random_code("OC", 6)
        if not c.execute(select(OC.c.id).where(OC.c.call_code == code)).first():
            return code


def plan() -> int:
    """Queue a call for every due event of every kind (allow-listed, not opted out). Idempotent."""
    now, n = config.now(), 0
    with db.engine.begin() as c:
        have = {r[0] for r in c.execute(select(OC.c.dedupe_key))}
        for kind in KINDS.values():
            for item in kind.due(c, now):
                if item["dedupe_key"] in have:
                    continue
                p = pt.get_by_id(c, item["patient_id"])
                if not p or p.get("is_guest") or not _allowed(p["phone"]) or _opted_out(c, p["phone"]):
                    continue
                if _queue(c, kind.name, item, p):
                    have.add(item["dedupe_key"])
                    n += 1
    return n


def _fail_attempt(c, call: dict, event: str, error: str = "") -> None:
    if call["attempts"] < config.OUTBOUND_MAX_ATTEMPTS:
        nxt = config.now() + timedelta(minutes=config.OUTBOUND_RETRY_MIN)
        c.execute(update(OC).where(OC.c.id == call["id"]).values(status="retry", last_event=event, error=error[:300] or None,
                                                                 next_attempt_at=nxt, updated_at=config.now()))
    else:
        c.execute(update(OC).where(OC.c.id == call["id"]).values(status="failed", last_event=event, outcome="unreachable",
                                                                 error=error[:300] or None, completed_at=config.now(),
                                                                 updated_at=config.now()))
        _log(c, call["patient_id"], "outbound_call", call["call_code"], f"{KINDS[call['kind']].label}: unreachable", False)


def _dial(call_id: int) -> dict:
    """Claim one due call and start it. The claim is atomic, so overlapping job runs never dial twice."""
    with db.engine.begin() as c:
        claimed = c.execute(update(OC).where(OC.c.id == call_id, OC.c.status.in_(OPEN))
                            .values(status="dialing", attempts=OC.c.attempts + 1, updated_at=config.now())).rowcount
        if not claimed:
            return {"call_id": call_id, "skipped": "already taken"}
        call = dict(c.execute(select(OC).where(OC.c.id == call_id)).mappings().first())
        p = pt.get_by_id(c, call["patient_id"])
        a = c.execute(select(A).where(A.c.id == call["appointment_id"])).mappings().first() if call["appointment_id"] else None
        kind = KINDS[call["kind"]]
        if _opted_out(c, p["phone"]) or (a is not None and call["kind"] == "appointment_reminder" and a["status"] != "booked"):
            c.execute(update(OC).where(OC.c.id == call_id).values(status="cancelled", outcome="not_needed",
                                                                  completed_at=config.now(), updated_at=config.now()))
            return {"call_id": call["call_code"], "status": "cancelled"}
        prompt = kind.prompt(c, p, a, _ref(call))
        if not prompt:                                     # the offer or report is gone: nothing to say
            c.execute(update(OC).where(OC.c.id == call_id).values(status="cancelled", outcome="not_needed",
                                                                  completed_at=config.now(), updated_at=config.now()))
            return {"call_id": call["call_code"], "status": "cancelled"}
        c.execute(update(OC).where(OC.c.id == call_id).values(prompt=prompt))
    inputs = {"call_id": call["call_code"], "patient_phone": call["to_number"], "patient_name": p["full_name"].split()[0],
              "call_type": call["kind"], "prompt": prompt, "booking_id": a["booking_code"] if a else "",
              "callback_url": f"{config.PUBLIC_BASE_URL}/api/outbound/event"}
    with db.engine.begin() as c:
        if mode() == "simulated":
            notify.queue(c, patient_id=p["id"], channel="voice_call", template=call["kind"], to=call["to_number"], body=prompt,
                         dedupe_key=f"{call['call_code']}:{call['attempts']}")
            c.execute(update(OC).where(OC.c.id == call_id).values(status="simulated", last_event="simulated",
                                                                  updated_at=config.now()))
            _log(c, p["id"], "outbound_call", call["call_code"], f"{kind.label} call (simulated, no Talkdesk credentials)")
            return {"call_id": call["call_code"], "status": "simulated"}
    try:
        interaction = talkdesk.start_flow(inputs)
    except Exception as e:
        with db.engine.begin() as c:
            _fail_attempt(c, call, "start_failed", str(e))
        log.warning("outbound %s failed to start: %s", call["call_code"], e)
        return {"call_id": call["call_code"], "status": "start_failed", "error": str(e)[:200]}
    with db.engine.begin() as c:
        c.execute(update(OC).where(OC.c.id == call_id).values(interaction_id=interaction, last_event="dialing",
                                                              updated_at=config.now()))
        _log(c, p["id"], "outbound_call", call["call_code"], f"{kind.label} call started to {mask_phone(call['to_number'])}")
    return {"call_id": call["call_code"], "status": "dialing", "interaction_id": interaction}


def dispatch() -> list[dict]:
    """Start due calls (a few per run, paced under Talkdesk's 2 requests per second); time out silent calls."""
    now = config.now()
    with db.engine.begin() as c:
        # a call with no word from the flow for 10 minutes counts as not answered
        for s in c.execute(select(OC).where(OC.c.status == "dialing", OC.c.updated_at < now - timedelta(minutes=10))).mappings().all():
            _fail_attempt(c, dict(s), "no_report")
        if not _in_hours(now):
            c.execute(update(OC).where(OC.c.status.in_(OPEN), OC.c.next_attempt_at <= now)
                      .values(next_attempt_at=_next_open(now)))
            return []
        due = [r[0] for r in c.execute(select(OC.c.id).where(OC.c.status.in_(OPEN), OC.c.next_attempt_at <= now)
                                       .order_by(OC.c.next_attempt_at).limit(config.OUTBOUND_MAX_PER_RUN))]
    out = []
    for i, cid in enumerate(due):
        if i and mode() == "talkdesk":
            _time.sleep(0.6)
        out.append(_dial(cid))
    return out


def run() -> dict:
    planned = plan()
    started = dispatch()
    return {"calls_planned": planned, "calls_started": len([s for s in started if s.get("status") in ("dialing", "simulated")]),
            "call_mode": mode()}


def trigger(booking_id: str, kind: str = "appointment_reminder") -> dict:
    """Staff / demo: queue a call for one booking now and start it (same path as the scheduler)."""
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown kind {kind}"}
    with db.engine.begin() as c:
        a = c.execute(select(A).where(A.c.booking_code == norm_code(booking_id, "WN"))).mappings().first()
        if not a:
            return {"ok": False, "error": "booking not found"}
        p = pt.get_by_id(c, a["patient_id"])
        if _opted_out(c, p["phone"]):
            return {"ok": False, "error": "patient opted out of calls"}
        open_call = c.execute(select(OC.c.id).where(OC.c.appointment_id == a["id"], OC.c.kind == kind,
                                                    OC.c.status.in_(OPEN + ("dialing", "in_progress")))).first()
        call = None if open_call else _queue(c, kind, {"appointment_id": a["id"], "due_at": config.now(),
                                                       "dedupe_key": f"manual:{kind}:{a['booking_code']}:{_time.time_ns()}"}, p)
    if open_call or not call:
        return {"ok": False, "error": "a call for this booking is already in progress"}
    return {"ok": True, **_dial(call["id"])}


# ------------------------------------------------------------------ events from the Studio flow
def handle_event(call_code: str, event: str, choice: str = "") -> dict:
    """event: answered | choice | no_answer | busy | invalid_number | failed | completed.
    Returns {"say": next sentence, "action": "end" | "transfer" | "repeat", "outcome"}."""
    code = norm_code(call_code, "OC")
    ev = clean(event).lower().replace(" ", "_")
    with db.engine.begin() as c:
        row = c.execute(select(OC).where(OC.c.call_code == code)).mappings().first() if code else None
        if not row:
            return {"ok": False, "say": "Thank you. Goodbye.", "action": "end", "error": "unknown call_id"}
        call = dict(row)
        p = pt.get_by_id(c, call["patient_id"])
        a = c.execute(select(A).where(A.c.id == call["appointment_id"])).mappings().first() if call["appointment_id"] else None
        kind = KINDS[call["kind"]]
        if ev in ("no_answer", "busy", "invalid_number", "failed"):
            if ev == "invalid_number":
                call["attempts"] = config.OUTBOUND_MAX_ATTEMPTS
            _fail_attempt(c, call, ev)
            return {"ok": True, "say": "", "action": "end", "status": "retry" if call["attempts"] < config.OUTBOUND_MAX_ATTEMPTS else "failed"}
        if ev == "answered":
            c.execute(update(OC).where(OC.c.id == call["id"]).values(status="in_progress", last_event="answered", updated_at=config.now()))
            return {"ok": True, "say": call["prompt"] or kind.prompt(c, p, a, _ref(call)), "action": "ask"}
        if ev == "completed":
            if call["status"] not in FINAL:
                c.execute(update(OC).where(OC.c.id == call["id"]).values(status="completed", last_event="completed",
                                                                         outcome=call["outcome"] or "no_response",
                                                                         completed_at=config.now(), updated_at=config.now()))
            return {"ok": True, "say": "", "action": "end"}
        # a keypress or a spoken word
        raw = clean(choice).lower()
        digit = raw if raw in kind.options else next((d for w, d in SPOKEN.items() if w in raw), "")
        outcome = kind.options.get(digit)
        if not outcome:
            return {"ok": True, "say": "Sorry, I didn't get that. " + (call["prompt"] or kind.prompt(c, p, a, _ref(call))), "action": "repeat"}
        if outcome == "opted_out":
            if not _opted_out(c, p["phone"]):
                c.execute(insert(db.call_optouts).values(phone=p["phone"], reason=f"Pressed 9 on {call['call_code']}",
                                                         created_at=config.now()))
            _log(c, p["id"], "call_opt_out", call["call_code"], "Asked not to receive calls")
            say, action = "Done. You will not receive these calls from us again. Goodbye.", "end"
        elif outcome == "transfer_to_ai":
            _log(c, p["id"], "outbound_transfer", call["call_code"], f"{kind.label}: connected to the AI assistant")
            say, action = "Connecting you to our assistant now. Please hold.", "transfer"
        elif outcome in kind.outside:
            say, action = None, "end"                      # done by another service once this transaction commits
        else:
            say, action = kind.act(c, call, p, a, outcome), "end"
        c.execute(update(OC).where(OC.c.id == call["id"]).values(
            status="in_progress" if action == "transfer" else "completed", outcome=outcome, last_event=f"choice:{digit}",
            summary=f"Patient chose {digit} ({outcome.replace('_', ' ')}).",
            completed_at=None if action == "transfer" else config.now(), updated_at=config.now()))
    if say is None:
        say = kind.act_outside(call, p, outcome, _ref(call))
    return {"ok": True, "say": say, "action": action, "outcome": outcome}


# ------------------------------------------------------------------ for the Outreach agent (MCP tools)
def _recent_call(c, p_id: int, call_code: str = "") -> dict | None:
    q = select(OC).where(OC.c.patient_id == p_id, OC.c.created_at >= config.now() - timedelta(hours=48))
    if call_code:
        q = q.where(OC.c.call_code == norm_code(call_code, "OC"))
    r = c.execute(q.order_by(OC.c.id.desc()).limit(1)).mappings().first()
    return dict(r) if r else None


def context_for(phone: str, call_code: str = "") -> Result:
    p_norm = norm_phone(phone)
    with db.engine.connect() as c:
        p = pt.get_by_phone(c, p_norm) if p_norm else None
        if not p and call_code:
            row = c.execute(select(OC).where(OC.c.call_code == norm_code(call_code, "OC"))).mappings().first()
            p = pt.get_by_id(c, row["patient_id"]) if row else None
        call = _recent_call(c, p["id"], call_code) if p else None
        a = c.execute(select(A).where(A.c.id == call["appointment_id"])).mappings().first() if call and call["appointment_id"] else None
        kind = KINDS[call["kind"]] if call else None
        about, ask = kind.topic(c, p, a, _ref(call)) if call else ("", "")
    if not call:
        return fail("not_found", "I don't see a recent call from WellNest to this number. How can I help you today?")
    first = p["full_name"].split()[0]
    msg = f"Hi {first}, we called about {about}. {ask}"
    data = {"call_id": call["call_code"], "call_type": call["kind"], "purpose": kind.label, "patient_first_name": first,
            "booking_id": a["booking_code"] if a else None, "reference": _ref(call) or None,
            "outcome_so_far": call["outcome"], "status": call["status"]}
    return ok(msg, **data)


def confirm(booking_id: str, phone: str, dob: str = "") -> Result:
    """Confirm a booking by phone. Allowed with date of birth, or when we called this patient about this booking."""
    with db.engine.begin() as c:
        a = c.execute(select(A).where(A.c.booking_code == norm_code(booking_id, "WN"))).mappings().first()
        if clean(dob):
            p, err = pt.check_identity(c, phone, dob)
            if err:
                return err
        else:
            p = pt.get_by_phone(c, phone)
        if not a or not p or a["patient_id"] != p["id"]:
            return fail("not_allowed", "That booking isn't under this mobile number, so I can't confirm it.")
        called = c.execute(select(OC.c.id).where(OC.c.appointment_id == a["id"],
                                                 OC.c.created_at >= config.now() - timedelta(hours=48))).first()
        if not clean(dob) and not called:
            return fail("not_verified", pt.ASK_IDENTITY)
        if a["status"] != "booked":
            return fail("not_allowed", f"Booking {a['booking_code']} is {a['status']}, so there is nothing to confirm.")
        _log(c, p["id"], "confirm_appointment", a["booking_code"], f"Confirmed with the AI assistant: {_who(a)}")
        c.execute(update(OC).where(and_(OC.c.appointment_id == a["id"], OC.c.status.in_(("in_progress", "dialing"))))
                  .values(status="completed", outcome="confirmed", summary="Confirmed with the AI assistant.",
                          completed_at=config.now(), updated_at=config.now()))
    return ok(f"Confirmed: {_who(a)} on {human_date(a['appt_date'])} at {human_time(a['appt_time'])}, booking ID "
              f"{a['booking_code']}. Please arrive 15 minutes early.", booking_id=a["booking_code"], confirmed=True)


OUTCOMES = ("confirmed", "reschedule_requested", "rescheduled", "feeling_well", "needs_help", "opted_out", "wrong_person",
            "call_back_later", "question_answered", "no_response")


def _when(text: str) -> datetime:
    """'tomorrow at 5 pm', 'after 6', 'in 2 hours', 'Monday morning' -> a time to call back (default: in 2 hours)."""
    t, now = clean(text).lower(), config.now()
    m = re.search(r"in (\d+) (hour|hr|minute|min)", t)
    if m:
        n = int(m.group(1))
        return now + (timedelta(hours=n) if m.group(2).startswith("h") else timedelta(minutes=n))
    d = now.date() + timedelta(days=1) if "tomorrow" in t else None
    if d is None:
        d = next((x for x in (parse_date(w) for w in t.split()) if x and x >= now.date()), now.date())
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", t)
    if m:
        hh = int(m.group(1)) % 24
        if m.group(3) == "pm" and hh < 12 or (not m.group(3) and 1 <= hh <= 7):
            hh += 12                                       # "after 6" means 6 PM
        hm = (hh, int(m.group(2) or 0))
    else:
        hm = (10, 0) if "morning" in t else (15, 0) if "afternoon" in t else (18, 0) if "evening" in t else None
    if hm is None:
        return now + timedelta(hours=2) if d == now.date() else datetime.combine(d, datetime.min.time()).replace(hour=10)
    when = datetime.combine(d, datetime.min.time()).replace(hour=hm[0], minute=hm[1])
    return when if when > now else when + timedelta(days=1)


def record_outcome(phone: str, outcome: str, summary: str = "", call_code: str = "", call_back_at: str = "") -> Result:
    out = clean(outcome).lower().replace(" ", "_")
    if out not in OUTCOMES:
        return fail("invalid_input", "Outcome must be one of: " + ", ".join(OUTCOMES) + ".")
    with db.engine.begin() as c:
        p = pt.get_by_phone(c, phone)
        call = _recent_call(c, p["id"], call_code) if p else None
        if not call:
            return fail("not_found", "I couldn't find a recent WellNest call to this number to record.")
        if out == "opted_out" and not _opted_out(c, p["phone"]):
            c.execute(insert(db.call_optouts).values(phone=p["phone"], reason=f"Asked the AI on {call['call_code']}",
                                                     created_at=config.now()))
        if out == "needs_help":
            from . import support
            support.flag_nurse_alert(p["phone"], clean(summary)[:250] or "Patient reported a problem on a follow-up call",
                                     patient=p, conn=c)
        c.execute(update(OC).where(OC.c.id == call["id"]).values(status="completed", outcome=out,
                                                                 summary=clean(summary)[:1000] or None,
                                                                 completed_at=config.now(), updated_at=config.now()))
        _log(c, p["id"], "record_call_outcome", call["call_code"], f"{out.replace('_', ' ')}: {clean(summary)[:150]}")
        again = None
        if out == "call_back_later" or clean(call_back_at):
            when = _when(call_back_at)
            again = _queue(c, call["kind"], {"appointment_id": call["appointment_id"], "due_at": when,
                                             "dedupe_key": f"{call['dedupe_key'].split(':')[0]}:{_ref(call) or 'again'}:"
                                                           f"{call['call_code']}:{_time.time_ns()}"}, p)
    if again:
        return ok(f"Okay, we'll call you back on {human_date(again['due_at'].date())} at "
                  f"{human_time(again['due_at'].strftime('%H:%M'))}.", call_id=call["call_code"], outcome=out,
                  call_back_id=again["call_code"])
    say = {"opted_out": "Done, we won't call you again for this.", "needs_help": "I've asked a nurse to call you shortly."}
    return ok(say.get(out, "Thank you, I've noted that."), call_id=call["call_code"], outcome=out)


def recent(limit: int = 30) -> list[dict]:
    with db.engine.connect() as c:
        rows = c.execute(select(OC, P.c.full_name).join(P, P.c.id == OC.c.patient_id)
                         .order_by(func.coalesce(OC.c.updated_at, OC.c.created_at).desc(), OC.c.id.desc()).limit(limit)).mappings().all()
    return [{"call_id": r["call_code"], "kind": r["kind"], "patient": r["full_name"].split()[0], "to": mask_phone(r["to_number"]),
             "status": r["status"], "outcome": r["outcome"], "attempts": r["attempts"], "last_event": r["last_event"],
             "due_at": r["due_at"].strftime("%d %b %H:%M"), "updated": (r["updated_at"] or r["created_at"]).strftime("%d %b %H:%M:%S"),
             "summary": r["summary"]} for r in rows]
