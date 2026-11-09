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
    # the details are said in the reply: only text in the conversation reaches the next Talkdesk agent
    assert "won't need to type your mobile number or date of birth" in r.message
    assert "9845000004" not in r.message and code not in r.message      # nothing private or internal is said
    assert r.data["chat_id"] == code
    # both identity values reach the agent, so a specialist can call any tool without asking
    assert r.data["date_of_birth"] == "10-09-1981"
    bal = mcp_tools.get_health_credits_balance(phone=r.data["patient_phone"], date_of_birth=r.data["date_of_birth"])
    assert bal["ok"], bal["message"]
    assert len(json.dumps(mcp_tools.open_signed_in_session(session_code=code))) < 1400


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


def test_caller_id_names_the_patient_but_does_not_verify():
    r = mcp_tools.recognise_caller(caller_id="+91 98450 00004")
    assert r["ok"] and r["data"]["patient_phone"] == pt.norm_phone(RAHUL) and r["data"]["verified"] is False
    assert "Am I speaking with Rahul" in r["message"] and "date of birth" in r["message"]
    assert not pt.recently_verified(pt.norm_phone(RAHUL))


def test_caller_id_after_verification_skips_the_questions():
    pt.remember_verified(pt.norm_phone(RAHUL))
    r = mcp_tools.recognise_caller(caller_id="919845000004")
    assert r["data"]["verified"] is True and "don't ask" in r["message"]


@pytest.mark.parametrize("cid,code", [("", "no_caller_id"), ("anonymous", "no_caller_id")])
def test_no_caller_id_falls_back_to_asking(cid, code):
    r = mcp_tools.recognise_caller(caller_id=cid)
    assert not r["ok"] and r["error_code"] == code


def test_unregistered_caller_is_offered_registration():
    r = mcp_tools.recognise_caller(caller_id="9000011111")
    assert r["ok"] and r["data"]["registered"] is False and "register" in r["message"]


def test_visit_history_also_mentions_recent_requests():
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.save_interaction_note(phone=RAHUL, summary="Ordered Telma 40 for home delivery.")["ok"]
    r = mcp_tools.get_visit_history(phone=RAHUL)
    assert r["ok"] and "Telma 40" in r["message"] and r["data"]["recent_activity"]
    assert len(json.dumps(r)) < 1400


def test_refund_asks_before_moving_money():
    pt.remember_verified(pt.norm_phone(RAHUL))
    q = mcp_tools.request_credits_refund(phone=RAHUL, amount="200")
    assert q["ok"] and q["data"]["needs_confirmation"] and "Shall I refund" in q["message"]
    assert "1,800" in mcp_tools.get_health_credits_balance(phone=RAHUL)["message"]
    done = mcp_tools.request_credits_refund(phone=RAHUL, amount="200", confirm="yes")
    assert done["ok"] and done["data"]["refund_id"].startswith("RF-") and done["data"]["balance_credits"] == 1600


def test_refund_yes_without_amount_refunds_only_what_was_offered():
    """Live bug: the 'yes' turn reached the server without the amount and the whole balance was refunded."""
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.request_credits_refund(phone=RAHUL, amount="50")["data"]["amount_inr"] == 50
    done = mcp_tools.request_credits_refund(phone=RAHUL, confirm="yes")
    assert done["data"]["refund_id"].startswith("RF-") and done["data"]["amount_inr"] == 50
    assert done["data"]["balance_credits"] == 1750


def test_refund_yes_with_nothing_offered_only_asks():
    pt.remember_verified(pt.norm_phone(RAHUL))
    first = mcp_tools.request_credits_refund(phone=RAHUL, amount="100", confirm="yes")
    assert first["data"]["needs_confirmation"] and "1,800" in mcp_tools.get_health_credits_balance(phone=RAHUL)["message"]
    other = mcp_tools.request_credits_refund(phone=RAHUL, amount="300", confirm="yes")     # a different amount: ask again
    assert other["data"]["needs_confirmation"] and other["data"]["amount_inr"] == 300
    done = mcp_tools.request_credits_refund(phone=RAHUL, amount="300", confirm="yes")
    assert done["data"]["refund_id"].startswith("RF-") and done["data"]["balance_credits"] == 1500


