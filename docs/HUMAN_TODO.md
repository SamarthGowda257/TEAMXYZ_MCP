# Things a human must do (Claude Code can't click these)

Numbered so we can refer to them ("done with 3"). Tick the box when done.

## Git
1. [ ] **Push the safety tag** (the cloud container's git proxy blocks tag pushes). From a laptop with the repo:
   ```bash
   git fetch origin && git tag v1-baseline fe2205e0ed95e66d0ba88aadf1640e990485cf76 && git push origin v1-baseline
   ```
   Or on GitHub: Releases → Draft a new release → "Choose a tag" → type `v1-baseline` → Target: branch `v1-baseline-branch` → Publish.
   Until then, branch `v1-baseline-branch` is the rollback point (same commit).

## Render
2. [ ] Open the `teamxyz-mcp` service → Settings and tell Claude (or note here): Python version shown in the build log, health check path, instance type. Nothing to change yet.
3. [ ] Env vars: (every new variable is listed here as phases add them)
4. [ ] Health check path `/health`

## Supabase
5. [ ] Create project "careline" in region Singapore
6. [ ] Copy transaction pooler URL → Render env `DATABASE_URL`
7. [ ] Run: `DATABASE_URL=... ./db/reset.sh` (from a laptop, or Supabase SQL editor: paste `schema.sql` then `seed.sql`)
8. [ ] Auth → Email provider on; Site URL = `PUBLIC_BASE_URL`; copy anon key + JWT settings

## Uptime/cron
9. [ ] Ping `/health` every 5 min; `POST /jobs/run?token=...` every 1 min

## Talkdesk
10. [ ] Refresh MCP server connection (`TeamXYZ_MCP`) so new tools appear
11. [ ] Map new skills to agents (table in `docs/05_AGENTS_AND_TOOLS.md`)
12. [ ] Create chat touchpoint → give `TALKDESK_TOUCHPOINT_ID` + region
