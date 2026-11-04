"""Hospital knowledge passages for hybrid search (RAG for get_hospital_info and suggest_department).

Built from the database's reference data (hospital_info, departments, procedures, insurers) plus the curated FAQ
below, which matches what the website says. Each passage is one short, speakable answer: the tool returns the best
passage as its message, so there is no generation step and nothing to hallucinate.
"""

import re
from pathlib import Path

from . import config
from .services.ref import REF

# Hospital documents you add: data/hospital/*.md or *.txt. Each "## Heading" section (or paragraph block) becomes
# one passage; see data/hospital/README.md. They are indexed and embedded like the passages below.
DOCS_DIR = config.ROOT / "data" / "hospital"
MAX_PASSAGE = 700

# Lay words patients actually use, per department code. Used by both the keyword and the meaning legs.
DEPT_WORDS = {
    "CARD": "heart, chest pain or tightness, palpitations, racing or irregular heartbeat, high blood pressure, BP, "
            "breathless when walking, swelling in the legs from the heart, cholesterol, ECG, echo, angiogram",
    "ORTH": "knee pain, joint pain, back pain, slipped disc, neck pain, shoulder pain, fracture, broken bone, sprain, "
            "sports injury, arthritis, difficulty walking or climbing stairs",
    "NEUR": "headache, migraine, dizziness, giddiness, fits or seizures, numbness, tingling, tremor, memory loss, "
            "stroke follow-up, nerve pain, fainting spells",
    "GMED": "fever, cold, cough for a few days, body pain, tiredness, weakness, infections, general check-up, "
            "not feeling well, viral fever, dengue or typhoid tests",
    "PAED": "child, baby, infant, newborn, kid, vaccination, immunisation, growth, feeding problems, child fever",
    "GYNO": "periods, irregular or painful periods, pregnancy, antenatal check-up, PCOS, PCOD, white discharge, "
            "pelvic pain, menopause, fertility",
    "DERM": "skin, rash, itching, acne, pimples, hair fall, dandruff, eczema, allergy on skin, fungal infection, "
            "pigmentation, nails",
    "ENT": "ear pain, ear discharge, hearing loss, ringing in ears, blocked nose, sinus, nose bleed, sore throat, "
           "tonsils, voice change, snoring",
    "OPHT": "eyes, blurred vision, red eye, watering eyes, cataract, glasses, spectacles, eye pain, night vision, "
            "diabetic eye check",
    "GAST": "stomach pain, acidity, gas, bloating, vomiting, loose motions, diarrhoea, constipation, liver, jaundice, "
            "piles, blood in stool, endoscopy, colonoscopy",
    "PULM": "cough that does not go away, asthma, wheezing, breathlessness, lung infection, TB, snoring and sleep apnoea, "
            "smoking related lung problems",
    "NEPH": "kidney, urine problems, burning urination, frequent urination, swelling of feet, creatinine, dialysis, "
            "kidney stones follow-up, protein in urine",
    "ENDO": "diabetes, high sugar, thyroid, weight gain, hormone problems, excessive thirst, frequent urination with "
            "high sugar, PCOS hormones",
    "RADI": "MRI, CT scan, X-ray, ultrasound, mammogram, DEXA bone density scan",
}

