"""Reference data (departments, doctors, procedures, insurers, coverage, hospital info) cached in memory.

Loaded once at startup and after a demo reset. Reads never hit the DB for these.
"""

import re
import threading
from dataclasses import dataclass, field

from sqlalchemy import select

from .. import db
from ..util import clean

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DEPT_ALIASES = {
    "CARD": ["heart", "cardio", "cardiac", "cardiologist", "chest", "bp", "blood pressure", "palpitation"],
    "ORTH": ["bone", "ortho", "orthopedic", "orthopaedic", "orthopedics", "joint", "knee", "back", "spine", "fracture", "shoulder"],
    "NEUR": ["neuro", "brain", "nerve", "neurologist", "headache", "migraine", "seizure", "stroke"],
    "GMED": ["general", "physician", "gp", "fever", "cold", "medicine", "family doctor", "diabetes doctor", "general physician"],
    "PAED": ["child", "children", "kid", "kids", "baby", "paediatric", "pediatric", "pediatrics", "paediatrician", "pediatrician"],
    "GYNO": ["gyn", "gynae", "gynec", "gynaec", "women", "woman", "pregnan", "obstetric", "periods", "obg"],
    "DERM": ["skin", "derma", "dermat", "hair", "acne", "rash", "nail"],
    "ENT": ["ear", "nose", "throat", "sinus", "hearing", "tonsil"],
    "OPHT": ["eye", "ophthal", "vision", "cataract", "spectacle"],
    "GAST": ["stomach", "gastro", "liver", "digest", "acidity", "abdomen", "endoscopy"],
    "PULM": ["lung", "pulmo", "breath", "asthma", "chest physician", "respirat", "cough"],
    "NEPH": ["kidney", "nephro", "renal", "dialysis"],
    "ENDO": ["thyroid", "endocrin", "hormone", "diabetes", "sugar"],
    "RADI": ["radiology", "radiologist", "scan", "x-ray", "xray", "mri", "ct ", "ultrasound"],
}

PROC_ALIASES = {
    "MRI-BRAIN": ["mri brain", "brain mri", "mri head", "head mri"],
    "MRI-SPINE": ["mri spine", "spine mri", "mri back", "back mri", "mri lumbar"],
    "MRI-KNEE": ["mri knee", "knee mri", "mri"],
    "CT-HEAD": ["ct head", "head ct", "ct brain", "ct scan"],
    "CT-CHEST": ["ct chest", "chest ct"],
    "CT-ABD": ["ct abdomen", "ct abd", "abdomen ct"],
    "XRAY-CHEST": ["x-ray chest", "xray chest", "chest x-ray", "chest xray", "x ray chest", "x-ray", "xray"],
    "XRAY-KNEE": ["x-ray knee", "knee x-ray", "xray knee", "knee xray"],
    "USG-ABD": ["ultrasound abdomen", "usg abdomen", "abdomen scan", "ultrasound", "sonography"],
    "USG-PELVIS": ["ultrasound pelvis", "pelvic scan", "usg pelvis"],
    "ECHO": ["echo", "2d echo", "echocardiogram"],
    "ECG": ["ecg", "ekg"],
    "TMT": ["tmt", "treadmill", "stress test"],
    "LAB-CBC": ["cbc", "blood count", "blood test"],
    "LAB-LIPID": ["lipid", "cholesterol"],
    "LAB-HBA1C": ["hba1c", "a1c"],
    "LAB-THYROID": ["thyroid", "tsh"],
    "LAB-FBS": ["fasting sugar", "sugar test", "fbs"],
    "PKG-BASIC": ["basic health check", "health check", "full body check", "master health"],
    "PKG-EXEC": ["executive"],
    "PKG-SENIOR": ["senior citizen", "senior health"],
    "PKG-CARDIAC": ["cardiac health"],
    "PKG-WOMEN": ["women's wellness", "womens wellness", "women wellness"],
}


@dataclass
class Ref:
    departments: dict = field(default_factory=dict)   # id -> row
    doctors: dict = field(default_factory=dict)       # id -> row (+ dept name, days list)
    procedures: dict = field(default_factory=dict)
    resources: dict = field(default_factory=dict)
    insurers: dict = field(default_factory=dict)
    coverage: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


REF = Ref()
_lock = threading.Lock()


def load() -> None:
    with _lock, db.engine.connect() as c:
        r = Ref()
        r.departments = {x["id"]: dict(x) for x in c.execute(select(db.departments)).mappings()}
        for x in c.execute(select(db.doctors)).mappings():
            d = dict(x)
            d["days"] = [int(v) for v in d["consult_days"].split(",")]
            d["dept"] = r.departments[d["department_id"]]["name"]
            d["dept_code"] = r.departments[d["department_id"]]["code"]
            d["lang_list"] = [v.strip() for v in d["languages"].split(",")]
            r.doctors[d["id"]] = d
        r.procedures = {x["id"]: dict(x) for x in c.execute(select(db.procedures)).mappings()}
        r.resources = {x["id"]: dict(x) for x in c.execute(select(db.resources)).mappings()}
        r.insurers = {x["id"]: dict(x) for x in c.execute(select(db.insurers)).mappings()}
        r.coverage = [dict(x) for x in c.execute(select(db.coverage_rules)).mappings()]
        r.info = {x["topic"]: x["content"] for x in c.execute(select(db.hospital_info)).mappings()}
    global REF
    REF.__dict__.update(r.__dict__)


