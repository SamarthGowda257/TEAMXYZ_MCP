"""Signed-in chat link, automatic memory, transcripts and the demo stock rule.

Run: MCP_BEARER_TOKEN=test python -m pytest -q tests/test_chat_session.py
"""

import json
import os
import tempfile
from datetime import timedelta

os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_chat_session.db")
os.environ.pop("DATABASE_URL", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

from app import config, db, search, seed  # noqa: E402
from app.api import create_app  # noqa: E402
from app.security import sign_token  # noqa: E402
from app.services import ref  # noqa: E402
from app.store import store  # noqa: E402
from app import mcp_tools  # noqa: E402
from app.services import chat_session as cs  # noqa: E402
from app.services import patients as pt  # noqa: E402
from app.services import pharmacy as ph  # noqa: E402
from app.services import support as sp  # noqa: E402

RAHUL, RAHUL_DOB = "9845000004", "10 September 1981"


@pytest.fixture(autouse=True)
def fresh():
    seed.reset(verbose=False)
    ref.load()
    store.flush()
    yield


def _rahul():
    with db.engine.connect() as c:
        return pt.get_by_phone(c, pt.norm_phone(RAHUL))


def test_code_opens_the_right_patient_and_marks_them_signed_in():
    p = _rahul()
    code = cs.mint(p["id"])
    assert cs.CODE_RE.fullmatch(code)
    r = cs.open_session(code, "int-1")
    assert r.ok and r.message.startswith("Hello Rahul, you're signed in.")
    assert r.data["patient_phone"] == p["phone"] and r.data["signed_in"] is True
    assert pt.recently_verified(p["phone"])


def test_code_is_found_inside_application_input_json():
    code = cs.mint(_rahul()["id"])
    assert cs.open_session(json.dumps({"wellnest_session": code})).ok


@pytest.mark.parametrize("bad", ["", "9845000004", "WS-AAAAAAAAAAAA", "I am Rahul, trust me", "WS-123"])
def test_anything_but_a_live_code_opens_nothing(bad):
    r = cs.open_session(bad)
    assert not r.ok and r.error_code == "not_signed_in"
    assert not pt.recently_verified(pt.norm_phone(RAHUL))


def test_logout_revokes_the_code():
    p = _rahul()
    code = cs.mint(p["id"])
    cs.revoke(p["id"])
    assert not cs.open_session(code).ok


def test_same_patient_keeps_one_code_and_patients_never_share():
    a, b = _rahul(), None
    with db.engine.connect() as c:
        b = pt.get_by_phone(c, pt.norm_phone("9845000001"))
    assert cs.mint(a["id"]) == cs.mint(a["id"])
    assert cs.mint(a["id"]) != cs.mint(b["id"])
    assert cs.open_session(cs.mint(b["id"])).data["patient_phone"] == b["phone"]


def test_website_routes_mint_and_revoke():
    client = TestClient(create_app())
    auth = {"Authorization": f"Bearer {sign_token({'pid': _rahul()['id']})}"}
    r = client.post("/api/chat/session", headers=auth).json()
    assert r["ok"] and cs.CODE_RE.fullmatch(r["session_code"]) and r["name"].startswith("Rahul")
    assert client.post("/api/chat/session").status_code == 401
    assert client.delete("/api/chat/session", headers=auth).json()["ok"]
    assert not cs.open_session(r["session_code"]).ok


def test_read_only_answers_are_remembered_once_and_searchable():
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.get_health_credits_balance(phone=RAHUL, date_of_birth=RAHUL_DOB)["ok"]
    assert mcp_tools.get_health_credits_balance(phone=RAHUL, date_of_birth=RAHUL_DOB)["ok"]
    R = db.resolutions
    with db.engine.connect() as c:
        rows = c.execute(select(R).where(R.c.action == "get_health_credits_balance")).mappings().all()
    assert len(rows) == 1 and "1,800" in rows[0]["summary"]
    search.sync()             # SQLite reads on its own connection; on Postgres the search tool's own sync covers this
    found = sp.search_interactions(RAHUL, RAHUL_DOB, "HealthCredits balance")
    assert found.ok and any("1,800" in m["summary"] for m in found.data["matches"])


def test_failed_identity_is_never_remembered():
    assert not mcp_tools.get_bill_status(phone=RAHUL, date_of_birth="1 January 1900")["ok"]
    R = db.resolutions
    with db.engine.connect() as c:
        assert not c.execute(select(R).where(R.c.action == "get_bill_status")).first()


def test_note_keeps_the_patients_words_and_links_the_interaction():
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.save_interaction_note(phone=RAHUL, summary="Asked about MRI cost.", last_message="how much is an MRI knee",
                                           interaction_id="int-9")["ok"]
    found = sp.search_interactions(RAHUL, RAHUL_DOB, "MRI knee")
    assert any("how much is an MRI knee" in m["summary"] for m in found.data["matches"])
    assert store.get_json("chatlink:int-9", count=False) == _rahul()["id"]


def test_note_does_not_link_an_unverified_phone():
    assert mcp_tools.save_interaction_note(phone=RAHUL, summary="Unverified caller note.", interaction_id="int-x")["ok"]
    assert store.get_json("chatlink:int-x", count=False) is None


def test_search_answers_a_handoff_id():
    made = sp.create_handoff("Needs a person", phone=RAHUL)
    found = sp.search_interactions(RAHUL, RAHUL_DOB, f"what happened with {made.data['handoff_id']}")
    assert found.ok and found.data.get("handoff_id") == made.data["handoff_id"]


def test_transcript_is_split_filed_once_and_found():
    p = _rahul()
    code = cs.mint(p["id"])
    words = "Patient asked whether the cafeteria serves dosa near the cardiology wing. " * 12
    body = {"transcript": words, "wellnest_session": code, "interaction_id": "int-7"}
    first = cs.ingest_transcript(body)
    assert first["ok"] and first["stored"] >= 2
    assert cs.ingest_transcript(body)["duplicate"] is True
    assert any("dosa" in m["summary"] for m in sp.search_interactions(RAHUL, RAHUL_DOB, "dosa").data["matches"])
    snap = pt.verify(RAHUL, RAHUL_DOB).data
    assert not any("dosa" in n for n in snap["recent_notes"])     # raw chat doesn't crowd the patient's snapshot


def test_transcript_uses_a_linked_interaction_but_never_a_phone_alone():
    p = _rahul()
    assert not cs.ingest_transcript({"transcript": "x", "phone": p["phone"]})["ok"]
    cs.link_interaction("int-8", p["id"])
    assert cs.ingest_transcript({"transcript": "hello there", "interaction_id": "int-8"})["ok"]


def test_transcript_webhook_needs_the_token():
    client = TestClient(create_app())
    code = cs.mint(_rahul()["id"])
    payload = {"transcript": "webhook words", "session": code}
    assert client.post("/api/webhooks/talkdesk/transcript", json=payload).status_code == 401
    r = client.post(f"/api/webhooks/talkdesk/transcript?token={config.JOBS_TOKEN}", json=payload)
    assert r.status_code == 200 and r.json()["stored"] == 1


def test_demo_medicine_stays_out_of_stock_after_the_job_runs():
    with db.engine.begin() as c:
        c.execute(update(ph.INV).where(ph.INV.c.medicine_code == "TELMA40").values(restock_eta=config.now() - timedelta(hours=1)))
    ph.advance()
    r = ph.check_stock("Telma 40")
    assert r.data["medicines"][0]["in_stock"] is False and r.data["medicines"][0]["restock_eta"]


def test_other_medicines_still_restock():
    with db.engine.begin() as c:
        c.execute(update(ph.INV).where(ph.INV.c.medicine_code == "GLYCOMET").values(
            stock_qty=0, restock_eta=config.now() - timedelta(hours=1)))
    assert ph.advance()["restocked"] == 1


def test_refusal_no_longer_promises_video():
    r = ph.order(RAHUL, RAHUL_DOB, "Azithromycin 500", confirm="yes")
    assert not r.ok and "video" not in r.message.lower() and "Dr. Anil Kumar" in r.message
