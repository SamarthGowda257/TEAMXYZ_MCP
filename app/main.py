"""Assembles the single ASGI app.

/mcp is served exactly as in V1: MCPServer.streamable_http_app(path="/mcp", stateless_http=True,
json_response=True) behind the same Bearer token middleware (401 missing, 403 wrong, constant-time compare).
Everything else (website, /api, /jobs, /health) is a FastAPI app mounted after the /mcp route.
"""

import hmac
import logging

from starlette.responses import JSONResponse
from starlette.routing import Mount

from . import config, db, notify, seed
from .api import create_app
from .mcp_tools import mcp
from .services import ref

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("careline")


def init_data() -> None:
    try:
        db.create_schema()
    except Exception as e:  # bad DATABASE_URL or database down: don't take the whole service down
        msg = str(e).splitlines()[0][:300]
        log.error("DATABASE_URL could not be used, falling back to local SQLite: %s", msg)
        db.fallback_to_sqlite(msg)
        db.create_schema()
    if config.AUTO_SEED and not seed.is_seeded():
        log.info("Seeding demo data: %s", seed.seed())
    ref.load()
    notify.start_sender()


class BearerTokenMiddleware:
    """/mcp requires 'Authorization: Bearer <MCP_BEARER_TOKEN>'. Missing -> 401, wrong -> 403."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if not auth.startswith("Bearer "):
                resp = JSONResponse({"error": "unauthorized", "detail": "Authorization: Bearer <token> header required."},
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
                await resp(scope, receive, send)
                return
            if not hmac.compare_digest(auth[len("Bearer "):].encode(), config.MCP_TOKEN.encode()):
                resp = JSONResponse({"error": "forbidden", "detail": "Invalid Bearer token."},
                                    status_code=403, headers={"WWW-Authenticate": "Bearer"})
                await resp(scope, receive, send)
                return
        await self.inner(scope, receive, send)


def build():
    init_data()
    mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True, host="0.0.0.0")
    mcp_app.router.routes.append(Mount("/", app=create_app()))
    return BearerTokenMiddleware(mcp_app)
