"""Input normalisers (messy human input -> clean values) and speakable formatting."""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .config import today

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "none", "null", "n/a", "na", "undefined"))


def clean(v) -> str:
    return "" if blank(v) else str(v).strip()


# ------------------------------------------------------------------ phone
def norm_phone(text) -> str | None:
    """'98450 12345', '+91-9845012345', '09845012345' -> '+919845012345'."""
    digits = re.sub(r"\D", "", clean(text))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    elif len(digits) == 13 and digits.startswith("091"):
        digits = digits[3:]
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    return None


def mask_phone(p: str | None) -> str:
    if not p:
        return ""
    return p[:3] + "******" + p[-4:] if len(p) >= 8 else "****"


def mask_email(e: str | None) -> str:
    if not e or "@" not in e:
        return ""
    name, dom = e.split("@", 1)
    return (name[:2] + "***@" + dom) if len(name) > 2 else ("***@" + dom)


# ------------------------------------------------------------------ dates
def _month(tok: str) -> int | None:
    return MONTHS.get(tok[:3].lower()) if tok[:3].lower() in MONTHS else None


def _parse_day_month(t: str) -> tuple[int, int, int | None] | None:
    """'4 nov', '4th november 2026', 'nov 4', 'november 4th, 2026' -> (day, month, year?)."""
    t = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", t).replace(",", " ")
    toks = t.split()
    if len(toks) in (2, 3):
        if toks[0].isdigit() and _month(toks[1]):
            d, m = int(toks[0]), _month(toks[1])
        elif _month(toks[0]) and toks[1].isdigit():
            d, m = int(toks[1]), _month(toks[0])
        else:
            return None
        y = int(toks[2]) if len(toks) == 3 and toks[2].isdigit() else None
        if len(toks) == 3 and y is None:
            return None
        return d, m, y
    return None


def parse_date(text, base: date | None = None) -> date | None:
    """Future-oriented date parser for appointments (Asia/Kolkata 'today')."""
    t = clean(text).lower().strip(" .")
    base = base or today()
    if not t:
        return None
    t = re.sub(r"\s+", " ", t)
    simple = {"today": 0, "now": 0, "tonight": 0, "tomorrow": 1, "tmrw": 1, "tommorow": 1, "tomorow": 1,
              "day after tomorrow": 2, "next week": 7}
    if t in simple:
        return base + timedelta(days=simple[t])
    m = re.fullmatch(r"in (\d{1,2}) days?", t)
    if m:
        return base + timedelta(days=int(m.group(1)))
    wd = t.replace("next ", "").replace("this ", "").replace("coming ", "")
    for i, name in enumerate(WEEKDAYS):
        if wd in (name, name[:3], name[:4]):
            delta = (i - base.weekday()) % 7
            if delta == 0 and not t.startswith("this"):
                delta = 7 if t.startswith("next") else 0
            return base + timedelta(days=delta)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})", t)
    if m:
        try:
            d = date(base.year, int(m.group(2)), int(m.group(1)))
            return d if d >= base else d.replace(year=base.year + 1)
        except ValueError:
            return None
    dm = _parse_day_month(t)
    if dm:
        d_, m_, y_ = dm
        try:
            d = date(y_ or base.year, m_, d_)
        except ValueError:
            return None
        if y_ is None and d < base:
            d = d.replace(year=base.year + 1)
        return d
    return None


def parse_dob(text) -> date | None:
    """Date of birth: '1958-03-04', '04/03/1958' (day first), '4 March 1958'."""
    t = clean(text).lower().strip(" .")
    if not t:
        return None
    # 8 digits typed with no separators, e.g. 25032005 (day first, as Indian patients write it), or 20050325
    digits = ("%d%m%Y", "%Y%m%d") if re.fullmatch(r"\d{8}", t) else ()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %m %Y", *digits):
        try:
            d = datetime.strptime(t, fmt).date()
            if 1900 < d.year <= today().year:
                return d
            if not digits:
                return None
        except ValueError:
            pass
    dm = _parse_day_month(t)
    if dm and dm[2]:
        try:
            return date(dm[2], dm[1], dm[0])
        except ValueError:
            return None
    return None


