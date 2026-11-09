"""Link a signed-in website patient to their Talkdesk chat, and keep what was said in that patient's memory.

Talkdesk's AI agents never see our login, and anything the browser sends can be forged, so a phone number from the
page proves nothing. Instead the signed-in site asks us for a random session code and passes only that code through the
chat widget's context:

    website -> setContextParam(wellnest_session) -> Studio Incoming Message -> Connect to Autopilot Digital
            -> system variable Application Input -> open_signed_in_session(session_code)

The server alone knows which patient a code belongs to. Logging out revokes it.

Transcripts: Talkdesk can post a closed conversation to us through an automation. We file it under the patient named by
the session code or by an interaction already linked to a patient, and never by a phone number the browser supplied.
"""

import hashlib
import re
import secrets

from sqlalchemy import insert

from .. import config, db, events
from ..store import store
from ..util import Result, clean, fail, ok
from . import patients as pt

CODE_RE = re.compile(r"\bWS-[A-HJ-NP-Z2-9]{12}\b")
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no 0/O or 1/I, so a code survives being read aloud
# One stable code per signed-in patient, renewed on every page load and revoked at sign-out. It must outlive a night:
# the page keeps #wn=<code> across reloads and Talkdesk can read that address before the site renews it (seen live
# 9 Nov: a 12-hour code had expired overnight, so the next morning's chat came in "not signed in").
TTL = 7 * 24 * 3600
LINK_TTL = 7 * 24 * 3600
TRANSCRIPT_TOPIC = "transcript"
CHUNK = 480
MAX_CHUNKS = 12

NOT_SIGNED_IN = ("This chat isn't linked to a signed-in account. Help with what they asked; only for something about "
                 "their own record, ask for the registered mobile number and date of birth.")


def mint(patient_id: int) -> str:
    """The patient's chat session code, created on first use. One code per patient, refreshed on each page load."""
    code = store.get_json(f"chatsess_p:{patient_id}", count=False)
    if not code:
        code = "WS-" + "".join(secrets.choice(_ALPHABET) for _ in range(12))
    store.set_json(f"chatsess:{code}", patient_id, ttl=TTL)
    store.set_json(f"chatsess_p:{patient_id}", code, ttl=TTL)
    store.set_json("chatlink:last_issued", config.now().strftime("%H:%M:%S"), ttl=7 * 24 * 3600)
    return code


def revoke(patient_id: int) -> None:
    code = store.get_json(f"chatsess_p:{patient_id}", count=False)
    keys = [f"chatsess_p:{patient_id}"] + ([f"chatsess:{code}"] if code else [])
    store.delete(*keys)


def _code_in(text) -> str:
    """Application Input may hold the bare code, a sentence or a JSON string, so look for the code inside it."""
    m = CODE_RE.search(clean(text).upper())
    return m.group(0) if m else ""


def _patient_for_code(text) -> int | None:
    code = _code_in(text)
    return store.get_json(f"chatsess:{code}", count=False) if code else None


def link_interaction(interaction_id, patient_id: int) -> None:
    """Remember whose conversation this is, so its transcript can be filed when Talkdesk sends it."""
    i = clean(interaction_id)[:80]
    if i:
        store.set_json(f"chatlink:{i}", patient_id, ttl=LINK_TTL)


DIAG_KEY = "chatlink:diag"


def _diag(session_code, caller_id, interaction_id, result: str) -> None:
    """Keep the last 10 attempts, masked, so /health shows which link of widget -> Studio -> agent is broken."""
    def shape(v) -> str:
        return re.sub(r"\d", "9", CODE_RE.sub("WS-<code>", clean(v).upper()))[:80] or "(empty)"
    raw = clean(session_code)
    entry = {"at": config.now().strftime("%H:%M:%S"), "application_input": shape(raw),
             "code_found": bool(_code_in(raw) or _code_in(caller_id)), "caller_id": shape(caller_id),
             "interaction_id": bool(clean(interaction_id)), "result": result}
    try:
        items = (store.get_json(DIAG_KEY, count=False) or [])[-9:] + [entry]
        store.set_json(DIAG_KEY, items, ttl=7 * 24 * 3600)
    except Exception:
        pass


def diagnostics() -> list:
    return store.get_json(DIAG_KEY, count=False) or []


def open_session(session_code, interaction_id="", caller_id="") -> Result:
    """A live website session code opens the record; failing that, on a phone call, the caller's number names the
    patient (without verifying them) so the agent asks only for the date of birth."""
    res = _open_session(session_code, interaction_id, caller_id)
    _diag(session_code, caller_id, interaction_id,
          "signed_in" if res.ok and (res.data or {}).get("signed_in") else (res.error_code or "caller_recognised"))
    return res