@pytest.mark.parametrize("q", ["What did I ask you in my last chat?", "what did we talk about before", "anything earlier?"])
def test_last_chat_questions_return_the_latest_conversation(q):
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.save_interaction_note(phone=RAHUL, summary="Asked for a refund of 200 HealthCredits.")["ok"]
    search.sync()
    r = sp.search_interactions(RAHUL, "", q)
    assert r.ok and "refund of 200" in r.message and r.data["matched_topic"]


def test_unmatched_topic_still_shows_recent_history():
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.save_interaction_note(phone=RAHUL, summary="Asked about parking near the main gate.")["ok"]
    search.sync()
    r = sp.search_interactions(RAHUL, "", "zebra crossing helicopter")
    assert r.ok and r.message.startswith("I don't see one on that exact topic") and r.data["matched_topic"] is False


def test_support_tool_recognises_a_phone_caller_without_a_session():
    r = mcp_tools.open_signed_in_session(session_code="", caller_id="+919845000004")
    assert r["ok"] and r["data"]["patient_phone"] == pt.norm_phone(RAHUL) and r["data"]["verified"] is False
    assert not pt.recently_verified(pt.norm_phone(RAHUL))


def test_session_code_wins_over_caller_id_and_chat_without_either_fails():
    code = cs.mint(_rahul()["id"])
    assert mcp_tools.open_signed_in_session(session_code=code, caller_id="9845000001")["data"]["signed_in"] is True
    assert mcp_tools.open_signed_in_session(session_code="", caller_id="chat-contact-abc")["error_code"] == "not_signed_in"


def test_past_orders_are_found_by_condition():
    """Live: 'Have I ever ordered anything for my diabetes?' answered 'no' after a Glycomet order."""
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.order_medicine(phone=RAHUL, medicine_name="2 strips of Glycomet")["data"]["quote"]
    placed = mcp_tools.order_medicine(phone=RAHUL, medicine_name="2 strips of Glycomet", confirm="yes")
    assert placed["ok"], placed["message"]
    code = placed["data"]["order_id"]
    h = mcp_tools.get_visit_history(phone=RAHUL)
    assert h["ok"] and code in h["message"] and "for diabetes" in h["message"]
    assert len(json.dumps(h)) < 1800
    search.sync()
    r = sp.search_interactions(RAHUL, "", "Have I ever ordered anything for my diabetes?")
    assert r.ok and code in r.message


def _cal_rows(ref_):
    with db.engine.connect() as c:
        return c.execute(select(db.notifications).where(db.notifications.c.channel == "calendar",
                                                        db.notifications.c.to_address == ref_)).mappings().all()


def test_unchanged_calendar_event_is_not_synced_again(monkeypatch):
    """Live: reminder jobs re-queued the same Google sync every minute (647 rows in 25 minutes)."""
    from datetime import datetime
    from app import google
    from app.services import calendar as cal
    monkeypatch.setattr(google, "configured", lambda: True)
    p = _rahul()
    kw = dict(ref="refill-rx:test", patient=p, kind="refill", title="Refill alert", starts_at=datetime(2026, 11, 9, 9),
              minutes=0, all_day=True, details="Reorder")
    for _ in range(3):
        with db.engine.begin() as c:
            cal.upsert(c, **kw)
    assert len(_cal_rows("refill-rx:test")) == 1
    with db.engine.begin() as c:
        cal.upsert(c, **dict(kw, title="Refill alert (changed)"))
    assert len(_cal_rows("refill-rx:test")) == 2


def test_emails_go_before_calendar_and_old_syncs_are_skipped(monkeypatch):
    from app import google, notify
    monkeypatch.setattr(google, "configured", lambda: True)
    synced, mailed = [], []
    from app.services import calendar as cal
    monkeypatch.setattr(cal, "sync", lambda ref_: (synced.append(ref_), ("sent", None))[1])
    monkeypatch.setattr(notify, "_send_email", lambda row: (mailed.append(row["id"]), ("sent", None))[1])
    with db.engine.begin() as c:
        for i in range(3):
            notify.queue(c, patient_id=None, channel="calendar", template="gcal_sync", to="WN-1", dedupe_key=f"t:{i}")
        notify.queue(c, patient_id=None, channel="email", template="t", to="x@gmail.com", subject="s", body="b")
    notify.flush(2)                       # room for two: the email goes first, the oldest WN-1 sync is skipped
    assert mailed and synced == []
    notify.flush(2)
    notify.flush(2)
    assert synced == ["WN-1"]             # only the newest of the three is sent to Google
    rows = _cal_rows("WN-1")
    assert [r["error"] for r in rows].count("superseded") == 2 and all(r["status"] == "sent" for r in rows)


