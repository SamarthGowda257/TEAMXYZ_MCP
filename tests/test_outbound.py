"""Autonomous outbound calls: queueing, dedupe, the Talkdesk Flows API request, flow events, retries, opt-out
and the Outreach agent's tools. Talkdesk itself is replaced by a fake HTTP layer; everything else is real.

Run: MCP_BEARER_TOKEN=test python -m pytest -q tests/test_outbound.py
"""

import os
import tempfile
from datetime import timedelta

os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_outbound.db")
os.environ.pop("DATABASE_URL", None)

import pytest  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

from app import config, db, seed, talkdesk  # noqa: E402
from app.services import outbound as ob  # noqa: E402
from app.services import ref  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    seed.reset(verbose=False)
    ref.load()
    monkeypatch.setattr(config, "OUTBOUND_CALL_HOURS", (0, 24))


def _call(code):
    with db.engine.connect() as c:
        return dict(c.execute(select(db.outbound_calls).where(db.outbound_calls.c.call_code == code)).mappings().first())


def test_reminder_call_simulated_then_confirm_by_keypress():
    r = ob.trigger("WN-48213")
    assert r["ok"] and r["status"] == "simulated"
    say = ob.handle_event(r["call_id"], "answered")
    assert say["action"] == "ask" and "Dr. Rajesh Iyer" in say["say"] and "press 1" in say["say"].lower()
    done = ob.handle_event(r["call_id"], "choice", "1")
    assert done["outcome"] == "confirmed" and "confirmed" in done["say"] and done["action"] == "end"
    assert _call(r["call_id"])["status"] == "completed"


def test_spoken_answer_and_unknown_answer():
    r = ob.trigger("WN-48213")
    assert ob.handle_event(r["call_id"], "choice", "umm what?")["action"] == "repeat"
    assert ob.handle_event(r["call_id"], "choice", "I want to change it please")["outcome"] == "reschedule_requested"


def test_talkdesk_request_is_sent_with_string_inputs(monkeypatch):
    sent = {}

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._b, self.text = code, body, str(body)

        def json(self):
            return self._b

    def fake_post(url, **kw):
        if url.endswith("/oauth/token"):
            assert kw["data"]["grant_type"] == "client_credentials" and kw["data"]["scope"] == "flows-interactions:start"
            return Resp(200, {"access_token": "tok", "expires_in": 600})
        sent.update(url=url, body=kw["json"], auth=kw["headers"]["Authorization"])
        return Resp(202, {"interaction_id": "int-123", "flow_version_id": "v", "flow_execution_id": "e"})

    for k, v in {"OUTBOUND_ENABLED": True, "TALKDESK_ACCOUNT": "acme", "TALKDESK_CLIENT_ID": "id",
                 "TALKDESK_CLIENT_SECRET": "secret", "TALKDESK_OUTBOUND_FLOW_ID": "flow-1",
                 "OUTBOUND_TEST_NUMBER": "+12184437744"}.items():
        monkeypatch.setattr(config, k, v)
    talkdesk._token.update(value="", expires=0)
    monkeypatch.setattr(talkdesk.httpx, "post", fake_post)
    r = ob.trigger("WN-48213")
    assert r["status"] == "dialing" and r["interaction_id"] == "int-123"
    assert sent["url"].endswith("/flows/flow-1/interactions") and sent["auth"] == "Bearer tok"
    body = sent["body"]
    assert body["patient_phone"] == "+12184437744" and body["call_id"] == r["call_id"]
    assert all(isinstance(v, str) for v in body.values()) and "Dr. Rajesh Iyer" in body["prompt"]
    assert ob.trigger("WN-48213")["ok"] is False                # one live call per booking at a time


