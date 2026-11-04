"""Mini-pharmacy, HealthCredits wallet, calendar invites, Google Calendar/Gmail sync and caregiver copies.
Google and Razorpay are replaced by fake HTTP layers; everything else is real.

Run: MCP_BEARER_TOKEN=test python -m pytest -q tests/test_pharmacy.py
"""

import os
import tempfile
from datetime import timedelta

os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_pharmacy.db")
os.environ.pop("DATABASE_URL", None)

import pytest  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

from app import config, db, google, notify, seed  # noqa: E402
from app.services import appointments as ap  # noqa: E402
from app.services import calendar as cal  # noqa: E402
from app.services import pharmacy as ph  # noqa: E402
from app.services import ref  # noqa: E402
from app.services import wallet as wl  # noqa: E402
from app.store import store  # noqa: E402

RAHUL, RAHUL_DOB = "9845000004", "10 September 1981"
SHAN, SHAN_DOB = "9845000001", "4 March 1959"
PRIYA, PRIYA_DOB = "9845000003", "20-01-1997"


@pytest.fixture(autouse=True)
def fresh():
    seed.reset(verbose=False)
    ref.load()
    store.flush()


def _bal(pid):
    with db.engine.connect() as c:
        return wl.balance(c, pid)


def test_stock_shows_restock_time_and_generic():
    r = ph.check_stock("Telma 40")
    assert r.ok and "out of stock" in r.message and "Cipla" in r.message and "prescription" in r.message
    assert r.data["medicines"][0]["restock_eta"]
    assert "Schedule X" in ph.check_stock("Alprax 0.25").message


def test_prescription_law_is_enforced_on_the_server():
    r = ph.order(RAHUL, RAHUL_DOB, "Augmentin 625", confirm="yes")
    assert r.error_code == "prescription_required" and "Dr. Anil Kumar" in r.message and "600" in r.message
    assert ph.order(RAHUL, RAHUL_DOB, "Zolfresh 10", confirm="yes").error_code == "not_allowed"
    assert _bal(4) == 1800                                          # nothing was charged


def test_order_with_credits_quote_then_confirm_and_no_double_charge():
    q = ph.order(RAHUL, RAHUL_DOB, "2 strips of Metformin 500mg and a strip of Dolo 650")
    assert q.ok and q.data["needs"] == "confirm"
    assert q.data["quote"]["total_inr"] == 2 * 48 + 32 + 50 and "178 rupees" in q.message and "1,800" in q.message
    assert _bal(4) == 1800                                          # a quote never charges
    r = ph.order(RAHUL, "", "2 strips of Metformin 500mg and a strip of Dolo 650", confirm="yes")   # verified: no DOB again
    assert r.ok and r.data["order_id"].startswith("PHARM-") and r.data["balance_credits"] == 1622
    assert "within 90 minutes" in r.message                          # Marathahalli is in the express zone
    again = ph.order(RAHUL, RAHUL_DOB, "2 strips of Metformin 500mg and a strip of Dolo 650", confirm="yes")
    assert again.data["duplicate"] and _bal(4) == 1622              # voice lag / double click: charged once
    with db.engine.connect() as c:
        ev = cal.get(c, f"refill:4:GLYCOMET")
    assert ev and ev["all_day"] and "Refill" in ev["title"]


def test_out_of_stock_brand_can_be_reserved():
    r = ph.order(RAHUL, RAHUL_DOB, "Telma 40", confirm="yes")
    assert r.error_code == "out_of_stock" and "Cipla" in r.message
    held = ph.order(RAHUL, RAHUL_DOB, "Telma 40", confirm="yes", wait_for_restock="yes")
    assert held.ok and held.data["status"] == "awaiting_stock"


