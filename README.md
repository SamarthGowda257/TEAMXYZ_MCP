# CareLine Hospitals · TeamXYZ (Talkdesk AI Hackday 2026)

An AI front desk for a (fictional) hospital in Bengaluru: patients book, reschedule, cancel, join waitlists, get lab
reports and check insurance by **Talkdesk chat or voice**, or on the **website**. Every action lands in one database,
shows on the patient portal and on a live operations dashboard.

- **Live:** https://teamxyz-mcp.onrender.com (Render, auto-deploys `main`)
- **Talkdesk:** MCP server `TeamXYZ_MCP` → `https://teamxyz-mcp.onrender.com/mcp` with `Authorization: Bearer <MCP_BEARER_TOKEN>`
- **Stack:** Python, official MCP SDK 2.x (Streamable HTTP), FastAPI, SQLAlchemy, Supabase Postgres (SQLite fallback),
  React + Vite + TypeScript website (pre-built into `web/dist`)

| Read | For |
|---|---|
| [`docs/V2_GUIDE.md`](docs/V2_GUIDE.md) | What's built, demo personas, how to run and test |
| [`docs/HUMAN_TODO.md`](docs/HUMAN_TODO.md) | Supabase, Render env vars, cron, Talkdesk changes (things to click) |
| [`docs/05_AGENTS_AND_TOOLS.md`](docs/05_AGENTS_AND_TOOLS.md) | The 9 agents and 34 tool contracts |
| [`CLAUDE.md`](CLAUDE.md) + `docs/00`–`10` | Full specification |

```
server.py            entry point (Render start command: python server.py)
app/                 config, db schema, seed data, MCP tools, website API, services (business rules)
frontend/            React source for the website   →   web/dist (built output, committed)
scripts/smoke_mcp.py 30 acceptance checks over the real MCP transport
tests/               unit tests
```

All patient data is invented. A real deployment would need patient consent, retention rules and DPDP Act compliance.
