"""Outbox: every outbound message is a `notifications` row. A background thread sends emails.

Tools only insert rows (inside their transaction); they never talk to SMTP.
SMS / WhatsApp / reminder calls are simulated (status 'simulated') and labelled as such.
If SMTP env vars are missing, emails are also marked 'simulated'.
"""

import logging
import smtplib
import threading
import time
from email.message import EmailMessage

from sqlalchemy import select, update

from . import config, db

log = logging.getLogger("wellnest.notify")
_wake = threading.Event()
FAKE_DOMAINS = ("@example.com", ".test", "@example.org")


def queue(conn, *, patient_id, channel: str, template: str, to: str | None, subject: str = "", body: str = "",
          dedupe_key: str | None = None) -> None:
    """Insert an outbox row inside the caller's transaction."""
    if not to:
        return
    if dedupe_key:
        exists = conn.execute(select(db.notifications.c.id).where(db.notifications.c.dedupe_key == dedupe_key)).first()
        if exists:
            return
    status = "queued" if channel == "email" else "simulated"
    if channel == "email" and to.lower().endswith(FAKE_DOMAINS):
        status = "simulated"          # seeded fake patients: never send real mail to invented addresses
    elif channel == "email" and config.DEMO_EMAIL_OVERRIDE:
        body = f"[Demo: originally to {to}]\n\n" + body
        to = config.DEMO_EMAIL_OVERRIDE
    conn.execute(db.notifications.insert().values(
        patient_id=patient_id, channel=channel, template=template, to_address=to, subject=subject[:200],
        body=body, status=status, dedupe_key=dedupe_key, created_at=config.now(),
        sent_at=config.now() if status == "simulated" else None))
    if status == "queued":
        _wake.set()
    from . import events
    events.publish("notification.queued", channel=channel, template=template, status=status)


def email_and_sms(conn, *, patient: dict, template: str, subject: str, body: str, sms: str, key: str | None = None):
    queue(conn, patient_id=patient.get("id"), channel="email", template=template, to=patient.get("email"),
          subject=subject, body=body, dedupe_key=f"{key}:email" if key else None)
    queue(conn, patient_id=patient.get("id"), channel="sms", template=template, to=patient.get("phone"),
          body=sms, dedupe_key=f"{key}:sms" if key else None)


def _send_one(row) -> tuple[str, str | None]:
    if not config.EMAIL_ENABLED:
        return "simulated", None
    msg = EmailMessage()
    msg["From"] = config.EMAIL_FROM
    msg["To"] = row["to_address"]
    msg["Subject"] = row["subject"] or "WellNest Hospitals"
    msg.set_content(row["body"] or "")
    try:
        if config.SMTP_PORT == 465:
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
