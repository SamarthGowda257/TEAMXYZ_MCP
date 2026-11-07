"""Prescriptions and the dispensing rules engine (Pharmacy V3).

Every medicine line in an order passes these checks on the server, in this order:
  1. patient fit      minimum age, listed allergies, pregnancy caution (pharmacist review)
  2. prescription     H and H1 need an active prescription item with days of supply left, not refilled too early,
                      at most `max_days_per_order` days per order (rounded up to whole packs)
  3. OTC limits       per order and per rolling 7 days, by ingredient across brands (mg) or by units
  4. duplicates       two products of the same ingredient in one order, or one ordered in the last 3 days
Schedule X is refused before any of this (pharmacy.order).

Quantities on a prescription are counted in days of supply: days = units / (dose_units x times_per_day), or
packs x days_per_unit for devices (pens, inhalers, bottles). Days already supplied are summed from `dispensations`
(reserved or dispensed), so two orders racing for the same prescription can't both use the last days.

Limits live in `drug_rules`, owned by the pharmacist. The seeded numbers are demo defaults, marked unsigned until a
pharmacist signs them off in the staff console.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from datetime import date, datetime, timedelta

from sqlalchemy import func, insert, or_, select, update

from .. import config, db, events, notify
from ..util import Result, clean, fail, human_date, ok
from . import patients as pt

RX, ITEM, DISP, RULES, INV, ORD = (db.prescriptions, db.prescription_items, db.dispensations, db.drug_rules,
                                   db.pharmacy_inventory, db.pharmacy_orders)
VALID_DAYS = 182                 # a prescription is honoured for 6 months unless the doctor sets a shorter date
DUPLICATE_WINDOW_DAYS = 3
REVIEW_HOURS = (8, 22)           # pharmacist review desk, IST
PHARMACY_DESK = "080 4000 1240"
GP = "Dr. Anil Kumar"

# ------------------------------------------------------------------ reference data
# ingredient: max adult mg/day, min age, pregnancy caution, OTC mg/order, OTC mg/7 days, OTC units/order, units/7 days,
# early refill %, max days per order, always pharmacist. Clinical numbers are DEMO DEFAULTS pending pharmacist sign-off.
RULES_SEED = {
    "paracetamol":  (4000, 12, False, 29250, 39000, None, None, 80, 30, False),
    "cetirizine":   (10, 6, False, None, None, 30, 30, 80, 30, False),
    "metformin":    (2550, 10, False, None, None, None, None, 80, 30, False),
    "telmisartan":  (80, 18, True, None, None, None, None, 80, 30, False),
    "amlodipine":   (10, 6, False, None, None, None, None, 80, 30, False),
    "atorvastatin": (80, 10, True, None, None, None, None, 80, 30, False),
    "rosuvastatin": (40, 10, True, None, None, None, None, 80, 30, False),
    "glimepiride":  (8, 18, True, None, None, None, None, 80, 30, False),
    "levothyroxine": (0.3, None, False, None, None, None, None, 80, 30, False),
    "aspirin":      (325, 16, True, None, None, None, None, 80, 30, False),
    "pantoprazole": (80, 12, False, None, None, None, None, 80, 30, False),
    "montelukast":  (10, 2, False, None, None, None, None, 80, 30, False),
    "salbutamol":   (None, 4, False, None, None, None, None, 80, 30, False),
    "budesonide":   (None, 6, False, None, None, None, None, 80, 30, False),
    "formoterol":   (None, 6, False, None, None, None, None, 80, 30, False),
    "amoxicillin":  (3000, None, False, None, None, None, None, 100, 14, False),
    "azithromycin": (500, None, False, None, None, None, None, 100, 7, False),
    "insulin":      (None, None, False, None, None, None, None, 70, 30, True),
    "cholecalciferol": (None, None, False, None, None, 8, 8, 80, 56, False),
}
DEVICE_DAYS = {"LANTUS": 30, "MIXTARD": 30, "ASTHALIN": 30, "BUDECORT": 30, "FORACORT": 30}


def ingredient_of(generic_name: str) -> str:
    """The rules key for a product: its first active ingredient, lower case ('Aspirin + Atorvastatin' -> aspirin)."""
    g = clean(generic_name).lower()
    for key in sorted(RULES_SEED, key=len, reverse=True):
        if key in g:
            return key
    return re.split(r"[ +(,]", g)[0] if g else ""


def _strength_mg(strength: str) -> float | None:
    s = clean(strength).lower()
    m = re.match(r"([\d.]+)\s*(mg|mcg|g)\b", s)
    if not m:
        return None
    v = float(m.group(1))
    return {"mg": v, "mcg": v / 1000, "g": v * 1000}[m.group(2)]


def _units_per_pack(pack: str) -> float:
    m = re.search(r"of\s+(\d+)\s*(tablets?|capsules?|lozenges?|sachets?)", clean(pack).lower())
    return float(m.group(1)) if m else 1.0


def ensure_reference(conn) -> dict:
    """Fill the V3 product fields and the rules table where missing. Idempotent; never overwrites staff edits."""
    done = {"products": 0, "rules": 0}
    for r in conn.execute(select(INV).where(or_(INV.c.ingredient.is_(None), INV.c.units_per_pack.is_(None)))).mappings().all():
        upp = _units_per_pack(r["pack"])
        conn.execute(update(INV).where(INV.c.id == r["id"]).values(
            ingredient=r["ingredient"] or ingredient_of(r["generic_name"]),
            strength_mg=r["strength_mg"] if r["strength_mg"] is not None else _strength_mg(r["strength"]),
            units_per_pack=upp, days_per_unit=DEVICE_DAYS.get(r["medicine_code"], 30.0 if upp == 1 else None),
            returnable=bool(r["returnable"]) if r["returnable"] is not None else False))
        done["products"] += 1
    have = {x[0] for x in conn.execute(select(RULES.c.ingredient))}
    for ing, v in RULES_SEED.items():
        if ing in have:
            continue
        conn.execute(insert(RULES).values(ingredient=ing, max_daily_mg_adult=v[0], min_age_years=v[1], pregnancy_caution=v[2],
                                          otc_max_mg_per_order=v[3], otc_max_mg_per_7d=v[4], otc_max_units_per_order=v[5],
                                          otc_max_units_per_7d=v[6], early_refill_pct=v[7], max_days_per_order=v[8],
                                          requires_pharmacist=v[9], updated_at=config.now()))
        done["rules"] += 1
    return done


def rule_for(conn, ingredient: str) -> dict | None:
    r = conn.execute(select(RULES).where(RULES.c.ingredient == clean(ingredient).lower())).mappings().first()
    return dict(r) if r else None


# ------------------------------------------------------------------ legacy prescriptions -> items
def _per_day(dosage: str) -> float:
    d = clean(dosage).lower()
    if "week" in d:
        return 1 / 7
    if "thrice" in d or "three times" in d or "tds" in d:
        return 3.0
    if "twice" in d or "two times" in d or "bd" in d.split():
        return 2.0
    return 1.0


def ensure_items(conn, patient_id: int | None = None) -> int:
    """V2 prescriptions were one row per medicine with only a dosage sentence. Give each one a header and an item so
    the rules engine can count days. Runs lazily before any check, so old rows and rows added by hand both work."""
    q = select(RX).where(~select(ITEM.c.id).where(ITEM.c.rx_id == RX.c.id).exists())
    if patient_id:
        q = q.where(RX.c.patient_id == patient_id)
    n = 0
    for r in conn.execute(q).mappings().all():
        start = r["start_date"] or config.today()
        duration = (r["end_date"] - start).days if r["end_date"] and r["end_date"] > start else 30
        product = _find_product(conn, r["medicine_name"])
        chronic = bool(product and product["chronic"])
        refills = max(0, math.ceil(VALID_DAYS / duration) - 1) if chronic else 0
        valid = max(start + timedelta(days=VALID_DAYS), r["end_date"] or start)
        vals = {"status": r["status"] or "active", "source": r["source"] or "legacy",
                "issued_at": r["issued_at"] or datetime.combine(start, datetime.min.time()),
                "valid_until": r["valid_until"] or valid, "updated_at": config.now()}
        if not r["rx_code"]:
            vals["rx_code"] = f"RX-L{r['id']:06d}"
        conn.execute(update(RX).where(RX.c.id == r["id"]).values(**vals))
        ing = product["ingredient"] if product and product["ingredient"] else ingredient_of(r["medicine_name"])
        conn.execute(insert(ITEM).values(rx_id=r["id"], medicine_code=None, ingredient=ing,
                                         strength_mg=_strength_mg(r["medicine_name"].split(" ", 1)[-1]),
                                         dose_units=1, times_per_day=_per_day(r["dosage"] or ""), duration_days=duration,
                                         refills_allowed=refills, substitution_allowed=True,
                                         instructions=(r["dosage"] or "")[:160], created_at=config.now()))
        n += 1
    return n


def _find_product(conn, text) -> dict | None:
    from . import pharmacy
    return pharmacy.find(conn, text)


# ------------------------------------------------------------------ supply arithmetic
def days_for(product: dict, item: dict | None, packs: int) -> float:
    """How many days `packs` of this product last on this prescription item (or one unit a day for OTC)."""
    upp = product.get("units_per_pack") or 1.0
    if upp == 1.0 and product.get("days_per_unit"):
        return packs * float(product["days_per_unit"])
    per_day = ((item or {}).get("dose_units") or 1.0) * ((item or {}).get("times_per_day") or 1.0)
    return packs * upp / per_day


def _used_days(conn, item_id: int) -> float:
    return float(conn.execute(select(func.coalesce(func.sum(DISP.c.days_supply), 0)).where(
        DISP.c.rx_item_id == item_id, DISP.c.status.in_(("reserved", "dispensed")))).scalar() or 0)


def _last_supply(conn, item_id: int) -> dict | None:
    r = conn.execute(select(DISP).where(DISP.c.rx_item_id == item_id, DISP.c.status.in_(("reserved", "dispensed")))
                     .order_by(DISP.c.created_at.desc(), DISP.c.id.desc())).mappings().first()
    return dict(r) if r else None


def item_status(conn, item: dict) -> dict:
    """Days allowed in total, used, left, and the first day a refill may be ordered."""
    total = float(item["duration_days"]) * (1 + int(item["refills_allowed"] or 0))
    used = _used_days(conn, item["id"])
    last = _last_supply(conn, item["id"])
    rule = rule_for(conn, item["ingredient"]) or {}
    pct = (rule.get("early_refill_pct") or 80) / 100
    next_ok = None
    if last and last["days_supply"]:
        next_ok = last["created_at"].date() + timedelta(days=math.floor(last["days_supply"] * pct))
    return {"total_days": total, "used_days": used, "left_days": max(0.0, total - used),
            "next_refill_from": next_ok if next_ok and next_ok > config.today() else None}


def coverage(conn, patient_id: int, product: dict) -> tuple[dict | None, dict | None, str | None]:
    """The active prescription item for this product: (item, status, reason it can't be used)."""
    ensure_items(conn, patient_id)
    ing = product.get("ingredient") or ingredient_of(product["generic_name"])
    rows = conn.execute(select(ITEM, RX.c.rx_code, RX.c.status.label("rx_status"), RX.c.valid_until, RX.c.doctor_id,
                               RX.c.issued_at).join(RX, RX.c.id == ITEM.c.rx_id)
                        .where(RX.c.patient_id == patient_id, ITEM.c.ingredient == ing)
                        .order_by(RX.c.issued_at.desc(), ITEM.c.id.desc())).mappings().all()
    reason = None
    for r in rows:
        r = dict(r)
        if r["medicine_code"] and r["medicine_code"] != product["medicine_code"] and not r["substitution_allowed"]:
            reason = reason or "brand"
            continue
        if r["rx_status"] == "pending_review":
            reason = reason or "pending_review"
            continue
        if r["rx_status"] in ("cancelled",) or r["stopped_at"]:
            reason = reason or "stopped"
            continue
        if r["valid_until"] and r["valid_until"] < config.today():
            reason = reason or "expired"
            continue
        st = item_status(conn, r)
        if st["left_days"] <= 0:
            reason = reason or "used_up"
            continue
        return r, st, None
    return None, None, reason or "none"


# ------------------------------------------------------------------ the dispensing check
def _age(p: dict) -> int | None:
    d = p.get("date_of_birth")
    if not d:
        return None
    t = config.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def _otc_used(conn, patient_id: int, ingredient: str, days: int) -> tuple[float, float]:
    """(mg, units) of this ingredient ordered in the last `days` days, any brand, cancelled orders excluded."""
    since = config.now() - timedelta(days=days)
    rows = conn.execute(select(DISP.c.units, INV.c.strength_mg).join(INV, INV.c.medicine_code == DISP.c.medicine_code)
                        .where(DISP.c.patient_id == patient_id, INV.c.ingredient == ingredient,
                               DISP.c.status.in_(("reserved", "dispensed")), DISP.c.created_at >= since)).all()
    return sum((u or 0) * (mg or 0) for u, mg in rows), sum(u or 0 for u, _ in rows)


def _recent_same(conn, patient_id: int, ingredient: str) -> dict | None:
    since = config.now() - timedelta(days=DUPLICATE_WINDOW_DAYS)
    r = conn.execute(select(DISP.c.created_at, INV.c.brand_name).join(INV, INV.c.medicine_code == DISP.c.medicine_code)
                     .where(DISP.c.patient_id == patient_id, INV.c.ingredient == ingredient,
                            DISP.c.status.in_(("reserved", "dispensed")), DISP.c.created_at >= since)
                     .order_by(DISP.c.created_at.desc())).first()
    return {"when": r[0], "brand": r[1]} if r else None


def _packs_word(n: int) -> str:
    return f"{n} pack" + ("" if n == 1 else "s")


def check(conn, p: dict, rows: list[tuple[dict, int]]) -> tuple[Result | None, dict]:
    """Run the rules for every line. Returns (refusal, None-ish) or (None, plan) where plan has per-line rx items,
    days of supply, notes for the patient and reasons a pharmacist must look before dispatch."""
    plan = {"lines": [], "notes": [], "review": [], "rx_doc": None}
    age = _age(p)
    allergies = [a.strip().lower() for a in re.split(r"[,;/]", p.get("allergies") or "") if a.strip()]
    pregnant = bool(p.get("pregnant_until") and p["pregnant_until"] >= config.today())
    seen_ing: dict[str, str] = {}
    for prod, packs in rows:
        ing = prod.get("ingredient") or ingredient_of(prod["generic_name"])
        rule = rule_for(conn, ing) or {}
        name = prod["brand_name"]
        line = {"code": prod["medicine_code"], "ingredient": ing, "packs": packs,
                "units": packs * (prod.get("units_per_pack") or 1.0), "rx_item_id": None, "days": 0.0,
                "schedule": prod["schedule_class"]}
        # 1. patient fit
        if rule.get("min_age_years") and age is not None and age < rule["min_age_years"]:
            return fail("not_suitable", f"{name} isn't suitable under the age of {rule['min_age_years']}, so I can't send it for "
                        f"{'an' if str(age)[0] == '8' or age in (11, 18) else 'a'} {age}-year-old by chat. A child's dose depends on weight; our pharmacist on {PHARMACY_DESK} or a "
                        "paediatrician can advise. Shall I book a paediatric consultation?", next_step="book_consultation",
                        department="Paediatrics"), plan
        hit = next((a for a in allergies if a and (a in prod["generic_name"].lower() or a in ing)), None)
        if hit:
            return fail("allergy", f"Your record lists an allergy to {hit}, and {name} contains {prod['generic_name']}. I can't "
                        f"send it. Our pharmacist on {PHARMACY_DESK} can suggest a safe alternative, or I can connect you "
                        "to a person now.", next_step="handoff"), plan
        if pregnant and rule.get("pregnancy_caution"):
            plan["review"].append(f"{name}: pregnancy caution")
        if age is not None and age < 12 and prod["schedule_class"] != "OTC":
            plan["review"].append(f"{name}: child, weight-based dose check")
        if rule.get("requires_pharmacist"):
            plan["review"].append(f"{name}: always checked by a pharmacist")
        # 2. prescription
        if prod["schedule_class"] in ("H", "H1"):
            item, st, why = coverage(conn, p["id"], prod)
            if not item:
                return _no_rx(prod, why, rows), plan
            days = days_for(prod, item, packs)
            one_pack = days_for(prod, item, 1)
            cap = float(rule.get("max_days_per_order") or 30)
            if days - one_pack >= min(st["left_days"], cap) - 1e-6 and packs > 1:
                most = max(1, math.ceil(min(st["left_days"], cap) / one_pack))
                return fail("over_prescription", f"Your prescription allows about {round(min(st['left_days'], cap))} more days of "
                            f"{name} in one order, which is {_packs_word(most)} ({prod['pack']} each). Shall I order "
                            f"{_packs_word(most)} instead?", allowed_packs=most), plan
            if st["next_refill_from"]:
                return fail("refill_too_early", f"Your last supply of {name} should last until about "
                            f"{human_date(st['next_refill_from'] + timedelta(days=2))}, so a refill can be ordered from "
                            f"{human_date(st['next_refill_from'])}. If you're running out early or your dose changed, I can "
                            "ask your doctor to review it.", refill_from=st["next_refill_from"].isoformat(),
                            next_step="request_prescription_refill"), plan
            line.update(rx_item_id=item["id"], days=days, rx_code=item["rx_code"])
            plan["rx_doc"] = plan["rx_doc"] or item
            if prod["schedule_class"] == "H1" or prod["schedule_class"] == "H":
                plan["review"].append(f"{name}: prescription check")
        # 3. OTC limits (by ingredient, across brands)
        else:
            mg = line["units"] * (prod.get("strength_mg") or 0)
            used_mg, used_units = _otc_used(conn, p["id"], ing, 7)
            same_order_mg = sum(l["units"] * (l.get("strength_mg") or 0) for l in plan["lines"] if l["ingredient"] == ing)
            same_order_units = sum(l["units"] for l in plan["lines"] if l["ingredient"] == ing)
            lim = []
            if rule.get("otc_max_mg_per_order") and mg + same_order_mg > rule["otc_max_mg_per_order"]:
                lim.append(("order", rule["otc_max_mg_per_order"] / ((prod.get("strength_mg") or 1) * (prod.get("units_per_pack") or 1))))
            if rule.get("otc_max_units_per_order") and line["units"] + same_order_units > rule["otc_max_units_per_order"]:
                lim.append(("order", rule["otc_max_units_per_order"] / (prod.get("units_per_pack") or 1)))
            if rule.get("otc_max_mg_per_7d") and used_mg + mg + same_order_mg > rule["otc_max_mg_per_7d"]:
                room = max(0.0, rule["otc_max_mg_per_7d"] - used_mg - same_order_mg)
                lim.append(("week", room / ((prod.get("strength_mg") or 1) * (prod.get("units_per_pack") or 1))))
            if rule.get("otc_max_units_per_7d") and used_units + line["units"] + same_order_units > rule["otc_max_units_per_7d"]:
                room = max(0.0, rule["otc_max_units_per_7d"] - used_units - same_order_units)
                lim.append(("week", room / (prod.get("units_per_pack") or 1)))
            if lim:
                kind, packs_ok = min(lim, key=lambda x: x[1])
                n_ok = int(math.floor(packs_ok + 1e-9))
                why = "per order" if kind == "order" else "in 7 days, counting every brand of " + ing
                msg = (f"For safety our pharmacy sends at most {_packs_word(max(n_ok, 0))} of {name} {why}."
                       if n_ok > 0 else f"You've already had the most {ing} our pharmacy sends in 7 days, counting every brand.")
                msg += (f" Shall I order {_packs_word(n_ok)} instead?" if n_ok > 0 else
                        f" If you still need it, please see a doctor: I can book {GP} in General Medicine.")
                return fail("otc_limit", msg, allowed_packs=max(n_ok, 0), ingredient=ing), plan
            line["strength_mg"] = prod.get("strength_mg") or 0
            line["days"] = 0.0
        # 4. duplicates
        if ing in seen_ing and seen_ing[ing] != name:
            plan["notes"].append(f"{seen_ing[ing]} and {name} are the same medicine ({ing}); please take only one of them.")
            plan["review"].append(f"{ing}: two brands in one order")
        else:
            recent = _recent_same(conn, p["id"], ing)
            if recent and prod["schedule_class"] == "OTC":
                plan["notes"].append(f"You ordered {recent['brand']} ({ing}) on {human_date(recent['when'].date())}; "
                                     f"don't take {name} together with it.")
        seen_ing.setdefault(ing, name)
        line.setdefault("strength_mg", prod.get("strength_mg") or 0)
        plan["lines"].append(line)
    return None, plan


def _no_rx(prod: dict, why: str | None, rows) -> Result:
    name = f"{prod['brand_name']} ({prod['generic_name']} {prod['strength']})"
    otc = [x for x, _ in rows if x["schedule_class"] == "OTC"]
    tail = (f" The other items ({', '.join(x['brand_name'] for x in otc)}) don't need a prescription; I can order those on "
            "their own." if otc else "")
    if why == "used_up":
        return fail("prescription_used", f"Your prescription for {name} has been fully supplied, including its refills. Your doctor "
                    "needs to renew it: shall I send a refill request, or book a review?" + tail,
                    next_step="request_prescription_refill")
    if why == "stopped":
        return fail("prescription_stopped", f"Your doctor has stopped or changed your prescription for {name}, so I can't send "
                    "it. Please follow the latest prescription, or I can book a review with your doctor." + tail,
                    next_step="book_consultation")
    if why == "expired":
        return fail("prescription_expired", f"Your prescription for {name} has expired. A doctor needs to renew it: shall I "
                    "send a refill request to your doctor, or book a review?" + tail, next_step="request_prescription_refill")
    if why == "pending_review":
        return fail("prescription_pending", f"The prescription you uploaded for {name} is still being checked by our pharmacist. "
                    "You'll get an SMS once it's approved, usually within a few hours in the daytime." + tail,
                    next_step="wait")
    kind = "an antibiotic" if any(w in prod["generic_name"].lower() for w in ("amoxicillin", "azithromycin", "cef", "cipro", "doxy")) \
        else "a prescription medicine"
    return fail("prescription_required",
                f"{name} is {kind} under Schedule {prod['schedule_class']}, and I can't find a prescription for it from the "
                "last 6 months on your record, so by law our pharmacy can't send it. I can book a quick consultation with "
                f"{GP} in General Medicine, 600 rupees, so a doctor can review it and prescribe the right treatment. Shall "
                "I check his slots? If you have a prescription from another hospital, you can upload it on the website "
                "under Pharmacy." + tail, next_step="book_consultation", department="General Medicine", doctor=GP)


def review_window_note() -> str:
    h = config.now().hour
    if REVIEW_HOURS[0] <= h < REVIEW_HOURS[1]:
        return "A pharmacist checks prescription medicines before they're sent, usually within 15 minutes."
    return (f"A pharmacist checks prescription medicines before they're sent; the desk opens at {REVIEW_HOURS[0]} AM, "
            "so it goes out after that check.")


def reserve(conn, order_id: int, patient_id: int, plan: dict, rows: list[tuple[dict, int]], auto: bool) -> None:
    """Record every line against its prescription item (reserved until a pharmacist approves) or as an OTC supply."""
    by_code = {r["medicine_code"]: r for r, _ in rows}
    for line in plan["lines"]:
        prod = by_code[line["code"]]
        status = "dispensed" if auto else "reserved"
        conn.execute(insert(DISP).values(order_id=order_id, rx_item_id=line["rx_item_id"], patient_id=patient_id,
                                         medicine_code=line["code"], schedule_class=prod["schedule_class"],
                                         packs=line["packs"], units=line["units"], days_supply=line["days"], status=status,
                                         pharmacist="auto" if auto else None, verified_at=config.now() if auto else None,
                                         created_at=config.now()))


def void(conn, order_id: int) -> None:
    conn.execute(update(DISP).where(DISP.c.order_id == order_id).values(status="void"))


def approve_lines(conn, order_id: int, pharmacist: str) -> None:
    conn.execute(update(DISP).where(DISP.c.order_id == order_id, DISP.c.status == "reserved")
                 .values(status="dispensed", pharmacist=pharmacist[:80], verified_at=config.now()))


# ------------------------------------------------------------------ prescribing (doctor) and uploads (patient)
def _signature(rx_code: str, doctor_id, patient_id, items: list[dict], issued: datetime) -> str:
    raw = json.dumps({"rx": rx_code, "d": doctor_id, "p": patient_id, "i": items, "t": issued.isoformat()}, sort_keys=True, default=str)
    return hmac.new(config.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()


def _new_rx_code(conn) -> str:
    while True:
        code = pt.random_code("RX", 6)
        if not conn.execute(select(RX.c.id).where(RX.c.rx_code == code)).first():
            return code


def validate_item(conn, it: dict) -> tuple[dict | None, str | None]:
    """Normalise one prescribed item and check the daily dose against the rule. Returns (item, error)."""
    prod = None
    if clean(it.get("medicine_code")):
        prod = conn.execute(select(INV).where(INV.c.medicine_code == clean(it["medicine_code"]).upper())).mappings().first()
        if not prod:
            return None, f"Unknown medicine code {it['medicine_code']}."
        prod = dict(prod)
    ing = clean(it.get("ingredient")).lower() or (prod["ingredient"] if prod else "")
    if not ing:
        return None, "Each item needs a medicine or an ingredient."
    try:
        dose = float(it.get("dose_units") or 1)
        times = float(it.get("times_per_day") or 1)
        days = int(it.get("duration_days") or 0)
        refills = int(it.get("refills_allowed") or 0)
    except (TypeError, ValueError):
        return None, "Dose, times per day, days and refills must be numbers."
    if not (0 < dose <= 20 and 0 < times <= 8 and 0 < days <= 365 and 0 <= refills <= 12):
        return None, "Dose 0-20 per intake, 1/7 to 8 times a day, 1-365 days and 0-12 refills."
    mg = it.get("strength_mg") or (prod["strength_mg"] if prod else None)
    rule = rule_for(conn, ing) or {}
    over = rule.get("max_daily_mg_adult") and mg and dose * times * float(mg) > rule["max_daily_mg_adult"] + 1e-9
    if over and not clean(it.get("override_reason")):
        return None, (f"{ing.title()}: {dose:g} x {times:g} a day at {float(mg):g} mg is {dose * times * float(mg):g} mg a day, "
                      f"above the usual adult maximum of {rule['max_daily_mg_adult']:g} mg. Lower it, or give a reason to "
                      "override.")
    return {"medicine_code": prod["medicine_code"] if prod else None, "ingredient": ing, "strength_mg": mg,
            "dose_units": dose, "times_per_day": times, "duration_days": days, "refills_allowed": refills,
            "substitution_allowed": bool(it.get("substitution_allowed", True)),
            "instructions": clean(it.get("instructions"))[:160] or None,
            "override_reason": clean(it.get("override_reason"))[:200] or None}, None


def prescribe(patient_id: int, doctor_id: int | None, items: list[dict], signed_by: str, valid_days: int = VALID_DAYS,
              appointment_id: int | None = None, source: str = "in_house", status: str = "active",
              conn=None) -> Result:
    """Create a signed prescription. A newer item for the same ingredient stops the older one (a dose change)."""
    if not items:
        return fail("invalid_input", "Add at least one medicine.")

    def run(c):
        p = pt.get_by_id(c, patient_id)
        if not p:
            return fail("not_found", "That patient doesn't exist.")
        clean_items = []
        for it in items:
            good, err = validate_item(c, it)
            if err:
                return fail("invalid_input", err)
            clean_items.append(good)
        now = config.now()
        code = _new_rx_code(c)
        first = clean_items[0]
        rx_id = c.execute(insert(RX).values(
            patient_id=patient_id, doctor_id=doctor_id, medicine_name=(first["ingredient"].title())[:80],
            dosage=f"{first['dose_units']:g} x {first['times_per_day']:g} a day for {first['duration_days']} days"[:80],
            start_date=now.date(), end_date=now.date() + timedelta(days=max(i["duration_days"] for i in clean_items)),
            rx_code=code, appointment_id=appointment_id, source=source, status=status, issued_at=now,
            valid_until=now.date() + timedelta(days=min(int(valid_days or VALID_DAYS), VALID_DAYS)), signed_by=signed_by[:80],
            signature_hash=_signature(code, doctor_id, patient_id, clean_items, now), updated_at=now)).inserted_primary_key[0]
        if status == "active":
            for it in clean_items:      # dose change: the newest prescription for an ingredient replaces the older ones
                old = select(ITEM.c.id).join(RX, RX.c.id == ITEM.c.rx_id).where(
                    RX.c.patient_id == patient_id, ITEM.c.ingredient == it["ingredient"], ITEM.c.stopped_at.is_(None),
                    RX.c.id != rx_id)
                c.execute(update(ITEM).where(ITEM.c.id.in_(old)).values(stopped_at=now, stop_reason=f"Replaced by {code}"))
        c.execute(insert(ITEM), [dict(rx_id=rx_id, created_at=now, **it) for it in clean_items])
        pt.log(c, patient_id, "prescription_issued", code, True,
               f"{signed_by} prescribed " + ", ".join(f"{i['ingredient']} {i['duration_days']} days" for i in clean_items),
               actor="staff", channel="staff")
        if status == "active":
            names = ", ".join(i["ingredient"].title() for i in clean_items)
            notify.queue(c, patient_id=patient_id, channel="sms", template="prescription_issued", to=p["phone"],
                         body=f"WellNest: {signed_by} prescribed {names} ({code}). You can order it in the WellNest chat or on "
                              f"the website, delivered home.", dedupe_key=f"rx:{code}")
        return ok(f"Prescription {code} saved for {p['full_name']}.", rx_code=code, rx_id=rx_id, items=len(clean_items))

    if conn is not None:
        res = run(conn)
    else:
        with db.engine.begin() as c:
            res = run(c)
    if res.ok:
        events.publish("interaction.noted", patient_id=patient_id)
    return res


def stop_item(item_id: int, reason: str, by: str) -> Result:
    with db.engine.begin() as c:
        it = c.execute(select(ITEM, RX.c.patient_id, RX.c.rx_code).join(RX, RX.c.id == ITEM.c.rx_id)
                       .where(ITEM.c.id == item_id)).mappings().first()
        if not it:
            return fail("not_found", "That prescription item doesn't exist.")
        if it["stopped_at"]:
            return ok("Already stopped.", item_id=item_id)
        c.execute(update(ITEM).where(ITEM.c.id == item_id).values(stopped_at=config.now(), stop_reason=clean(reason)[:160] or "Stopped"))
        pending = c.execute(select(DISP.c.order_id).where(DISP.c.rx_item_id == item_id, DISP.c.status == "reserved")).all()
        pt.log(c, it["patient_id"], "prescription_stopped", it["rx_code"], True, f"{by} stopped {it['ingredient']}: {clean(reason)}",
               actor="staff", channel="staff")
    for (oid,) in pending:          # an order still waiting for its check can't go out on a stopped prescription
        from . import pharmacy
        pharmacy.reject(oid, f"The doctor stopped this medicine ({clean(reason) or 'prescription changed'}).", by)
    return ok(f"Stopped {it['ingredient']}." + (f" {len(pending)} waiting order cancelled and refunded." if pending else ""),
              item_id=item_id, cancelled_orders=len(pending))


MAX_UPLOAD = 4 * 1024 * 1024
UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def upload(patient_id: int, file_name: str, content_type: str, data: bytes, note: str = "") -> Result:
    if content_type not in UPLOAD_TYPES:
        return fail("invalid_input", "Please upload a photo (JPG, PNG or WebP) or a PDF of the prescription.")
    if not data or len(data) > MAX_UPLOAD:
        return fail("invalid_input", "The file must be under 4 MB.")
    with db.engine.begin() as c:
        pending = c.execute(select(func.count()).select_from(db.prescription_uploads).where(
            db.prescription_uploads.c.patient_id == patient_id, db.prescription_uploads.c.status == "pending")).scalar() or 0
        if pending >= 5:
            return fail("not_allowed", "You already have 5 prescriptions waiting for review. We'll message you as each is checked.")
        code = pt.random_code("UP", 6)
        c.execute(insert(db.prescription_uploads).values(upload_code=code, patient_id=patient_id, file_name=clean(file_name)[:120],
                                                         content_type=content_type, data=data, note=clean(note)[:200],
                                                         status="pending", created_at=config.now()))
        pt.log(c, patient_id, "prescription_uploaded", code, True, "Uploaded an outside prescription for review", channel="web")
    return ok(f"Thanks. Prescription {code} is with our pharmacist. You'll get an SMS once it's checked, usually within a few "
              "hours in the daytime. Medicines on it can be ordered after that.", upload_code=code)


def review_upload(upload_id: int, approve: bool, reviewer: str, reason: str = "", items: list[dict] | None = None,
                  doctor_name: str = "", valid_days: int = VALID_DAYS) -> Result:
    U = db.prescription_uploads
    with db.engine.begin() as c:
        u = c.execute(select(U).where(U.c.id == upload_id).with_for_update()).mappings().first()
        if not u:
            return fail("not_found", "That upload doesn't exist.")
        if u["status"] != "pending":
            return fail("not_allowed", f"This upload was already {u['status']}.")
        p = pt.get_by_id(c, u["patient_id"])
        if not approve:
            if not clean(reason):
                return fail("invalid_input", "Give the patient a reason (for example: unreadable, older than 6 months, no doctor's "
                                             "registration number).")
            c.execute(update(U).where(U.c.id == upload_id).values(status="rejected", reviewer=reviewer[:80], reason=clean(reason)[:200],
                                                                  reviewed_at=config.now()))
            notify.queue(c, patient_id=p["id"], channel="sms", template="rx_upload_rejected", to=p["phone"],
                         body=f"WellNest: we couldn't accept prescription {u['upload_code']}: {clean(reason)}. Please upload a "
                              "clearer or current one, or book a consultation.", dedupe_key=f"upr:{u['upload_code']}")
            pt.log(c, p["id"], "prescription_upload_rejected", u["upload_code"], True, clean(reason), actor="staff", channel="staff")
            return ok(f"Rejected {u['upload_code']}.", status="rejected")
        res = prescribe(p["id"], None, items or [], signed_by=f"{clean(doctor_name) or 'Outside doctor'} (checked by {reviewer})",
                        valid_days=valid_days, source="external_upload", conn=c)
        if not res.ok:
            return res
        c.execute(update(U).where(U.c.id == upload_id).values(status="approved", reviewer=reviewer[:80], reviewed_at=config.now(),
                                                              created_rx_id=res.data["rx_id"]))
        return ok(f"Approved {u['upload_code']} as prescription {res.data['rx_code']}.", rx_code=res.data["rx_code"])


def patient_summary(conn, patient_id: int) -> list[dict]:
    """Active prescription items with what's left, for the patient and the agent."""
    ensure_items(conn, patient_id)
    rows = conn.execute(select(ITEM, RX.c.rx_code, RX.c.valid_until, RX.c.status.label("rx_status"), RX.c.doctor_id,
                               RX.c.signed_by, RX.c.issued_at).join(RX, RX.c.id == ITEM.c.rx_id)
                        .where(RX.c.patient_id == patient_id).order_by(RX.c.issued_at.desc())).mappings().all()
    from .ref import REF
    out = []
    for r in rows:
        r = dict(r)
        st = item_status(conn, r)
        active = (r["rx_status"] == "active" and not r["stopped_at"]
                  and (not r["valid_until"] or r["valid_until"] >= config.today()) and st["left_days"] > 0)
        doc = REF.doctors.get(r["doctor_id"], {}).get("name") if r["doctor_id"] else r["signed_by"]
        out.append({"item_id": r["id"], "rx_code": r["rx_code"], "ingredient": r["ingredient"], "medicine_code": r["medicine_code"],
                    "dose": f"{r['dose_units']:g} x {r['times_per_day']:g} a day" if r["times_per_day"] >= 1 else
                            f"{r['dose_units']:g} once a week",
                    "instructions": r["instructions"], "doctor": doc, "valid_until": r["valid_until"].isoformat() if r["valid_until"] else None,
                    "days_left": round(st["left_days"]), "next_refill_from": st["next_refill_from"].isoformat() if st["next_refill_from"] else None,
                    "status": "active" if active else ("stopped" if r["stopped_at"] else r["rx_status"] if r["rx_status"] != "active"
                                                       else "expired" if r["valid_until"] and r["valid_until"] < config.today() else "used_up"),
                    "stop_reason": r["stop_reason"]})
    return out


def summary_sentence(items: list[dict]) -> str:
    act = [i for i in items if i["status"] == "active"]
    if not act:
        return "You have no active prescriptions on file that can be ordered from."
    parts = []
    for i in act[:4]:
        s = f"{i['ingredient'].title()} ({i['dose']}), about {i['days_left']} days left"
        if i["next_refill_from"]:
            s += f", next refill from {human_date(date.fromisoformat(i['next_refill_from']))}"
        parts.append(s)
    return "Your active prescriptions: " + "; ".join(parts) + "."
