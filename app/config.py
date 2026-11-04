"""All settings come from environment variables. See .env.example for the full list."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


# --- MCP connection (unchanged from V1: Talkdesk is registered with this token) ---
MCP_TOKEN = env("MCP_BEARER_TOKEN") or env("MCP_TOKEN")
PORT = int(env("PORT", "8000"))

# --- database: Postgres when DATABASE_URL is set, otherwise a local SQLite file ---
DATABASE_URL = env("DATABASE_URL")
REDIS_URL = env("REDIS_URL")            # Render Key Value / Upstash; empty = in-process memory and queue
DB_PATH = env("DB_PATH", str(ROOT / "wellnest.db"))
AUTO_SEED = env("AUTO_SEED", "true").lower() != "false"

# --- ops tokens (fall back to the MCP token so nothing extra is required to start) ---
DASHBOARD_TOKEN = env("DASHBOARD_TOKEN") or MCP_TOKEN
JOBS_TOKEN = env("JOBS_TOKEN") or MCP_TOKEN
SECRET_KEY = env("SECRET_KEY") or hashlib.sha256(f"wellnest-session:{MCP_TOKEN}".encode()).hexdigest()

# --- admin console sign-in (/admin). An ID and password, not a token in the URL.
# ADMIN_PASSWORD falls back to the dashboard token so the console works before anything is added to Render.
ADMIN_USER = env("ADMIN_USER", "admin")
ADMIN_PASSWORD = env("ADMIN_PASSWORD") or DASHBOARD_TOKEN

# --- website / widget ---
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "https://teamxyz-mcp.onrender.com").rstrip("/")
TALKDESK_TOUCHPOINT_ID = env("TALKDESK_TOUCHPOINT_ID")
TALKDESK_REGION = env("TALKDESK_REGION", "td-us-1")
TALKDESK_VOICE_NUMBER = env("TALKDESK_VOICE_NUMBER")      # the Talkdesk number that reaches the AI receptionist
DEMO_PASSWORD = env("DEMO_PASSWORD", "WellNest@2026")
# After a phone + date of birth match, tools accept the phone alone for this many minutes (no re-asking).
VERIFIED_SESSION_MIN = int(env("VERIFIED_SESSION_MIN", "30"))
# A patient signed in on the website who opens the chat counts as verified for this long.
WEB_SESSION_MIN = int(env("WEB_SESSION_MIN", "120"))

# --- autonomous outbound calls (Talkdesk Flows API -> Studio "API request" flow) ---
TALKDESK_ACCOUNT = env("TALKDESK_ACCOUNT")                  # account name in <account>.mytalkdesk.com
TALKDESK_CLIENT_ID = env("TALKDESK_CLIENT_ID")              # Builder -> OAuth Clients, Client Credentials,
TALKDESK_CLIENT_SECRET = env("TALKDESK_CLIENT_SECRET")      # scope flows-interactions:start
TALKDESK_OUTBOUND_FLOW_ID = env("TALKDESK_OUTBOUND_FLOW_ID")
TALKDESK_API = {"td-us-1": "https://api.talkdeskapp.com", "td-eu-1": "https://api.talkdeskapp.eu",
                "td-ca-1": "https://api.talkdeskappca.com", "td-uk-1": "https://api.talkdeskapp.co.uk"}.get(TALKDESK_REGION, "https://api.talkdeskapp.com")
OUTBOUND_ENABLED = env("OUTBOUND_ENABLED", "false").lower() in ("1", "true", "yes")
OUTBOUND_TEST_NUMBER = env("OUTBOUND_TEST_NUMBER")          # when set, every call rings this number (demo safety)
# Patients the scheduler may call ("*" = everyone). Default: the demo personas only.
OUTBOUND_ALLOWLIST = [x.strip() for x in env("OUTBOUND_ALLOWLIST", "+919845000001,+919845000002,+919845000003,"
                                                                   "+919845000004,+919845000005").split(",") if x.strip()]
OUTBOUND_WEBHOOK_TOKEN = env("OUTBOUND_WEBHOOK_TOKEN") or JOBS_TOKEN
OUTBOUND_CALL_HOURS = tuple(int(x) for x in env("OUTBOUND_CALL_HOURS", "9-20").split("-"))   # IST, start-end hour
OUTBOUND_MAX_ATTEMPTS = int(env("OUTBOUND_MAX_ATTEMPTS", "3"))
OUTBOUND_RETRY_MIN = int(env("OUTBOUND_RETRY_MIN", "30"))
OUTBOUND_MAX_PER_RUN = int(env("OUTBOUND_MAX_PER_RUN", "2"))

# --- email ---
SMTP_HOST = env("SMTP_HOST")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER")
SMTP_PASSWORD = env("SMTP_PASSWORD")
EMAIL_FROM = env("EMAIL_FROM", "WellNest Hospitals <no-reply@wellnest.test>")
DEMO_EMAIL_OVERRIDE = env("DEMO_EMAIL_OVERRIDE")
try:
    DEMO_PERSONA_EMAILS: dict = json.loads(env("DEMO_PERSONA_EMAILS", "{}"))
except ValueError:
    DEMO_PERSONA_EMAILS = {}

EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

# --- hybrid search (Postgres full-text + trigram + pgvector) ---
# The keyword and fuzzy legs always run on Postgres. The meaning (vector) leg needs an embeddings key:
# Google AI Studio (free tier) -> EMBEDDINGS_API_KEY. "hash" is a local, non-semantic stand-in for tests only.
EMBEDDINGS_API_KEY = env("EMBEDDINGS_API_KEY") or env("GEMINI_API_KEY")
EMBEDDINGS_PROVIDER = (env("EMBEDDINGS_PROVIDER") or ("gemini" if EMBEDDINGS_API_KEY else "none")).lower()
EMBEDDINGS_MODEL = env("EMBEDDINGS_MODEL", "gemini-embedding-001")
EMBEDDINGS_DIM = 768                      # fixed: the pgvector column is vector(768)
EMBEDDINGS_TIMEOUT = float(env("EMBEDDINGS_TIMEOUT", "1.5"))   # seconds, for the query embedding in a live call
SEARCH_MIN_SIM = float(env("SEARCH_MIN_SIM", "0.70"))          # cosine needed for a meaning-only match to count
SEARCH_VEC_FLOOR = float(env("SEARCH_VEC_FLOOR", "0.50"))      # below this a vector match adds no ranking credit
# Background embedding cap per day (IST). Gemini's free tier is roughly 1,000 requests/day per project, so this leaves
# headroom for live query embeddings. Only natural-language text is embedded (knowledge passages and notes).
EMBED_DAILY_BUDGET = int(env("EMBED_DAILY_BUDGET", "900"))

# --- hospital clock: fixed IST offset (no tzdata needed) ---
IST = timezone(timedelta(hours=5, minutes=30), "IST")


def now() -> datetime:
    """Current IST time as a naive datetime (all DB timestamps are naive IST)."""
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)


def today():
    return now().date()


HOSPITAL_NAME = "WellNest Hospitals"
VERSION = "2.0.0"