def test_persona_email_does_not_clash_with_a_real_login(monkeypatch):
    """Live: the tester's own account used the same address, the unique login email failed, and Rahul kept his
    invented address, so every email to him was 'simulated'."""
    from app import config as cfg
    with db.engine.begin() as c:
        c.execute(update(db.patients).where(db.patients.c.id == 1).values(web_email="tester@gmail.com"))
    monkeypatch.setattr(cfg, "DEMO_PERSONA_EMAILS", {"rahul": "Tester@gmail.com"})
    seed.ensure_extras()
    p = _rahul()
    assert p["email"] == "Tester@gmail.com" and p["web_email"] != "tester@gmail.com"


def test_assistant_order_needs_the_quote_first():
    """Live: the AI sent confirm=yes on its first call and an order was placed that the patient never heard priced."""
    pt.remember_verified(pt.norm_phone(RAHUL))
    first = mcp_tools.order_medicine(phone=RAHUL, medicine_name="1 strip of Dolo 650", confirm="yes")
    assert first["ok"] and first["data"]["quote"] and "order_id" not in first["data"]
    placed = mcp_tools.order_medicine(phone=RAHUL, medicine_name="1 strip of Dolo 650", confirm="yes")
    assert placed["data"]["order_id"].startswith("PHARM-")
    again = mcp_tools.order_medicine(phone=RAHUL, medicine_name="1 strip of Dolo 650", confirm="yes")
    assert again["data"].get("duplicate") and again["data"]["order_id"] == placed["data"]["order_id"]
    # a different quantity is a different quote: asked again, not placed
    other = mcp_tools.order_medicine(phone=RAHUL, medicine_name="2 strips of Dolo 650", confirm="yes")
    assert other["data"].get("quote") and "order_id" not in other["data"]


def test_code_in_the_page_address_opens_the_record():
    """Live: for a web chat Talkdesk gives a conversation UUID as Application Input and the page address as Caller ID.
    The signed-in site puts #wn=<code> in the address, so the code arrives inside Caller ID."""
    p = _rahul()
    code = cs.mint(p["id"])
    r = mcp_tools.open_signed_in_session(session_code="3f2a9c1e-77b0-4c1d-9e2a-5b6c7d8e9f00",
                                         caller_id=f"https://teamxyz-mcp.onrender.com/portal#wn={code}")
    assert r["ok"] and r["data"]["signed_in"] and r["data"]["patient_phone"] == p["phone"]
    assert cs.diagnostics()[-1]["result"] == "signed_in"
    # a page address without a live code opens nothing
    bad = mcp_tools.open_signed_in_session(session_code="", caller_id="https://teamxyz-mcp.onrender.com/#wn=WS-AAAAAAAAAAAA")
    assert bad["error_code"] == "not_signed_in"


@pytest.mark.parametrize("q", ["can i know about your hospital", "Tell me about WellNest", "what is wellnest?"])
def test_about_the_hospital_gets_an_overview_not_a_policy(q):
    """Live: 'can i know about your hospital' answered with the privacy policy."""
    r = mcp_tools.get_hospital_info(topic=q)
    assert r["ok"] and "350-bed" in r["message"] and "privacy" not in r["message"].lower()
    assert mcp_tools.get_hospital_info(topic="tell me about the hospital parking")["data"].get("topic") != "about"


def test_last_chat_recall_covers_the_whole_conversation():
    """Live: the answer named only the insurance question and left out the booking made in the same chat."""
    pt.remember_verified(pt.norm_phone(RAHUL))
    assert mcp_tools.save_interaction_note(phone=RAHUL, summary="Asked whether Star Health covers an MRI of the knee.")["ok"]
    from app.services import appointments as ap
    from app.util import parse_time
    s = ap.find_slots("next available", doctor_name="Dr. Anil Kumar")
    t = parse_time(s.data["doctors"][0]["free_slots"][0])
    b = mcp_tools.book_appointment(phone=RAHUL, date="next available", time=t, doctor_name="Dr. Anil Kumar",
                                   date_of_birth=RAHUL_DOB)
    assert b["ok"], b["message"]
    search.sync()
    r = sp.search_interactions(RAHUL, "", "what did we speak about in the last chat?")
    assert r.ok and "MRI" in r.message and b["data"]["booking_id"] in r.message, r.message
    assert len(r.message) < 900


