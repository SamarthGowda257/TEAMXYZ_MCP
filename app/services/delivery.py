"""Doorstep delivery through a courier provider (Pharmacy V3).

The order logic never talks to a courier directly: it calls `dispatch(order)` and reacts to `apply_event(...)`.
A provider is a small class with `book` and `cancel`; status changes arrive as signed webhooks
(POST /api/webhooks/delivery/{provider}) or, for the simulated courier, from the jobs runner and the staff console.

  DELIVERY_PROVIDER=simulated   (default) books instantly, delivers when the ETA passes. Demos and tests.
  DELIVERY_PROVIDER=<partner>   add a class below with the partner's API (Porter, Shadowfax, Borzo, own riders...),
                                put its keys in Render, and point the partner's webhook at our endpoint with
                                DELIVERY_WEBHOOK_SECRET as the HMAC key.

Rules the provider can't break:
  - Schedule H1 and cold-chain parcels need the patient's 4-digit delivery code (sent by SMS), and H1 a photo ID.
  - A missed delivery is tried once more; after the second miss the parcel comes back and the credits are refunded.
  - No rider found: book once more; if that fails too, the order is ready to collect at the pharmacy counter.
  - Each webhook event is applied once (provider + event_id is unique).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from .. import config, db, events, notify
from ..util import Result, fail, ok
from . import patients as pt

log = logging.getLogger("wellnest.delivery")
D, E, ORD = db.deliveries, db.delivery_events, db.pharmacy_orders
MAX_ATTEMPTS = 2
PROVIDER = (config.env("DELIVERY_PROVIDER", "simulated") or "simulated").lower()
WEBHOOK_SECRET = config.env("DELIVERY_WEBHOOK_SECRET", "")


class Simulated:
    name = "simulated"

    def book(self, order: dict) -> dict:
        return {"job_id": f"SIM-{order['order_code']}-{secrets.token_hex(2)}", "rider": "WellNest rider"}

    def cancel(self, job_id: str) -> bool:
        return True


PROVIDERS = {"simulated": Simulated}


def provider():
    return PROVIDERS.get(PROVIDER, Simulated)()


def _otp_hash(order_code: str, otp: str) -> str:
    return hashlib.sha256(f"{order_code}|{otp}|{config.SECRET_KEY}".encode()).hexdigest()


def needs_code(order: dict) -> bool:
    return bool(order.get("cold_chain")) or any(i.get("schedule") == "H1" for i in order.get("items") or [])


def latest(order_id: int) -> dict | None:
    with db.engine.connect() as c:
        r = c.execute(select(D).where(D.c.order_id == order_id).order_by(D.c.id.desc())).mappings().first()
    return dict(r) if r else None


def dispatch(c, o: dict, p: dict) -> dict:
    """Book the courier inside the caller's transaction. Returns the delivery row values."""
    prov = provider()
    try:
        job = prov.book(o)
    except Exception as e:                      # partner down: try again on the next jobs run
        log.warning("courier booking failed for %s: %s", o["order_code"], e)
        return {}
    vals = dict(order_id=o["id"], provider=prov.name, provider_job_id=job.get("job_id"), status="booked", attempts=0,
                rider_name=job.get("rider"), last_event_at=config.now(), created_at=config.now())
    otp = None
    if needs_code(o):
        otp = f"{secrets.randbelow(10000):04d}"
        vals["otp_hash"] = _otp_hash(o["order_code"], otp)
    c.execute(insert(D).values(**vals))
    if otp:
        h1 = any(i.get("schedule") == "H1" for i in o["items"])
        notify.queue(c, patient_id=p["id"], channel="sms", template="delivery_code", to=p["phone"],
                     body=f"WellNest: your delivery code for order {o['order_code']} is {otp}. Give it to the rider only "
                          f"when the parcel is in your hands." + (" Please keep a photo ID ready." if h1 else ""),
                     dedupe_key=f"otp:{o['order_code']}")
    return vals


def verify_code(order_code: str, code: str) -> bool:
    with db.engine.connect() as c:
        o = c.execute(select(ORD.c.id).where(ORD.c.order_code == order_code)).first()
        d = c.execute(select(D).where(D.c.order_id == o[0]).order_by(D.c.id.desc())).mappings().first() if o else None
    return bool(d and d["otp_hash"] and hmac.compare_digest(d["otp_hash"], _otp_hash(order_code, code)))


def signature_ok(raw: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return False
    good = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, (signature or "").removeprefix("sha256="))


