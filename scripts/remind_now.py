"""Demo: place the appointment-reminder call for one booking right now, instead of waiting for the scheduler.

The scheduler does this by itself 2 to 26 hours before every visit; this script only skips the wait.

  WELLNEST_TOKEN=<DASHBOARD_TOKEN from Render> python3 scripts/remind_now.py WN-12345
  WELLNEST_TOKEN=... python3 scripts/remind_now.py WN-12345 post_visit_followup     # a completed visit instead

It first prints whether real calls are switched on (mode "talkdesk") or only simulated, and what is missing.
The token goes in a header, never in the URL. Uses only the Python standard library.
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

try:                                      # python.org builds on macOS ship without CA certificates
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

BASE = os.environ.get("WELLNEST_URL", "https://teamxyz-mcp.onrender.com").rstrip("/")


def call(method: str, path: str, token: str) -> dict:
    req = urllib.request.Request(BASE + path, method=method, headers={"x-dashboard-token": token})
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"ok": False, "http": e.code, "error": e.read().decode()[:300]}


def main() -> None:
    token = os.environ.get("WELLNEST_TOKEN", "")
    if len(sys.argv) < 2 or not token:
        sys.exit(__doc__)
    booking = sys.argv[1].strip().upper()
    kind = sys.argv[2] if len(sys.argv) > 2 else "appointment_reminder"

    status = call("GET", "/api/ops/outbound?limit=1", token)
    if status.get("http") == 401:
        sys.exit("The token was refused. Use DASHBOARD_TOKEN from Render (or MCP_BEARER_TOKEN if DASHBOARD_TOKEN is unset).")
    print(f"Call mode: {status.get('mode')}   calling hours (IST): {status.get('calling_hours_ist')}   "
          f"test number: {status.get('test_number') or 'none (rings the patient)'}")
    if status.get("missing_settings"):
        print("Missing on Render, so the call will only be simulated:", ", ".join(status["missing_settings"]))

    q = urllib.parse.urlencode({"booking_id": booking, "kind": kind})
    res = call("POST", f"/api/ops/outbound/call?{q}", token)
    if res.get("ok"):
        state = res.get("status")
        print(f"Call {res.get('call_id')}: {state}"
              + ("  -> the phone should ring within 30 seconds." if state == "dialing" else ""))
        if state == "simulated":
            print("Simulated: it is logged in Admin -> Outbound calls but no phone rings.")
        if state == "start_failed":
            print("Talkdesk refused to start the flow:", res.get("error"))
    else:
        print("Not placed:", res.get("error") or res)


if __name__ == "__main__":
    main()
