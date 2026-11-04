"""Outbox: every outbound message is a `notifications` row. A background thread sends emails and calendar syncs.

Tools only insert rows (inside their transaction); they never talk to SMTP or Google.
Email goes out through the hospital's Gmail (Gmail API with the connected Google account, or Gmail SMTP with an
app password); with neither configured, emails are marked 'simulated'. Calendar rows push the event to Google
Calendar (services/calendar.py). SMS / WhatsApp / reminder calls are simulated and labelled as such.
Caregivers get operational copies only (bookings, delays, deliveries), never results (DPDP Act 2023).
"""

import logging
import smtplib
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from sqlalchemy import insert, select, update

from . import config, db

log = logging.getLogger("wellnest.notify")
_wake = threading.Event()
FAKE_DOMAINS = ("@example.com", ".test", "@example.org")
SENT_BY_WORKER = ("email", "calendar")


def queue(conn, *, patient_id, channel: str, template: str, to: str | None, subject: str = "", body: str = "",
          dedupe_key: str | None = None, attachments: list[tuple[str, str, str]] | None = None) -> None:
    """Insert an outbox row inside the caller's transaction. attachments: [(filename, mime, text)]."""
    if not to:
        return
    if dedupe_key:
        exists = conn.execute(select(db.notifications.c.id).where(db.notifications.c.dedupe_key == dedupe_key)).first()
        if exists:
            return
    status = "queued" if channel in SENT_BY_WORKER else "simulated"
    if channel == "email" and to.lower().endswith(FAKE_DOMAINS):
        status = "simulated"          # seeded fake patients: never send real mail to invented addresses
    elif channel == "email" and config.DEMO_EMAIL_OVERRIDE:
        body = f"[Demo: originally to {to}]\n\n" + body
        to = config.DEMO_EMAIL_OVERRIDE
    res = conn.execute(db.notifications.insert().values(
        patient_id=patient_id, channel=channel, template=template, to_address=to[:120], subject=subject[:200],
        body=body, status=status, dedupe_key=dedupe_key, created_at=config.now(),
        sent_at=config.now() if status == "simulated" else None))
    for name, mime, content in attachments or []:
        conn.execute(insert(db.notification_files).values(notification_id=res.inserted_primary_key[0], filename=name,
                                                          mime=mime, content=content))
    if status == "queued":
        _wake.set()
    from . import events
    events.publish("notification.queued", channel=channel, template=template, status=status)


def email_and_sms(conn, *, patient: dict, template: str, subject: str, body: str, sms: str, key: str | None = None,
                  attachments: list[tuple[str, str, str]] | None = None):
    queue(conn, patient_id=patient.get("id"), channel="email", template=template, to=patient.get("email"),
          subject=subject, body=body, dedupe_key=f"{key}:email" if key else None, attachments=attachments)
    queue(conn, patient_id=patient.get("id"), channel="sms", template=template, to=patient.get("phone"),
          body=sms, dedupe_key=f"{key}:sms" if key else None)


def to_caregiver(conn, patient: dict, *, template: str, subject: str, body: str, sms: str, key: str | None = None,
                 attachments: list[tuple[str, str, str]] | None = None) -> bool:
    """Operational copy for a caregiver the patient registered and consented to. Returns True if anything was queued."""
    if not patient.get("caregiver_consent"):
        return False
    who = patient.get("caregiver_name") or "there"
    greet = body if body.lower().startswith(("hello", "dear")) else f"Hello {who},\n\n{body}"
    if patient.get("caregiver_email"):
        queue(conn, patient_id=patient.get("id"), channel="email", template=f"{template}_cg"[:30],
              to=patient["caregiver_email"], subject=subject, body=greet + ("" if "WellNest Hospitals" in greet[-40:] else "\n\nWellNest Hospitals"),
              dedupe_key=f"{key}:cg:email"[:80] if key else None, attachments=attachments)
    if patient.get("caregiver_phone"):
        queue(conn, patient_id=patient.get("id"), channel="sms", template=f"{template}_cg"[:30], to=patient["caregiver_phone"],
              body=sms if sms.startswith("WellNest") else "WellNest: " + sms, dedupe_key=f"{key}:cg:sms"[:80] if key else None)
    return bool(patient.get("caregiver_email") or patient.get("caregiver_phone"))


# ------------------------------------------------------------------ sending
def transport() -> str:
    from . import google
    if config.EMAIL_VIA in ("gmail_api", "auto") and google.configured() and config.GOOGLE_SEND_MAIL:
        return "gmail_api"
    if config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD:
        return "smtp"
    return "none"


def _message(row, files) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((config.EMAIL_FROM_NAME, config.EMAIL_FROM_ADDRESS))
    msg["To"] = row["to_address"]
    msg["Subject"] = row["subject"] or "WellNest Hospitals"
    msg["Message-ID"] = make_msgid(domain="wellnest-hospitals")
    msg.set_content(row["body"] or "")
    for f in files:
        sub = f["mime"].split(";")[0].split("/")[1]
        params = dict(p.strip().split("=", 1) for p in f["mime"].split(";")[1:] if "=" in p)
        msg.add_attachment(f["content"], subtype=sub, filename=f["filename"], params=params)
    return msg


def _send_email(row) -> tuple[str, str | None]:
    how = transport()
    if how == "none":
        return "simulated", None
    with db.engine.connect() as c:
        files = c.execute(select(db.notification_files).where(db.notification_files.c.notification_id == row["id"])).mappings().all()
    msg = _message(row, files)
    try:
        if how == "gmail_api":
            from . import google
            google.send_mail(msg.as_bytes())
        elif config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
        return "sent", None
    except Exception as e:  # keep the message, record the failure
        return "failed", str(e)[:280]


def _send_one(row) -> tuple[str, str | None]:
    if row["channel"] == "calendar":
        from .services import calendar
        return calendar.sync(row["to_address"])
    return _send_email(row)


def flush(limit: int = 20) -> int:
    n = 0
    with db.engine.connect() as c:
        rows = c.execute(select(db.notifications).where(db.notifications.c.status == "queued",
                                                        db.notifications.c.attempts < 3)
                         .order_by(db.notifications.c.id).limit(limit)).mappings().all()
    for r in rows:
        status, err = _send_one(r)
        if status == "failed" and r["attempts"] < 2:
            status = "queued"
        with db.engine.begin() as c:
            c.execute(update(db.notifications).where(db.notifications.c.id == r["id"]).values(
                status=status, error=err, attempts=r["attempts"] + 1,
                sent_at=config.now() if status in ("sent", "simulated") else None))
        n += 1
    return n


def _loop():
    while True:
        _wake.wait(timeout=20)
        _wake.clear()
        try:
            flush()
        except Exception as e:
            log.warning("email sender error: %s", e)
            time.sleep(5)


def wake() -> None:
    _wake.set()


def start_sender() -> None:
    threading.Thread(target=_loop, name="email-sender", daemon=True).start()
