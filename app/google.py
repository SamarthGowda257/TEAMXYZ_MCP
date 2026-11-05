"""Google APIs for the hospital's own Google account (wellnesthospitals@gmail.com): Gmail (send) and Calendar.

One OAuth client + one refresh token (scripts/google_connect.py prints it once) gives both:
  token:     POST https://oauth2.googleapis.com/token   (grant_type=refresh_token)
  calendar:  https://www.googleapis.com/calendar/v3/calendars/<id>/events?sendUpdates=all
             Patients and consented caregivers are attendees, so Google itself emails them the invite and puts
             it on their Google Calendar; updates and cancellations follow the same way.
  gmail:     POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send  {raw: base64url(MIME)}
Only called from background workers (outbox), never inside an MCP tool call.
"""

import base64
import threading
import time
from urllib.parse import quote

import httpx

from . import config

SCOPES = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.send"
_lock = threading.Lock()
_token = {"value": "", "expires": 0.0}


class GoogleError(Exception):
    pass


def configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET and config.GOOGLE_REFRESH_TOKEN)


def access_token() -> str:
    with _lock:
        if _token["value"] and _token["expires"] > time.time() + 60:
            return _token["value"]
        r = httpx.post("https://oauth2.googleapis.com/token", timeout=10, data={
            "grant_type": "refresh_token", "refresh_token": config.GOOGLE_REFRESH_TOKEN,
            "client_id": config.GOOGLE_CLIENT_ID, "client_secret": config.GOOGLE_CLIENT_SECRET})
        if r.status_code != 200:
            raise GoogleError(f"token {r.status_code}: {r.text[:200]}")
        body = r.json()
        _token["value"], _token["expires"] = body["access_token"], time.time() + int(body.get("expires_in", 3600))
        return _token["value"]


def _call(method: str, url: str, **kw) -> httpx.Response:
    for attempt in (1, 2):
        r = httpx.request(method, url, headers={"Authorization": f"Bearer {access_token()}"}, timeout=15, **kw)
        if r.status_code == 401 and attempt == 1:
            _token["value"] = ""
            continue
        return r
    return r


# ------------------------------------------------------------------ Gmail
def send_mail(mime_bytes: bytes) -> str:
    raw = base64.urlsafe_b64encode(mime_bytes).decode()
    r = _call("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", json={"raw": raw})
    if r.status_code not in (200, 202):
        raise GoogleError(f"gmail {r.status_code}: {r.text[:200]}")
    return r.json().get("id", "")


# ------------------------------------------------------------------ Calendar
def _events_url(event_id: str = "") -> str:
    cal = quote(config.GOOGLE_CALENDAR_ID or "primary", safe="")
    return f"https://www.googleapis.com/calendar/v3/calendars/{cal}/events" + (f"/{quote(event_id, safe='')}" if event_id else "")


def upsert_event(body: dict, event_id: str = "") -> str:
    params = {"sendUpdates": "all"}
    if event_id:
        r = _call("PUT", _events_url(event_id), params=params, json=body)
        if r.status_code == 404:                       # deleted by hand in Google Calendar: create it again
            event_id = ""
        else:
            if r.status_code != 200:
                raise GoogleError(f"calendar update {r.status_code}: {r.text[:200]}")
            return r.json()["id"]
    r = _call("POST", _events_url(), params=params, json=body)
    if r.status_code != 200:
        raise GoogleError(f"calendar create {r.status_code}: {r.text[:200]}")
    return r.json()["id"]


def delete_event(event_id: str) -> None:
    r = _call("DELETE", _events_url(event_id), params={"sendUpdates": "all"})
    if r.status_code not in (200, 204, 404, 410):
        raise GoogleError(f"calendar delete {r.status_code}: {r.text[:200]}")
