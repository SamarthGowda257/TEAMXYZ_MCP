"""Lab reports, visit history, prescription refills, insurance + coverage, bills, hospital information."""

import re
from datetime import timedelta

from sqlalchemy import func, insert, select, update

from .. import config, db, notify
from ..util import Result, clean, fail, human_date, human_time, mask_email, norm_code, ok, rupees, short_date
from . import blackboard as bb
from . import patients as pt
from .ref import REF, coverage_rule, doctor_card, doctors_in, find_department, find_doctor, find_doctors, find_insurer, find_procedure, not_found_doctor_message

LR = db.lab_reports
DISCLAIMER = "This is not medical advice; a doctor will guide you."


def _when(dt) -> str:
    if not dt:
        return "soon"
    t = config.today()
    day = "today" if dt.date() == t else "tomorrow" if dt.date() == t + timedelta(days=1) else human_date(dt.date())
    return f"{day} by {human_time(dt.strftime('%H:%M'))}"


# ------------------------------------------------------------------ lab reports
def lab_status(phone, dob, patient_id=None) -> Result:
    with db.engine.begin() as c:
        p = pt.get_by_id(c, patient_id) if patient_id else None
        if not p:
            p, err = pt.check_identity(c, phone, dob)
            if err:
                return err
        rows = [dict(r) for r in c.execute(select(LR).where(LR.c.patient_id == p["id"])
                                           .order_by(LR.c.ordered_at.desc()).limit(3)).mappings()]
    if not rows:
        return ok("You have no lab reports on record with us.", reports=[])
    reports, parts = [], []
    for r in rows:
        item = {"report_id": r["report_code"], "test": r["test_name"], "status": r["status"]}
        if r["status"] == "pending":
            item["expected_at"] = r["expected_at"].isoformat() if r["expected_at"] else None
            parts.append(f"{r['test_name']} is still being processed and should be ready {_when(r['expected_at'])}")
        else:
            item["ready_at"] = r["ready_at"].isoformat() if r["ready_at"] else None
            parts.append(f"{r['test_name']} is ready" + (" and already viewed" if r["status"] == "collected" else ""))
        reports.append(item)
    msg = "; ".join(parts[:3]) + "."
    if any(r["status"] == "ready" for r in rows):
        msg += " I can email the ready report to your registered email."
    return Result(True, pt.say(p, msg[0].upper() + msg[1:], parts[0][0].upper() + parts[0][1:] + "."),
                  {"reports": reports}, related=bb.related(p["phone"]))


def email_report(phone, dob, report_id="", patient_id=None, actor="agent", channel="chat") -> Result:
    with db.engine.begin() as c:
        p = pt.get_by_id(c, patient_id) if patient_id else None
        if not p:
            p, err = pt.check_identity(c, phone, dob)
            if err:
                return err
        if not p["email"]:
            return fail("not_found", "There's no email on your record. You can add one on the website under Profile, or I can request a call back.")
        q = select(LR).where(LR.c.patient_id == p["id"])
        if clean(report_id):
            q = q.where(LR.c.report_code == norm_code(report_id, "LR"))
        else:
            q = q.where(LR.c.status.in_(["ready", "collected"])).order_by(LR.c.ready_at.desc())
        r = c.execute(q.limit(1)).mappings().first()
        if not r:
            return fail("not_found", "I couldn't find a ready report on your record." if not clean(report_id)
                        else "I couldn't find that report under your details.")
        if r["status"] == "pending":
            return fail("not_allowed", f"{r['test_name']} isn't ready yet; it should be ready {_when(r['expected_at'])}. "
                        "We'll email you when it is.")
        notify.queue(c, patient_id=p["id"], channel="email", template="lab_report", to=p["email"],
                     subject=f"Your {r['test_name']} report is ready - {r['report_code']}",
                     body=f"Dear {p['full_name']},\n\nYour {r['test_name']} report ({r['report_code']}) is ready.\n"
                          f"Summary: {r['summary'] or 'Please view the report in the portal.'}\n\n"
                          f"For your privacy the full values are only in the patient portal: {config.PUBLIC_BASE_URL}/portal/reports\n\n"
                          f"{DISCLAIMER}\n\nWellNest Hospitals")
        if r["status"] == "ready":
            c.execute(update(LR).where(LR.c.id == r["id"]).values(status="collected"))
        pt.log(c, p["id"], "email_lab_report", r["report_code"], True, f"Emailed {r['test_name']}", actor, channel)
    bb.invalidate(p["phone"])
    masked = mask_email(p["email"])
    return ok(f"Done. I've emailed your {r['test_name']} report summary to {masked}, with a link to view it securely in the portal.",
              sent_to=masked, report_id=r["report_code"])


