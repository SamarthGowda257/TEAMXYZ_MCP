"""Pharmacy V3: prescription days, OTC limits across brands, patient safety, pharmacist review, hold and capture,
courier events and the staff and patient routes. One test per edge case in docs/PHARMACY_V3_PLAN.md section 8.

Run: MCP_BEARER_TOKEN=test python -m pytest -q tests/test_pharmacy_v3.py
"""

import base64
import hashlib
import hmac
import json
import os
import tempfile
from datetime import timedelta

os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_pharmacy_v3.db")
os.environ.pop("DATABASE_URL", None)
os.environ["DELIVERY_WEBHOOK_SECRET"] = "whsec-test"

import pytest  # noqa: E402
from sqlalchemy import select, text, update  # noqa: E402

from app import config, db, mcp_tools, seed  # noqa: E402
from app.services import delivery as dl  # noqa: E402
from app.services import patients as pt  # noqa: E402
from app.services import pharmacy as ph  # noqa: E402
from app.services import ref  # noqa: E402
from app.services import rx  # noqa: E402
from app.services import wallet as wl  # noqa: E402
from app.store import store  # noqa: E402

RAHUL, RAHUL_DOB = "9845000004", "10 September 1981"          # 1,800 credits; Metformin + Telmisartan on file
SHAN, SHAN_DOB = "9845000001", "4 March 1959"                 # Amlodipine on file (90 days)
PRIYA, PRIYA_DOB = "9845000003", "20-01-1997"                 # 400 credits


@pytest.fixture(autouse=True)
def fresh():
    seed.reset(verbose=False)
    ref.load()
    store.flush()
    dl.WEBHOOK_SECRET = "whsec-test"


def _bal(pid):
    with db.engine.connect() as c:
        return wl.balance(c, pid)


def _order(code):
    with db.engine.connect() as c:
        return dict(c.execute(select(db.pharmacy_orders).where(db.pharmacy_orders.c.order_code == code)).mappings().first())


def _age_disp(order_code, days):
    """Pretend an order's supply was handed out `days` ago."""
    o = _order(order_code)
    with db.engine.begin() as c:
        c.execute(update(db.dispensations).where(db.dispensations.c.order_id == o["id"])
                  .values(created_at=config.now() - timedelta(days=days)))
        c.execute(update(db.pharmacy_orders).where(db.pharmacy_orders.c.id == o["id"])
                  .values(idempotency_key=f"old-{o['id']}"))


def _prescribe(pid, code, dose=1, times=1, days=5, refills=0, **kw):
    r = rx.prescribe(pid, 11, [dict(medicine_code=code, dose_units=dose, times_per_day=times, duration_days=days,
                                    refills_allowed=refills, **kw)], signed_by="Dr. Anil Kumar")
    assert r.ok, r.message
    return r


def _dispatch(order_code):
    with db.engine.begin() as c:
        c.execute(update(db.pharmacy_orders).where(db.pharmacy_orders.c.order_code == order_code)
                  .values(updated_at=config.now() - timedelta(minutes=11)))
    ph.advance()
    return _order(order_code)


# ------------------------------------------------------------------ OTC limits
def test_dolo_within_limits_goes_out_without_a_pharmacist():
    r = ph.order(RAHUL, RAHUL_DOB, "2 strips of Dolo 650", confirm="yes")
    assert r.ok and r.data["status"] == "confirmed" and not r.data["pharmacist_check"]
    assert _order(r.data["order_id"])["verification"] == "auto"


def test_dolo_per_order_cap_offers_the_allowed_amount():
    r = ph.order(RAHUL, RAHUL_DOB, "4 strips of Dolo 650", confirm="yes")
    assert r.error_code == "otc_limit" and r.data["allowed_packs"] == 3 and "3 packs" in r.message
    assert _bal(4) == 1800


