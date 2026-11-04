"""Fast unit tests: input normalisers, envelope, and the core booking/identity rules on a fresh SQLite DB.

Run: MCP_BEARER_TOKEN=test python -m pytest -q
"""

import os
import tempfile
from datetime import date, timedelta

os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.pop("DATABASE_URL", None)

import pytest  # noqa: E402

from app import config, db, seed  # noqa: E402
from app.services import appointments as ap  # noqa: E402
from app.services import patients as pt  # noqa: E402
from app.services import ref  # noqa: E402
from app.util import (Result, norm_code, norm_phone, parse_date, parse_dob, parse_time, spoken_code)  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def data():
    seed.reset(verbose=False)
    ref.load()


@pytest.mark.parametrize("raw,want", [
    ("98450 12345", "+919845012345"), ("+91-9845012345", "+919845012345"), ("09845012345", "+919845012345"),
    ("919845012345", "+919845012345"), ("12345", None), ("", None), ("5845012345", None)])
def test_phone(raw, want):
    assert norm_phone(raw) == want


def test_dates():
    base = date(2026, 11, 3)  # a Tuesday
    assert parse_date("tomorrow", base) == date(2026, 11, 4)
    assert parse_date("2026-11-04", base) == date(2026, 11, 4)
    assert parse_date("4 Nov", base) == date(2026, 11, 4)
    assert parse_date("Nov 4th", base) == date(2026, 11, 4)
    assert parse_date("wednesday", base) == date(2026, 11, 4)
    assert parse_date("friday", base) == date(2026, 11, 6)
    assert parse_date("1 Jan", base) == date(2027, 1, 1)
    assert parse_date("in 3 days", base) == date(2026, 11, 6)
    assert parse_date("banana", base) is None


@pytest.mark.parametrize("raw,want", [("10:30", "10:30"), ("10:30 AM", "10:30"), ("10.30am", "10:30"), ("2 pm", "14:00"),
                                      ("1430", "14:30"), ("noon", "12:00"), ("later", None)])
def test_time(raw, want):
    assert parse_time(raw) == want


def test_dob_and_codes():
    assert parse_dob("4 March 1958") == date(1958, 3, 4)
    assert parse_dob("04/03/1958") == date(1958, 3, 4)
    assert norm_code("cl 48213", "WN") == "WN-48213"
    assert norm_code("CH4821", "WN") == "WN-4821"
    assert spoken_code("WN-48213") == "W N 4 8 2 1 3"


def test_envelope_is_small_and_clean():
    r = Result(True, "ok", {"a": None, "b": [], "c": list(range(500))}).as_dict()
    assert "a" not in r["data"] and "b" not in r["data"]
    import json
    assert len(json.dumps(r)) <= 2000


def test_identity_is_server_side_and_generic():
    good = pt.verify("9845000002", "1992-06-15")
    assert good.ok and good.data["name"] == "Arjun Mehta"
    bad = pt.verify("9845000002", "1990-01-01")
    unknown = pt.verify("9845099999", "1990-01-01")
    assert not bad.ok and bad.message == unknown.message  # never reveals whether the number exists


def test_cancel_needs_owner():
    shan = pt.verify("9845000001", "1959-03-04").data["upcoming"][0]["booking_id"]
    r = ap.cancel(shan, "9845000002", "1992-06-15")
    assert not r.ok and r.error_code == "not_allowed"
    r = ap.cancel(shan, "9845000001", "")
    assert not r.ok and r.error_code == "not_verified"


def test_double_booking_is_impossible():
    d = config.today() + timedelta(days=1)
    while d.isoweekday() == 7:
        d += timedelta(days=1)
    s = ap.find_slots(d.isoformat(), department="General Medicine")
    doc = next(x for x in s.data["doctors"] if x["free_slots"])
    t = parse_time(doc["free_slots"][0])
    a = ap.book("9845000004", d.isoformat(), t, doctor_name=doc["name"])
    b = ap.book("9845000003", d.isoformat(), t, doctor_name=doc["name"])
    assert a.ok and not b.ok and b.error_code == "slot_taken"
    again = ap.book("9845000004", d.isoformat(), t, doctor_name=doc["name"])
    assert again.ok and again.data["booking_id"] == a.data["booking_id"]


def test_cancel_offers_slot_to_waitlist():
    shan = pt.verify("9845000001", "1959-03-04").data["upcoming"][0]["booking_id"]
    r = ap.cancel(shan, "9845000001", "1959-03-04")
    assert r.ok and r.data["offered_to_waitlist"]
    offer = pt.verify("9845000002", "1992-06-15").data["open_offer"]
    assert offer and offer["doctor"] == "Dr. Rajesh Iyer"
    assert ap.accept_offer(offer["offer_code"], "9845000002").ok
    assert not ap.accept_offer(offer["offer_code"], "9845000003").ok


def test_db_schema_has_double_booking_guard():
    idx = {i.name for i in db.appointments.indexes}
    assert "uq_doctor_slot_booked" in idx


