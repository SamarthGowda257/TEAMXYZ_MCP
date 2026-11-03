# 00 — Start Here

## What you are building, in one paragraph
WellNest Hospitals is a (fictional) multi-specialty hospital in Bengaluru. Patients reach it three ways: the **website** (login, book, see appointments and lab reports), **web chat** (a Talkdesk chat widget on the website), and **phone** (a Talkdesk number). The chat and phone conversations are handled by **AI agents configured inside Talkdesk**. Those agents act on the hospital's data by calling **tools on our MCP server**. You build the MCP server, the website, the website's API and the database layer, all as **one FastAPI app** in this repo.

```
Website ──/api──►┐
Talkdesk agents ─/mcp─► ONE FASTAPI APP (Render) ──► Supabase Postgres
Cron pinger ─/jobs─►┘          │
                               └─► Email (SMTP) + simulated SMS/WhatsApp outbox
```

## The situation
- **Event**: Talkdesk AI Hackday, PES University, Wed 4 Nov 2026. Demos start 2 PM. Code freeze 12:30 PM that day.
- **Judging**: integration & architecture with Talkdesk, problem worth solving, real-world impact, presentation and Q&A. The Talkdesk PM said **"realness" of the product** matters.
- **V1 exists and is live**: 3 agents + this MCP server with 6 tools and in-memory data. It was evaluated (score 88.75, about 5/10 goals truly achieved). V2 must fix the failures and add the full product. See `01_PROJECT_OVERVIEW.md`.
- **Time is short.** Build in the priority order of `10_BUILD_PLAN.md`. A smaller thing that works end to end beats a bigger thing that half works.

## Ground rules
1. **Inspect before changing.** Read `server.py`, `requirements.txt`, `render.yaml` (if any), `.env.example`, any dashboard HTML and any skills folder. Write a short summary of what exists (MCP library, transport, auth header, env var names, current data model) before Phase 1.
2. **Keep V1 tools compatible.** The 6 existing tools keep their names and existing parameters. New parameters are optional. The V1 evaluation numbers are already recorded; behaviour may improve, but calls V1 makes must not error.
3. **Safety tag.** `git tag v1-baseline` on the current `main` commit and push the tag, so the live V1 server can be redeployed from it if anything goes wrong.
4. **Branching.** Work on `v2`. Merge to `main` only when the user says so, in small steps, with the smoke test passing.
5. **Commit identity.** Use whatever `git config user.name/user.email` the user set. No `Co-Authored-By` trailers, no "Generated with Claude" lines, in commits or PR bodies. If the environment adds them automatically, remove them.
6. **Secrets.** Only in env vars. Keep `.env` in `.gitignore`. Update `.env.example` with every new variable (names only, fake values).
7. **Data is fake.** All patients, phones and emails in seed data are invented. Use `example.com` / `wellnest.test` emails except the demo personas the user provides via env.
8. **No medical advice anywhere** in tool messages. Department suggestions are routing only, with a disclaimer.

## Your environment (important)
- You are **Claude Code running in a cloud container**, not on the user's laptop. The user cannot see your terminal. Report results in plain words.
- **You cannot** log into Talkdesk, Render or Supabase dashboards. When something must be clicked, write it into `docs/HUMAN_TODO.md` (create it) as numbered steps.
- **Network may be restricted.** Package registries and GitHub usually work. Supabase or Render URLs may be blocked from the container. If you cannot reach the real database:
  - try to run a local Postgres (`apt-get install -y postgresql` or a `pg_ctl` binary from pip such as `postgresql-wheel`, or `testing.postgresql`), and
  - if that also fails, keep the DB layer behind small repository functions and test the logic with fakes. Say clearly what was not tested against real Postgres.
- **Deploys happen via git push**: Render auto-deploys `main`. Never push to `main` without the user's OK.
- **Long-running servers** you start in the container are only for local tests. They are not reachable by Talkdesk.

## Priorities (if time runs out, cut from the bottom)
| Tier | Scope |
|---|---|
| **P0 must** | DB + seed, `verify_patient`, the 6 existing tools DB-backed, waitlist (join, auto-offer on cancel, accept), lab report status + email, insurance info + coverage, emergency `create_handoff`, response envelope, auth on `/mcp`, smoke test |
| **P1 should** | Website: login, portal, booking, lab reports, waitlist accept page, chat widget embed; email sending; reminders job; read-only dashboard with metrics; senior flag + preferences; interaction memory (notes + search) |
| **P2 could** | Billing tools, aftercare tools, caregiver updates, prescription refill, Redis L2 cache, pgvector embeddings, birthday job |

## What "done" means for any feature
- Tool or endpoint implemented, input-validated, returns the envelope.
- Unit test or smoke-test line covering the happy path and one failure.
- Listed in `05_AGENTS_AND_TOOLS.md` with the exact name the Talkdesk team will map.
- If it needs a human click (env var, Talkdesk skill mapping), it is in `docs/HUMAN_TODO.md`.