def test_weekly_paracetamol_limit_counts_every_brand():
    assert ph.order(RAHUL, RAHUL_DOB, "3 strips of Dolo 650", confirm="yes").ok        # 29.25 g
    more = ph.order(RAHUL, "", "2 strips of Dolo 650", confirm="yes")                  # would be 48.75 g in 7 days
    assert more.error_code == "otc_limit" and more.data["allowed_packs"] == 1 and "every brand" in more.message
    crocin = ph.order(RAHUL, "", "Crocin Advance")                                     # 7.5 g more fits under 39 g
    assert crocin.ok and "Dolo 650" in crocin.message and "don't take" in crocin.message
    two_crocin = ph.order(RAHUL, "", "2 strips of Crocin Advance")                     # 15 g does not
    assert two_crocin.error_code == "otc_limit"


def test_cancelled_orders_free_the_limit_again():
    a = ph.order(RAHUL, RAHUL_DOB, "3 strips of Dolo 650", confirm="yes")
    assert ph.track(RAHUL, "", a.data["order_id"], "cancel").ok
    assert ph.order(RAHUL, "", "3 Dolo 650 strips", confirm="yes").ok


def test_two_brands_of_one_medicine_in_one_order_are_flagged():
    r = ph.order(RAHUL, RAHUL_DOB, "Dolo 650 and Crocin Advance", confirm="yes")
    assert r.ok and "same medicine" in r.message and r.data["pharmacist_check"]
    assert r.data["status"] == "awaiting_review"


# ------------------------------------------------------------------ prescriptions
def test_antibiotic_course_cant_be_reordered():
    _prescribe(4, "AZITHRAL", days=3)                                                  # one strip of 3 = the course
    first = ph.order(RAHUL, RAHUL_DOB, "Azithral 500", confirm="yes")
    assert first.ok and first.data["status"] == "awaiting_review" and "pharmacist" in first.message
    assert ph.approve(_order(first.data["order_id"])["id"], "Pharm. Kavya").ok
    _age_disp(first.data["order_id"], 4)
    again = ph.order(RAHUL, "", "Azithral 500", confirm="yes")
    assert again.error_code == "prescription_used" and "renew" in again.message


def test_chronic_refill_too_early_then_allowed():
    first = ph.order(SHAN, SHAN_DOB, "2 strips of Amlong 5", confirm="yes")            # 30 days, once daily
    assert first.ok
    early = ph.order(SHAN, "", "Amlong 5", confirm="yes")
    assert early.error_code == "refill_too_early" and early.data["refill_from"]
    _age_disp(first.data["order_id"], 25)                                              # 25 of 30 days gone (> 80%)
    assert ph.order(SHAN, "", "Amlong 5", confirm="yes").ok


def test_at_most_thirty_days_per_order_rounded_to_whole_packs():
    r = ph.order(SHAN, SHAN_DOB, "5 strips of Amlong 5", confirm="yes")
    assert r.error_code == "over_prescription" and r.data["allowed_packs"] == 2


def test_doctor_stopping_a_medicine_cancels_the_waiting_order_and_refunds():
    _prescribe(4, "AZITHRAL", days=3)
    o = ph.order(RAHUL, RAHUL_DOB, "Azithral 500", confirm="yes")
    held = o.data["credits_used"]
    assert held and _bal(4) == 1800 - held
    with db.engine.connect() as c:
        item_id = c.execute(select(db.prescription_items.c.id).where(db.prescription_items.c.medicine_code == "AZITHRAL")).scalar()
    res = rx.stop_item(item_id, "Switched to another antibiotic", "Dr. Anil Kumar")
    assert res.ok and res.data["cancelled_orders"] == 1
    after = _order(o.data["order_id"])
    assert after["status"] == "cancelled" and after["verification"] == "rejected" and _bal(4) == 1800
    assert ph.order(RAHUL, "", "Azithral 500").error_code == "prescription_stopped"