def test_fake_addresses_are_never_emailed():
    from sqlalchemy import select
    from app import notify
    with db.engine.begin() as c:
        notify.queue(c, patient_id=None, channel="email", template="t", to="someone.1@example.com", subject="s", body="b", dedupe_key="fake-1")
        notify.queue(c, patient_id=None, channel="email", template="t", to="real.person@gmail.com", subject="s", body="b", dedupe_key="real-1")
        rows = dict(c.execute(select(db.notifications.c.dedupe_key, db.notifications.c.status)
                              .where(db.notifications.c.dedupe_key.in_(["fake-1", "real-1"]))).all())
    assert rows == {"fake-1": "simulated", "real-1": "queued"}


def test_rate_limiter_blocks_after_limit():
    from app import ratelimit
    ip = "203.0.113.9"
    results = [ratelimit.hit("login", ip) for _ in range(12)]
    assert results[:10] == [True] * 10 and results[10:] == [False, False]
    assert ratelimit.client_ip({"x-forwarded-for": "198.51.100.7, 10.0.0.1"}) == "198.51.100.7"


def test_api_login_rate_limited_and_headers():
    from fastapi.testclient import TestClient
    from app.api import create_app
    c = TestClient(create_app())
    h = {"x-forwarded-for": "192.0.2.44"}
    codes = [c.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"}, headers=h).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    r = c.get("/health")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"] and r.headers["x-frame-options"] == "DENY"


def test_store_falls_back_to_memory_when_redis_is_down(monkeypatch):
    from app import config
    from app import store as st
    monkeypatch.setattr(config, "REDIS_URL", "redis://127.0.0.1:1/0")   # nothing listens there
    s = st.Store()
    assert "down" in s.status
    s.set_json("t:x", {"a": 1}, 60)
    assert s.get_json("t:x") == {"a": 1}


def test_blackboard_registry_and_levels():
    from app.services import blackboard as bb
    bb.put_snapshot("9845000002", {"name": "Arjun"})
    bb.add("9845000002", "coverage", "Star covers MRI.", 1, "MRI-KNEE")
    reg = bb.registry("9845000002")
    assert reg["snapshot"]["state"] == "READY" and reg["snapshot"]["level"] == "P1"
    assert reg["coverage"]["level"] == "P0"
    assert bb.related("98450 00002", ref="MRI-KNEE")[0]["kind"] == "coverage"
    bb.invalidate("9845000002")
    assert bb.get_snapshot("9845000002") is None and bb.registry("9845000002")["snapshot"]["state"] == "MISSING"


def test_events_are_processed_in_process():
    import time
    from app import events
    seen = []
    events.on("test.ping")(lambda e: seen.append(e["n"]))
    events.start_workers()
    events.publish("test.ping", n=7)
    for _ in range(50):
        if seen:
            break
        time.sleep(0.05)
    assert seen == [7]


def test_waitlist_accept_survives_booking_code_clash(monkeypatch):
    """Regression: accept_offer picked a random WN- code without checking it, so ~8% of accepts failed as 'slot taken'."""
    from sqlalchemy import select
    with db.engine.connect() as c:
        existing = c.execute(select(db.appointments.c.booking_code).where(db.appointments.c.booking_code.isnot(None))).first()[0]
    codes = iter([existing, existing, "WN-99998"])
    orig = pt.random_code
    monkeypatch.setattr(pt, "random_code", lambda prefix, n=5: next(codes, None) or orig(prefix, n))
    from app.services import blackboard as bb
    seed.reset(verbose=False)
    ref.load()
    bb.clear_all()                      # as /ops/reset-demo does: drop snapshots cached by earlier tests
    shan = pt.verify("9845000001", "1959-03-04").data["upcoming"][0]["booking_id"]
    assert ap.cancel(shan, "9845000001", "1959-03-04").ok
    offer = pt.verify("9845000002", "1992-06-15").data["open_offer"]
    r = ap.accept_offer(offer["offer_code"], "9845000002")
    assert r.ok and r.data["booking_id"] == "WN-99998"


def test_unknown_doctor_is_not_silently_swapped():
    """Regression (Talkdesk test, 3 Nov): 'Dr. Samarth Gowda' (no such doctor) was matched to Dr. Harish Gowda."""
    r = ap.find_slots("tomorrow", doctor_name="Dr. Samarth Gowda")
    assert not r.ok and r.error_code == "not_found"
    assert "don't have a Dr. Samarth Gowda" in r.message and "Harish Gowda" in r.message
    from app.services import records
    g = records.get_doctors(doctor_name="Samarth Gowda")
    assert not g.ok and "Harish Gowda" in g.message


def test_doctor_names_still_forgiving():
    from app.services.ref import find_doctors
    assert [d["name"] for d in find_doctors("Iyer")] == ["Dr. Rajesh Iyer"]
    assert [d["name"] for d in find_doctors("rajesh iyyer")] == ["Dr. Rajesh Iyer"]      # typo
    assert [d["name"] for d in find_doctors("Dr Harish Gowda")] == ["Dr. Harish Gowda"]
    assert find_doctors("Samarth Gowda") == []


