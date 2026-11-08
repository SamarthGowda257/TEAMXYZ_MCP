# Chat latency: where the time goes and the plan (8 Nov 2026)

## Measured live (website chat, signed in, `/health` → `chat_link.recent_tool_calls` gives server time)
| Message | Sent | Talkdesk called our tool | Our server time | Reply on screen | Total |
|---|---|---|---|---|---|
| "What's my HealthCredits balance?" | 20:48:56 | 20:49:06 (+10 s) | 89 ms | ≈ +16 s | **≈ 16 s** |
| "When is a cardiologist free tomorrow?" | 20:50:20 | 20:50:25 (+5 s) | 24 ms | ≈ +11 s | **≈ 11 s** |

Network from India to our server: 0.15–0.2 s per request including the database check (Cloudflare, Chennai edge).

**Our server is under 1% of the wait.** All the rest happens inside Talkdesk, which runs every turn through a
chain of sequential AI steps:

```
patient ─► Receptionist decides who handles it (AI step 1, 2–5 s)
        ─► specialist decides which tool to call (AI step 2, 2–5 s)
        ─► our tool (0.03–0.1 s + 0.3–0.6 s network US ⇄ Singapore)
        ─► specialist writes the answer (AI step 3, 2–3 s)
        ─► Receptionist rewrites the answer for the patient (AI step 4, 2–3 s)
```
Each AI step costs more the longer its instructions are and the more text it writes. Ours are long: Receptionist
about 3,000 characters plus the 2,000-character Conditions box, Booking Agent 4,400 characters, and the
Receptionist re-writes every specialist answer (which is also why it kept dropping IDs and details).

## What 3–5 s means here
Four sequential AI steps on Talkdesk's platform cannot reliably finish in 3–5 s; each step is 1.5–5 s on its own.
Realistic targets:
- **6–8 s** typical for one-tool questions after steps 1–4 below (from 11–16 s today).
- **4–6 s** for the most common questions if step 5 (Receptionist answers simple FAQs itself) works on this platform.
- A guaranteed **3–5 s** would need one AI step per turn, i.e. not the Receptionist + specialist design (see "Not
  recommended" at the end).

## The plan, in order of payoff per minute of work
| # | Change | Where | Expected saving | Effort |
|---|---|---|---|---|
| 1 | **Receptionist relays the specialist's answer word for word** instead of rewriting it | Talkdesk: Receptionist instructions | 2–3 s every turn (removes most of AI step 4's writing) | 2 min |
| 2 | **Drop the "first message goes to Support" rules** (F2/F3). Since `caller_id` works in every tool, the sign-in check before each new chat is an extra full hop | Talkdesk: Receptionist + Support + Conditions | 4–8 s on the first message of every chat | 5 min |
| 3 | **Shorten every instruction box** to the rules that matter (Receptionist ≤ 1,500 chars, specialists ≤ 1,500, Conditions ≤ 1,200). I write the short versions | Me (text) → you (paste) | 0.5–1.5 s per AI step, so 1.5–4 s per turn | Me 1 h, you 15 min |
| 4 | **Shorter tool replies**: one ready-to-say sentence first, details only in `data`; the agent copies it instead of composing | Me (server) | 0.5–1 s on AI step 3 | Me 1 h |
| 5 | **Receptionist answers hospital FAQs itself** (address, hours, parking, visiting) with Knowledge Management on, no specialist hop | Talkdesk: Receptionist + KB | Those questions drop to one AI step (≈ 3–5 s) | 20 min, test whether the platform allows it |
| 6 | **Keep the server warm**: confirm the Render plan doesn't sleep (cron pings `/jobs/run` every minute; a paid "Starter" instance removes 30–60 s cold starts for good) | You: Render dashboard | Removes rare 30–60 s first replies | 2 min |
| 7 | **Move server + database to the US** (Render Oregon/Ohio + Supabase US) next to Talkdesk `td-us-1` | You + me | 0.3–0.6 s per tool call | 2–3 h with data migration; only after 1–6 |

Already done on our side (no action): tool server time 24–89 ms, email/calendar/embeddings off the request path,
reference data cached, one specialist answers the common combinations (slots include doctor, fee, room).

## How we'll know
After each step I re-run the same two questions plus a booking and an order, signed in, and fill in this table from
the chat timestamps and `/health`:

| Step done | Balance | Cardiologist slots | Booking (2 turns) | Order (2 turns) |
|---|---|---|---|---|
| Before (20:49) | ≈ 16 s | ≈ 11 s | not timed | not timed |
| After 1–2 + J5/J6 (21:09–21:25) | ≈ 14 s (tool at +8 s, 81 ms) | ≈ 9 s (tool at +6 s, 21 ms) | | |
| After 3–4 | | | | |

## Perceived speed (free, do anyway)
- Talkdesk already shows "Thinking…" and has Conversation Fillers on; keep both.
- In the demo video, cut or speed up the waits (the script already says so).

## Not recommended
- **Our own chat engine instead of Talkdesk** (one AI call with all 47 tools, streaming): 2–4 s is realistic, but the
  hackathon is about Talkdesk, and the phone line would still use Talkdesk. Mention it as future work only.
- **Merging agents into one**: Talkdesk allows 5 skills per agent, and we use 47 tools.

## Round 1 result (8 Nov, 21:25)
- Saved 2–3 s per reply; most of the remaining time is **before** the tool call (6–8 s: Receptionist routing +
  specialist choosing the tool). That is what round 2 (shorter instructions, Receptionist first) targets.
- Answers checked unchanged: cardiologist slots (word for word), Azithromycin refusal, balance, last-chat recall,
  emergency (full 108 / entrance B / team member text in a fresh chat).
- Seen once: in a long chat the emergency reply came back as Talkdesk's "Sorry, I cannot handle your request right
  now" although our urgent handoff was created; a fresh chat answered correctly. Watch in round 2.

## Round 2 result (8 Nov, 21:37)
| Message | Before (20:49) | After round 1 | After round 2 (short Receptionist) |
|---|---|---|---|
| Balance | ≈ 16 s | ≈ 14 s | ≈ 13 s |
| Cardiologist slots | ≈ 11 s | ≈ 9 s | ≈ 11–13 s |

- The same question varies by about ±3 s from run to run inside Talkdesk; that is now larger than anything the
  instruction text changes. The Talkdesk call to our tool still comes 6–9 s after the message, and our server takes
  under 0.1 s.
- **Conclusion:** the configuration levers are used up. What is left inside the WellNest code (region move to the US)
  would save about 0.3–0.6 s per tool call: not worth the migration risk before the demo.
- What remains is Talkdesk's own pipeline (Receptionist and specialist AI steps). Options outside our code, for the
  team to decide: ask Talkdesk whether the hackathon tenant can use a faster model or a single-agent setup for chat; in
  the demo video, speed up the waits (the script already says so).
