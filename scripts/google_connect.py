"""Connect the hospital's Google account once and print the refresh token for Render (GOOGLE_REFRESH_TOKEN).

Before running: in Google Cloud Console enable the Calendar and Gmail APIs and create an OAuth client of type
"Desktop app". Run on your own computer, sign in as the hospital account, and paste the printed token straight into
Render. Never commit it or paste it into chat.

  GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python scripts/google_connect.py
"""

import http.server
import os
import sys
import urllib.parse
import webbrowser

import httpx

SCOPES = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.send"
PORT = 8765


def main() -> None:
    cid, secret = os.environ.get("GOOGLE_CLIENT_ID", ""), os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not cid or not secret:
        sys.exit("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first.")
    redirect = f"http://127.0.0.1:{PORT}"
    got: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and go back to the terminal.")

        def log_message(self, *args):
            pass

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent"})
    print("Opening your browser. If it doesn't open, visit:\n" + url)
    webbrowser.open(url)
    with http.server.HTTPServer(("127.0.0.1", PORT), Handler) as srv:
        srv.handle_request()
    if "code" not in got:
        sys.exit(f"Google did not return a code: {got.get('error')}")
    r = httpx.post("https://oauth2.googleapis.com/token", timeout=15, data={
        "grant_type": "authorization_code", "code": got["code"][0], "client_id": cid, "client_secret": secret,
        "redirect_uri": redirect})
    if r.status_code != 200 or "refresh_token" not in r.json():
        sys.exit(f"Token request failed ({r.status_code}): {r.text[:300]}")
    print("\nSet this on Render as GOOGLE_REFRESH_TOKEN:\n\n" + r.json()["refresh_token"])


if __name__ == "__main__":
    main()