# ------------------------------------------------------------------ lookups (fuzzy, forgiving)
def find_department(text) -> dict | None:
    t = clean(text).lower()
    if not t:
        return None
    for d in REF.departments.values():
        if t in (d["name"].lower(), d["code"].lower()) or d["name"].lower().startswith(t) and len(t) >= 4:
            return d
    by_code = {d["code"]: d for d in REF.departments.values()}
    for code, words in DEPT_ALIASES.items():
        if any(w in t for w in words):
            return by_code.get(code)
    for d in REF.departments.values():
        if d["name"].lower().split()[0][:5] in t:
            return d
    return None


def _name_tokens(name: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z' ]", " ", name.lower().replace("dr.", " ").replace("dr ", " ")).split() if w]


def find_doctors(text) -> list[dict]:
    """Return doctors matching a name fragment (best matches first). Needs >= 3 letters."""
    t = clean(text).lower()
    t = re.sub(r"^(dr\.?|doctor)\s*", "", t).strip()
    if len(t) < 3:
        return []
    q = _name_tokens(t)
    scored = []
    for d in REF.doctors.values():
        toks = _name_tokens(d["name"])
        full = " ".join(toks)
        if t == full or t == d["code"].lower():
            score = 100
        elif all(any(tok.startswith(w) for tok in toks) for w in q):
            score = 50 + 10 * len(q)
        elif any(w in toks for w in q if len(w) >= 4):
            score = 20
        else:
            continue
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return []
    top = scored[0][0]
    return [d for s, d in scored if s == top]


def find_doctor(text) -> dict | None:
    m = find_doctors(text)
    return m[0] if len(m) == 1 else None


def find_procedure(text) -> dict | None:
    t = clean(text).lower()
    if not t:
        return None
    by_code = {p["code"]: p for p in REF.procedures.values()}
    if t.upper() in by_code:
        return by_code[t.upper()]
    for p in REF.procedures.values():
        if t == p["name"].lower():
            return p
    for code, words in PROC_ALIASES.items():   # ordered: specific before generic
        if any(w == t for w in words):
            return by_code.get(code)
    for code, words in PROC_ALIASES.items():
        if any(w in t for w in words if len(w) > 3):
            return by_code.get(code)
    for p in REF.procedures.values():
        if t in p["name"].lower() and len(t) >= 3:
            return p
    return None


def find_insurer(text) -> dict | None:
    t = re.sub(r"[^a-z ]", "", clean(text).lower())
    if not t:
        return None
    for i in REF.insurers.values():
        n = i["name"].lower()
        if t == n or t == i["code"].lower() or t in n or n.split()[0] in t:
            return i
    aliases = {"hdfc": "HDFCERGO", "icici": "ICICILOM", "niva": "NIVA", "max bupa": "NIVA", "bupa": "NIVA",
               "religare": "CARE", "care": "CARE", "aditya": "ABHI", "birla": "ABHI", "tata": "TATAAIG",
               "bajaj": "BAJAJ", "star": "STAR", "cghs": "CGHS", "echs": "ECHS"}
    for k, code in aliases.items():
        if k in t:
            return next((i for i in REF.insurers.values() if i["code"] == code), None)
    return None


def doctors_in(dept_id: int) -> list[dict]:
    return [d for d in REF.doctors.values() if d["department_id"] == dept_id]


def days_text(d: dict) -> str:
    days = d["days"]
    if days == [1, 2, 3, 4, 5, 6]:
        return "Monday to Saturday"
    if days == [1, 2, 3, 4, 5]:
        return "Monday to Friday"
    names = [DAY_FULL[i - 1] for i in days]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]


def hours_text(d: dict) -> str:
    from ..util import human_time
    return f"{human_time(d['start_time'])} to {human_time(d['end_time'])}"


def doctor_card(d: dict, full: bool = True) -> dict:
    out = {"name": d["name"], "department": d["dept"], "days": days_text(d), "hours": hours_text(d),
           "fee_inr": d["fee_inr"], "room": d["room"]}
    if full:
        out["languages"] = ", ".join(d["lang_list"])
    return out


def coverage_rule(insurer_id: int, procedure_id: int | None = None, department_id: int | None = None) -> dict | None:
    for r in REF.coverage:
        if r["insurer_id"] != insurer_id:
            continue
        if procedure_id and r["procedure_id"] == procedure_id:
            return r
        if not procedure_id and department_id and r["department_id"] == department_id:
            return r
    return None
