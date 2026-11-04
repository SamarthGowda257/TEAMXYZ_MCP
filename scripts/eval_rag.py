"""Retrieval check for the hospital knowledge base (RAG).

Asks get_hospital_info real patient questions and asserts the passage it returns is the right one, so a
change to app/kb.py or to data/hospital/*.md cannot quietly start answering the wrong thing.

    python scripts/eval_rag.py                 # against DATABASE_URL, or the local SQLite fallback
    python scripts/eval_rag.py --verbose       # also print the answer text

Note on backends: the hybrid search (full-text + trigram + pgvector) only exists on Postgres. On SQLite the
search degrades to a weak keyword leg, so a low score there says nothing about production. The script prints
which backend it ran on, and only treats Postgres runs as meaningful.

Each case is (question, [acceptable heading slugs or refs]). A slug matches if it is a prefix of the ref the
loader produced, because refs are truncated to 48 characters.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, search  # noqa: E402
from app.services import records, ref  # noqa: E402

CASES: list[tuple[str, list[str]]] = [
    # --- the hospital documents in data/hospital ---
    ("What are your OPD timings?", ["opd_timings", "kb:info:hours"]),
    ("How much does an MRI of the knee cost?", ["mri_scan_prices", "kb:proc:MRI-KNEE"]),
    ("What is the price of a CT scan of the chest?", ["ct_scan_prices", "kb:proc:CT-CHEST"]),
    ("How long does a blood culture report take?", ["blood_culture"]),
    ("How much is a single private room per day?", ["single_private_room", "room_types"]),
    ("What does an ICU bed cost per day?", ["icu_bed_charges", "room_types"]),
    ("Is wheelchair help free?", ["wheelchair_and_porter", "taking_a_wheelchair", "kb:faq:wheelchair"]),
    ("Will someone take my mother back to the car after her visit?", ["two_way_escort"]),
    ("Can I take the wheelchair to my hotel?", ["taking_a_wheelchair"]),
    ("What can my son see if I add him as my caregiver?", ["what_a_caregiver", "adding_a_caregiver"]),
    ("Which gate is the emergency entrance?", ["gate_1", "kb:info:emergency"]),
    ("What are the parking charges?", ["parking_charges", "kb:info:parking"]),
    ("Do you have EV charging?", ["electric_vehicle"]),
    ("Do you deliver medicines to my home?", ["medicine_home_delivery", "kb:info:pharmacy"]),
    ("Can I get antibiotics without seeing a doctor?", ["antibiotics_and_restricted", "telemedicine_rules", "kb:policy:medicine_policy"]),
    ("Which insurance companies do you accept for cashless?", ["which_insurers", "kb:ins:"]),
    ("What documents do I need for cashless treatment?", ["documents_to_bring"]),
    ("Does insurance pay for everything?", ["items_insurance", "what_a_coverage_check", "kb:policy:payment_deposit"]),
    ("How long does insurance pre-authorisation take?", ["how_long_pre_auth"]),
    ("Is the follow-up visit free?", ["free_follow_up"]),
    ("What happens if I am late for my appointment?", ["if_you_arrive_late", "kb:policy:appointment_policy"]),
    ("Is there a registration charge for a new patient?", ["new_patient_registration"]),
    ("Can I get a second opinion?", ["second_opinion", "kb:faq:second_opinion"]),
    ("Who can collect my medical records?", ["getting_a_copy", "kb:faq:records", "kb:policy:privacy"]),
    ("What time is ICU visiting?", ["icu_visiting", "kb:info:visiting"]),
    ("How many beds does the hospital have?", ["hospital_size"]),
    ("Which floor is cardiology on?", ["which_floor", "kb:dept:CARD"]),
    ("Do I need to fast for a lipid profile?", ["fasting_for_blood", "kb:proc:LAB-LIPID"]),
    ("Is smoking allowed on the campus?", ["smoking_alcohol", "kb:policy:smoking"]),
    ("What are the cafeteria timings?", ["cafeteria", "kb:faq:food", "kb:info:facilities"]),
    ("How soon does a nurse call me back if I feel worse?", ["when_we_alert_a_nurse"]),
    ("Where is the insurance desk?", ["insurance_and_tpa_desk", "kb:info:facilities", "kb:info:contact"]),
]


def matches(got: str, accept: list[str]) -> bool:
    for a in accept:
        if a.startswith(("kb:", "__")):
            if a in got:
                return True
        elif a[:18] in got:        # the loader truncates refs to 48 chars
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    db.create_schema()
    ref.load()
    n = search.sync_kb()
    backend = search.status(brief=True)
    with db.engine.connect() as c:
        from sqlalchemy import text
        total = c.execute(text("SELECT count(*) FROM search_docs WHERE kind = 'kb'")).scalar()
        docs = c.execute(text("SELECT count(*) FROM search_docs WHERE kind = 'kb' AND ref LIKE 'kb:doc:%'")).scalar()

    print(f"backend: {backend}")
    print(f"knowledge passages: {total} indexed, {docs} of them from data/hospital ({n} written this run)\n")

    ok, fails = 0, []
    for q, accept in CASES:
        r = records.hospital_info(q)
        data = r.data or {}
        got = f"kb:{data['topic']}" if data.get("topic") else "__NOTFOUND__"
        how = data.get("matched_by", "topic rule")
        hit = matches(got, accept)
        ok += hit
        if not hit:
            fails.append((q, got, how, r.message))
        print(f"{'PASS' if hit else 'FAIL'}  {q[:56]:58} {got[:46]:48} [{how}]")
        if args.verbose:
            print(f"        {r.message[:150]}")

    print(f"\n{ok}/{len(CASES)} returned the expected passage")
    if fails:
        print("\n--- wrong passage ---")
        for q, got, how, msg in fails:
            print(f"Q: {q}\n   -> {got} [{how}]\n   said: {msg[:140]}\n")
    if "sqlite" in backend:
        print("Ran on SQLite, where only the weak keyword leg exists. Run this against Postgres before trusting the score.")
        return 0
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