# Curated FAQ (consistent with frontend/src/content.ts and hospital_info). (ref, title, answer)
FAQ = [
    ("food", "Food and cafeteria", "The cafeteria on the ground floor is open 7 AM to 10 PM and serves vegetarian meals. "
     "Ward patients get meals from our kitchen as advised by the dietitian; outside food for patients needs the nurse's approval."),
    ("wifi", "Wi-Fi and internet", "Free guest Wi-Fi (wifi internet) called WellNest-Guest is available in all waiting areas. Ask the front desk for the password."),
    ("documents", "What to bring", "Please bring a photo ID, your insurance card, your booking ID, old reports and the medicines you take. "
     "Arrive 15 minutes early."),
    ("attendant", "Attendant pass", "Each admitted patient gets one attendant pass. The attendant can stay overnight in the ward. "
     "Ward visiting hours are 11 AM to 1 PM and 5 PM to 7 PM."),
    ("icu", "ICU visiting hours", "ICU visiting hours are 5 PM to 6 PM, one visitor at a time. Children under 12 are not allowed in the ICU. "
     "Doctors brief the family every day at 12 noon."),
    ("children", "Children visiting", "Children under 12 may visit general wards with an adult during visiting hours, but not the ICU."),
    ("payment", "Payment methods", "We accept UPI, debit and credit cards, net banking and cash. You can also pay a bill online from the "
     "payment link we send by SMS and email."),
    ("cashless", "Cashless insurance", "For cashless treatment, show your insurance card and photo ID at the TPA desk on the ground floor. "
     "Planned procedures like MRI or CT may need pre-authorisation, which usually takes 4 to 24 hours. TPA desk: 080 4000 1250."),
    ("reports", "Lab reports", "Most blood reports are ready the same day. Your report is in the patient portal under Lab reports, "
     "and we can email you a secure link. Printed copies are at the lab counter on the ground floor."),
    ("records", "Medical records", "To get copies of your medical records or a discharge summary, ask at the medical records desk "
     "on the 1st floor with a photo ID. Copies are ready within 2 working days."),
    ("second_opinion", "Second opinion", "You can book a second-opinion consultation with any of our specialists. Bring your earlier reports "
     "and scans; the doctor will review them during the visit."),
    ("cancel_policy", "Cancelling or changing a booking", "You can cancel or reschedule a booking free of charge on chat, by phone or in "
     "the patient portal. If your doctor is fully booked, we can add you to the waitlist and message you when a slot opens."),
    ("waitlist", "Waitlist", "If the doctor you want is full, join the waitlist. When a slot opens we send you an offer by SMS and email; "
     "the slot is held for you for 30 minutes, so accept it from the link or on chat to confirm."),
    ("senior", "Senior citizen help", "Our senior citizen desk at entrance B offers wheelchair help, priority billing, early-morning slots "
     "and updates to a family member if you wish."),
    ("wheelchair", "Wheelchairs and accessibility", "Wheelchairs are free at the main entrance and entrance B. All floors have lifts and "
     "accessible toilets. Ask at the front desk for a staff member to help."),
    ("languages", "Languages", "Our staff and doctors speak English, Kannada, Hindi, Tamil, Telugu and Malayalam. Ask for a doctor who "
     "speaks your language when you book."),
    ("packages", "Health check packages", "Basic Health Check: 2,499 rupees, 32 tests. Executive Health Check: 6,999 rupees, 68 tests. "
     "Senior Citizen Health Check: 4,999 rupees, 54 tests. Come fasting for 10 to 12 hours."),
    ("home_collection", "Home sample collection", "We collect blood samples at home within 10 km, 7 AM to 11 AM, for a fee of 200 rupees. "
     "Book it on chat or by phone."),
    ("teleconsult", "Video consultation", "Follow-up visits can be done by video for most departments. Ask for a video consultation "
     "when you book; the link comes by SMS and email."),
    ("ambulance", "Ambulance", "For an emergency call 108. Our own ambulance service is on 080 4000 1108, 24 hours, with ventilator-equipped "
     "ambulances."),
    ("blood_bank", "Blood bank", "The blood bank on the ground floor is open 24 hours. Voluntary donors are welcome from 9 AM to 5 PM."),
    ("lost_found", "Lost and found", "Lost something? Ask at the security desk at the main entrance or call the front desk on 080 4000 1234."),
    ("feedback", "Complaints and feedback", "We want to hear from you. Tell us on chat, write to care@wellnest.test, or ask for the "
     "patient relations officer at the front desk, 9 AM to 6 PM."),
    ("prayer", "Prayer room", "A quiet prayer and meditation room is on the 1st floor, open all day for patients and families."),
    ("atm", "ATM", "There is an ATM next to the pharmacy on the ground floor."),
    ("discharge", "Discharge", "Discharge usually happens before 12 noon. The billing team prepares your final bill and the doctor gives "
     "a discharge summary with medicines and follow-up date."),
    ("getting_here", "Getting here", "We are next to the Innovative Multiplex on Outer Ring Road, 10 minutes from Marathahalli bridge. "
     "Nearest BMTC stop: Kalamandir."),
    ("emergency_signs", "Emergency warning signs", "Chest pain or pressure, trouble breathing, a face drooping or slurred speech, sudden "
     "weakness on one side, fainting or not responding, heavy bleeding, a seizure, a severe burn or head injury are emergencies. "
     "Call 108 now or come to emergency entrance B, open 24 hours."),
]


