"""Branded HTML for every outgoing email, built from the plain-text body so both versions always say the same thing.

Tools keep writing plain text into the outbox; the sender adds this as the HTML alternative. Inline styles and tables
only, no images or web fonts, because email clients strip the rest. Colours follow DESIGN.md.

How a body line is shown:
  "Booking confirmed: Dr. X"  a highlighted banner
  "Room: OPD-310"             a row in the details table
  "Track: https://..."        a button
  a block of 3 or more lines  a "Good to know" list
  anything else               a paragraph
"""

import html
import re

ACCENT, INK, MUTED, LINE, SKY, ALERT, ALERT_TINT = "#0b5cad", "#0d2240", "#4a5b72", "#dde6f0", "#e8f2fd", "#d0312d", "#fdecea"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
URL = re.compile(r"https?://[^\s<>]+")
FACT = re.compile(r"^([A-Z][A-Za-z0-9 &'/()-]{0,24}):\s+(.+)$")
BANNER = re.compile(r"^(Booking (?:confirmed|rescheduled)|Booked from the waitlist):\s*(.+)$")
CODE = re.compile(r"^(WN|LR|BL|PHARM|OC|PL|RF|HC|AS|CN|GRV)-[0-9A-Z]+$")
SIGN_OFF = ("wellnest hospitals", "wellnest hospitals.")


def _e(t: str) -> str:
    return html.escape(t, quote=True)


def _button(label: str, url: str, primary: bool) -> str:
    bg, fg = (ACCENT, "#ffffff") if primary else ("#ffffff", ACCENT)
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 10px"><tr>'
            f'<td style="border-radius:999px;background:{bg};border:1px solid {ACCENT}">'
            f'<a href="{_e(url)}" style="display:inline-block;padding:12px 24px;font:700 15px {FONT};color:{fg};'
            f'text-decoration:none;border-radius:999px">{_e(label)}</a></td></tr></table>')


def _row(key: str, value: str) -> str:
    code = bool(CODE.match(value.strip()))
    style = "letter-spacing:.04em;font-weight:700" if code else "font-weight:600" if len(value) <= 40 else "font-weight:400;line-height:1.45"
    return (f'<tr><td valign="top" style="padding:10px 12px 10px 0;border-top:1px solid {LINE};font:14px {FONT};color:{MUTED};'
            f'width:38%">{_e(key)}</td><td valign="top" style="padding:10px 0;border-top:1px solid {LINE};font:15px {FONT};'
            f'color:{INK};{style}">{_e(value)}</td></tr>')


def _table(rows: list[str]) -> str:
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;'
            f'border-bottom:1px solid {LINE}">{"".join(rows)}</table>')


def _para(t: str, style: str = "") -> str:
    return f'<p style="margin:0 0 16px;font:16px/1.55 {FONT};color:{INK};{style}">{_e(t)}</p>'


def _clean_label(text: str) -> str:
    return re.sub(r"(\s+(at|here)|\s*:)\s*$", "", text.strip(), flags=re.I).strip()


def _plain_line(line: str) -> bool:
    return bool(line.strip()) and not URL.search(line) and not line.startswith(" ")


def render(subject: str, body: str) -> str:
    """The full HTML document for one email."""
    parts: list[str] = []
    buttons: list[tuple[str, str]] = []
    rows: list[str] = []

    def flush_rows():
        if rows:
            parts.append(_table(list(rows)))
            rows.clear()

    for block in re.split(r"\n\s*\n", (body or "").strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        # three or more plain sentences together are a list of things to know (the policy lines)
        if len(lines) >= 3 and all(_plain_line(x) and not FACT.match(x) and not BANNER.match(x) for x in lines[:3]):
            flush_rows()
            items = "".join(f'<li style="margin:0 0 8px">{_e(x.strip())}</li>' for x in lines)
            parts.append(f'<p style="margin:4px 0 8px;font:700 15px {FONT};color:{INK}">Good to know</p>'
                         f'<ul style="margin:0 0 20px;padding:0 0 0 20px;font:15px/1.5 {FONT};color:{MUTED}">{items}</ul>')
            continue
        for raw in lines:
            line = raw.strip()
            if line.lower() in SIGN_OFF or line.startswith("WellNest Hospitals, 42") or line == "For emergencies call 108.":
                continue                            # the footer on every email already says these
            m = BANNER.match(line)
            if m:
                flush_rows()
                parts.append(f'<div style="background:{SKY};border-radius:14px;padding:16px 18px;margin:0 0 20px">'
                             f'<div style="font:700 13px {FONT};color:{ACCENT};margin:0 0 4px">{_e(m.group(1))}</div>'
                             f'<div style="font:700 19px/1.3 {FONT};color:{INK}">{_e(m.group(2))}</div></div>')
                continue
            u = URL.search(line)
            if u:
                flush_rows()
                url = u.group(0).rstrip(".,)")
                before, after = line[:u.start()].strip(), line[u.end():].strip(" .")
                label = _clean_label(before)
                if label and len(label) <= 40:
                    buttons.append((label.capitalize() if label.islower() else label, url))
                else:
                    if before:
                        parts.append(_para(before.rstrip(":") + "."))
                    buttons.append(("Open link", url))
                if after:
                    parts.append(_para(after + "."))
                continue
            indented = raw.startswith(" ")
            if indented and " = " in line:          # itemised lines: "2 x Dolo 650 (strip) @ 32 = 64 rupees"
                k, v = line.rsplit(" = ", 1)
                rows.append(_row(k, v))
                continue
            f = FACT.match(line)
            if f:
                rows.append(_row(f.group(1), f.group(2)))
                continue
            flush_rows()
            parts.append(_para(line))
    flush_rows()
    for i, (label, url) in enumerate(buttons):
        parts.append(_button(label, url, i == 0))

    content = "".join(parts)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{_e(subject)}</title></head>
<body style="margin:0;padding:0;background:#f3f7fc">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{_e(subject)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f7fc"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid {LINE};border-radius:14px;border-collapse:separate">
<tr><td style="padding:20px 28px;border-bottom:1px solid {LINE}">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td width="36" height="36" align="center" valign="middle" style="width:36px;height:36px;background:{ACCENT};border-radius:10px;font:700 24px/36px Arial,sans-serif;color:#ffffff">+</td>
<td style="padding-left:12px;font:700 18px {FONT};color:{INK}">WellNest<span style="display:block;font:12px {FONT};color:{MUTED}">Hospitals, Bengaluru</span></td>
</tr></table></td></tr>
<tr><td style="padding:28px">{content}</td></tr>
<tr><td style="padding:14px 28px;background:{ALERT_TINT};font:700 14px {FONT};color:{ALERT}">Medical emergency? Call <a href="tel:108" style="color:{ALERT}">108</a></td></tr>
<tr><td style="padding:18px 28px;font:13px/1.5 {FONT};color:{MUTED}">WellNest Hospitals, 42 Outer Ring Road, Marathahalli, Bengaluru 560037<br>
Helpline 080 4000 1234. This is an automated message about your care at WellNest.</td></tr>
</table></td></tr></table></body></html>"""
