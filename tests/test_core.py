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
    assert norm_code("cl 48213", "CL") == "CL-48213"
    assert norm_code("CH4821", "CL") == "CL-4821"
    assert spoken_code("CL-48213") == "C L 4 8 2 1 3"


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