def visit_history(phone, dob) -> Result:
    A = db.appointments
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        rows = c.execute(select(A).where(A.c.patient_id == p["id"], A.c.status == "completed")
                         .order_by(A.c.appt_date.desc()).limit(5)).mappings().all()
    visits = []
    for a in rows:
        who = REF.doctors[a["doctor_id"]]["name"] if a["doctor_id"] else REF.procedures[a["procedure_id"]]["name"]
        dept = REF.doctors[a["doctor_id"]]["dept"] if a["doctor_id"] else "Diagnostics"
        visits.append({"date": human_date(a["appt_date"]), "date_iso": a["appt_date"].isoformat(), "with": who, "department": dept})
    if not visits:
        return ok("I don't see any completed visits on your record yet.", visits=[])
    parts = [f"{v['date']} with {v['with']}" for v in visits[:3]]
    return ok("Your recent visits: " + "; ".join(parts) + ".", visits=visits)


def prescription_refill(phone, dob, medicine_name, doctor_name="") -> Result:
    med = clean(medicine_name)
    if not med:
        return fail("invalid_input", "Which medicine do you need a refill for?")
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        doc = find_doctor(doctor_name) if clean(doctor_name) else None
        if not doc:
            rx = c.execute(select(db.prescriptions.c.doctor_id).where(db.prescriptions.c.patient_id == p["id"],
                                                                      db.prescriptions.c.medicine_name.ilike(f"%{med.split()[0]}%"))
                           .limit(1)).first()
            doc = REF.doctors.get(rx[0]) if rx and rx[0] else None
        code = pt.random_code("RX")
        c.execute(insert(db.prescription_requests).values(request_code=code, patient_id=p["id"], doctor_id=doc["id"] if doc else None,
                                                          medicine_name=med[:80], status="pending_doctor", created_at=config.now()))
        pt.log(c, p["id"], "request_prescription_refill", code, True, f"Refill request {med}")
    who = doc["name"] if doc else "your doctor"
    return ok(f"I've sent a refill request for {med} to {who}, reference {code}. The doctor must approve it; "
              "we'll message you once they review it, usually within one working day.",
              request_id=code, status="pending_doctor")


# ------------------------------------------------------------------ insurance
def insurance_info(insurance_provider="") -> Result:
    if not clean(insurance_provider):
        names = [i["name"] for i in list(REF.insurers.values())[:6]]
        return ok(f"We accept {', '.join(names[:5])} and more, including CGHS and ECHS. Most offer cashless treatment. "
                  "The insurance desk is open 9 AM to 6 PM, Monday to Saturday.", accepted=names)
    ins = find_insurer(insurance_provider)
    if not ins:
        return ok(f"{clean(insurance_provider)} isn't on our cashless list. You can still pay and claim reimbursement from your insurer; "
                  "our insurance desk can help with the papers.", accepted=False)
    mode = {"both": "cashless and reimbursement", "cashless": "cashless", "reimbursement": "reimbursement only"}[ins["mode"]]
    return ok(f"Yes, we accept {ins['name']} ({mode}). Please bring: {ins['documents']}. Insurance desk hours are 9 AM to 6 PM, "
              "Monday to Saturday.", accepted=True, insurer=ins["name"], mode=ins["mode"], tpa=ins["tpa_name"],
              documents=ins["documents"], desk_hours="Mon-Sat 9 AM to 6 PM")


