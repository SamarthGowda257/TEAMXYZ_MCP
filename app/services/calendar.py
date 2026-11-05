"""Calendar for every patient event: doctor visits, scans, medicine deliveries, refill alarms, free-review expiry.

Each event is one `calendar_events` row keyed by a reference (booking ID, order ID, ...). Three ways it reaches
the patient (and a caregiver who consented: operational events only, never results):
  1. Google Calendar API (when the hospital Google account is connected): a real event on the hospital calendar
     with the patient and caregiver as guests; Google sends them the invite and keeps it in sync, including
     reschedules (same event moved) and cancellations (removed from their calendar).
  2. An RFC 5545 invite.ics attached to the confirmation email when Google is not connected (Gmail, Apple and
     Outlook all add it to the calendar). Times carry the Asia/Kolkata zone so nobody's calendar shifts 5.5 hours.
  3. A one-click "Add to Google Calendar" link in messages and on the website.
Google calls run in the outbox worker, so no tool waits on them.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import insert, select, update

from .. import config, db, google, notify

log = logging.getLogger("wellnest.calendar")
CE = db.calendar_events
TZ = "Asia/Kolkata"
HOSPITAL_ADDRESS = "WellNest Hospitals, 42 Outer Ring Road, Marathahalli, Bengaluru 560037"


def attendees_for(patient: dict, caregiver: bool = True) -> list[str]:
    out = []
    if patient.get("email") and not patient["email"].lower().endswith(notify.FAKE_DOMAINS):
        out.append(patient["email"].strip().lower())
    cg = (patient.get("caregiver_email") or "").strip().lower()
    if caregiver and patient.get("caregiver_consent") and cg and not cg.endswith(notify.FAKE_DOMAINS) and cg not in out:
        out.append(cg)
    return out


def upsert(conn, *, ref: str, patient: dict, kind: str, title: str, starts_at: datetime, minutes: int = 30,
           location: str = HOSPITAL_ADDRESS, details: str = "", all_day: bool = False, caregiver: bool = True) -> dict:
    """Create or move the event for `ref` inside the caller's transaction, then queue the Google sync."""
    vals = dict(patient_id=patient.get("id"), kind=kind, title=title[:160], starts_at=starts_at, minutes=minutes,
                all_day=all_day, details=details, location=(location or HOSPITAL_ADDRESS)[:200],
                attendees=attendees_for(patient, caregiver), status="active", updated_at=config.now())
    row = conn.execute(select(CE).where(CE.c.ref == ref)).mappings().first()
    if row:
        seq = row["sequence"] + 1
        conn.execute(update(CE).where(CE.c.id == row["id"]).values(sequence=seq, sync_status="pending", sync_error=None, **vals))
    else:
        seq = 0
        conn.execute(insert(CE).values(ref=ref, sequence=0, sync_status="pending", created_at=config.now(), **vals))
    _queue_sync(conn, ref, seq)
    return dict(vals, ref=ref, sequence=seq)


def cancel(conn, ref: str) -> None:
    row = conn.execute(select(CE).where(CE.c.ref == ref)).mappings().first()
    if not row or row["status"] == "cancelled":
        return
    conn.execute(update(CE).where(CE.c.id == row["id"]).values(status="cancelled", sequence=row["sequence"] + 1,
                                                               sync_status="pending", updated_at=config.now()))
    _queue_sync(conn, ref, row["sequence"] + 1)


def _queue_sync(conn, ref: str, seq: int) -> None:
    if google.configured():
        notify.queue(conn, patient_id=None, channel="calendar", template="gcal_sync", to=ref,
                     dedupe_key=f"gcal:{ref}:{seq}"[:80])
    else:
        conn.execute(update(CE).where(CE.c.ref == ref).values(sync_status="ics_only"))


def get(conn, ref: str) -> dict | None:
    r = conn.execute(select(CE).where(CE.c.ref == ref)).mappings().first()
    return dict(r) if r else None


# ------------------------------------------------------------------ Google Calendar sync (outbox worker)
def _google_body(e: dict) -> dict:
    if e["all_day"]:
        d = e["starts_at"].date()
        when = {"start": {"date": d.isoformat()}, "end": {"date": (d + timedelta(days=1)).isoformat()}}
        reminders = [{"method": "popup", "minutes": 15 * 60}]                 # 9 AM the day before
    else:
        end = e["starts_at"] + timedelta(minutes=e["minutes"] or 30)
        when = {"start": {"dateTime": e["starts_at"].isoformat(), "timeZone": TZ},
                "end": {"dateTime": end.isoformat(), "timeZone": TZ}}
        reminders = ([{"method": "popup", "minutes": 24 * 60}, {"method": "popup", "minutes": 120}]
                     if e["kind"] == "appointment" else [{"method": "popup", "minutes": 30}])
    return {"summary": e["title"], "description": e["details"] or "", "location": e["location"] or "",
            "attendees": [{"email": a} for a in (e["attendees"] or [])], "guestsCanModify": False,
            "guestsCanInviteOthers": False, "reminders": {"useDefault": False, "overrides": reminders},
            "source": {"title": "WellNest Hospitals", "url": config.PUBLIC_BASE_URL}, **when}


