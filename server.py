"""
TeamXYZ-MCP: City Hospital, Bengaluru appointment system (Talkdesk AI Hackday)

What runs here
  /mcp         MCP endpoint for the Talkdesk AI agent (Streamable HTTP, Bearer token)
  /dashboard   Web page to watch doctors' slots and bookings live (?token=...)
  /api/...     JSON used by the dashboard
  /health      Simple "is it up?" check

Run:  export MCP_BEARER_TOKEN=your-secret && python server.py      (see README.md)
"""

import hmac
import os
import random
import sqlite3
import sys
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from datetime import timezone

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

# ============================================================== config
TOKEN = (os.environ.get("MCP_BEARER_TOKEN") or os.environ.get("MCP_TOKEN") or "").strip()
if not TOKEN:
    sys.exit("ERROR: MCP_BEARER_TOKEN environment variable is not set.\n"
             "Set it before starting the server:  export MCP_BEARER_TOKEN=your-secret-token")
PORT = int(os.environ.get("PORT", "8000"))
HERE = Path(__file__).parent
DB_PATH = os.environ.get("DB_PATH", str(HERE / "hospital.db"))
IST = timezone(timedelta(hours=5, minutes=30), "IST")  # fixed offset: works on Windows without tzdata

HOSPITAL = {
    "name": "City Hospital, Bengaluru",
    "address": "12 MG Road, Bengaluru 560001",
    "opd_hours": "Mon-Sat 9:00 AM - 5:00 PM (lunch 1:00-2:00 PM). Sunday closed.",
    "emergency": "24x7 emergency ward. For life-threatening emergencies call 108.",
}

# ============================================================== doctors (mock but realistic)
# days: 0=Mon ... 5=Sat ; slot = consultation length in minutes ; fee in INR
DOCTORS = [
    {"id": "D01", "name": "Dr. Anil Kumar",    "dept": "General Medicine", "days": [0, 1, 2, 3, 4, 5], "start": "09:00", "end": "17:00", "slot": 15, "fee": 500,  "room": "OPD-101", "languages": ["English", "Kannada", "Hindi"]},
    {"id": "D02", "name": "Dr. Sneha Rao",     "dept": "General Medicine", "days": [0, 2, 4],          "start": "10:00", "end": "16:00", "slot": 15, "fee": 500,  "room": "OPD-102", "languages": ["English", "Kannada", "Telugu"]},
    {"id": "D03", "name": "Dr. Priya Mehta",   "dept": "Dermatology",      "days": [0, 1, 3, 5],       "start": "09:30", "end": "13:00", "slot": 20, "fee": 800,  "room": "OPD-205", "languages": ["English", "Hindi"]},
    {"id": "D04", "name": "Dr. Farhan Ali",    "dept": "Dermatology",      "days": [1, 2, 4],          "start": "14:00", "end": "17:00", "slot": 20, "fee": 800,  "room": "OPD-206", "languages": ["English", "Hindi", "Urdu"]},
    {"id": "D05", "name": "Dr. Rajesh Iyer",   "dept": "Cardiology",       "days": [0, 2, 4],          "start": "10:00", "end": "13:00", "slot": 30, "fee": 1200, "room": "OPD-310", "languages": ["English", "Tamil"]},
    {"id": "D06", "name": "Dr. Kavya Reddy",   "dept": "Cardiology",       "days": [1, 3, 5],          "start": "14:00", "end": "17:00", "slot": 30, "fee": 1200, "room": "OPD-311", "languages": ["English", "Telugu", "Kannada"]},
    {"id": "D07", "name": "Dr. Kiran Shetty",  "dept": "Orthopaedics",     "days": [0, 1, 2, 3, 4],    "start": "09:00", "end": "13:00", "slot": 20, "fee": 1000, "room": "OPD-402", "languages": ["English", "Kannada", "Tulu"]},
    {"id": "D08", "name": "Dr. Lakshmi Nair",  "dept": "Paediatrics",      "days": [0, 1, 2, 3, 4, 5], "start": "09:00", "end": "13:00", "slot": 15, "fee": 700,  "room": "OPD-120", "languages": ["English", "Malayalam", "Kannada"]},
    {"id": "D09", "name": "Dr. Arjun Desai",   "dept": "ENT",              "days": [1, 3, 5],          "start": "10:00", "end": "16:00", "slot": 20, "fee": 700,  "room": "OPD-215", "languages": ["English", "Hindi", "Marathi"]},
    {"id": "D10", "name": "Dr. Meera Joshi",   "dept": "Gynaecology",      "days": [0, 2, 4, 5],       "start": "09:30", "end": "15:30", "slot": 20, "fee": 900,  "room": "OPD-130", "languages": ["English", "Hindi", "Kannada"]},
]
DOC_BY_ID = {d["id"]: d for d in DOCTORS}
DEPARTMENTS = sorted({d["dept"] for d in DOCTORS})
LUNCH = (time(13, 0), time(14, 0))