def test_split_payment_when_credits_are_short():
    r = ph.order(PRIYA, PRIYA_DOB, "5 Gelusil", confirm="yes")       # 600 rupees, free delivery, 400 credits
    assert r.ok and r.data["credits_used"] == 400 and r.data["amount_by_link_inr"] == 200
    assert r.data["status"] == "awaiting_payment" and "/pay/PL-" in r.data["payment_url"]
    code = r.data["payment_url"].rsplit("/", 1)[1]
    assert wl.mark_paid(code)["ok"] and wl.mark_paid(code)["already"]
    assert ph.track(PRIYA, PRIYA_DOB).data["status"] == "confirmed"


def test_cancel_before_dispatch_refunds_and_after_dispatch_is_refused():
    o = ph.order(RAHUL, RAHUL_DOB, "Dolo 650", quantity="3", confirm="yes")
    assert _bal(4) == 1800 - (96 + 50)
    c1 = ph.track(RAHUL, RAHUL_DOB, o.data["order_id"], "cancel")
    assert c1.ok and c1.data["refunded_credits"] == 146 and _bal(4) == 1800
    o2 = ph.order(RAHUL, RAHUL_DOB, "Dolo 650", quantity="2", confirm="yes")
    with db.engine.begin() as c:
        c.execute(update(db.pharmacy_orders).where(db.pharmacy_orders.c.order_code == o2.data["order_id"])
                  .values(updated_at=config.now() - timedelta(minutes=11)))
    assert ph.advance()["dispatched"] == 1
    r = ph.track(RAHUL, RAHUL_DOB, o2.data["order_id"], "cancel")
    assert r.error_code == "not_allowed" and "can't be recalled" in r.message


def test_cold_chain_and_child_account():
    r = ph.order(SHAN, SHAN_DOB, "Lantus pen")
    assert r.error_code == "prescription_required"                  # no insulin prescription on file
    with db.engine.begin() as c:
        c.execute(db.prescriptions.insert().values(patient_id=1, doctor_id=38, medicine_name="Insulin glargine 100 IU",
                                                   start_date=config.today() - timedelta(days=10)))
    q = ph.order(SHAN, SHAN_DOB, "Lantus pen")
    assert q.ok and "ice-pack" in q.message and "adult" in q.message
    child = ph.order("9845000005", "12 May 2018", "Dolo 650")
    assert child.ok and child.data["quote"]["credits_to_use"] == 0 and "guardian" in child.message


def test_wallet_topup_bonus_pay_booking_and_refund_on_cancel():
    r = wl.recharge(SHAN, "2000", SHAN_DOB)
    assert r.ok and r.data["bonus_credits"] == 100 and r.data["total_credits"] == 2100
    wl.mark_paid(r.data["payment_url"].rsplit("/", 1)[1])
    assert _bal(1) == 3500 + 2100
    p = wl.pay(SHAN, "WN-48213", "")
    assert p.ok and p.data["paid_credits"] == 1200 and _bal(1) == 5600 - 1200
    assert "already paid" in wl.pay(SHAN, "WN-48213", "").message and _bal(1) == 4400
    c = ap.cancel("WN-48213", SHAN, "")
    assert c.ok and "1,200 HealthCredits are back" in c.message and _bal(1) == 5600
    rf = wl.request_refund(SHAN, "600", "")
    assert rf.ok and rf.data["refund_id"].startswith("RF-") and _bal(1) == 5000