def check_coverage(insurance_provider="", procedure="", department="", phone="", dob="") -> Result:
    patient = None
    if clean(phone) and clean(dob):
        with db.engine.begin() as c:
            patient, _err = pt.check_identity(c, phone, dob)
    ins = find_insurer(insurance_provider) if clean(insurance_provider) else None
    if not ins and patient and patient["insurer_id"]:
        ins = REF.insurers[patient["insurer_id"]]
    if not ins:
        if patient and not patient["insurer_id"]:
            return ok("You don't have an insurer on record, so this would be self-pay. I can share the price.", covered="no")
        return fail("invalid_input", "Which insurance company is it? For example Star Health or HDFC ERGO.")
    proc = find_procedure(procedure) if clean(procedure) else None
    dept = None if proc else find_department(department or procedure)
    if not proc and not dept:
        return fail("invalid_input", "Which test or department should I check? For example MRI Knee or Cardiology consultation.")
    rule = coverage_rule(ins["id"], proc["id"] if proc else None, dept["id"] if dept else None)
    what = proc["name"] if proc else f"{dept['name']} consultation"
    price = proc["price_inr"] if proc else min((d["fee_inr"] for d in doctors_in(dept["id"])), default=800)
    if not rule or rule["coverage"] == "no":
        msg = f"{ins['name']} does not cover {what}; the estimated cost is {rupees(price)}. This is an estimate."
        data = dict(covered="no", estimated_patient_share_inr=price, preauth_required=False)
    else:
        share = round(price * (rule["copay_percent"] or 0) / 100)
        if rule["cap_inr"] and price > rule["cap_inr"]:
            share += price - rule["cap_inr"]
        cov = "yes" if rule["coverage"] == "yes" and share == 0 else "partial"
        pre = rule["preauth_required"]
        msg = f"{ins['name']} covers {what}" + (f" with a co-pay; your estimated share is {rupees(share)}" if share else " in full") + "."
        if pre:
            msg += f" Pre-approval is needed first, usually within {rule['preauth_turnaround_hours']} hours; our insurance desk will raise it."
        msg += " This is an estimate; the final amount depends on your policy."
        data = dict(covered=cov, estimated_patient_share_inr=share, preauth_required=pre,
                    preauth_turnaround=f"{rule['preauth_turnaround_hours']} hours" if pre else None)
    data.update(insurer=ins["name"], item=what, price_inr=price)
    key_phone = phone if clean(phone) else None
    if key_phone:
        ref = proc["code"] if proc else None
        if data.get("preauth_required"):
            bb.add(key_phone, "preauth", f"{ins['name']} needs pre-approval for {what}, usually within "
                   f"{data['preauth_turnaround']}; estimated patient share {rupees(data['estimated_patient_share_inr'])}.", 1, ref)
        elif data["covered"] == "no":
            bb.add(key_phone, "not_covered", f"{ins['name']} does not cover {what}; self-pay {rupees(price)}.", 1, ref)
        else:
            bb.add(key_phone, "coverage", f"{ins['name']} covers {what}; estimated share {rupees(data['estimated_patient_share_inr'])}.", 4, ref)
    return ok(msg, **data)