def test_dose_change_replaces_the_old_item():
    _prescribe(1, "AMLONG5", days=30, refills=2)                                       # newer Amlodipine for Shanthamma
    with db.engine.connect() as c:
        stopped = c.execute(select(db.prescription_items.c.stop_reason).where(
            db.prescription_items.c.ingredient == "amlodipine", db.prescription_items.c.stopped_at.is_not(None))).scalars().all()
    assert stopped and all(s.startswith("Replaced by RX-") for s in stopped)


def test_daily_dose_above_the_maximum_needs_a_reason():
    bad = rx.prescribe(4, 11, [dict(medicine_code="DOLO650", dose_units=2, times_per_day=4, duration_days=3)], "Dr. X")
    assert not bad.ok and "5200 mg a day" in bad.message
    good = rx.prescribe(4, 11, [dict(medicine_code="DOLO650", dose_units=2, times_per_day=4, duration_days=3,
                                     override_reason="Short supervised course")], "Dr. X")
    assert good.ok


def test_signature_is_stored_and_tamper_evident():
    r = _prescribe(4, "AZITHRAL", days=3)
    with db.engine.connect() as c:
        h = c.execute(select(db.prescriptions.c.signature_hash).where(db.prescriptions.c.rx_code == r.data["rx_code"])).scalar()
    assert len(h) == 64


# ------------------------------------------------------------------ uploads
def test_uploaded_prescription_waits_for_the_pharmacist():
    up = rx.upload(4, "rx.jpg", "image/jpeg", b"\xff\xd8fakejpeg", "From Apollo")
    assert up.ok and up.data["upload_code"].startswith("UP-")
    blocked = ph.order(RAHUL, RAHUL_DOB, "Augmentin 625")
    assert blocked.error_code == "prescription_required" and "upload" in blocked.message
    with db.engine.connect() as c:
        uid = c.execute(select(db.prescription_uploads.c.id)).scalar()
    assert not rx.review_upload(uid, False, "Pharm. Kavya").ok                       # a rejection needs a reason
    ok_ = rx.review_upload(uid, True, "Pharm. Kavya", items=[dict(medicine_code="AUGMENTIN", dose_units=1, times_per_day=2,
                                                                  duration_days=5)], doctor_name="Dr. Rao, Apollo")
    assert ok_.ok and ok_.data["rx_code"].startswith("RX-")
    assert ph.order(RAHUL, "", "2 strips of Augmentin 625").ok


def test_bad_upload_types_and_sizes_are_refused():
    assert rx.upload(4, "x.exe", "application/x-msdownload", b"MZ").error_code == "invalid_input"
    assert rx.upload(4, "big.pdf", "application/pdf", b"0" * (rx.MAX_UPLOAD + 1)).error_code == "invalid_input"


# ------------------------------------------------------------------ patient safety
def test_listed_allergy_blocks_the_medicine():
    with db.engine.begin() as c:
        c.execute(update(db.patients).where(db.patients.c.id == 4).values(allergies="Amoxicillin"))
    _prescribe(4, "AUGMENTIN", times=2, days=5)
    r = ph.order(RAHUL, RAHUL_DOB, "Augmentin 625")
    assert r.error_code == "allergy" and "amoxicillin" in r.message.lower()


def test_pregnancy_caution_goes_to_the_pharmacist():
    with db.engine.begin() as c:
        c.execute(update(db.patients).where(db.patients.c.id == 3).values(pregnant_until=config.today() + timedelta(days=90)))
    _prescribe(3, "ATORVA10", days=30)
    q = ph.order(PRIYA, PRIYA_DOB, "Atorva 10")
    assert q.ok and q.data["pharmacist_check"]
    placed = ph.order(PRIYA, "", "Atorva 10", confirm="yes")
    assert "pregnancy" in _order(placed.data["order_id"])["review_notes"]