def test_booking_sends_calendar_invite_policies_and_caregiver_copy():
    d = config.today() + timedelta(days=2)
    while d.isoweekday() not in (1, 2, 3, 4, 5, 6):
        d += timedelta(days=1)
    s = ap.find_slots(d.isoformat(), department="General Medicine")
    t = s.data["slots"][0]["times"][0] if "slots" in s.data else None
    assert t
    b = ap.book(SHAN, d.isoformat(), t, department="General Medicine", date_of_birth=SHAN_DOB)
    assert b.ok
    code = b.data["booking_id"]
    with db.engine.connect() as c:
        ev = cal.get(c, code)
        mail = c.execute(select(db.notifications).where(db.notifications.c.dedupe_key.like(f"%{code}%:email"))).mappings().first()
        files = c.execute(select(db.notification_files).where(db.notification_files.c.notification_id == mail["id"])).mappings().all()
        cg = c.execute(select(db.notifications).where(db.notifications.c.template == "caregiver_update",
                                                      db.notifications.c.body.like(f"%{code}%"))).first()
    assert ev and ev["kind"] == "appointment" and ev["sync_status"] == "ics_only"
    assert "free follow-up" in mail["body"] and "calendar.google.com" in mail["body"]
    assert files and "TZID=Asia/Kolkata" in files[0]["content"] and "BEGIN:VALARM" in files[0]["content"]
    assert cg is not None                                           # Shanthamma's son consented to updates
    ap.cancel(code, SHAN, "")
    with db.engine.connect() as c:
        assert cal.get(c, code)["status"] == "cancelled"
    assert "METHOD:CANCEL" in cal.ics(cal.get(db.engine.connect(), code))


def test_google_calendar_and_gmail_sync(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._b, self.text = code, body, str(body)

        def json(self):
            return self._b

    def fake_post(url, **kw):
        assert url.endswith("/token") and kw["data"]["grant_type"] == "refresh_token"
        return Resp(200, {"access_token": "g-tok", "expires_in": 3600})

    def fake_request(method, url, **kw):
        calls.append((method, url, kw.get("json"), kw.get("params")))
        if "gmail" in url:
            return Resp(200, {"id": "m1"})
        return Resp(200 if method != "DELETE" else 204, {"id": "evt-123"})

    for k, v in {"GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "s", "GOOGLE_REFRESH_TOKEN": "r", "GOOGLE_SEND_MAIL": True,
                 "DEMO_EMAIL_OVERRIDE": ""}.items():
        monkeypatch.setattr(config, k, v)
    google._token.update(value="", expires=0)
    monkeypatch.setattr(google.httpx, "post", fake_post)
    monkeypatch.setattr(google.httpx, "request", fake_request)
    with db.engine.begin() as c:                                    # a real inbox for the demo patient
        c.execute(update(db.patients).where(db.patients.c.id == 4).values(email="rahul.real@gmail.com"))
    d = config.today() + timedelta(days=3)
    while d.isoweekday() == 7:
        d += timedelta(days=1)
    s = ap.find_slots(d.isoformat(), department="General Medicine")
    b = ap.book(RAHUL, d.isoformat(), s.data["slots"][0]["times"][0], department="General Medicine", date_of_birth=RAHUL_DOB)
    assert b.ok
    notify.flush(50)
    ev_calls = [x for x in calls if "calendar/v3" in x[1]]
    assert ev_calls and ev_calls[0][0] == "POST" and ev_calls[0][3] == {"sendUpdates": "all"}
    assert ev_calls[0][2]["attendees"] == [{"email": "rahul.real@gmail.com"}]
    assert ev_calls[0][2]["start"]["timeZone"] == "Asia/Kolkata"
    assert any("gmail" in x[1] for x in calls)                     # confirmation mail went out through Gmail
    with db.engine.connect() as c:
        assert cal.get(c, b.data["booking_id"])["google_event_id"] == "evt-123"
    ap.cancel(b.data["booking_id"], RAHUL, "")
    notify.flush(50)
    assert any(x[0] == "DELETE" and x[1].endswith("/evt-123") for x in calls)


def test_refill_reminder_job_and_verified_session():
    assert ph.refill_reminders() >= 2                              # Rahul's Metformin + Telmisartan end in 4 days
    with db.engine.connect() as c:
        n = c.execute(select(db.notifications).where(db.notifications.c.template == "refill_reminder")).all()
    assert n
    assert wl.get_balance(RAHUL, "").error_code == "not_verified"    # cold: needs the date of birth
    assert wl.get_balance(RAHUL, RAHUL_DOB).ok
    assert wl.get_balance(RAHUL, "").data["balance_credits"] == 1800
