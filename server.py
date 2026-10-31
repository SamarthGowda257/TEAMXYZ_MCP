"""
TeamXYZ-MCP Server
==================
A minimal MCP (Model Context Protocol) server using Streamable HTTP transport.

Exposes three tools:
  - add_numbers      : Returns the sum of two integers.
  - multiply_numbers : Returns the product of two integers.
  - greet_user       : Returns a personalised greeting string.

Usage:
    python server.py

Environment variables:
    PORT              - Port to listen on (default: 8000)
    MCP_BEARER_TOKEN  - Required secret token for Bearer authentication.
                        All incoming requests must carry:
                          Authorization: Bearer <MCP_BEARER_TOKEN>
                        Server refuses to start if this variable is not set.
"""

import json
import os
import sys

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Startup guard — fail fast if the secret token is missing
# ---------------------------------------------------------------------------

_BEARER_TOKEN = os.environ.get("MCP_BEARER_TOKEN", "").strip()
if not _BEARER_TOKEN:
    sys.exit(
        "ERROR: MCP_BEARER_TOKEN environment variable is not set.\n"
        "Set it before starting the server:\n"
        "  export MCP_BEARER_TOKEN=your-secret-token"
    )


# ---------------------------------------------------------------------------
# Bearer token authentication middleware
# ---------------------------------------------------------------------------


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces a static Bearer token on every request.

    Requests without a valid 'Authorization: Bearer <token>' header receive
    a 401 JSON response and never reach the MCP handler.
    """

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "detail": "Authorization: Bearer <token> header required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        provided_token = auth_header[len("Bearer "):]

        # Constant-time comparison to prevent timing attacks
        import hmac
        if not hmac.compare_digest(provided_token, _BEARER_TOKEN):
            return JSONResponse(
                {"error": "forbidden", "detail": "Invalid Bearer token."},
                status_code=403,
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# MCP server — tool definitions
# ---------------------------------------------------------------------------

mcp = MCPServer(name="TeamXYZ-MCP")


@mcp.tool(description="Adds two integers and returns their sum.")
def add_numbers(a: int, b: int) -> int:
    """Add two integers together.

    Args:
        a: The first integer.
        b: The second integer.

    Returns:
        The sum of a and b.
    """
    return a + b


@mcp.tool(description="Multiplies two integers and returns their product.")
def multiply_numbers(a: int, b: int) -> int:
    """Multiply two integers together.

    Args:
        a: The first integer.
        b: The second integer.

    Returns:
        The product of a and b.
    """
    return a * b


@mcp.tool(description="Greets a user by name and returns a friendly greeting string.")
def greet_user(name: str) -> str:
    """Produce a personalised greeting for the given name.

    Args:
        name: The name of the person to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}! Welcome to TeamXYZ-MCP 👋"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    # Get the Starlette ASGI app from the SDK
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        host="0.0.0.0",
    )

    # Wrap it with Bearer token authentication (outermost layer)
    app.add_middleware(BearerTokenMiddleware)

    print(f"Starting TeamXYZ-MCP server on http://0.0.0.0:{port}/mcp")
    print("Authentication: Bearer token required on all requests.")

    uvicorn.run(app, host="0.0.0.0", port=port)
