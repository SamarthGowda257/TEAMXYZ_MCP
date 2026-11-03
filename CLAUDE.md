# CLAUDE.md — CareLine (TeamXYZ, Talkdesk AI Hackday)

You are building **CareLine V2**: the backend, MCP server and website for "CareLine Hospitals, Bengaluru", a hospital customer-experience product whose chat and voice support runs on **Talkdesk**. Everything lives in this one repo (`SamarthGowda257/TEAMXYZ_MCP`).

**Read these before writing any code, in this order:**

| # | File | What it gives you |
|---|---|---|
| 0 | `docs/00_START_HERE.md` | Ground rules, environment, priorities |
| 1 | `docs/01_PROJECT_OVERVIEW.md` | The product, the hackathon, V1 results, demo story |
| 2 | `docs/02_TALKDESK_PRIMER.md` | How Talkdesk works and how our code must fit it |
| 3 | `docs/03_REQUIREMENTS.md` | Functional and non-functional requirements (IDs) |
| 4 | `docs/04_ARCHITECTURE.md` | System design, code layout, env vars, auth, deploy |
| 5 | `docs/05_AGENTS_AND_TOOLS.md` | The 9 Talkdesk agents and all 34 MCP tool contracts |
| 6 | `docs/06_DATABASE.md` | Schema, constraints, seed data generator |
| 7 | `docs/07_CONTEXT_BLACKBOARD.md` | P0/P1/P2 context, cache, prefetch, memory, RAG |
| 8 | `docs/08_LATENCY.md` | Latency budget and the rules that keep tools fast |
| 9 | `docs/09_FRONTEND.md` | Pages, design system, chat widget |
| 10 | `docs/10_BUILD_PLAN.md` | Phases, acceptance tests, definition of done |

Also read any skills already in this repo (look for `.claude/skills/` or a `skills/` folder) and follow them where they apply.

## Non-negotiables (short version; details in 00)
1. **Read the existing code first** (`server.py` and friends). It is live and connected to Talkdesk. Keep its MCP library, transport, endpoint path and auth scheme exactly as they are.
2. **Never break the 6 existing tool names**: `get_doctors`, `find_available_slots`, `book_appointment`, `find_appointments`, `reschedule_appointment`, `cancel_appointment`. Add inputs as optional; never rename or remove.
3. **Never commit secrets** (bearer token, DB URL, SMTP password, Supabase keys). Use env vars and `.env.example`.
4. **Git**: before the first change, tag the current commit `v1-baseline`. Work on branch `v2`. Commits are authored by the user's git identity. Do **not** add `Co-Authored-By` or any Claude attribution lines to commits or PRs.
5. **Ask before** pushing to `main` (Render auto-deploys `main`, which is the live server Talkdesk calls).
6. **Every tool returns** `{ "ok", "message", "data" }`, never raises, stays under ~1 KB, and puts a ready-to-speak sentence in `message`.
7. **Identity-sensitive tools** (cancel, reschedule, lab email, bills, history, preferences) verify **phone + date of birth on the server**.
8. You run in a **cloud container**, not on the user's computer. You cannot open the Talkdesk UI, Render dashboard or Supabase dashboard. Write the code, the tests and a clear list of what the human must click.