# Hospital policies (demo wording, to be replaced by the real policies via data/hospital/). (ref, title, answer)
POLICIES = [
    ("visitors", "Visitor policy", "Visitors are welcome during ward visiting hours, 11 AM to 1 PM and 5 PM to 7 PM, two at a time per "
     "patient. Please carry a photo ID and the visitor pass from the front desk. The ICU allows one visitor from 5 PM to 6 PM."),
    ("cancellation", "Cancellation and refund policy", "You can cancel or reschedule an outpatient booking free of charge until the "
     "appointment time. Prepaid consultation fees are refunded to the original payment method within 5 to 7 working days. "
     "Health check packages cancelled less than 24 hours before are refunded after a 10 percent fee."),
    ("payment_deposit", "Admission deposit and billing policy", "Planned admissions need an advance deposit, which depends on the "
     "procedure and room type; the billing desk gives an estimate in writing. Cashless insurance patients pay only items the "
     "policy does not cover. Final bills are settled at discharge."),
    ("privacy", "Patient privacy and records policy", "Your medical information is shared only with you, people you authorise in "
     "writing, and your treating team. Reports are sent only to your registered email or the patient portal. Copies of records "
     "are given to the patient or an authorised family member with a photo ID."),
    ("consent", "Consent policy", "Procedures and surgeries need your written informed consent after the doctor explains the benefits "
     "and risks. For a child or a patient who cannot decide, a parent or legal guardian gives consent."),
    ("patient_rights", "Patient rights", "You have the right to respectful care, to know your diagnosis and treatment options in a "
     "language you understand, to a second opinion, to see your bill in detail, to privacy, and to raise a complaint without it "
     "affecting your care."),
    ("complaints", "Complaint and grievance policy", "Raise a complaint on chat, by phone, by email to care@wellnest.test, or with the "
     "patient relations officer at the front desk. We acknowledge within 24 hours and aim to resolve within 7 working days."),
    ("smoking", "No smoking and no alcohol", "The whole campus is no smoking, no tobacco and no alcohol, including the parking areas."),
    ("valuables", "Valuables policy", "Please do not bring jewellery or large amounts of cash. The hospital is not responsible for "
     "valuables left in rooms; the nursing station can keep small items in a locker."),
    ("outside_food", "Outside food policy", "Outside food for patients needs the nurse's or dietitian's approval. Visitors may use the "
     "cafeteria on the ground floor."),
    ("photography", "Photography and mobile phones", "Please do not take photos or videos of other patients or staff. Mobile phones "
     "should be on silent in wards and switched off in the ICU and operating areas."),
    ("discharge_policy", "Discharge policy", "Discharge usually happens before 12 noon after the doctor's review. You receive a "
     "discharge summary, medicine list and follow-up date. Leaving against medical advice needs a signed form."),
    ("children_policy", "Children and minors policy", "Patients under 18 must be accompanied by a parent or guardian, who gives consent "
     "for treatment. Children under 12 cannot visit the ICU."),
    ("emergency_policy", "Emergency care policy", "Emergency treatment is never delayed for payment or paperwork. Call 108 or come to "
     "emergency entrance B, open 24 hours. Medico-legal cases are reported to the police as the law requires."),
    ("medicine_policy", "Medicine and prescription policy", "Prescription refills are approved only by a doctor. The pharmacy needs a "
     "valid prescription for prescription-only medicines. We never recommend medicines over chat or phone."),
    ("appointment_policy", "Appointment and late arrival policy", "Please arrive 15 minutes before your appointment. If you are more "
     "than 15 minutes late, the doctor may see you after the next patient or we can reschedule you at no charge."),
]


