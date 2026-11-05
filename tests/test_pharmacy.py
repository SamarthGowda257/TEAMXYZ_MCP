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


def _first_free_time(d):
    s = ap.find_slots(d.isoformat(), department="General Medicine")
    return next(x for x in s.data["doctors"] if x["free_slots"])["free_slots"][0]


def test_failed_balance_checks_count_towards_the_lockout():
    for _ in range(5):
        assert wl.get_balance(RAHUL, "1990-01-01").error_code == "not_verified"
    assert wl.get_balance(RAHUL, RAHUL_DOB).error_code == "locked_out"


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
    t = _first_free_time(d)
    b = ap.book(SHAN, d.isoformat(), t, department="General Medicine", date_of_birth=SHAN_DOB)
    assert b.ok
    code = b.data["booking_id"]
    with db.engine.connect() as c:
        ev = cal.get(c, code)
        mail = c.execute(select(db.notifications).where(db.notifications.c.dedupe_key.like(f"%{code}%:email"))).mappings().first()
        files = c.execute(select(db.notification_files).where(db.notification_files.c.notification_id == mail["id"])).mappings().all()
        cg = c.execute(select(db.notifications).where(db.notifications.c.template == "caregiver_update_cg",
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
    b = ap.book(RAHUL, d.isoformat(), _first_free_time(d), department="General Medicine", date_of_birth=RAHUL_DOB)
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


def test_shared_family_wallet_limits_sms_and_refund():
    r = wl.set_share(SHAN, SHAN_DOB, PRIYA, per_txn_limit="1000")
    assert r.ok and r.data["shared"]
    assert wl.set_share(SHAN, "1990-01-01", PRIYA).error_code == "not_verified"
    o = ph.order(PRIYA, PRIYA_DOB, "5 Gelusil", confirm="yes")       # 600 rupees: 400 her own, 200 from Shanthamma
    assert o.ok and o.data["credits_used"] == 600 and o.data["amount_by_link_inr"] == 0
    assert _bal(3) == 0 and _bal(1) == 3300
    with db.engine.connect() as c:
        assert c.execute(select(db.notifications).where(db.notifications.c.template == "shared_wallet_debit",
                                                        db.notifications.c.to_address == "+919845000001")).first()
    assert ph.track(PRIYA, PRIYA_DOB, o.data["order_id"], "cancel").ok
    assert _bal(3) == 400 and _bal(1) == 3500                        # each payer gets their own share back
    assert wl.set_share(SHAN, SHAN_DOB, PRIYA, action="stop").data["shared"] is False
    with db.engine.connect() as c:
        assert wl.pool_available(c, 3) == (None, 0)


def test_off_campus_wheelchair_deposit_held_and_released():
    needs_dob = ap.request_assistance("WN-48213", SHAN, "wheelchair", off_campus="yes")
    assert needs_dob.error_code == "not_verified"
    r = ap.request_assistance("WN-48213", SHAN, "wheelchair", "Gate 2", date_of_birth=SHAN_DOB, off_campus="yes")
    assert r.ok and _bal(1) == 2500 and r.data["assistance_id"].startswith("AS-")
    assert wl.release_wheelchair_deposit("WN-48213").ok and _bal(1) == 3500
    assert wl.release_wheelchair_deposit("WN-48213").ok and _bal(1) == 3500     # releasing twice pays once


def test_two_way_escort_token_and_caregiver_copy():
    r = ap.request_assistance("WN-48213", SHAN, "wheelchair", "Gate 1, 9:40 AM")
    assert r.ok and r.data["two_way"] and r.data["gate"] == "Gate 1" and r.data["assistance_id"] in r.message
    assert "back to your vehicle" in r.message                       # Shanthamma is a senior: short reply, same promise
    with db.engine.connect() as c:
        assert c.execute(select(db.notifications).where(db.notifications.c.template == "assistance_cg")).first()


def test_cancellation_reference_and_grievance_code():
    from app.services import support
    c = ap.cancel("WN-48213", SHAN, SHAN_DOB)
    assert c.data["cancellation_id"].startswith("CN-") and c.data["cancellation_id"] in c.message
    h = support.create_handoff("Charged twice", "normal", RAHUL, "complaint")
    assert h.data["grievance_id"].startswith("GRV-") and h.data["grievance_id"] in h.message
    assert support.handoff_status(h.data["grievance_id"]).ok         # the patient can quote either reference


def test_free_review_within_seven_days_once():
    from app.services import support
    with db.engine.connect() as c:
        a = c.execute(select(db.appointments).where(db.appointments.c.patient_id == 1, db.appointments.c.doctor_id == 5)).mappings().first()
    doc = ref.REF.doctors[5]
    with db.engine.begin() as c:                                     # her visit was 3 days ago
        c.execute(update(db.appointments).where(db.appointments.c.id == a["id"]).values(appt_date=config.today() - timedelta(days=3)))
    d = config.today() + timedelta(days=1)
    while d.isoweekday() not in doc["days"]:
        d += timedelta(days=1)
    s = ap.find_slots(d.isoformat(), doctor_name=doc["name"])
    first = ap.book(SHAN, d.isoformat(), s.data["doctors"][0]["free_slots"][0], doctor_name=doc["name"], date_of_birth=SHAN_DOB)
    if (d - (config.today() - timedelta(days=3))).days <= 7:
        assert first.ok and first.data["fee_inr"] == 0 and "free" in first.message
        assert wl.pay(SHAN, first.data["booking_id"], "").data["paid_credits"] == 0 and _bal(1) == 3500
        s2 = ap.find_slots(d.isoformat(), doctor_name=doc["name"])
        second = ap.book(SHAN, d.isoformat(), s2.data["doctors"][0]["free_slots"][0], doctor_name=doc["name"])
        assert second.ok and second.data["fee_inr"] == doc["fee_inr"]    # only one free review
    assert support.schedule_followup(SHAN, "", doc["name"]).ok


def test_refill_offered_with_lab_status_and_in_verify():
    from app.services import patients as pt, records
    r = records.lab_status(RAHUL, RAHUL_DOB)
    assert "Lipid Profile is ready" in r.message and "runs out" in r.message
    assert "runs out" in records.email_report(RAHUL, "").message
    assert pt.verify(RAHUL, RAHUL_DOB).data["refill_due"]


def test_caregiver_voice_alert_is_queued_after_nurse_alert_without_symptoms():
    from app.services import outbound as ob, support
    support.flag_nurse_alert(SHAN, "severe wound bleeding")
    with db.engine.connect() as c:
        call = c.execute(select(db.outbound_calls).where(db.outbound_calls.c.kind == "caregiver_update")).mappings().first()
    assert call and call["to_number"] == "+919845000011" and "bleeding" not in call["prompt"]
    assert ob._dial(call["id"])["status"] == "simulated"
    assert ob.handle_event(call["call_code"], "choice", "1")["outcome"] == "acknowledged"


def test_scan_event_starts_with_the_fast_and_signed_calendar_link():
    from fastapi.testclient import TestClient
    from app.api import create_app
    d = config.today() + timedelta(days=2)
    while d.isoweekday() == 7:
        d += timedelta(days=1)
    s = ap.find_slots(d.isoformat(), procedure="Ultrasound Abdomen", phone="")
    b = ap.book(RAHUL, d.isoformat(), s.data["free_slots"][-1], procedure="Ultrasound Abdomen", date_of_birth=RAHUL_DOB)
    with db.engine.connect() as c:
        ev = cal.get(c, b.data["booking_id"])
    assert ev["title"].startswith("Prep & Scan") and ev["minutes"] == 20 + 6 * 60 and "Fasting: 6 hours" in ev["details"]
    web = TestClient(create_app(), follow_redirects=False)
    path = b.data["calendar_link"].split(config.PUBLIC_BASE_URL)[1]
    assert web.get(path).headers["location"].startswith("https://calendar.google.com/")
    assert web.get("/cal/not-a-real-token").status_code == 404


def _mail_for(code):
    with db.engine.connect() as c:
        row = c.execute(select(db.notifications).where(db.notifications.c.channel == "email", db.notifications.c.dedupe_key.like(f"%{code}%:email"))).mappings().first()
        files = c.execute(select(db.notification_files).where(db.notification_files.c.notification_id == row["id"])).mappings().all()
    return row, files


def test_booking_email_is_html_with_details_buttons_and_invite():
    d = config.today() + timedelta(days=2)
    while d.isoweekday() == 7:
        d += timedelta(days=1)
    b = ap.book(RAHUL, d.isoformat(), _first_free_time(d), department="General Medicine", date_of_birth=RAHUL_DOB)
    row, files = _mail_for(b.data["booking_id"])
    msg = notify._message(row, files)
    page = msg.get_body(("html",)).get_content()
    assert msg.get_body(("plain",)).get_content().startswith("Dear Rahul")     # plain text stays as the fallback
    assert b.data["booking_id"] in page and "Booking confirmed" in page and "Good to know" in page
    assert "Add to Google Calendar</a>" in page and "Manage your bookings</a>" in page and "tel:108" in page
    assert row["subject"].startswith("Confirmed: Dr.")
    assert [p.get_filename() for p in msg.iter_attachments()] == ["invite.ics"]


def test_email_text_cannot_inject_html():
    from app import email_ui
    page = email_ui.render("Hi", 'Dear <script>alert(1)</script>,\n\nReason: <b>x</b>')
    assert "<script>alert" not in page and "&lt;script&gt;" in page and "<b>x</b>" not in page


def test_new_patient_email_is_saved_but_never_replaces_one_on_file():
    d = config.today() + timedelta(days=2)
    while d.isoweekday() == 7:
        d += timedelta(days=1)
    t = _first_free_time(d)
    new = ap.book("9845077777", d.isoformat(), t, department="General Medicine", patient_name="New Person", email="New.Person@gmail.com")
    assert new.ok and new.data["confirmation_email"].endswith("@gmail.com")
    assert _mail_for(new.data["booking_id"])[0]["to_address"] == "new.person@gmail.com"
    other = ap.book(RAHUL, d.isoformat(), _first_free_time(d), department="General Medicine", email="attacker@gmail.com")
    assert _mail_for(other.data["booking_id"])[0]["to_address"] != "attacker@gmail.com"
    assert ap.book("9845077778", d.isoformat(), t, department="General Medicine", patient_name="X", email="nope").error_code == "invalid_input"
    none = ap.book("9845077779", d.isoformat(), _first_free_time(d), department="General Medicine", patient_name="No Mail")
    assert "email address" in none.message


def test_demo_override_reaches_personas_but_not_other_invented_patients(monkeypatch):
    monkeypatch.setattr(config, "DEMO_EMAIL_OVERRIDE", "team@gmail.com")
    with db.engine.begin() as c:
        notify.queue(c, patient_id=None, channel="email", template="t", to="rahul.demo@example.com", subject="s", body="b", dedupe_key="o1")
        notify.queue(c, patient_id=None, channel="email", template="t", to="someone.7@example.com", subject="s", body="b", dedupe_key="o2")
        rows = {r.dedupe_key: r for r in c.execute(select(db.notifications).where(db.notifications.c.dedupe_key.in_(["o1", "o2"])))}
    assert rows["o1"].status == "queued" and rows["o1"].to_address == "team@gmail.com"
    assert rows["o2"].status == "simulated"


def test_website_booking_mails_the_profile_email():
    from fastapi.testclient import TestClient
    from app.api import create_app
    web = TestClient(create_app())
    with db.engine.begin() as c:                                    # a patient on file with no website account yet
        c.execute(update(db.patients).where(db.patients.c.id == 4).values(web_email=None, password_hash=None))
    r = web.post("/api/auth/signup", json={"email": "rahul.real@gmail.com", "password": "longenough1", "phone": RAHUL, "date_of_birth": RAHUL_DOB},
                 headers={"x-forwarded-for": "198.51.100.77"}).json()
    h = {"Authorization": f"Bearer {r['token']}"}
    assert web.get("/api/me", headers=h).json()["email"] == "rahul.real@gmail.com"
    assert web.patch("/api/me/preferences", json={"email": "rahul.new@gmail.com"}, headers=h).status_code == 200
    d = config.today() + timedelta(days=2)
    while d.isoweekday() == 7:
        d += timedelta(days=1)
    b = web.post("/api/me/appointments", json={"date": d.isoformat(), "time": _first_free_time(d), "department": "General Medicine"}, headers=h).json()
    row, _ = _mail_for(b["data"]["booking_id"])
    assert row["to_address"] == "rahul.new@gmail.com" and row["status"] == "queued"