def sync(ref: str) -> tuple[str, str | None]:
    """Push one event's latest state to Google Calendar. Returns (notification status, error)."""
    with db.engine.connect() as c:
        e = get(c, ref)
    if not e:
        return "sent", None
    try:
        if e["status"] == "cancelled":
            if e["google_event_id"]:
                google.delete_event(e["google_event_id"])
            gid = e["google_event_id"]
        else:
            gid = google.upsert_event(_google_body(e), e["google_event_id"] or "")
        with db.engine.begin() as c:
            c.execute(update(CE).where(CE.c.ref == ref).values(google_event_id=gid, sync_status="synced", sync_error=None))
        return "sent", None
    except Exception as ex:
        with db.engine.begin() as c:
            c.execute(update(CE).where(CE.c.ref == ref).values(sync_status="failed", sync_error=str(ex)[:300]))
        return "failed", str(ex)[:280]


# ------------------------------------------------------------------ .ics invite and Google link
def _esc(t: str) -> str:
    return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets continue on the next line after a space."""
    out, b = [], line.encode("utf-8")
    while len(b) > 75:
        cut = 75
        while (b[cut] & 0xC0) == 0x80:                 # don't split a multi-byte character
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b" " + b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def ics(e: dict, organizer: str | None = None) -> str:
    """invite.ics for one event (METHOD:REQUEST, or METHOD:CANCEL once cancelled)."""
    cancelled = e.get("status") == "cancelled"
    org = organizer or config.EMAIL_FROM_ADDRESS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if e["all_day"]:
        d = e["starts_at"].date()
        when = [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
        alarms = [("-PT15H", f"Today: {e['title']}")]
    else:
        end = e["starts_at"] + timedelta(minutes=e["minutes"] or 30)
        when = [f"DTSTART;TZID={TZ}:{e['starts_at']:%Y%m%dT%H%M%S}", f"DTEND;TZID={TZ}:{end:%Y%m%dT%H%M%S}"]
        alarms = ([("-PT24H", f"Tomorrow: {e['title']}"), ("-PT2H", "Leave in time: report 15 minutes early for vitals.")]
                  if e["kind"] == "appointment" else [("-PT30M", e["title"])])
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//WellNest Hospitals//Patient Schedule 2.0//EN", "CALSCALE:GREGORIAN",
             f"METHOD:{'CANCEL' if cancelled else 'REQUEST'}",
             "BEGIN:VTIMEZONE", f"TZID:{TZ}", "BEGIN:STANDARD", "DTSTART:19700101T000000", "TZOFFSETFROM:+0530",
             "TZOFFSETTO:+0530", "TZNAME:IST", "END:STANDARD", "END:VTIMEZONE",
             "BEGIN:VEVENT", f"UID:{e['ref']}@wellnest-hospitals", f"SEQUENCE:{e.get('sequence') or 0}", f"DTSTAMP:{stamp}",
             *when, f"SUMMARY:{_esc(e['title'])}", f"DESCRIPTION:{_esc(e.get('details') or '')}",
             f"LOCATION:{_esc(e.get('location') or HOSPITAL_ADDRESS)}", f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
             f"ORGANIZER;CN=WellNest Hospitals:mailto:{org}"]
    for a in e.get("attendees") or []:
        lines.append(f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=FALSE:mailto:{a}")
    if not cancelled:
        for trig, text in alarms:
            lines += ["BEGIN:VALARM", f"TRIGGER:{trig}", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(text)}", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def google_link(e: dict) -> str:
    """Mode B: opens Google Calendar with the event pre-filled (times in UTC)."""
    if e["all_day"]:
        d = e["starts_at"].date()
        dates = f"{d:%Y%m%d}/{d + timedelta(days=1):%Y%m%d}"
    else:
        start = e["starts_at"] - timedelta(hours=5, minutes=30)
        end = start + timedelta(minutes=e["minutes"] or 30)
        dates = f"{start:%Y%m%dT%H%M%SZ}/{end:%Y%m%dT%H%M%SZ}"
    q = {"action": "TEMPLATE", "text": e["title"], "dates": dates, "details": (e.get("details") or "")[:900],
         "location": e.get("location") or HOSPITAL_ADDRESS, "ctz": TZ}
    return "https://calendar.google.com/calendar/render?" + urlencode(q)


def invite_attachment(e: dict) -> list[tuple[str, str, str]]:
    """Attach invite.ics only when Google is not connected; otherwise Google already sent the invite and a second
    one would put the visit on the patient's calendar twice."""
    if google.configured():
        return []
    return [("invite.ics", "text/calendar; method=" + ("CANCEL" if e.get("status") == "cancelled" else "REQUEST"), ics(e))]


def describe_status() -> dict:
    with db.engine.connect() as c:
        rows = c.execute(select(CE.c.sync_status, CE.c.sync_error)).all()
    counts: dict = {}
    for s, _ in rows:
        counts[s] = counts.get(s, 0) + 1
    last_err = next((e for s, e in reversed(rows) if s == "failed" and e), None)
    return {"google_connected": google.configured(), "calendar_id": config.GOOGLE_CALENDAR_ID, "events": counts,
            "last_error": last_err}


def to_json(e: dict) -> str:
    return json.dumps(e, default=str)
