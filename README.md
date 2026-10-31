# TeamXYZ-MCP

A minimal, remotely deployable **Model Context Protocol (MCP) server** built with
the official Python MCP SDK. Designed as a clean learning foundation for the
Talkdesk hackathon and compatible with the **Talkdesk AI Agent Platform Custom MCP Server** integration.

---

## What is MCP?

The **Model Context Protocol** is an open standard (developed by Anthropic) that
lets AI models (like Claude or any MCP-compatible client) connect to external
tools and data sources in a structured, interoperable way.

Instead of building bespoke integrations, MCP gives you:
- A standardised wire protocol between AI clients and tool servers.
- Typed tool definitions with automatic schema generation.
- Multiple transport options (stdio, SSE, Streamable HTTP).

This server uses **Streamable HTTP** — the modern, stateless HTTP POST-based
transport (not the deprecated SSE approach).

---

## What This Server Does

`TeamXYZ-MCP` exposes **three tools** that an AI client can discover and call:

| Tool | Inputs | Returns |
|------|--------|---------|
| `add_numbers` | `a: int`, `b: int` | Sum of `a + b` |
| `multiply_numbers` | `a: int`, `b: int` | Product of `a * b` |
| `greet_user` | `name: str` | Personalised greeting string |

---

## How the Server Works

```
AI Client (e.g. Talkdesk, Claude, MCP Inspector)
        │
        │  HTTP POST /mcp
        │  Authorization: Bearer <MCP_BEARER_TOKEN>
        ▼
 BearerTokenMiddleware   ← rejects invalid/missing tokens (401/403)
        │
        ▼
 TeamXYZ-MCP  (MCPServer — mcp 2.x SDK)
        │
   Starlette ASGI app (Streamable HTTP transport)
        │
   Tool handlers: add_numbers | multiply_numbers | greet_user
```

1. The server starts and validates that `MCP_BEARER_TOKEN` is set.
2. Every HTTP request is intercepted by `BearerTokenMiddleware`.
3. Requests missing or carrying a wrong `Authorization: Bearer` header get a 401/403 immediately — the MCP layer is never reached.
4. Authenticated requests are forwarded to the MCP handler, which routes them to the correct tool function.
5. Return values are type-checked and serialised back to the client.

---

## Project Structure

```
TeamXYZ_MCP/
├── server.py          # MCP server — auth middleware + tool definitions
├── requirements.txt   # Python dependencies
├── .env.example       # Environment variable template
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

---

## ⚠️ Security

### Current state
- **Bearer token authentication** is enforced on every request.
- The token is read from `MCP_BEARER_TOKEN` — never hardcoded.
- Token comparison uses `hmac.compare_digest` to prevent timing attacks.
- The server refuses to start if `MCP_BEARER_TOKEN` is not set.

### What this does NOT cover (add before hardened production use)
- Token rotation / expiry.
- Per-client scoping or OAuth flows.
- Rate limiting.
- Audit logging.
- HTTPS termination (Render provides HTTPS automatically; add a reverse proxy
  for self-hosted deployments).

**Never commit `.env` or any file containing a real token to source control.**

---

## Local Setup

### Prerequisites

- Python 3.11+
- `pip`

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/TeamXYZ_MCP.git
cd TeamXYZ_MCP
```

### 2. Create and activate a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate a Bearer token

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output — this is your `MCP_BEARER_TOKEN`.

### 5. Set environment variables and start the server

```bash
export MCP_BEARER_TOKEN="<token-you-generated>"
export PORT=8000          # optional, defaults to 8000

python server.py
```

You should see:

```
Starting TeamXYZ-MCP server on http://0.0.0.0:8000/mcp
Authentication: Bearer token required on all requests.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The MCP endpoint is now live at: **`http://localhost:8000/mcp`**

---

## Testing with MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) is the
official interactive tool for testing MCP servers.

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI:
1. Set **Transport** to `Streamable HTTP`.
2. Set **URL** to `http://localhost:8000/mcp`.
3. Add a custom header: `Authorization: Bearer <your-token>`.
4. Click **Connect**.
5. Go to the **Tools** tab — you should see `add_numbers`, `multiply_numbers`, and `greet_user`.
6. Select a tool, enter inputs, and click **Run Tool**.

### Quick curl tests

```bash
TOKEN="your-secret-token"

# Should return 401
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'

# Should return 200 + server capabilities
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'
```

---

## Deploying to Render

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial TeamXYZ-MCP server with Bearer auth"
git remote add origin https://github.com/<your-username>/TeamXYZ_MCP.git
git push -u origin main
```

### 2. Create a Web Service on Render

1. Go to [render.com](https://render.com) and sign in.
2. Click **New → Web Service**.
3. Connect your GitHub repository.
4. Fill in the service settings:

| Setting | Value |
|---------|-------|
| **Environment** | Python |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python server.py` |

5. Under **Environment Variables**, add:

| Key | Value |
|-----|-------|
| `MCP_BEARER_TOKEN` | *(paste your generated token — Render stores this securely)* |
| `PORT` | *(leave blank — Render injects this automatically)* |

6. Click **Deploy**.

### 3. Your public MCP endpoint

Once deployed, your MCP endpoint will be:

```
https://<your-render-service-name>.onrender.com/mcp
```

---

## Connecting to Talkdesk AI Agent Platform

In the Talkdesk AI Agent Platform **Custom MCP Server** configuration:

| Field | Value |
|-------|-------|
| **Server URL** | `https://<your-render-service-name>.onrender.com/mcp` |
| **Transport** | Streamable HTTP |
| **Authorization Header** | `Authorization: Bearer <MCP_BEARER_TOKEN>` |

Talkdesk will send the `Authorization` header on every MCP request, which
`BearerTokenMiddleware` validates before forwarding to the tool handlers.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_BEARER_TOKEN` | **Yes** | — | Secret Bearer token. Server exits on startup if not set. |
| `PORT` | No | `8000` | Port the server listens on. Set automatically by Render. |

---

## Extending This Server

To add a new tool, add a decorated function to `server.py`:

```python
@mcp.tool(description="Describe what this tool does for the AI client.")
def my_new_tool(input_param: str) -> str:
    return f"Result: {input_param}"
```

The SDK auto-generates the JSON schema from Python type annotations.