# Doctors on leave (relative to "today" so the demo always has some)
def leave_days() -> dict[str, set[str]]:
    t = today()
    return {"D01": {(t + timedelta(days=3)).isoformat()}, "D05": {(t + timedelta(days=2)).isoformat()}}

ALIASES = {
    "general": "General Medicine", "general medicine": "General Medicine", "physician": "General Medicine",
    "fever": "General Medicine", "gp": "General Medicine",
    "skin": "Dermatology", "dermatology": "Dermatology", "dermatologist": "Dermatology", "hair": "Dermatology",
    "heart": "Cardiology", "cardiology": "Cardiology", "cardiologist": "Cardiology",
    "bone": "Orthopaedics", "ortho": "Orthopaedics", "orthopaedics": "Orthopaedics", "orthopedics": "Orthopaedics",
    "orthopedic": "Orthopaedics", "joint": "Orthopaedics",
    "child": "Paediatrics", "children": "Paediatrics", "kids": "Paediatrics", "paediatrics": "Paediatrics",
    "pediatrics": "Paediatrics", "paediatrician": "Paediatrics", "pediatrician": "Paediatrics",
    "ent": "ENT", "ear": "ENT", "nose": "ENT", "throat": "ENT",
    "gynaecology": "Gynaecology", "gynecology": "Gynaecology", "gynaecologist": "Gynaecology",
    "gynecologist": "Gynaecology", "women": "Gynaecology", "pregnancy": "Gynaecology",
}

_lock = threading.Lock()


# ============================================================== helpers
def now() -> datetime:
    return datetime.now(IST)