# ------------------------------------------------------------------ bills
def bill_status(phone, dob) -> Result:
    B = db.bills
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        rows = c.execute(select(B).where(B.c.patient_id == p["id"], B.c.status.in_(["due", "partially_paid"]))
                         .order_by(B.c.due_date).limit(3)).mappings().all()
    if not rows:
        return ok("You have no outstanding bills. Thank you.", bills=[])
    bills = [{"bill_id": b["bill_code"], "for": b["description"], "amount_due_inr": b["amount_inr"] - (b["insurer_paid_inr"] or 0),
              "due_date": b["due_date"].isoformat() if b["due_date"] else None} for b in rows]
    total = sum(b["amount_due_inr"] for b in bills)
    b0 = bills[0]
    return ok(f"You have {len(bills)} outstanding bill{'s' if len(bills) > 1 else ''} totalling {rupees(total)}. "
              f"The first, {b0['bill_id']} for {b0['for']}, is due on {short_date(rows[0]['due_date'])}. "
              "I can email you a payment link.", bills=bills, total_due_inr=total)


def send_payment_link(phone, dob, bill_id="") -> Result:
    B = db.bills
    with db.engine.begin() as c:
        p, err = pt.check_identity(c, phone, dob)
        if err:
            return err
        q = select(B).where(B.c.patient_id == p["id"], B.c.status.in_(["due", "partially_paid"]))
        if clean(bill_id):
            q = q.where(B.c.bill_code == norm_code(bill_id, "BL"))
        b = c.execute(q.order_by(B.c.due_date).limit(1)).mappings().first()
        if not b:
            return fail("not_found", "I couldn't find an outstanding bill to pay.")
        if not p["email"]:
            return fail("not_found", "There's no email on your record for the payment link.")
        amt = b["amount_inr"] - (b["insurer_paid_inr"] or 0)
        link = f"{config.PUBLIC_BASE_URL}/pay?bill={b['bill_code']}"
        notify.queue(c, patient_id=p["id"], channel="email", template="payment_link", to=p["email"],
                     subject=f"Payment link for bill {b['bill_code']}",
                     body=f"Dear {p['full_name']},\n\nAmount due: Rs {amt} for {b['description']}.\nPay securely: {link}\n"
                          "(Demo: this link is simulated and never asks for card details by chat or phone.)\n\nWellNest Hospitals")
        notify.queue(c, patient_id=p["id"], channel="sms", template="payment_link", to=p["phone"],
                     body=f"WellNest: pay bill {b['bill_code']} Rs {amt}: {link}")
        pt.log(c, p["id"], "send_payment_link", b["bill_code"], True, f"Payment link Rs {amt}")
    m = mask_email(p["email"])
    return ok(f"I've emailed a secure payment link for {rupees(amt)} to {m}. We never take card details over chat or phone.",
              sent_to=m, bill_id=b["bill_code"], amount_inr=amt)


# ------------------------------------------------------------------ info
def get_doctors(department="", doctor_name="") -> Result:
    if clean(doctor_name):
        m = find_doctors(doctor_name)
        if not m:
            dept = find_department(doctor_name)
            if not dept:
                msg, sug = not_found_doctor_message(doctor_name)
                return fail("not_found", msg, did_you_mean=sug)
            m = doctors_in(dept["id"])
        cards = [doctor_card(d) for d in m[:5]]
        d = cards[0]
        msg = (f"{d['name']} ({d['department']}) consults {d['days']}, {d['hours']}, room {d['room']}, fee {rupees(d['fee_inr'])}. "
               f"Languages: {d['languages']}.") if len(cards) == 1 else "Doctors: " + "; ".join(
            f"{x['name']}, {x['department']}" for x in cards) + "."
        return ok(msg, doctors=cards)
    if clean(department):
        dept = find_department(department)
        if not dept:
            return fail("not_found", f"I couldn't match {clean(department)} to a department.",
                        departments=[d["name"] for d in REF.departments.values()])
        docs = sorted(doctors_in(dept["id"]), key=lambda x: -x["experience_years"])
        cards = [doctor_card(d) for d in docs[:5]]
        msg = f"{dept['name']} doctors: " + "; ".join(f"{x['name']}, {x['days']}, {x['hours']}, fee {rupees(x['fee_inr'])}, "
                                                      f"speaks {x['languages']}" for x in cards[:3]) + "."
        return ok(msg, department=dept["name"], doctors=cards)
    names = [d["name"] for d in REF.departments.values()]
    return ok(f"We have {len(names)} departments, including " + ", ".join(names[:6]) + ". Which one would you like?",
              departments=names)