def test_eval_fixes_3nov(monkeypatch):
    """Regressions from the Talkdesk 100-scenario evaluation (3 Nov)."""
    from app.services import blackboard as bb, records
    from app import search
    seed.reset(verbose=False); ref.load(); bb.clear_all(); search.sync_kb(); search.sync()
    # 008: "book Dr. X on his next consulting day" -> earliest free day, no date needed
    r = ap.find_slots("next available", doctor_name="Dr. Harish Gowda")
    assert r.ok and r.data["date_iso"] and r.data["doctors"][0]["free_slots"]
    assert ap.find_slots("", doctor_name="Dr. Harish Gowda").ok
    # 011: include_past shows upcoming AND past (also for seniors, whose replies are shortened)
    r = ap.find_appointments("9845000001", "1959-03-04", include_past="true")
    assert "WN-48213" in r.message and r.data["past_visits"]
    assert "recent visits" in r.message.lower()
    # 093: the waitlist entry comes with verify's data (read out by find_appointments, not unasked by verify)
    assert pt.verify("9845000002", "1992-06-15").data["waitlist"]
    # 081/082/044-style FAQ questions in the caller's words; unknown questions are not answered with random facts
    assert "blood bank" in records.hospital_info("can I donate blood").message.lower()
    assert "cafeteria" in records.hospital_info("where can I grab a bite to eat").message.lower()
    assert "security desk" in records.hospital_info("I lost my phone in the waiting area").message.lower()
    assert records.hospital_info("what is the cricket score today").data.get("found") is False
    assert "Outer Ring Road" in records.hospital_info("where are you located").message


def test_eval_fixes_v3():
    """Regressions from the v3 evaluation dataset replay (3 Nov)."""
    from app.services import blackboard as bb
    seed.reset(verbose=False); ref.load(); bb.clear_all()
    # Booking agent carries 'next available' from find_available_slots into book_appointment: book that same day
    s = ap.find_slots("next available", doctor_name="Dr. Harish Gowda")
    t = parse_time(s.data["doctors"][0]["free_slots"][0])
    b = ap.book("9845000003", "next available", t, doctor_name="Dr. Harish Gowda", date_of_birth="1997-01-20")
    assert b.ok and b.data["date_iso"] == s.data["date_iso"]
    # Dr. Rajesh Iyer stays fully booked for the coming week (waitlist demo): no cancelled holes
    iyer = ref.find_doctor("Rajesh Iyer")
    for k in range(1, 8):
        assert not ap.free_for_doctors(db.engine.connect(), [iyer], config.today() + timedelta(days=k)).get(iyer["id"])
    # one find_appointments reply answers "my appointments", "my last visit" and "am I on the waitlist"
    r = ap.find_appointments("9845000002", "1992-06-15")
    assert "waitlist" in r.message and r.data["waitlist"]
    assert "last visit" in ap.find_appointments("9845000001", "1959-03-04").message
    assert "waitlist" in ap.accept_offer("ZZZZ9999QQ", "9845000002").message
    from app.services import records
    assert "Kannada" in records.get_doctors(department="Cardiology").message


def test_ops_benchmark_compares_architecture():
    from fastapi.testclient import TestClient
    from app.api import create_app
    from app.services import blackboard as bb
    seed.reset(verbose=False); ref.load(); bb.clear_all()
    c = TestClient(create_app())
    assert c.get("/api/ops/benchmark?n=3").status_code == 401
    r = c.get(f"/api/ops/benchmark?n=3&token={config.DASHBOARD_TOKEN}").json()
    ctx = r["patient_context_5_patients"]
    assert ctx["wellnest_redis_blackboard"]["p50_ms"] < ctx["plain_mcp_rebuild_from_db"]["p50_ms"]
    assert any("pre-approval" in f for f in r["context_carried_between_agents"]["facts_in_next_reply"])


def test_hospital_policies_and_redis_answer_cache(tmp_path):
    from app import kb, search
    from app.services import blackboard as bb, hospital_ctx, records
    seed.reset(verbose=False); ref.load(); bb.clear_all(); search.sync_kb()
    hospital_ctx.publish(kb.documents())
    assert hospital_ctx.profile()["passages_by_kind"]["policy"] >= 10
    q = "Can I smoke in the parking area?"
    first = records.hospital_info(q)
    assert "no smoking" in first.message.lower() and first.data["matched_by"] != "redis cache"
    assert records.hospital_info(q).data["matched_by"] == "redis cache"
    (tmp_path / "rules.md").write_text("## Pets\nPets are not allowed, except guide dogs.\n")
    docs = kb.hospital_documents(tmp_path)
    assert docs[-1]["ref"] == "kb:doc:rules:pets" and "guide dogs" in docs[-1]["body"]