def today() -> date:
    return now().date()


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def norm_dept(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in ALIASES:
        return ALIASES[t]
    for d in DEPARTMENTS:
        if t == d.lower():
            return d
    for k, v in ALIASES.items():
        if k in t:
            return v
    return None


def find_doctor(text: str) -> dict | None:
    t = (text or "").strip().lower().replace("dr.", "").replace("dr ", "").strip()
    if not t:
        return None
    for d in DOCTORS:
        full = d["name"].lower().replace("dr. ", "")
        if t == d["id"].lower() or t == full or t in full.split() or t in full:
            return d
    return None


def parse_date(text: str) -> date | None:
    t = (text or "").strip().lower()
    base = today()
    if t in ("today", "now"):
        return base
    if t in ("tomorrow", "tmrw", "tommorow"):
        return base + timedelta(days=1)
    if t in ("day after tomorrow",):
        return base + timedelta(days=2)
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, name in enumerate(days):
        if t.replace("next ", "").replace("this ", "") in (name, name[:3]):
            delta = (i - base.weekday()) % 7 or 7
            return base + timedelta(days=delta)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%d %b", "%d %B"):
        try:
            d = datetime.strptime(t.title() if "%b" in fmt or "%B" in fmt else t, fmt).date()
            if d.year == 1900:
                d = d.replace(year=base.year)
                if d < base:
                    d = d.replace(year=base.year + 1)
            return d
        except ValueError:
            pass
    return None


def parse_time(text: str) -> str | None:
    t = (text or "").strip().upper().replace(".", ":").replace(" ", "")
    for fmt in ("%H:%M", "%I:%M%p", "%I%p", "%H"):
        try:
            return datetime.strptime(t, fmt).strftime("%H:%M")
        except ValueError:
            pass
    return None


def clean_phone(p: str) -> str | None:
    digits = "".join(c for c in (p or "") if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else None


def human_time(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def human_date(d: date) -> str:
    return d.strftime("%A, %d %B %Y")


def all_slots(doc: dict) -> list[str]:
    s = datetime.combine(date.today(), time.fromisoformat(doc["start"]))
    e = datetime.combine(date.today(), time.fromisoformat(doc["end"]))
    out = []
    while s + timedelta(minutes=doc["slot"]) <= e:
        if not (LUNCH[0] <= s.time() < LUNCH[1]):
            out.append(s.strftime("%H:%M"))
        s += timedelta(minutes=doc["slot"])
    return out


def doctor_status(doc: dict, d: date) -> str | None:
    """None if the doctor sits that day, otherwise a reason."""
    if d.weekday() == 6:
        return "OPD is closed on Sundays."
    if d.weekday() not in doc["days"]:
        names = ", ".join(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][i] for i in doc["days"])
        return f"{doc['name']} does not consult on {d.strftime('%A')}s (available: {names})."
    if d.isoformat() in leave_days().get(doc["id"], set()):
        return f"{doc['name']} is on leave on {human_date(d)}."
    return None


def booked_times(con, doc_id: str, d: str) -> set[str]:
    rows = con.execute("SELECT time FROM bookings WHERE doctor_id=? AND date=? AND status='booked'", (doc_id, d)).fetchall()
    return {r["time"] for r in rows}


def free_slots(con, doc: dict, d: date) -> list[str]:
    if doctor_status(doc, d):
        return []
    busy = booked_times(con, doc["id"], d.isoformat())
    slots = [t for t in all_slots(doc) if t not in busy]
    if d == today():
        cutoff = (now() + timedelta(minutes=30)).strftime("%H:%M")
        slots = [t for t in slots if t >= cutoff]
    return slots


def next_id(con) -> str:
    n = con.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    return f"CH{1001 + n}"


# ============================================================== database + realistic seed data
FIRST = ["Aarav", "Diya", "Rohan", "Ananya", "Vikram", "Isha", "Karthik", "Pooja", "Manoj", "Divya",
         "Suresh", "Nisha", "Rahul", "Sneha", "Arjun", "Kavitha", "Naveen", "Meghana", "Prakash", "Shruti"]
LAST = ["Sharma", "Reddy", "Gowda", "Iyer", "Nair", "Patel", "Rao", "Kumar", "Shetty", "Joshi", "Hegde", "Menon"]
REASONS = ["Follow-up", "Fever and cold", "Skin rash", "Chest discomfort", "Knee pain", "Routine check-up",
           "Child vaccination", "Ear pain", "Back pain", "Acne", "BP review", "Prenatal visit"]


def init_db() -> None:
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY, patient_name TEXT, phone TEXT, doctor_id TEXT, doctor TEXT,
                department TEXT, date TEXT, time TEXT, reason TEXT, status TEXT,
                source TEXT, created_at TEXT, updated_at TEXT)"""
        )
        if con.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 0:
            seed(con)


def seed(con) -> None:
    """Fill ~35% of the next 7 days so the calendar looks like a real, busy hospital."""
    rnd = random.Random(42)
    ts = now().isoformat(timespec="seconds")
    for offset in range(0, 8):
        d = today() + timedelta(days=offset)
        for doc in DOCTORS:
            if doctor_status(doc, d):
                continue
            for t in all_slots(doc):
                if rnd.random() < 0.35:
                    name = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
                    phone = f"9{rnd.randint(100000000, 999999999)}"
                    con.execute(
                        "INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (next_id(con), name, phone, doc["id"], doc["name"], doc["dept"], d.isoformat(), t,
                         rnd.choice(REASONS), "booked", "existing", ts, ts),
                    )


# ============================================================== MCP tools (what the AI agent can do)
mcp = MCPServer(
    name="TeamXYZ-MCP",
    instructions="Appointment desk for City Hospital, Bengaluru: doctors, free slots, booking, "
                 "rescheduling and cancelling. Always confirm details with the caller before booking.",
)


@mcp.tool()
def get_doctors(department: str = "") -> dict:
    """List departments and doctors with their consultation days, hours, fee and languages.
    department is optional (e.g. 'Dermatology', or plain words like 'skin', 'heart', 'child')."""
    dept = norm_dept(department) if department else None
    docs = [d for d in DOCTORS if not dept or d["dept"] == dept]
    day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    return {
        "hospital": HOSPITAL,
        "departments": DEPARTMENTS,
        "doctors": [
            {"name": d["name"], "department": d["dept"], "days": [day[i] for i in d["days"]],
             "hours": f"{human_time(d['start'])} - {human_time(d['end'])}", "fee_inr": d["fee"],
             "languages": d["languages"]}
            for d in docs
        ],
    }


@mcp.tool()
def find_available_slots(date: str, department: str = "", doctor_name: str = "", time_preference: str = "any") -> dict:
    """Find free appointment slots on a date, for a department or a specific doctor.
    date: 'today', 'tomorrow', a weekday like 'Monday', or YYYY-MM-DD.
    department: e.g. Dermatology or plain words like 'skin'. doctor_name: e.g. 'Dr. Priya Mehta' or 'Mehta'.
    time_preference: 'morning', 'afternoon' or 'any'. Returns at most 6 slots per doctor."""
    d = parse_date(date)
    if not d:
        return {"error": "Date not understood. Use today, tomorrow, a weekday, or YYYY-MM-DD."}
    if d < today():
        return {"error": "That date is in the past."}
    doc = find_doctor(doctor_name) if doctor_name else None
    if doctor_name and not doc:
        return {"error": f"No doctor named '{doctor_name}'.", "doctors": [x["name"] for x in DOCTORS]}
    dept = doc["dept"] if doc else norm_dept(department)
    if not doc and not dept:
        return {"error": "Please give a department or doctor.", "departments": DEPARTMENTS}
    docs = [doc] if doc else [x for x in DOCTORS if x["dept"] == dept]
    pref = (time_preference or "any").lower()
    results, unavailable = [], []
    with db() as con:
        for x in docs:
            reason = doctor_status(x, d)
            if reason:
                unavailable.append(reason)
                continue
            slots = free_slots(con, x, d)
            if pref.startswith("morn"):
                slots = [s for s in slots if s < "12:00"]
            elif pref.startswith("after") or pref.startswith("even"):
                slots = [s for s in slots if s >= "12:00"]
            results.append({"doctor": x["name"], "fee_inr": x["fee"], "room": x["room"],
                            "free_slots": [human_time(s) for s in slots[:6]], "total_free": len(slots)})
    out = {"date": human_date(d), "date_iso": d.isoformat(), "department": dept, "availability": results}
    if unavailable:
        out["notes"] = list(dict.fromkeys(unavailable))
    if not any(r["free_slots"] for r in results):
        out["suggestion"] = "No free slots. Try another date (call this tool again with a different date)."
    return out


@mcp.tool()
def book_appointment(patient_name: str, phone: str, date: str, time: str,
                     department: str = "", doctor_name: str = "", reason: str = "") -> dict:
    """Book an appointment. Required: patient_name, phone (10-digit Indian mobile), date, time,
    and either doctor_name or department. reason is optional (symptom / purpose).
    Always confirm details with the caller first. Returns a booking ID like CH1234."""
    p = clean_phone(phone)
    if not patient_name.strip():
        return {"status": "failed", "reason": "Patient name is required."}
    if not p:
        return {"status": "failed", "reason": "Please provide a valid 10-digit mobile number."}
    d, t = parse_date(date), parse_time(time)
    if not d or d < today():
        return {"status": "failed", "reason": "Invalid or past date."}
    if not t:
        return {"status": "failed", "reason": "Time not understood (e.g. 10:30 AM)."}
    doc = find_doctor(doctor_name) if doctor_name else None
    dept = doc["dept"] if doc else norm_dept(department)
    if not doc and not dept:
        return {"status": "failed", "reason": "Please give a department or doctor.", "departments": DEPARTMENTS}
    candidates = [doc] if doc else [x for x in DOCTORS if x["dept"] == dept]
    with _lock, db() as con:
        chosen = None
        for x in candidates:
            if t in free_slots(con, x, d):
                chosen = x
                break
        if not chosen:
            alts = []
            for x in candidates:
                alts += [f"{x['name']} at {human_time(s)}" for s in free_slots(con, x, d)[:3]]
            notes = list(dict.fromkeys(r for x in candidates if (r := doctor_status(x, d))))
            return {"status": "failed", "reason": "That time is not available.",
                    "alternatives_same_day": alts[:5], "notes": notes}
        bid = next_id(con)
        ts = now().isoformat(timespec="seconds")
        con.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (bid, patient_name.strip().title(), p, chosen["id"], chosen["name"], chosen["dept"],
                     d.isoformat(), t, reason.strip() or "Consultation", "booked", "ai_agent", ts, ts))
    msg = (f"Booking confirmed. Booking ID {bid}. {chosen['name']} ({chosen['dept']}), "
           f"{human_date(d)} at {human_time(t)}, room {chosen['room']}, fee Rs {chosen['fee']}. "
           f"Tell the caller the booking ID {bid} and ask them to keep it.")
    return {"message": msg, "status": "booked", "booking_id": bid, "patient_name": patient_name.strip().title(),
            "doctor": chosen["name"], "department": chosen["dept"], "date": human_date(d),
            "time": human_time(t), "room": chosen["room"], "fee_inr": chosen["fee"],
            "instructions": "Please arrive 15 minutes early with a photo ID. An SMS confirmation has been sent."}


@mcp.tool()
def find_appointments(phone: str = "", booking_id: str = "") -> dict:
    """Look up a patient's upcoming appointments by phone number or by booking ID (e.g. CH1042)."""
    with db() as con:
        if booking_id:
            rows = con.execute("SELECT * FROM bookings WHERE id=?", (booking_id.strip().upper(),)).fetchall()
        else:
            p = clean_phone(phone)
            if not p:
                return {"error": "Give a valid 10-digit phone number or a booking ID."}
            rows = con.execute("SELECT * FROM bookings WHERE phone=? AND date>=? ORDER BY date, time",
                               (p, today().isoformat())).fetchall()
    if not rows:
        return {"appointments": [], "message": "No appointments found."}
    return {"appointments": [
        {"booking_id": r["id"], "patient_name": r["patient_name"], "doctor": r["doctor"],
         "department": r["department"], "date": human_date(date.fromisoformat(r["date"])),
         "time": human_time(r["time"]), "status": r["status"]} for r in rows]}


@mcp.tool()
def reschedule_appointment(booking_id: str, new_date: str, new_time: str) -> dict:
    """Move an existing booking (same doctor) to a new date and time. Check free slots first."""
    bid = booking_id.strip().upper()
    d, t = parse_date(new_date), parse_time(new_time)
    if not d or d < today() or not t:
        return {"status": "failed", "reason": "Invalid new date or time."}
    with _lock, db() as con:
        r = con.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
        if not r or r["status"] != "booked":
            return {"status": "failed", "reason": f"No active booking {bid} (it may be cancelled or not exist). "
                    "Tell the caller and offer a new booking."}
        doc = DOC_BY_ID[r["doctor_id"]]
        if t not in free_slots(con, doc, d):
            fail = {"status": "failed", "reason": "That slot is not available.",
                    "free_slots": [human_time(s) for s in free_slots(con, doc, d)[:6]]}
            if doctor_status(doc, d):
                fail["note"] = doctor_status(doc, d)
            return fail
        con.execute("UPDATE bookings SET date=?, time=?, updated_at=?, source='ai_agent' WHERE id=?",
                    (d.isoformat(), t, now().isoformat(timespec="seconds"), bid))
    msg = (f"Rescheduled. Booking ID {bid} is now with {doc['name']} on {human_date(d)} at "
           f"{human_time(t)}, room {doc['room']}, fee Rs {doc['fee']}. Tell the caller the booking ID {bid}.")
    return {"message": msg, "status": "rescheduled", "booking_id": bid, "doctor": doc["name"],
            "date": human_date(d), "time": human_time(t), "room": doc["room"], "fee_inr": doc["fee"]}


@mcp.tool()
def cancel_appointment(booking_id: str, phone: str = "") -> dict:
    """Cancel a booking by ID. If phone is given it must match the booking (identity check)."""
    bid = booking_id.strip().upper()
    with _lock, db() as con:
        r = con.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
        if not r:
            return {"status": "failed", "reason": f"No booking {bid}."}
        if phone and clean_phone(phone) != r["phone"]:
            return {"status": "failed", "reason": "Phone number does not match this booking."}
        if r["status"] == "cancelled":
            return {"message": f"Booking {bid} was already cancelled earlier. Offer a new booking if needed.",
                    "status": "already_cancelled", "booking_id": bid}
        con.execute("UPDATE bookings SET status='cancelled', updated_at=?, source='ai_agent' WHERE id=?",
                    (now().isoformat(timespec="seconds"), bid))
    msg = (f"Cancelled. Booking ID {bid} with {r['doctor']} on {human_date(date.fromisoformat(r['date']))} "
           f"at {human_time(r['time'])} is cancelled. Tell the caller the booking ID {bid} is cancelled.")
    return {"message": msg, "status": "cancelled", "booking_id": bid, "doctor": r["doctor"],
            "date": human_date(date.fromisoformat(r["date"])), "time": human_time(r["time"])}


# ============================================================== dashboard + JSON API
def authed(request: Request) -> bool:
    return hmac.compare_digest(request.query_params.get("token", ""), TOKEN)


async def health(request: Request):
    return JSONResponse({"ok": True, "hospital": HOSPITAL["name"], "time_ist": now().isoformat(timespec="seconds")})


async def dashboard(request: Request):
    return HTMLResponse((HERE / "dashboard.html").read_text(encoding="utf-8"))


async def api_schedule(request: Request):
    if not authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    d = parse_date(request.query_params.get("date", "today")) or today()
    with db() as con:
        rows = con.execute("SELECT * FROM bookings WHERE date=?", (d.isoformat(),)).fetchall()
        by_slot = {(r["doctor_id"], r["time"]): dict(r) for r in rows if r["status"] == "booked"}
        doctors = []
        for doc in DOCTORS:
            status = doctor_status(doc, d)
            cells = []
            if not status:
                for t in all_slots(doc):
                    b = by_slot.get((doc["id"], t))
                    past = d == today() and t < now().strftime("%H:%M")
                    cells.append({"time": t, "state": "booked" if b else ("past" if past else "free"),
                                  "booking": b})
            doctors.append({**doc, "unavailable": status, "cells": cells})
    return JSONResponse({"date": d.isoformat(), "date_human": human_date(d), "today": today().isoformat(),
                         "now": now().strftime("%H:%M"), "departments": DEPARTMENTS, "doctors": doctors})


async def api_bookings(request: Request):
    if not authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    with db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM bookings WHERE source='ai_agent' ORDER BY updated_at DESC LIMIT 50")]
        stats = dict(con.execute(
            """SELECT COUNT(*) total, SUM(status='booked') booked, SUM(status='cancelled') cancelled,
               SUM(source='ai_agent') by_ai FROM bookings WHERE date>=?""", (today().isoformat(),)).fetchone())
    return JSONResponse({"recent_ai_activity": rows, "stats": stats})


mcp_app = mcp.streamable_http_app(
    streamable_http_path="/mcp", stateless_http=True, json_response=True, host="0.0.0.0")
for path, fn in [("/health", health), ("/", dashboard), ("/dashboard", dashboard),
                 ("/api/schedule", api_schedule), ("/api/bookings", api_bookings)]:
    mcp_app.router.routes.append(Route(path, fn))


class BearerTokenMiddleware:
    """Pure ASGI middleware: /mcp requires 'Authorization: Bearer <token>'.
    Missing header -> 401, wrong token -> 403 (constant-time compare).
    Dashboard/API routes use ?token= instead so they open in a browser."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if not auth.startswith("Bearer "):
                resp = JSONResponse({"error": "unauthorized", "detail": "Authorization: Bearer <token> header required."},
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
                await resp(scope, receive, send)
                return
            if not hmac.compare_digest(auth[len("Bearer "):], TOKEN):
                resp = JSONResponse({"error": "forbidden", "detail": "Invalid Bearer token."},
                                    status_code=403, headers={"WWW-Authenticate": "Bearer"})
                await resp(scope, receive, send)
                return
        await self.inner(scope, receive, send)


app = BearerTokenMiddleware(mcp_app)
init_db()

if __name__ == "__main__":
    print(f"Starting TeamXYZ-MCP (City Hospital) on http://0.0.0.0:{PORT}/mcp")
    print("Authentication: Bearer token required on /mcp.")
    print(f"Dashboard: http://localhost:{PORT}/dashboard?token=<MCP_BEARER_TOKEN>")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