# ------------------------------------------------------------------ pharmacist, money, delivery
def test_pharmacist_rejection_gives_everything_back():
    _prescribe(4, "AZITHRAL", days=3)
    with db.engine.connect() as c:
        stock0 = c.execute(select(db.pharmacy_inventory.c.stock_qty).where(db.pharmacy_inventory.c.medicine_code == "AZITHRAL")).scalar()
    o = ph.order(RAHUL, RAHUL_DOB, "Azithral 500", confirm="yes")
    oid = _order(o.data["order_id"])["id"]
    assert not ph.reject(oid, "", "Pharm. Kavya").ok
    r = ph.reject(oid, "Interaction with a current medicine; please see your doctor", "Pharm. Kavya")
    assert r.ok and _bal(4) == 1800
    with db.engine.connect() as c:
        stock1 = c.execute(select(db.pharmacy_inventory.c.stock_qty).where(db.pharmacy_inventory.c.medicine_code == "AZITHRAL")).scalar()
        st = c.execute(select(db.dispensations.c.status).where(db.dispensations.c.order_id == oid)).scalar()
    assert stock1 == stock0 and st == "void"
    assert "pharmacist" in ph.track(RAHUL, "", o.data["order_id"]).message
    assert ph.order(RAHUL, "", "Azithral 500").ok                                      # the course is available again


def test_credits_are_held_then_captured_at_dispatch():
    o = ph.order(RAHUL, RAHUL_DOB, "Dolo 650", confirm="yes")
    bal = mcp_tools.get_health_credits_balance(phone=RAHUL)
    assert "held for a medicine order" in bal["message"] and bal["data"]["held_credits"] == o.data["credits_used"]
    after = _dispatch(o.data["order_id"])
    assert after["status"] == "dispatched" and after["captured_at"] and after["credits_held"] == 0
    assert "held" not in mcp_tools.get_health_credits_balance(phone=RAHUL)["message"]


def test_reviewed_order_waits_then_ships_after_approval():
    _prescribe(4, "AZITHRAL", days=3)
    o = ph.order(RAHUL, RAHUL_DOB, "Azithral 500", confirm="yes")
    assert _dispatch(o.data["order_id"])["status"] == "awaiting_review"                # never leaves unchecked
    ph.approve(_order(o.data["order_id"])["id"], "Pharm. Kavya")
    out = _dispatch(o.data["order_id"])
    assert out["status"] == "dispatched"
    with db.engine.connect() as c:
        reg = c.execute(select(db.dispensations).where(db.dispensations.c.order_id == out["id"])).mappings().first()
    assert reg["status"] == "dispensed" and reg["schedule_class"] == "H1" and reg["pharmacist"] == "Pharm. Kavya"


def test_unpaid_link_releases_stock_and_credits_after_thirty_minutes():
    r = ph.order(PRIYA, PRIYA_DOB, "5 Gelusil", confirm="yes")
    assert r.data["status"] == "awaiting_payment" and _bal(3) == 0
    with db.engine.begin() as c:
        c.execute(update(db.pharmacy_orders).where(db.pharmacy_orders.c.order_code == r.data["order_id"])
                  .values(created_at=config.now() - timedelta(minutes=31)))
    assert ph.advance()["expired"] == 1
    assert _order(r.data["order_id"])["status"] == "cancelled" and _bal(3) == 400


def _h1_dispatched():
    _prescribe(4, "AZITHRAL", days=3)
    o = ph.order(RAHUL, RAHUL_DOB, "Azithral 500", confirm="yes")
    ph.approve(_order(o.data["order_id"])["id"], "Pharm. Kavya")
    out = _dispatch(o.data["order_id"])
    d = dl.latest(out["id"])
    return o, out, d


