"""CareLine Hospitals (TeamXYZ, Talkdesk AI Hackday) - entry point.

  /mcp          MCP endpoint for the Talkdesk AI agents (Streamable HTTP, Bearer token)  [unchanged from V1]
  /             patient website (portal, booking, reports, waitlist accept, chat widget)
  /api/...      website + dashboard JSON API
  /dashboard    live operations dashboard (?token=DASHBOARD_TOKEN)
  /jobs/run     reminders + waitlist offer expiry (?token=JOBS_TOKEN), call every minute
  /health       uptime + DB check

Run:  export MCP_BEARER_TOKEN=your-secret && python server.py
"""

import sys

import uvicorn

from app import config

if not config.MCP_TOKEN:
    sys.exit("ERROR: MCP_BEARER_TOKEN environment variable is not set.\n"
             "Set it before starting the server:  export MCP_BEARER_TOKEN=your-secret-token")

from app.main import build  # noqa: E402

app = build()

if __name__ == "__main__":
    print(f"Starting CareLine Hospitals on http://0.0.0.0:{config.PORT}  (MCP at /mcp, website at /)")
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, log_level="warning", workers=1)