def test_no_answer_retries_then_gives_up(monkeypatch):
    monkeypatch.setattr(config, "OUTBOUND_MAX_ATTEMPTS", 2)
    r = ob.trigger("WN-48213")
    code = r["call_id"]
    with db.engine.begin() as c:                              # pretend Talkdesk was dialling this attempt
        c.execute(update(db.outbound_calls).where(db.outbound_calls.c.call_code == code).values(status="dialing"))
    assert ob.handle_event(code, "no_answer")["status"] == "retry"
    row = _call(code)
    assert row["status"] == "retry" and row["next_attempt_at"] > config.now()
    with db.engine.begin() as c:
        c.execute(update(db.outbound_calls).where(db.outbound_calls.c.call_code == code)
                  .values(next_attempt_at=config.now() - timedelta(minutes=1)))
    ob.dispatch()                                              # second attempt
    assert _call(code)["attempts"] == 2
    ob.handle_event(code, "busy")
    assert _call(code)["status"] == "failed" and _call(code)["outcome"] == "unreachable"


def test_opt_out_stops_future_calls():
    r = ob.trigger("WN-48213")
    assert ob.handle_event(r["call_id"], "choice", "9")["outcome"] == "opted_out"
    assert ob.trigger("WN-48213") == {"ok": False, "error": "patient opted out of calls"}


def test_follow_up_needs_help_alerts_nurse():
    with db.engine.connect() as c:
        a = c.execute(select(db.appointments).where(db.appointments.c.patient_id == 3, db.appointments.c.status == "completed",
                                                    db.appointments.c.doctor_id.is_not(None))).mappings().first()
    r = ob.trigger(a["booking_code"], "post_visit_followup")
    assert "feeling better" in ob.handle_event(r["call_id"], "answered")["say"]
    assert "nurse" in ob.handle_event(r["call_id"], "choice", "2")["say"]
    with db.engine.connect() as c:
        assert c.execute(select(db.nurse_alerts).where(db.nurse_alerts.c.patient_id == 3)).first()


def test_planner_is_idempotent_and_respects_allowlist(monkeypatch):
    monkeypatch.setattr(config, "OUTBOUND_ALLOWLIST", ["*"])
    first = ob.plan()
    assert first > 0 and ob.plan() == 0                        # same events never queued twice
    monkeypatch.setattr(config, "OUTBOUND_ALLOWLIST", ["+910000000000"])
    seed.reset(verbose=False)
    assert ob.plan() == 0


def test_outreach_tools_after_transfer():
    r = ob.trigger("WN-48213")
    assert ob.handle_event(r["call_id"], "choice", "3")["action"] == "transfer"
    ctx = ob.context_for("98450 00001")
    assert ctx.ok and ctx.data["booking_id"] == "WN-48213" and "confirm" in ctx.message
    assert ob.confirm("WN-48213", "9845000001").ok                 # we called them about it: no birth date needed
    assert ob.confirm("WN-48213", "9845000002").error_code == "not_allowed"
    out = ob.record_outcome("9845000001", "confirmed", "Patient confirmed with the assistant.")
    assert out.ok and _call(r["call_id"])["outcome"] == "confirmed"


def test_waitlist_offer_call_books_the_slot_by_keypress():
    from app.services import appointments as ap
    assert ap.cancel("WN-48213", "9845000001", "1959-03-04").data.get("offered_to_waitlist")
    assert ob.plan() >= 1
    with db.engine.connect() as c:
        row = c.execute(select(db.outbound_calls).where(db.outbound_calls.c.kind == "waitlist_offer")).mappings().first()
    ob.dispatch()
    assert "held for you" in ob.handle_event(row["call_code"], "answered")["say"]
    booked = ob.handle_event(row["call_code"], "choice", "book it")
    assert booked["outcome"] == "offer_accepted" and "WN-" in booked["say"]


def test_lab_report_call_emails_link_and_agent_schedules_call_back():
    ob.plan()
    with db.engine.connect() as c:
        row = c.execute(select(db.outbound_calls).where(db.outbound_calls.c.dedupe_key == "report:LR-20931")).mappings().first()
    assert row and row["patient_id"] == 3
    ob.dispatch()
    assert "never read results" in ob.handle_event(row["call_code"], "answered")["say"]
    assert "pr***@" in ob.handle_event(row["call_code"], "choice", "1")["say"]
    later = ob.record_outcome("9845000003", "call_back_later", "Busy now.", call_back_at="tomorrow at 5 pm")
    assert later.ok and "5:00 PM" in later.message and later.data["call_back_id"].startswith("OC-")