def test_h1_parcel_needs_the_delivery_code():
    o, out, d = _h1_dispatched()
    assert d and d["otp_hash"]
    with db.engine.connect() as c:
        sms = c.execute(select(db.notifications.c.body).where(db.notifications.c.template == "delivery_code")).scalar()
    code = sms.split("is ")[1][:4]
    assert dl.apply_event("simulated", "e1", d["provider_job_id"], "delivered", otp="0000" if code != "0000" else "1111").error_code == "code_required"
    assert dl.apply_event("simulated", "e2", d["provider_job_id"], "delivered", otp=code).ok
    assert _order(o.data["order_id"])["status"] == "delivered"


def test_two_missed_deliveries_return_the_parcel_and_refund():
    o, out, d = _h1_dispatched()
    first = dl.apply_event("simulated", "m1", d["provider_job_id"], "failed_attempt")
    assert first.ok and "one more attempt" in first.message
    assert "try again" in ph.track(RAHUL, "", o.data["order_id"]).message
    assert dl.apply_event("simulated", "m1", d["provider_job_id"], "failed_attempt").data["duplicate"]   # applied once
    dl.apply_event("simulated", "m2", d["provider_job_id"], "failed_attempt")
    assert _order(o.data["order_id"])["status"] == "returned" and _bal(4) == 1800
    assert ph.order(RAHUL, "", "Azithral 500").ok                                      # days given back to the course


def test_no_rider_rebooks_once_then_offers_pickup():
    o = ph.order(RAHUL, RAHUL_DOB, "Dolo 650", confirm="yes")
    out = _dispatch(o.data["order_id"])
    d1 = dl.latest(out["id"])
    assert "Rebooked" in dl.apply_event("simulated", "n1", d1["provider_job_id"], "no_rider").message
    d2 = dl.latest(out["id"])
    assert d2["id"] != d1["id"]
    dl.apply_event("simulated", "n2", d2["provider_job_id"], "no_rider")
    assert _order(o.data["order_id"])["status"] == "ready_for_pickup"
    assert "collect" in ph.track(RAHUL, "", o.data["order_id"]).message


# ------------------------------------------------------------------ agent tools
def test_stock_check_tells_the_patient_what_they_may_order():
    r = mcp_tools.check_medicine_stock(medicine_name="Glycomet", phone=RAHUL, date_of_birth=RAHUL_DOB)
    assert r["ok"] and "days left" in r["message"] and "per order" in r["message"]
    dolo = mcp_tools.check_medicine_stock(medicine_name="Dolo 650", phone=RAHUL)
    assert "at most 3 packs per order" in dolo["message"]
    mine = mcp_tools.check_medicine_stock(medicine_name="my prescriptions", phone=RAHUL)
    assert mine["ok"] and mine["message"].startswith("Your active prescriptions") and "Metformin" in mine["message"]
    assert mcp_tools.check_medicine_stock(medicine_name="Dolo 650")["ok"]                # still works without a patient


def test_every_message_stays_small():
    _prescribe(4, "AZITHRAL", days=3)
    for out in (mcp_tools.order_medicine(phone=RAHUL, date_of_birth=RAHUL_DOB, medicine_name="Azithral 500 and Dolo 650"),
                mcp_tools.check_medicine_stock(medicine_name="my prescriptions", phone=RAHUL)):
        assert len(json.dumps(out)) < 2500


# ------------------------------------------------------------------ staff roles and web routes
def _staff(client, role, doctor_id=None):
    from app.security import hash_password
    with db.engine.begin() as c:
        c.execute(db.staff_users.insert().values(username=f"{role}1", full_name=f"Test {role}", role=role, doctor_id=doctor_id,
                                                 password_hash=hash_password("correct horse battery"), active=True,
                                                 created_at=config.now()))
    r = client.post("/api/admin/login", json={"username": f"{role}1", "password": "correct horse battery"})
    assert r.status_code == 200 and r.json()["role"] == role