RED_FLAGS = ["chest pain", "chest tightness", "heart attack", "can't breathe", "cannot breathe", "breathless", "difficulty breathing",
             "shortness of breath", "stroke", "face drooping", "slurred speech", "weakness on one side", "unconscious",
             "fainted", "not responding", "seizure now", "fits", "heavy bleeding", "bleeding a lot", "suicid", "kill myself",
             "end my life", "overdose", "poison", "severe burn", "accident", "head injury", "choking"]
SYMPTOM_MAP = [
    (["chest", "palpitation", "heart", "bp", "blood pressure"], "Cardiology"),
    (["knee", "joint", "back pain", "fracture", "bone", "shoulder", "neck pain", "sprain"], "Orthopaedics"),
    (["headache", "migraine", "dizz", "numb", "seizure", "memory", "tremor"], "Neurology"),
    (["skin", "rash", "acne", "itch", "hair fall", "pimple", "eczema"], "Dermatology"),
    (["ear", "nose", "throat", "sinus", "tonsil", "hearing"], "ENT"),
    (["eye", "vision", "blurr", "red eye"], "Ophthalmology"),
    (["stomach", "acidity", "vomit", "diarr", "constipation", "abdominal", "liver", "jaundice"], "Gastroenterology"),
    (["cough", "asthma", "wheez", "breath", "snoring"], "Pulmonology"),
    (["kidney", "urine", "swelling of feet", "creatinine"], "Nephrology"),
    (["thyroid", "diabetes", "sugar", "weight gain", "hormone"], "Endocrinology"),
    (["period", "pregnan", "pelvic", "pcos", "pcod"], "Gynaecology & Obstetrics"),
    (["child", "baby", "vaccin", "kid"], "Paediatrics"),
    (["fever", "cold", "fatigue", "weakness", "body pain", "infection"], "General Medicine"),
]


# Words that say nothing about which department ("I need a check up", "book a consultation").
ROUTING_FILLER = frozenset("""check checkup consult consultation appointment appointments book booking problem problems issue
issues test tests see specialist treatment review visit general need help""".split())


def is_emergency(text: str) -> bool:
    t = clean(text).lower()
    return any(f in t for f in RED_FLAGS)


def suggest_department(symptoms) -> Result:
    t = clean(symptoms).lower()
    if not t:
        return fail("invalid_input", "Please describe the main problem in a few words.")
    if is_emergency(t):
        return ok("This may be an emergency. Please call 108 now or go to the nearest emergency department. "
                  "Our emergency entrance B is open 24 hours.", department="Emergency", emergency=True, disclaimer=DISCLAIMER)
    for words, dept in SYMPTOM_MAP:
        if any(w in t for w in words):
            return ok(f"{dept} would be the right department to start with. {DISCLAIMER} Shall I check free slots?",
                      department=dept, emergency=False, disclaimer=DISCLAIMER, matched_by="keywords")
    # No rule matched: hybrid search over department passages (patients' own words, typos, paraphrases).
    # Red flags stay deterministic above; a meaning match to the emergency passage only ever escalates.
    from .. import search
    res = search.search(t, ref_prefixes=("kb:dept:", "kb:faq:emergency_signs"), k=2, ignore=ROUTING_FILLER)
    if res["hits"]:
        h = res["hits"][0]
        if h["ref"] == "kb:faq:emergency_signs":
            return ok("This may be an emergency. Please call 108 now or go to the nearest emergency department. "
                      "Our emergency entrance B is open 24 hours.", department="Emergency", emergency=True,
                      disclaimer=DISCLAIMER, matched_by=res["mode"])
        dept = h["title"]
        if dept != "Radiology":
            return ok(f"{dept} would be the right department to start with. {DISCLAIMER} Shall I check free slots?",
                      department=dept, emergency=False, disclaimer=DISCLAIMER, matched_by=res["mode"])
    return ok(f"General Medicine is a good place to start; the physician can refer you if needed. {DISCLAIMER}",
              department="General Medicine", emergency=False, disclaimer=DISCLAIMER, matched_by="default")