def _open_session(session_code, interaction_id="", caller_id="") -> Result:
    # the code may reach us in Application Input or, for a chat, in the contact field Talkdesk passes as Caller ID;
    # either way only a live code the server issued opens a record
    code = _code_in(session_code) or _code_in(caller_id)
    pid = _patient_for_code(session_code) or _patient_for_code(caller_id)
    if not pid:
        if pt.norm_phone(caller_id):
            return recognise_caller(caller_id)
        return fail("not_signed_in", NOT_SIGNED_IN)
    with db.engine.connect() as c:
        p = pt.get_by_id(c, pid)
    if not p:
        return fail("not_signed_in", NOT_SIGNED_IN)
    pt.remember_verified(p["phone"], config.WEB_SESSION_MIN)
    link_interaction(interaction_id, pid)
    res = pt.verify(p["phone"], "")
    if not res.ok:
        return res
    from . import support as sp
    earlier = sp.search_interactions(p["phone"], "", "")
    first = p["full_name"].split()[0]
    msg = re.sub(r"^Thank you, [^,]+, you're verified\.", f"Hello {first}, you're signed in.", res.message)
    data = dict(res.data or {})
    # Talkdesk agents only reuse details that appear in the conversation itself: a value inside a tool result stays
    # with the agent that called the tool, so the next team asked again (seen live 8 Nov). The signed-in patient's own
    # number and date of birth are therefore said in this reply, in their own authenticated chat, never on a call.
    dob = p["date_of_birth"].strftime("%d-%m-%Y") if p.get("date_of_birth") else ""
    # Every tool now reads the signed-in page from Talkdesk's Caller ID, so nothing has to be said in the chat to carry
    # the identity (the chat ID still works in phone/date_of_birth, kept in data only).
    if code:
        msg += " I'll use the details on your account, so you won't need to type your mobile number or date of birth."
    data.update(patient_phone=p["phone"], date_of_birth=dob, chat_id=code, patient_name=p["full_name"], signed_in=True,
                earlier=[{"date": m["date"], "summary": m["summary"][:140]} for m in (earlier.data or {}).get("matches", [])])
    return Result(True, msg, data, related=res.related)


NO_CALLER = ("There's no caller number on this conversation. Ask for the registered mobile number and date of birth.")


def recognise_caller(caller_id) -> Result:
    """On a phone call Talkdesk knows the number the patient is calling from (or the number we dialled), so the agent
    should never ask for it again. A caller ID can be spoofed, so this names the patient but does not verify them: the
    agent still confirms who it is speaking to and asks for the date of birth before anything personal."""
    phone = pt.norm_phone(caller_id)
    if not phone:
        return fail("no_caller_id", NO_CALLER)
    with db.engine.connect() as c:
        p = pt.get_by_phone(c, phone)
    last4 = phone[-4:]
    if not p or p["is_guest"]:
        return ok(f"This call is from a number ending {last4} that isn't registered with us. Ask whether they'd like to "
                  f"use this number, give their registered number, or register as a new patient.",
                  caller_phone=phone, registered=False)
    first = p["full_name"].split()[0]
    if pt.recently_verified(phone):
        return ok(f"This call is from {first}'s registered number ending {last4}, already verified in this conversation. "
                  f"Use this number; don't ask for it or the date of birth again.",
                  caller_phone=phone, patient_phone=phone, first_name=first, registered=True, verified=True)
    return ok(f"This call is from the number ending {last4}, registered to {first}. Ask: 'Am I speaking with {first}? "
              f"For your security, please tell me your date of birth.' Use this number as the mobile number; don't ask for it.",
              caller_phone=phone, patient_phone=phone, first_name=first, registered=True, verified=False)


def ingest_transcript(body: dict) -> dict:
    """File a closed conversation in the patient's memory, split so each passage can be found and embedded."""
    text = clean(next((body.get(k) for k in ("transcript", "transcription", "text", "body") if body.get(k)), ""))
    if not text:
        return {"ok": False, "error_code": "invalid_input", "message": "No transcript in the request."}
    interaction = clean(body.get("interaction_id"))[:80]
    pid = _patient_for_code(next((body.get(k) for k in ("session", "wellnest_session", "session_code") if body.get(k)), ""))
    if not pid and interaction:
        pid = store.get_json(f"chatlink:{interaction}", count=False)
    if not pid:
        return {"ok": False, "error_code": "not_matched", "message": "This conversation isn't linked to a patient."}
    seen = "transcript:" + hashlib.sha256(f"{pid}|{interaction}|{text}".encode()).hexdigest()[:32]
    if store.get_json(seen, count=False):
        return {"ok": True, "duplicate": True, "stored": 0}
    chunks = [text[i:i + CHUNK] for i in range(0, min(len(text), CHUNK * MAX_CHUNKS), CHUNK)]
    with db.engine.begin() as c:
        p = pt.get_by_id(c, pid)
        if not p:
            return {"ok": False, "error_code": "not_matched", "message": "This conversation isn't linked to a patient."}
        now = config.now()
        c.execute(insert(db.interaction_notes), [
            dict(patient_id=pid, phone=p["phone"], channel="chat", summary=part, topics=TRANSCRIPT_TOPIC,
                 outcome=None, created_at=now) for part in chunks])
        from .. import search
        search.sync(c, pid)
    store.set_json(seen, 1, ttl=LINK_TTL)
    events.publish("interaction.noted", patient_id=pid)
    return {"ok": True, "stored": len(chunks)}