def apply_event(provider_name: str, event_id: str, job_id: str, event: str, body: dict | None = None,
                otp: str = "") -> Result:
    """One courier status change, applied once. event: picked_up, delivered, failed_attempt, no_rider, cancelled."""
    from . import pharmacy as ph
    from . import wallet
    event = (event or "").lower()
    if event not in ("picked_up", "delivered", "failed_attempt", "no_rider", "cancelled"):
        return fail("invalid_input", f"Unknown delivery event {event}.")
    with db.engine.begin() as c:
        d = c.execute(select(D).where(D.c.provider == provider_name, D.c.provider_job_id == job_id).with_for_update()).mappings().first()
        if not d:
            return fail("not_found", "No delivery with that job ID.")
        try:
            with c.begin_nested():
                c.execute(insert(E).values(provider=provider_name, event_id=event_id[:80], delivery_id=d["id"], event=event,
                                           body=body or {}, created_at=config.now()))
        except IntegrityError:
            return ok("Already applied.", duplicate=True)
        o = dict(c.execute(select(ORD).where(ORD.c.id == d["order_id"]).with_for_update()).mappings().first())
        p = pt.get_by_id(c, o["patient_id"])
        now = config.now()
        if event == "picked_up":
            c.execute(update(D).where(D.c.id == d["id"]).values(status="picked_up", last_event_at=now))
            msg = "Picked up."
        elif event == "delivered":
            if d["otp_hash"] and not (otp and hmac.compare_digest(d["otp_hash"], _otp_hash(o["order_code"], otp))):
                return fail("code_required", "This parcel needs the patient's delivery code; it doesn't match.")
            c.execute(update(D).where(D.c.id == d["id"]).values(status="delivered", last_event_at=now,
                                                                proof=str((body or {}).get("proof", ""))[:200] or None))
            c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="delivered", updated_at=now))
            msg = "Delivered."
        elif event == "failed_attempt":
            attempts = d["attempts"] + 1
            if attempts < MAX_ATTEMPTS:
                retry = now + timedelta(days=1) if now.hour >= 17 else now + timedelta(hours=3)
                c.execute(update(D).where(D.c.id == d["id"]).values(status="failed_attempt", attempts=attempts, last_event_at=now))
                c.execute(update(ORD).where(ORD.c.id == o["id"]).values(eta=retry, updated_at=now))
                notify.queue(c, patient_id=p["id"], channel="sms", template="delivery_missed", to=p["phone"],
                             body=f"WellNest: our rider couldn't deliver order {o['order_code']}. We'll try again "
                                  f"{ph._eta_text(retry)}. Reply in the chat or call {ph.PHARMACY_DESK} to change the time.",
                             dedupe_key=f"miss1:{o['order_code']}")
                msg = "Missed; one more attempt booked."
            else:
                c.execute(update(D).where(D.c.id == d["id"]).values(status="returned", attempts=attempts, last_event_at=now))
                back = o["credits_used"] or 0
                if back:
                    wallet.give_back(c, o["patient_id"], back, o["order_code"], f"order:{o['order_code']}",
                                     f"order_refund:{o['order_code']}")
                from . import rx
                rx.void(c, o["id"])       # the prescription days come back; the pharmacist re-checks the sealed parcel
                c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="returned", updated_at=now))
                notify.queue(c, patient_id=p["id"], channel="sms", template="delivery_returned", to=p["phone"],
                             body=f"WellNest: we missed you twice, so order {o['order_code']} went back to the pharmacy. "
                                  + (f"{back:,} HealthCredits are refunded. " if back else "")
                                  + "Reorder any time in the chat.", dedupe_key=f"ret:{o['order_code']}")
                pt.log(c, o["patient_id"], "delivery_returned", o["order_code"], True, f"Two missed attempts; refunded {back}",
                       actor="system", channel="system")
                msg = "Returned and refunded."
        else:   # no_rider / cancelled by the partner
            again = c.execute(select(D.c.id).where(D.c.order_id == o["id"])).all()
            if len(again) < 2:
                c.execute(update(D).where(D.c.id == d["id"]).values(status=event, last_event_at=now))
                dispatch(c, o, p)
                msg = "Rebooked with another rider."
            else:
                c.execute(update(D).where(D.c.id == d["id"]).values(status=event, last_event_at=now))
                c.execute(update(ORD).where(ORD.c.id == o["id"]).values(status="ready_for_pickup", updated_at=now))
                notify.queue(c, patient_id=p["id"], channel="sms", template="delivery_pickup", to=p["phone"],
                             body=f"WellNest: no rider is free for order {o['order_code']}. It's ready to collect at the "
                                  f"pharmacy counter, Gate 1 (24 hours), or call {ph.PHARMACY_DESK} for a new delivery time.",
                             dedupe_key=f"pick:{o['order_code']}")
                msg = "No rider twice; ready for pickup."
    events.publish("pharmacy.delivery", patient_id=o["patient_id"], order_id=o["order_code"], event=event)
    return ok(msg, order_id=o["order_code"], event=event)
