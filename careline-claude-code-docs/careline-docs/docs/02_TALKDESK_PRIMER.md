# 02 — Talkdesk Primer (what you must know to build for it)

Talkdesk is a cloud contact-center platform. For this project we use its **AI Agent Platform** (LLM agents), **Studio** (call/chat flow designer), **Autopilot** (connects flows to agents), **Digital Engagement chat widget**, **phone numbers**, and **Conversations** (where human agents take chats/calls). The humans on the team configure all of this in the Talkdesk UI. **You build the server those agents call.**

## How a conversation reaches our code
```
Chat:  Browser widget ──► Talkdesk chat touchpoint ──► Studio chat flow
                                                    ──► Connect to Autopilot Digital ─┐
Voice: Caller ──► Talkdesk number ──► Studio voice flow                               │
                                   ──► Connect to Autopilot Voice ────────────────────┤
                                                                                      ▼
                         AI Agent Platform orchestration (Receptionist + 8 specialists)
                                                                                      │
                                         MCP tool call over HTTPS + bearer token      ▼
                                                              OUR FASTAPI APP  /mcp
```
- **Chat messages never pass through our backend.** The widget talks to Talkdesk directly. Our server only sees **tool calls** the agents decide to make.
- **Voice**: Talkdesk does speech-to-text and text-to-speech. Our tools return text; the agent speaks it. Write `message` fields that sound natural when read aloud (no tables, no markdown, no emojis, spell out short codes clearly).
- **Human handoff**: Studio routes the conversation to a human in the Conversations app. Our `create_handoff` tool records the reason and summary so our dashboard and the human have context.

## The AI Agent Platform model
- An **orchestration** is a tree of agents. Ours: **Receptionist** (supervisor, talks to the patient) with 8 specialist children. Depth 2.
- Platform limits (from Talkdesk docs): up to **3 hierarchy levels**, up to **10 agents per level**, up to **5 skills (tools) per agent**.
- A **skill** = one tool from a connected MCP server (or other integration) attached to one agent. The same tool can be a skill on several agents.
- **Custom variables** hold conversation facts (phone, date, booking ID...). Skill inputs are mapped from variables or filled by the LLM. Variables are how agents share facts with each other.
- The supervisor routes using **Conditions** text written by the team and **Instructions** (prompts) per agent.
- **Measured behaviour (3 Nov test):** the supervisor delegates to child agents **one at a time** (sequential), then combines their answers itself. Each hop is roughly one LLM step (~2–3 s). There is no parallel fan-out to rely on. Design tools so common requests need **one** specialist.
- **Insight** in the test console shows each agent hop, tool input and tool result. The team uses it to debug; make tool results easy to read there.
- **Agent Evaluation** runs simulated conversations against a dataset and scores them. We compare V1 vs V2.

## How Talkdesk calls our MCP server
- The team registered our server in Talkdesk as a **custom MCP server**: a URL (ending in the MCP path used by `server.py`) plus a **bearer token** header. Talkdesk lists the tools it finds there, and the team attaches them as skills.
- **Keep the existing transport, path and auth exactly** as in `server.py`. If you add tools, the team presses "Test connection" / refresh in Talkdesk and the new tools appear.
- Talkdesk reads each tool's **name, description and input schema**. These are effectively part of the prompt:
  - Names: `snake_case`, verb first, stable forever once mapped.
  - Description: 1–3 sentences: what it does, when to use it, what it needs, and what not to use it for.
  - Inputs: **flat** (no nested objects), mostly strings, each with a description that states the format, e.g. `date: "Appointment date as YYYY-MM-DD (Asia/Kolkata)"`. Mark optional inputs optional.
  - Accept messy input and normalise it on the server: phone `98450 12345`, `+91-9845012345`, `9845012345` → `+919845012345`; dates `2026-11-04`, `4 Nov`, `tomorrow`, `Wednesday`; times `10:30`, `10:30 AM`, `10.30am`.
- **Results**: return the standard envelope (see `05_AGENTS_AND_TOOLS.md`). Never raise an exception to Talkdesk; a raised error gives the agent nothing useful to say. Return `ok: false` with an `error_code` and a speakable `message`.
- **Speed**: Talkdesk waits for our reply inside the patient's turn. Every millisecond is user-visible. See `08_LATENCY.md`.
- `get_weekday_for_date_internal` appeared in the V1 trace. Find out whether it is one of our tools in `server.py`. If it is, keep it working, but also return the resolved date + weekday from every date-taking tool so agents rarely need it.

