"""Smoke + acceptance test over the real MCP transport (Streamable HTTP + Bearer token).

Usage:
  MCP_URL=http://localhost:8000/mcp MCP_BEARER_TOKEN=... python scripts/smoke_mcp.py
  MCP_URL=https://teamxyz-mcp.onrender.com/mcp MCP_BEARER_TOKEN=... python scripts/smoke_mcp.py --readonly

--readonly skips scenarios that change data (safe against the live server).
Uses the demo personas from app/seed.py.
"""

import asyncio
import json
import os
import sys
import time

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")
TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
READONLY = "--readonly" in sys.argv

SHAN = {"phone": "98450 00001", "date_of_birth": "1959-03-04"}
ARJUN = {"phone": "+91-9845000002", "date_of_birth": "15/06/1992"}
PRIYA = {"phone": "9845000003", "date_of_birth": "20 January 1997"}
RAHUL = {"phone": "9845000004", "date_of_birth": "1981-09-10"}

results = []


async def call(s, name, args):
    t0 = time.perf_counter()
    r = await s.call_tool(name, args)
    ms = (time.perf_counter() - t0) * 1000
    body = json.loads(r.content[0].text)
    size = len(r.content[0].text.encode())
    return body, ms, size


def check(label, cond, body, ms=0):
    results.append((label, bool(cond)))
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {label}  ({ms:.0f} ms)\n       -> {body.get('message', body)[:220]}")


