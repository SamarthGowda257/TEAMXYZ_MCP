"""Hospital knowledge passages for hybrid search (RAG for get_hospital_info and suggest_department).

Built from the database's reference data (hospital_info, departments, procedures, insurers) plus the curated FAQ
below, which matches what the website says. Each passage is one short, speakable answer: the tool returns the best
passage as its message, so there is no generation step and nothing to hallucinate.
"""

from .services.ref import REF

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
     "accept it within 2 hours to confirm."),
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
    docs += [{"ref": f"kb:faq:{r}", "title": t, "body": b} for r, t, b in FAQ]
    return docs
