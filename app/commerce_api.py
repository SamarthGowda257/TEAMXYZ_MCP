"""Small server-rendered pages and hooks for payments, medicine tracking, calendar files and staff alerts.

  GET  /pay/<code>                payment link: redirects to Razorpay, or shows the labelled demo payment page
  POST /pay/<code>/demo           demo page "pay" button (only when Razorpay is not configured)
  GET  /pay/<code>/done           Razorpay return page: asks Razorpay whether it's paid before applying it
  POST /api/payments/razorpay     Razorpay webhook (signature checked with RAZORPAY_WEBHOOK_SECRET)
  GET  /track/<order>             medicine delivery status (no names or medicines shown)
  GET  /api/me/appointments/<id>/calendar.ics   the signed-in patient's own invite
  POST /api/ops/doctor-delay      staff: tell today's patients (and caregivers) that a doctor is running late
  GET  /api/ops/integrations      staff: email, Google Calendar and payment connection status
"""

import hashlib
import hmac
import html
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select

from . import config, db, google, notify
from .services import calendar as cal
from .services import patients as pt
from .services import pharmacy as ph
from .services import wallet as wl
from .services.ref import REF, find_doctor
from .util import human_time, norm_code

router = APIRouter()


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} - WellNest Hospitals</title>
<style>body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f7f5;color:#1d2b24;margin:0;padding:24px}}
.card{{max-width:460px;margin:40px auto;background:#fff;border-radius:16px;padding:28px;box-shadow:0 2px 14px rgba(0,0,0,.06)}}
h1{{font-size:20px;margin:0 0 6px}}p{{line-height:1.5}}.amt{{font-size:32px;font-weight:700;margin:12px 0}}
.muted{{color:#5b6b63;font-size:14px}}button{{background:#1f6f4a;color:#fff;border:0;border-radius:10px;padding:12px 18px;
font-size:16px;cursor:pointer;width:100%}}.tag{{display:inline-block;background:#fff4d6;color:#7a5b00;border-radius:8px;
padding:2px 8px;font-size:12px}}</style></head><body><div class="card">{body}
<p class="muted">WellNest Hospitals, 42 Outer Ring Road, Marathahalli, Bengaluru &middot; 080 4000 1234</p></div></body></html>""",
                        status_code=status)


def _link(code: str) -> dict | None:
    with db.engine.connect() as c:
        r = c.execute(select(db.payment_links).where(db.payment_links.c.link_code == code.upper())).mappings().first()
    return dict(r) if r else None


PURPOSE = {"topup": "HealthCredits top-up", "pharmacy": "Medicine order", "bill": "Hospital bill"}


@router.get("/pay/{code}", include_in_schema=False)
def pay_page(code: str):
    link = _link(code)
    if not link:
        return _page("Payment link", "<h1>Link not found</h1><p>Please check the link in your message.</p>", 404)
    what = PURPOSE.get(link["purpose"], "Payment") + (f" {html.escape(link['reference'])}" if link["reference"] else "")
    if link["status"] == "paid":
        return _page("Paid", f"<h1>Already paid</h1><p>{what}: thank you, this was paid.</p>")
    if link["status"] != "created":
        return _page("Expired", "<h1>This link has expired</h1><p>Ask in the WellNest chat for a new one.</p>", 410)
    if wl.razorpay_on():
        url = wl.provider_url(link["link_code"])
        if url:
            return RedirectResponse(url, status_code=302)
        return _page("Payment", "<h1>Payments are busy</h1><p>Please try this link again in a minute.</p>", 503)
    extra = (f"<p>You will receive <b>{link['credits_to_add']:,} HealthCredits</b>.</p>"
             if link["purpose"] == "topup" else "")
    return _page("Payment", f"""<span class="tag">Demo payment page: no money is taken</span>
<h1>{what}</h1><div class="amt">&#8377;{link['amount_inr']:,}</div>{extra}
<form method="post" action="/pay/{link['link_code']}/demo"><button type="submit">Pay &#8377;{link['amount_inr']:,}</button></form>""")


@router.post("/pay/{code}/demo", include_in_schema=False)
def pay_demo(code: str):
    if wl.razorpay_on():
        raise HTTPException(404, detail={"message": "Not available"})
    res = wl.mark_paid(code.upper())
    if not res.get("ok"):
        return _page("Payment", "<h1>Link not found</h1>", 404)
    return _page("Paid", "<h1>Payment received</h1><p>Thank you. A confirmation is on its way to your phone and email.</p>"
                 + (f"<p>Your HealthCredits balance is <b>{res['balance']:,}</b>.</p>" if res.get("balance") is not None else ""))


@router.get("/pay/{code}/done", include_in_schema=False)
def pay_done(code: str):
    if wl.razorpay_on() and wl.razorpay_paid(code.upper()):
        res = wl.mark_paid(code.upper())
        return _page("Paid", "<h1>Payment received</h1><p>Thank you. A confirmation is on its way.</p>"
                     + (f"<p>Your HealthCredits balance is <b>{res['balance']:,}</b>.</p>" if res.get("balance") is not None else ""))
    return _page("Payment", "<h1>We're confirming your payment</h1><p>If it went through you'll get a message shortly.</p>")


@router.post("/api/payments/razorpay", include_in_schema=False)
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(default="")):
    raw = await request.body()
    if not config.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(404, detail={"message": "Webhook not configured"})
    good = hmac.new(config.RAZORPAY_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, x_razorpay_signature):
        raise HTTPException(401, detail={"message": "Bad signature"})
    body = json.loads(raw or b"{}")
    if body.get("event") == "payment_link.paid":
        ref = (((body.get("payload") or {}).get("payment_link") or {}).get("entity") or {}).get("reference_id")
        if ref:
            wl.mark_paid(ref)
    return {"ok": True}


@router.get("/track/{order}", include_in_schema=False)
def track_page(order: str):
    s = ph.public_status(order)
    if not s:
        return _page("Track order", "<h1>Order not found</h1><p>Please check the order number.</p>", 404)
    cold = "<p>Cold-chain parcel: the rider will ask for an OTP and hand it to an adult.</p>" if s["cold_chain"] else ""
    return _page("Track order", f"<h1>Order {html.escape(s['order_id'])}</h1><div class='amt' style='font-size:22px'>"
                                f"{html.escape(s['status'].title())}</div><p>Expected: {html.escape(s['eta'])}</p>{cold}")


def _patient_from_token(authorization: str) -> dict:
    from .security import read_token
    tok = authorization[7:] if authorization.startswith("Bearer ") else ""
    body = read_token(tok) if tok else None
    if not body or "pid" not in body:
        raise HTTPException(401, detail={"error_code": "not_verified", "message": "Please log in again."})
    return body


@router.get("/api/me/appointments/{code}/calendar.ics", include_in_schema=False)
def my_ics(code: str, authorization: str = Header(default="")):
    pid = _patient_from_token(authorization)["pid"]
    with db.engine.connect() as c:
        e = cal.get(c, norm_code(code, "WN") or "")
    if not e or e["patient_id"] != pid:
        raise HTTPException(404, detail={"message": "No calendar entry for that booking."})
    return Response(cal.ics(e), media_type="text/calendar", headers={"Content-Disposition": f'attachment; filename="{e["ref"]}.ics"'})


# ------------------------------------------------------------------ staff
def _ops(request: Request, token: str = "", x_dashboard_token: str = Header(default="")):
    from .api import ops_auth
    return ops_auth(request, token, x_dashboard_token)


class Delay(BaseModel):
    doctor: str
    minutes: int
    reason: str = "an urgent clinical review"


@router.post("/api/ops/doctor-delay", dependencies=[Depends(_ops)])
def doctor_delay(b: Delay):
    """Tell every patient booked with this doctor later today (and their consented caregivers) the new estimated time.
    20 minutes or more also moves their calendar event."""
    doc = find_doctor(b.doctor)
    if not doc:
        raise HTTPException(404, detail={"message": "Doctor not found"})
    now, n = config.now(), 0
    A = db.appointments
    with db.engine.begin() as c:
        rows = c.execute(select(A).where(A.c.doctor_id == doc["id"], A.c.appt_date == now.date(), A.c.status == "booked")).mappings().all()
        for a in rows:
            start = datetime.combine(a["appt_date"], datetime.strptime(a["appt_time"], "%H:%M").time())
            if start < now - timedelta(minutes=15):
                continue
            new = start + timedelta(minutes=b.minutes)
            p = pt.get_by_id(c, a["patient_id"])
            when = human_time(new.strftime("%H:%M"))
            text = (f"{doc['name']} has been called into {b.reason}. Your {human_time(a['appt_time'])} consultation "
                    f"({a['booking_code']}) is now expected to start around {when}. If you booked wheelchair help, the porter "
                    "will meet you at Gate 2 15 minutes before that.")
            notify.email_and_sms(c, patient=p, template="doctor_delay", key=f"delay:{a['booking_code']}:{b.minutes}",
                                 subject=f"Update: {doc['name']} is running about {b.minutes} minutes late",
                                 body=f"Dear {p['full_name']},\n\n{text}\n\nSorry for the wait.\n\nWellNest Hospitals",
                                 sms=f"WellNest: {doc['name']} running ~{b.minutes} min late. New time ~{when} ({a['booking_code']}).")
            notify.to_caregiver(c, p, template="doctor_delay", key=f"delay:{a['booking_code']}:{b.minutes}",
                                subject=f"Update for {p['full_name']}: doctor running late",
                                body=f"{p['full_name']}'s visit: {text}",
                                sms=f"{p['full_name']}'s visit with {doc['name']} now ~{when} ({b.minutes} min delay).")
            if p.get("caregiver_consent") and p.get("caregiver_phone") and b.minutes >= 20:
                notify.queue(c, patient_id=p["id"], channel="voice_call", template="doctor_delay_call", to=p["caregiver_phone"],
                             body=f"Hello {p.get('caregiver_name') or ''}, this is an automated update from WellNest Hospitals about "
                                  f"{p['full_name']}. {text}", dedupe_key=f"delaycall:{a['booking_code']}:{b.minutes}")
            e = cal.get(c, a["booking_code"])
            if e and b.minutes >= 20:
                cal.upsert(c, ref=a["booking_code"], patient=p, kind="appointment", title=e["title"] + " (delayed)",
                           starts_at=new, minutes=e["minutes"], location=e["location"],
                           details=f"Delayed by about {b.minutes} minutes.\n\n" + (e["details"] or ""))
            n += 1
    return {"ok": True, "doctor": doc["name"], "patients_notified": n}


@router.get("/api/ops/integrations", dependencies=[Depends(_ops)])
def integrations():
    with db.engine.connect() as c:
        recent = c.execute(select(db.notifications.c.channel, db.notifications.c.status, db.notifications.c.error)
                           .where(db.notifications.c.channel.in_(("email", "calendar")))
                           .order_by(db.notifications.c.id.desc()).limit(50)).all()
    counts: dict = {}
    for ch, st, _ in recent:
        counts[f"{ch}:{st}"] = counts.get(f"{ch}:{st}", 0) + 1
    last_error = next((e for _, st, e in recent if st == "failed" and e), None)
    return {"email": {"transport": notify.transport(), "from": config.EMAIL_FROM, "demo_override": bool(config.DEMO_EMAIL_OVERRIDE)},
            "google": {"connected": google.configured(), "send_mail_with_gmail_api": config.GOOGLE_SEND_MAIL},
            "calendar": cal.describe_status(),
            "payments": {"provider": "razorpay" if wl.razorpay_on() else "demo page", "webhook": bool(config.RAZORPAY_WEBHOOK_SECRET)},
            "recent_outbox": counts, "last_error": last_error}