async def main():
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60) as hc, \
            streamable_http_client(URL, http_client=hc) as streams:
        async with ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            tools = {t.name: t for t in (await s.list_tools()).tools}
            print(f"{len(tools)} tools on {URL}")
            v1 = ["get_doctors", "find_available_slots", "book_appointment", "find_appointments",
                  "reschedule_appointment", "cancel_appointment"]
            check("V1 tool names all present", all(n in tools for n in v1), {"message": ", ".join(v1)})
            req = {n: set(tools[n].input_schema.get("required") or []) for n in v1}
            check("V1 required inputs unchanged or looser",
                  req["find_available_slots"] <= {"date"} and req["book_appointment"] <= {"patient_name", "phone", "date", "time"}
                  and req["reschedule_appointment"] <= {"booking_id", "new_date", "new_time"}
                  and req["cancel_appointment"] <= {"booking_id"} and not req["get_doctors"] and not req["find_appointments"],
                  {"message": str(req)})

            # A9: garbage input never raises
            bad = 0
            for n, t in tools.items():
                args = {k: "???" for k in (t.input_schema.get("required") or [])}
                b, ms, size = await call(s, n, args)
                if "ok" not in b or "message" not in b or size > 2048:
                    bad += 1
                    print("   bad envelope:", n, b)
            check(f"A9 every tool returns the envelope on garbage input ({len(tools)} tools)", bad == 0, {"message": f"{bad} bad"})

            # V1-style calls (exact inputs the current Talkdesk skills send)
            b, ms, _ = await call(s, "find_available_slots", {"date": "tomorrow", "department": "heart", "doctor_name": "", "time_preference": "any"})
            check("V1 find_available_slots(date=tomorrow, department=heart)", b["ok"] and b["data"].get("weekday"), b, ms)
            b, ms, _ = await call(s, "get_doctors", {"department": "skin"})
            check("V1 get_doctors(department=skin) - no hospital block", b["ok"] and "hospital" not in b.get("data", {}), b, ms)

            # A10: slots + doctors + fees in one call
            b, ms, _ = await call(s, "find_available_slots", {"date": "tomorrow", "department": "Cardiology"})
            docs = b.get("data", {}).get("doctors", [])
            check("A10 slots include every doctor's days, hours and fee", docs and all("fee_inr" in d and "days" in d for d in docs), b, ms)

            # A1 verify
            b, ms, _ = await call(s, "verify_patient", ARJUN)
            check("A1 verify Arjun with correct DOB", b["ok"] and b["data"]["name"] == "Arjun Mehta", b, ms)
            b, ms, _ = await call(s, "verify_patient", {"phone": ARJUN["phone"], "date_of_birth": "1990-01-01"})
            check("A1 wrong DOB -> generic failure", not b["ok"] and b["error_code"] == "not_verified" and "Arjun" not in b["message"], b, ms)

            # A11 senior shorter
            sb, _, _ = await call(s, "verify_patient", SHAN)
            check("A11 senior flag for Shanthamma", sb["ok"] and sb["data"]["is_senior"], sb)

            # A6 lab
            b, ms, _ = await call(s, "get_lab_report_status", PRIYA)
            check("A6 Priya has a ready report", b["ok"] and any(r["status"] in ("ready", "collected") for r in b["data"]["reports"]), b, ms)
            b, ms, _ = await call(s, "get_insurance_info", {"insurance_provider": "star"})
            check("Insurance info for Star Health", b["ok"] and b["data"]["accepted"], b, ms)

            # memory
            b, ms, _ = await call(s, "search_past_interactions", dict(PRIYA, query="did I ask about my MRI report last week"))
            check("Memory: Priya asked about MRI report", b["ok"] and "MRI" in b["message"], b, ms)

            # hybrid search (keyword + fuzzy + meaning): must hold even with the meaning leg off
            b, ms, _ = await call(s, "search_past_interactions", dict(SHAN, query="anything about WN-48213?"))
            check("Search: exact booking code found", b["ok"] and "WN-48213" in b["message"], b, ms)
            b, ms, _ = await call(s, "get_hospital_info", {"topic": "can my son stay overnight with me in the ward"})
            check("Search: free-text question -> attendant rule", b["ok"] and "attendant" in b["message"].lower(), b, ms)
            b, ms, _ = await call(s, "get_hospital_info", {"topic": "is there wifi"})
            check("Search: FAQ answer (Wi-Fi)", b["ok"] and "Wi-Fi" in b["message"], b, ms)
            b, ms, _ = await call(s, "suggest_department", {"symptoms": "need a cardiolgy check up"})
            check("Search: typo 'cardiolgy' -> Cardiology", b["ok"] and b["data"]["department"] == "Cardiology", b, ms)

            # emergency
            b, ms, _ = await call(s, "suggest_department", {"symptoms": "I have chest pain and sweating"})
            check("Red flag symptoms -> emergency", b["ok"] and b["data"]["emergency"], b, ms)

            if READONLY:
                return

            b, ms, _ = await call(s, "create_handoff", {"summary": "Caller reports chest pain", "priority": "urgent", "phone": SHAN["phone"]})
            check("A8 urgent handoff starts with 108 advice", b["ok"] and b["message"].startswith("Please call 108"), b, ms)

            # A7 coverage -> booking carries preauth fact
            b, ms, _ = await call(s, "check_coverage", {"insurance_provider": "Star Health", "procedure": "MRI Knee", "phone": SHAN["phone"]})
            check("A7 Star Health MRI Knee needs pre-approval", b["ok"] and b["data"]["preauth_required"], b, ms)
            sl, _, _ = await call(s, "find_available_slots", {"date": "tomorrow", "procedure": "MRI Knee"})
            tm = (sl["data"].get("free_slots") or sl["data"].get("next_available", {}).get("free_slots"))[0]
            dt = "tomorrow" if sl["data"].get("free_slots") else sl["data"]["next_available"]["date_iso"]
            b, ms, _ = await call(s, "book_appointment", dict(phone=SHAN["phone"], date=dt, time=tm, procedure="MRI Knee"))
            check("A7 MRI booking response carries the pre-auth fact in related",
                  b["ok"] and any(r["kind"] == "preauth" for r in b.get("related", [])), b, ms)
            short_len = len(b["message"])

            # A3 idempotency + A2 double booking
            sl, _, _ = await call(s, "find_available_slots", {"date": "tomorrow", "department": "General Medicine"})
            d0 = next(d for d in sl["data"]["doctors"] if d["free_slots"])
            args = dict(phone=RAHUL["phone"], date=sl["data"]["date_iso"], time=d0["free_slots"][0], doctor_name=d0["name"],
                        idempotency_key="smoke-1", patient_name="Rahul Verma")
            b1, ms, _ = await call(s, "book_appointment", args)
            b2, _, _ = await call(s, "book_appointment", args)
            check("A3 same idempotency key returns the same booking", b1["ok"] and b2["ok"] and
                  b1["data"]["booking_id"] == b2["data"]["booking_id"], b1, ms)
            check("V1 booking ID appears in message", b1["data"]["booking_id"] in b1["message"], b1)
            nonsenior_len = len(b1["message"])
            check("A11 senior message shorter than non-senior", short_len < nonsenior_len, {"message": f"{short_len} vs {nonsenior_len}"})
            sl, _, _ = await call(s, "find_available_slots", {"date": "tomorrow", "doctor_name": d0["name"]})
            t2 = sl["data"]["doctors"][0]["free_slots"][0]
            race = [dict(phone=p, date=sl["data"]["date_iso"], time=t2, doctor_name=d0["name"], patient_name="Race Test")
                    for p in ("9845000004", "9845000003")]
            rs = await asyncio.gather(*(call(s, "book_appointment", a) for a in race))
            oks = [r[0]["ok"] for r in rs]
            check("A2 parallel booking of the same slot -> exactly one success", sorted(oks) == [False, True],
                  {"message": str([r[0].get("error_code") or r[0]["data"]["booking_id"] for r in rs])})

            # A4 imposter cancel
            up, _, _ = await call(s, "find_appointments", SHAN)
            shan_bid = next(a["booking_id"] for a in up["data"]["appointments"] if "Iyer" in a["with"])
            b, ms, _ = await call(s, "cancel_appointment", dict(booking_id=shan_bid, **ARJUN))
            check("A4 Arjun cannot cancel Shanthamma's booking", not b["ok"] and b["error_code"] == "not_allowed", b, ms)
            b, ms, _ = await call(s, "cancel_appointment", {"booking_id": shan_bid, "phone": SHAN["phone"]})
            check("V1-style cancel without DOB asks for it", not b["ok"] and b["error_code"] == "not_verified", b, ms)

            # A5 cancel -> waitlist offer -> accept
            b, ms, _ = await call(s, "cancel_appointment", dict(booking_id=shan_bid, **SHAN))
            check("A5 cancel offers the slot to the waitlist", b["ok"] and b["data"].get("offered_to_waitlist"), b, ms)
            vb, _, _ = await call(s, "verify_patient", ARJUN)
            code = (vb["data"].get("open_offer") or {}).get("offer_code", "")
            check("A5 verify_patient tells Arjun about the held slot", bool(code) and code in vb["message"], vb)
            b, ms, _ = await call(s, "accept_waitlist_offer", {"offer_code": code, "phone": ARJUN["phone"]})
            check("A5 Arjun accepts the offer and is booked", b["ok"] and "Iyer" in b["message"], b, ms)
            b, ms, _ = await call(s, "accept_waitlist_offer", {"offer_code": code, "phone": SHAN["phone"]})
            check("A5 someone else cannot use the offer", not b["ok"], b, ms)

            # A6 email ready report; pending cannot be emailed
            b, ms, _ = await call(s, "email_lab_report", PRIYA)
            check("A6 email ready report -> masked address", b["ok"] and "***@" in b["data"]["sent_to"], b, ms)
            b, ms, _ = await call(s, "email_lab_report", dict(SHAN, report_id="LR-20940"))
            check("A6 pending report cannot be emailed", not b["ok"], b, ms)

            # V1 reschedule with identity
            mine, _, _ = await call(s, "find_appointments", RAHUL)
            bid = mine["data"]["appointments"][0]["booking_id"]
            sl, _, _ = await call(s, "find_available_slots", {"date": "day after tomorrow", "department": "General Medicine"})
            d1 = next(d for d in sl["data"]["doctors"] if d["free_slots"])
            b, ms, _ = await call(s, "reschedule_appointment", dict(booking_id=bid, new_date=sl["data"]["date_iso"],
                                                                     new_time=d1["free_slots"][0], doctor_name=d1["name"], **RAHUL))
            check("Reschedule own booking", b["ok"], b, ms)

            # A1 lockout
            for _ in range(5):
                await call(s, "verify_patient", {"phone": "9845000005", "date_of_birth": "2000-01-01"})
            b, ms, _ = await call(s, "verify_patient", {"phone": "9845000005", "date_of_birth": "2018-05-12"})
            check("A1 6th try after 5 failures -> locked_out", b.get("error_code") == "locked_out", b, ms)

    print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
    if not all(ok for _, ok in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