def test_chat_id_stands_in_for_mobile_and_date_of_birth():
    """Talkdesk agents only reuse what is in the conversation; the signed-in reply states a chat ID that any tool
    accepts in place of the number and date of birth, until sign-out."""
    p = _rahul()
    code = cs.mint(p["id"])
    assert mcp_tools.get_health_credits_balance(phone=code)["ok"]
    assert mcp_tools.find_appointments(phone=f"my chat ID is {code}")["ok"]
    assert mcp_tools.get_health_credits_balance(phone="9845000004", date_of_birth=code)["ok"]
    cs.revoke(p["id"])
    gone = mcp_tools.get_health_credits_balance(phone=code)
    assert not gone["ok"] and "expired" in gone["message"]


def test_caller_id_page_address_identifies_a_signed_in_patient_in_any_tool():
    """Talkdesk fills the Caller ID system variable itself (for a web chat: the page address with #wn=<code>), so any
    agent's tool knows the signed-in patient without the AI repeating a number. Live 8 Nov the AI dropped every
    identity detail it was told to repeat."""
    import asyncio
    from app.mcp_tools import mcp
    p = _rahul()
    code = cs.mint(p["id"])
    page = f"https://teamxyz-mcp.onrender.com/portal#wn={code}"
    assert mcp_tools.get_health_credits_balance(caller_id=page)["ok"]
    assert mcp_tools.find_appointments(caller_id=page)["ok"]
    assert mcp_tools.search_past_interactions(query="last chat", caller_id=page)["ok"]
    # through the MCP layer, exactly as Talkdesk calls it
    out = asyncio.run(mcp.call_tool("get_health_credits_balance", {"caller_id": page}))
    assert "HealthCredits" in str(out)
    # not signed in (no code in the address): asks, never guesses
    anon = mcp_tools.get_health_credits_balance(caller_id="https://teamxyz-mcp.onrender.com/")
    assert not anon["ok"]
    # a typed number for someone else wins over the page (a family member), and needs that person's date of birth
    other = mcp_tools.get_health_credits_balance(phone="9845000001", caller_id=page)
    assert not other["ok"] or "Shanthamma" in other["message"]
    cs.revoke(p["id"])
    assert not mcp_tools.get_health_credits_balance(caller_id=page)["ok"]


def test_chat_code_survives_overnight():
    """The page keeps #wn=<code> across reloads and Talkdesk may read it before the site renews it, so a signed-in
    patient's code must outlive a night and stay the same on every visit (seen live 9 Nov)."""
    assert cs.TTL >= 7 * 24 * 3600
    p = _rahul()
    first = cs.mint(p["id"])
    assert cs.mint(p["id"]) == first
    assert cs.open_session("", caller_id=f"https://x/portal#wn={first}").data["signed_in"]


def test_phone_call_uses_the_calling_number_and_asks_only_the_date_of_birth():
    """Live 9 Nov: on a voice call the agent refused to cancel rather than ask for identity. On a call Talkdesk's
    Caller ID is the number calling: tools use it as the mobile number and ask only for the date of birth."""
    from app.services import blackboard as bb
    store.delete(f"verified:{bb.ref_for(RAHUL)}")
    r = mcp_tools.find_appointments(caller_id="+91 " + RAHUL)
    assert r["ok"] and r["data"]["needs"] == "date_of_birth"
    r = mcp_tools.cancel_appointment(booking_id="WN-00000", caller_id="+91 " + RAHUL)
    assert r["error_code"] == "not_verified" and r["message"] == pt.ASK_DOB
    r = mcp_tools.find_appointments(date_of_birth=RAHUL_DOB, caller_id="+91 " + RAHUL)
    assert r["ok"]
    # a typed number wins over the caller ID; a web page address is never taken for a phone number
    store.delete(f"verified:{bb.ref_for(RAHUL)}")
    assert mcp_tools.cancel_appointment(booking_id="WN-00000", caller_id="https://x/portal/9845000004")["message"] == pt.ASK_IDENTITY