def hospital_info(topic="") -> Result:
    t = clean(topic).lower()
    keys = {"address": ["address", "where", "location", "direction", "map", "reach"], "hours": ["hour", "timing", "open", "close", "time"],
            "parking": ["park", "car", "valet"], "visiting": ["visit", "attendant", "ward"], "emergency": ["emergency", "casualty", "108", "ambulance"],
            "facilities": ["facilit", "service", "cafeteria", "atm", "wheelchair"], "pharmacy": ["pharmac", "medicine", "chemist"],
            "contact": ["contact", "phone", "number", "email", "call"]}
    if t in keys:
        return ok(REF.info[t], topic=t)
    if not t:
        return ok(f"{REF.info['address']} {REF.info['hours']}", topic="address,hours")
    from .. import search
    # 1) The caller's own words: hybrid search over the knowledge base (FAQ, visiting, insurance, procedures,
    #    departments), so "can my son stay overnight with me?" finds the attendant rule, not opening hours.
    res = search.search(t, ref_prefixes=("kb:",), k=3, gate=False)
    hits = res["hits"]
    sure = [h for h in hits if h.get("confident")]
    if sure:
        h = sure[0]
        return ok(h["body"], topic=h["ref"].split(":", 1)[1], source=h["title"], matched_by=res["mode"])
    # 2) A weaker FAQ / hospital-info match that still shares a real word ("grab a bite to eat" -> cafeteria) beats a
    #    generic keyword rule. Procedures and departments need a confident match (no "blood" -> blood sugar test).
    for h in hits:
        sig = h["signals"]
        shared = sig.get("fts") or (sig.get("words") and not sig["words"].startswith("0/"))
        if shared and h["ref"].startswith(("kb:faq:", "kb:info:")):
            return ok(h["body"], topic=h["ref"].split(":", 1)[1], source=h["title"], matched_by=res["mode"] + " (partial)")
    # 3) Simple topic words ("where are you", "timings", "parking"), whole words only.
    words = set(re.findall(r"[a-z0-9]+", t))
    for k, kws in keys.items():
        if any(w in words or (len(w) > 4 and any(x.startswith(w) for x in words)) for w in kws):
            return ok(REF.info[k], topic=k)
    # 4) Honest "don't know" instead of a random fact.
    return ok("I don't have that information. Our front desk on 080 4000 1234 can help, or I can arrange a call back.",
              topic=None, found=False)


def visit_instructions(department="", procedure="") -> Result:
    proc = find_procedure(procedure) if clean(procedure) else None
    if proc:
        ins = proc["instructions"] or ""
        extra = (f" Fasting: {proc['fasting_hours']} hours." if proc["fasting_hours"] and "fast" not in ins.lower() else
                 " No fasting is needed." if "fast" not in ins.lower() else "")
        extra += "" if "photo id" in ins.lower() else " Bring a photo ID, the doctor's request and any previous reports."
        return ok(f"For {proc['name']}: {ins}{extra}",
                  procedure=proc["name"], fasting_hours=proc["fasting_hours"], arrive_before_min=30 if proc["category"] in ("MRI", "CT") else 20,
                  preauth_required=proc["preauth_required"])
    dept = find_department(department)
    name = dept["name"] if dept else "your visit"
    return ok(f"For {name}: please arrive 15 minutes early with a photo ID, your insurance card and any old reports or medicines. "
              "No fasting is needed unless your doctor asked for blood tests.", department=name, fasting_hours=0, arrive_before_min=15)