## The web chat widget (built into our website)
Talkdesk provides a JS snippet (Chat Widget V2). We embed it on every website page:
```html
<script>
  var webchat;
  (function (window, document, node, props, configs) {
    if (window.TalkdeskChatSDK) { return; }
    var div = document.createElement("div"); div.id = node; document.body.appendChild(div);
    var script = document.createElement("script");
    script.src = "https://talkdeskchatsdk.talkdeskapp.com/v2/talkdeskchatsdk.js";
    script.async = true;
    script.onload = function () {
      webchat = TalkdeskChatSDK(node, props);
      webchat.init(configs);
      // after login, pass context (see below)
    };
    document.head.appendChild(script);
  })(window, document, "tdWebchat",
     { touchpointId: window.CARELINE_CONFIG.touchpointId, accountId: "", region: window.CARELINE_CONFIG.region },
     { enableEmoji: false, enableAttachments: false, enableResponsiveLayout: true,
       styles: { chatTitle: "CareLine Assistant", chatSubtitle: "Bookings, reports, insurance" } });
</script>
```
- `touchpointId` and `region` come from config (env var → injected into `/config.js`). The team creates the touchpoint in Talkdesk later; until then show the widget area with a "chat coming soon" placeholder when the ID is empty.
- Methods available: `webchat.open()`, `webchat.close()`, `webchat.reset()` (call on logout), `webchat.end()`, `webchat.setContextParam({...})` (flat key/values only).
- Events: `webchat.onOpenWebchat`, `onConversationStart`, `onConversationEnded`, `onCloseWebchat`.
- After login, call `webchat.setContextParam({ patient_name, patient_phone, td_contact_person_identification: patient_phone })` on `onConversationStart` and `onOpenWebchat`. This shows in the human agent's Context card. **This data is set by the browser and can be spoofed**, so the agents still verify phone + DOB through `verify_patient`. Never put the Supabase JWT in the context.
- On `onOpenWebchat`, the website also calls our `POST /api/session/warm` (authenticated). This is our only real "session start" signal and triggers async prefetch (`07_CONTEXT_BLACKBOARD.md`).
- CSP: if we set a Content-Security-Policy header, allow `https://talkdeskchatsdk.talkdeskapp.com` (script, style, frame) and the region API host (e.g. `https://api.talkdeskapp.com`) in `connect-src`.

## Voice
- The team gets a phone number (from organisers), creates an Agentic Autopilot for the V2 orchestration, and builds a Studio voice flow: Incoming Call → Connect to Autopilot Voice → (escalation) Assignment and Dial.
- Our implications: tool `message` must be speakable; keep lists to 3 items; read booking IDs in a speakable form (e.g. `CL-4821` spoken as "C L 4 8 2 1") by also returning `booking_id_spoken`.
- The caller ID may reach the agent as a variable; we cannot rely on it. Phone + DOB verification stays the rule.

## Talkdesk REST APIs (optional, P2)
With an OAuth client (Client Credentials, `POST https://{account}.talkdeskid.com/oauth/token` — confirm the exact token URL in the OAuth client screen), the backend could call: Contacts API (upsert a patient as a Talkdesk contact), Callback API (request a callback), Flows API (start a Studio flow with an "API request" trigger). Build a `talkdesk_client.py` stub behind `TALKDESK_ENABLED=false`. Do not block anything on it. SMS via Messages API needs a dedicated number and is unlikely in the sandbox: SMS/WhatsApp stay **simulated** in our outbox.

## What is real vs simulated (be honest in the UI)
| Channel | Status |
|---|---|
| Web chat with AI agents | Real (Talkdesk) |
| Voice with AI agents | Real if the team gets a number |
| Human handoff in Conversations | Real (Talkdesk) |
| Email (confirmations, reports, offers) | Real (our SMTP) |
| SMS, WhatsApp, reminder calls | Simulated: written to `notifications` with `status='simulated'`, shown on dashboard as such |

## Things you must not assume
- No webhook from Talkdesk to us at conversation start or end.
- No transcript feed into our backend. Memory comes from our own tool logs and the `save_interaction_note` tool.
- No parallel agent execution.
- Tool results are only seen by the agent that called the tool, which then reports up to the Receptionist. Keep `message` complete and self-contained.