# Words patients use for each FAQ. Added to the searchable title only; the spoken answer stays clean.
FAQ_KEYWORDS = {
    "lost_found": "lost phone, wallet, bag, umbrella, keys, documents",
    "blood_bank": "donate blood, blood donation, donor",
    "records": "copies of papers, discharge summary, case sheet",
    "teleconsult": "video call, online consultation, teleconsultation from home",
    "payment": "UPI, PhonePe, Google Pay, GPay, Paytm, card, cash",
    "food": "food, eat, grab a bite, hungry, snacks, canteen, coffee, tea, breakfast, lunch, dinner, meals",
    "prayer": "pray, temple, mosque, church, meditation",
    "home_collection": "blood test at home, sample from home, house visit",
    "atm": "cash withdrawal, cash machine",
    "wifi": "internet, online, wifi password",
    "attendant": "stay overnight, stay with patient, relative staying",
}


def documents() -> list[dict]:
    """All knowledge passages: {ref, title, body}."""
    docs = [{"ref": f"kb:info:{k}", "title": k.replace("_", " ").title(), "body": v} for k, v in REF.info.items()]
    for d in REF.departments.values():
        extra = DEPT_WORDS.get(d["code"], "")
        docs.append({"ref": f"kb:dept:{d['code']}", "title": d["name"],
                     "body": f"{d['name']} ({d['floor']}): {d['description'] or ''} Common reasons to visit: {extra}."})
    for p in REF.procedures.values():
        bits = [f"{p['name']}: {p['instructions'] or ''}"]
        if p.get("fasting_hours"):
            bits.append(f"Fasting: {p['fasting_hours']} hours.")
        if p.get("preauth_required"):
            bits.append("Insurance pre-authorisation is usually needed.")
        docs.append({"ref": f"kb:proc:{p['code']}", "title": p["name"], "body": " ".join(bits)})
    for i in REF.insurers.values():
        mode = {"both": "cashless and reimbursement", "cashless": "cashless", "reimbursement": "reimbursement only"}.get(i["mode"], i["mode"])
        docs.append({"ref": f"kb:ins:{i['code']}", "title": i["name"],
                     "body": f"We accept {i['name']} ({mode}). {i.get('notes') or ''} Documents: {i.get('documents') or 'insurance card and photo ID'}."})
    docs += [{"ref": f"kb:faq:{r}", "title": f"{t}: {FAQ_KEYWORDS[r]}" if r in FAQ_KEYWORDS else t, "body": b}
             for r, t, b in FAQ]
    docs += [{"ref": f"kb:policy:{r}", "title": t, "body": b} for r, t, b in POLICIES]
    return docs + hospital_documents()


def _slug(text: str, n: int) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:n] or "x"


def _passages(text: str) -> list[str]:
    """Split a section into speakable passages of at most MAX_PASSAGE characters, at paragraph or sentence ends."""
    out, cur = [], ""
    for part in re.split(r"\n\s*\n|(?<=[.!?])\s+", text.strip()):
        part = " ".join(part.split())
        if not part:
            continue
        if cur and len(cur) + 1 + len(part) > MAX_PASSAGE:
            out.append(cur)
            cur = part
        else:
            cur = f"{cur} {part}".strip()
    return out + ([cur] if cur else [])


def hospital_documents(folder: Path | None = None) -> list[dict]:
    """Passages from data/hospital/*.md|*.txt: one per '## ' section (split further if long). README.md is skipped."""
    folder = folder or DOCS_DIR
    docs, seen = [], set()
    for f in sorted(folder.glob("*")) if folder.exists() else []:
        if f.suffix.lower() not in (".md", ".txt") or f.name.lower() == "readme.md":
            continue
        text = f.read_text(encoding="utf-8")
        doc_title = f.stem.replace("_", " ").replace("-", " ").title()
        sections = re.split(r"(?m)^#{1,3}\s+(.+)$", text)
        pairs = [(doc_title, sections[0])] + list(zip(sections[1::2], sections[2::2]))
        for head, body in pairs:
            for i, chunk in enumerate(_passages(body)):
                ref = f"kb:doc:{_slug(f.stem, 14)}:{_slug(head, 18)}" + (f":{i + 1}" if i else "")
                while ref in seen:
                    ref += "_"
                seen.add(ref)
                docs.append({"ref": ref[:48], "title": f"{head.strip()} ({doc_title})"[:160], "body": chunk})
    return docs