def parse_time(text) -> str | None:
    """'10:30', '10.30am', '10:30 AM', '10 am', '1030', '14:00' -> 'HH:MM'."""
    t = clean(text).upper().replace(".", ":").replace(" ", "")
    t = t.replace("A:M:", "AM").replace("P:M:", "PM").replace("A:M", "AM").replace("P:M", "PM")
    t = t.replace("HRS", "").replace("HR", "")
    if not t:
        return None
    if t in ("NOON", "12NOON"):
        return "12:00"
    if re.fullmatch(r"\d{3,4}", t):
        t = t[:-2] + ":" + t[-2:]
    for fmt in ("%H:%M", "%I:%M%p", "%I%p", "%H", "%H:%M:%S"):
        try:
            return datetime.strptime(t, fmt).strftime("%H:%M")
        except ValueError:
            pass
    return None


def norm_time_pref(text) -> str:
    t = clean(text).lower()
    if t.startswith("morn") or t in ("am", "early"):
        return "morning"
    if t.startswith("after") or t in ("pm", "noon"):
        return "afternoon"
    if t.startswith("even") or t.startswith("late"):
        return "evening"
    return "any"


def in_pref(hhmm: str, pref: str) -> bool:
    if pref == "morning":
        return hhmm < "12:00"
    if pref == "afternoon":
        return "12:00" <= hhmm < "17:00"
    if pref == "evening":
        return hhmm >= "17:00"
    return True


def yes_no(text) -> bool | None:
    t = clean(text).lower()
    if t in ("yes", "y", "true", "1", "ok", "sure", "haan", "ha", "agree"):
        return True
    if t in ("no", "n", "false", "0", "nahi", "nope"):
        return False
    return None


def age_on(dob: date, on: date | None = None) -> int:
    on = on or today()
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


# ------------------------------------------------------------------ speakable formatting
def human_date(d: date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def short_date(d: date) -> str:
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def human_time(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def rupees(n) -> str:
    return f"{int(n):,} rupees"


def spoken_code(code: str) -> str:
    return " ".join(ch for ch in code.upper() if ch.isalnum())


def norm_code(text, prefix: str) -> str | None:
    """'cl 48213', 'CL48213', '48213', 'ch-48213' -> 'WN-48213' for the given prefix."""
    t = re.sub(r"[^A-Za-z0-9]", "", clean(text)).upper()
    if not t:
        return None
    digits = re.sub(r"^[A-Z]+", "", t)
    if not digits.isdigit():
        return None
    return f"{prefix}-{digits}"


def split_list(text) -> list[str]:
    return [x.strip() for x in re.split(r"[,;/]", clean(text)) if x.strip()]


# ------------------------------------------------------------------ result envelope
@dataclass
class Result:
    ok: bool
    message: str
    data: dict = field(default_factory=dict)
    error_code: str | None = None
    related: list = field(default_factory=list)

    def as_dict(self) -> dict:
        out = {"ok": self.ok, "message": self.message}
        data = {k: v for k, v in (self.data or {}).items() if v not in (None, "", [], {})}
        if data:
            out["data"] = data
        if self.related:
            out["related"] = self.related[:3]
        if self.error_code:
            out["error_code"] = self.error_code
        return cap_size(out)


def ok(message: str, **data) -> Result:
    return Result(True, message, data)


def fail(code: str, message: str, **data) -> Result:
    return Result(False, message, data, code)


def cap_size(out: dict, limit: int = 2000) -> dict:
    """Keep responses small: trim lists in data until under the byte limit."""
    def size():
        return len(json.dumps(out, default=str))
    data = out.get("data") or {}
    while size() > limit:
        lists = [k for k, v in data.items() if isinstance(v, list) and len(v) > 1]
        if not lists:
            break
        k = max(lists, key=lambda k: len(json.dumps(data[k], default=str)))
        data[k] = data[k][:-1]
    return out