def test_doctor_can_prescribe_but_not_run_the_admin_console():
    client = TestClient(_app())
    _staff(client, "doctor", doctor_id=11)
    r = client.post("/api/staff/prescriptions", json={"patient_id": 4, "items": [
        {"medicine_code": "AZITHRAL", "dose_units": 1, "times_per_day": 1, "duration_days": 3}]})
    assert r.status_code == 200 and r.json()["rx_code"].startswith("RX-")
    assert client.get("/api/admin/doctors").status_code == 403
    assert client.get("/api/staff/pharmacist/queue").status_code == 403


def test_pharmacist_queue_approve_and_register():
    client = TestClient(_app())
    _staff(client, "pharmacist")
    _prescribe(4, "AZITHRAL", days=3)
    o = ph.order(RAHUL, RAHUL_DOB, "Azithral 500", confirm="yes")
    q = client.get("/api/staff/pharmacist/queue").json()
    assert any(x["order_code"] == o.data["order_id"] for x in q["orders"])
    oid = _order(o.data["order_id"])["id"]
    assert client.post(f"/api/staff/pharmacist/orders/{oid}/approve", json={}).json()["ok"]
    assert client.post("/api/staff/prescriptions", json={"patient_id": 4, "items": []}).status_code == 403
    rules = client.get("/api/staff/drug-rules").json()["rules"]
    assert any(r["ingredient"] == "paracetamol" and not r["signed_off_by"] for r in rules)
    assert client.post("/api/staff/drug-rules/paracetamol", json={"otc_max_mg_per_order": 19500, "sign_off": True}).json()["ok"]
    assert ph.order(RAHUL, "", "3 strips of Dolo 650").error_code == "otc_limit"      # the pharmacist's number now applies


def test_patient_sees_prescriptions_and_uploads_one():
    from app.security import sign_token
    client = TestClient(_app())
    auth = {"Authorization": f"Bearer {sign_token({'pid': 4})}"}
    mine = client.get("/api/me/prescriptions", headers=auth).json()
    assert mine["ok"] and any(i["ingredient"] == "metformin" for i in mine["prescriptions"])
    body = {"file_name": "rx.png", "content_type": "image/png", "data": base64.b64encode(b"\x89PNGfake").decode()}
    up = client.post("/api/me/prescriptions/upload", headers=auth, json=body).json()
    assert up["ok"] and up["upload_code"].startswith("UP-")
    assert client.get("/api/me/prescriptions").status_code == 401


def test_courier_webhook_is_signed_and_applied_once():
    client = TestClient(_app())
    o = ph.order(RAHUL, RAHUL_DOB, "Dolo 650", confirm="yes")
    d = dl.latest(_dispatch(o.data["order_id"])["id"])
    raw = json.dumps({"event_id": "w1", "job_id": d["provider_job_id"], "event": "picked_up"}).encode()
    sig = hmac.new(b"whsec-test", raw, hashlib.sha256).hexdigest()
    assert client.post("/api/webhooks/delivery/simulated", content=raw, headers={"x-signature": "bad"}).status_code == 401
    ok1 = client.post("/api/webhooks/delivery/simulated", content=raw, headers={"x-signature": sig}).json()
    ok2 = client.post("/api/webhooks/delivery/simulated", content=raw, headers={"x-signature": sig}).json()
    assert ok1["ok"] and ok2["data"]["duplicate"]


def _app():
    from app.api import create_app
    return create_app()


def TestClient(app):          # the staff cookie is Secure, so talk to the app over https as the browser does
    from fastapi.testclient import TestClient as _TC
    return _TC(app, base_url="https://testserver")


# ------------------------------------------------------------------ migration
def test_old_database_gains_the_new_columns():
    with db.engine.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS legacy_probe (id INTEGER PRIMARY KEY)"))
    from sqlalchemy import Column, Integer, String, Table
    probe = Table("legacy_probe", db.md, Column("id", Integer, primary_key=True), Column("added_later", String(10)),
                  extend_existing=True)
    try:
        assert "legacy_probe.added_later" in db.add_missing_columns()
        assert db.add_missing_columns() == []
    finally:
        db.md.remove(probe)
