# 🏥 Talkdesk Hackathon: The Simple Guide

> **Event:** Talkdesk AI Hackday, Wed 4 Nov 2026, 9 AM to 4 PM, PESU-52, RR Campus
> **Briefings:** Mon 2 Nov and Tue 3 Nov (the real problem statement comes here)
> **Sandbox:** https://pesit-hackathon.mytalkdesk.com

This guide explains everything in plain language, using one example the whole way through: **an AI receptionist for a hospital.**

---

## Part 1: The 5 things you must understand first

### 1. What is Talkdesk?
Talkdesk is software for **customer support call centres**. When you call your bank and hear *"Press 1 for cards…"* or an AI voice answers, that's software like Talkdesk.

Talkdesk sells **AI bots that answer customer calls**. At this hackathon, they want to see what **you** can build with their AI tools.

### 2. What is the sandbox?
A **practice copy of Talkdesk** where nothing real is at stake. It's a fully working account with no real customers. Think of it like a **driving-school car**: a real car, but mistakes don't matter.

### 3. Why can I see other teams' stuff?
Every team logs in with its **own login**, but all teams share **one account**. It works like a **shared Google Drive folder**: everyone sees every file.

So there are two rules:
- ✅ Always put your team name in what you create: `ClinicBot_TeamX`
- ❌ Never edit or delete anything without your team name. Audit logs record who did what.

### 4. What is our job?
**Build an AI bot inside Talkdesk that solves a real customer-support problem, then show it working to the judges.**

The exact topic gets announced at the 2 Nov briefing. This guide uses "hospital" as the practice example.

### 5. Do we need to code?
**Mostly no, but code gives you an edge.**

| Part | How it's built | Required? |
|---|---|---|
| The AI bot (agents, instructions, routing) | Clicking and typing in Talkdesk's website | ✅ Yes, this is the main thing |
| A backend that gives the bot real abilities (book a slot, check a record) | Your own code (Python/FastAPI/MCP) in VS Code or Claude Code | ⭐ Optional, but makes you stand out |
| A customer website | Not needed, because customers **call** and **Talkdesk is the frontend** | ❌ Skip |

---

## Part 2: The big picture in one diagram

```
👤 Patient calls the hospital's number
        │
        ▼
🔀 STUDIO FLOW                     "What happens when someone calls"
        │
        ▼
🎙️ AUTOPILOT (made in AI Launchpad)  "Gives the bot a voice"
        │
        ▼
🤖 AI AGENT PLATFORM                "The bot's brain"
     Receptionist (boss agent, the only one who talks to the patient)
        ├── Booking Agent  → uses a "skill" → 💻 YOUR CODE (book slot)
        ├── Info Agent     → answers timings, departments, address
        └── Emergency Agent → transfers to a human
        │
        ▼
👩 If the bot can't help → transferred to a human agent (Conversations app)
```

**Remember this order:** Bot brain → Voice → Call path → Phone number.

---

## Part 3: The sidebar in plain words

| Sidebar item | Plain meaning | Use it? |
|---|---|---|
| **AI Agent Platform** | Where you build the bot's brain | ⭐⭐⭐ Main tool |
| **Studio** | Drag-and-drop "what happens on a call" designer. Also has **Reference hub** (simple data tables) | ⭐⭐⭐ |
| **Admin → AI Launchpad** | Turns your bot into a voice bot ("Autopilot") | ⭐⭐⭐ |
| **Automation Flows** | "When X happens → do Y" workflows | ⭐⭐ |
| **Builder** | Connects Talkdesk to outside code (OAuth Clients, Integrations) | ⭐⭐ |
| **Workspace Designer** | Builds info cards shown to a *human* agent during a call | ⭐ Only for "help the human agent" ideas |
| **Interaction Analytics / Live / Explore** | Reports and dashboards | 👀 Look only |
| **Conversations** | The human agent's phone/chat screen | 👀 For the handoff demo |
| **Contacts / Voicemails / Activities** | Address book, voicemail inbox, history | 👀 Look only |
| **Admin (everything else)** | Account-wide settings that affect **all teams** | ❌ Don't touch |
| **AppConnect** (grid icon, bottom) | Talkdesk's "app store" of other companies' add-ons | ❌ Don't install. Good for ideas only |

---

## Part 4: What the sandbox has right now (checked 30 Oct)

The sandbox is **brand new and almost empty**. Every team starts from zero.

- 0 bots, 0 Studio flows, 0 Autopilots, 0 automations
- ⚠️ **0 phone numbers**, so **nobody can call in yet.** The organisers have to provide numbers. Ask them.
- ✅ **MCP Servers** page exists, so you can plug your own code in
- ✅ **Agentic Autopilot** can be created in AI Launchpad, so voice bots are possible
- ✅ **Agent Evaluation** and **Agent Observability** exist for testing bot quality and showing analytics to judges
- The ~15 "+91" contacts are **real students' phones** from test calls. Don't call or edit them.

### ⚠️ Your login has admin power, so be careful
| ✅ Safe to create (with team name) | 👀 Look only | ❌ Never touch |
|---|---|---|
| AI Agent Platform bots and MCP servers | Explore reports | **Admin → Numbers → "Buy number"** (real money!) |
| AI Launchpad Autopilot | Interaction Analytics | Admin → Customization, Preferences, Holiday Hours |
| Studio flows | Live dashboards | Admin → Channels, Queues, Recording, Subscription |
| Studio → Reference hub tables | Governance | Dialing out from Conversations |
| Automation Flows, Workspace Designer cards | | Anything with another team's name |

---

## Part 5: 🏥 Full hackathon walkthrough with the hospital example

### The problem (example)
> *"City Hospital gets 500 calls a day just to book appointments. The receptionists are overloaded. Build an AI receptionist."*

### The final demo we want
A judge calls the number:

> 🤖 **Bot:** "Hello, welcome to City Hospital. How can I help you today?"
> 👤 **Judge:** "I want to see a skin doctor tomorrow."
> 🤖 **Bot:** "Sure! Dr. Mehta from Dermatology is free at 10:30 AM or 3 PM. Which works for you?"
> 👤 **Judge:** "10:30."
> 🤖 **Bot:** "May I have your name?" → "Ravi." → "Done, Ravi. You're booked with Dr. Mehta tomorrow at 10:30 AM."
> 👤 **Judge:** "Actually I have bad chest pain right now."
> 🤖 **Bot:** "That sounds urgent. I'm connecting you to our staff immediately." *(transfers to a human)*

---

### STEP 1: Plan the agents (on paper, 15 min)

| Agent | Job | Talks to patient? |
|---|---|---|
| **Receptionist** (Supervisor) | Greets, understands what the patient wants, sends work to the right agent | ✅ Yes, the ONLY one |
| **Booking Agent** | Finds free slots and books them | ❌ Reports back to Receptionist |
| **Info Agent** | Visiting hours, departments, address, insurance | ❌ |
| **Emergency Agent** | Spots emergencies and asks for transfer to a human | ❌ |

> 💡 **Key rule:** Only the top agent (Supervisor) speaks to the customer. Child agents report back to their parent. Siblings can't talk to each other.

**Limits:** max 3 levels deep, 10 agents per level, 5 skills per agent.

---

### STEP 2: Build the bot's brain (AI Agent Platform)

1. Click **AI Agent Platform** → **Create Agent Orchestration** (or **+ New Orchestration**).
2. Name it `CityHospital_TeamX`.
3. You'll see a canvas with **one AI Agent node**. This is the **Receptionist (Supervisor)**.
4. Fill in its fields:

   **Name:** `Receptionist`
   **Description** (what it is, NOT how to behave):
   ```
   Front-desk receptionist for City Hospital that handles all patient calls.
   ```
   **Instructions** (how to behave, i.e. the prompt):
   ```
   You are the friendly receptionist of City Hospital, Bengaluru.
   - Greet the caller warmly and ask how you can help.
   - If they want to book, change or cancel an appointment → use Booking Agent.
   - If they ask about timings, departments, location or insurance → use Info Agent.
   - If they mention chest pain, breathing trouble, heavy bleeding, unconsciousness
     or any emergency → use Emergency Agent IMMEDIATELY.
   - Keep replies short (1–2 sentences). This is a phone call.
   - Never give medical advice or diagnoses.
   - Always confirm details (name, doctor, date, time) before finishing.
   ```

5. Add **child agents** under the Receptionist (Booking, Info, Emergency). A **Conditions node** appears automatically.
6. In the **Conditions node**, write when to use each child, using their exact names:
   ```
   Emergency Agent: caller describes a medical emergency. Check this FIRST.
   Booking Agent: caller wants to book, reschedule or cancel an appointment.
   Info Agent: caller asks general questions about the hospital.
   ```
7. Fill in each child agent's Name, Description and Instructions the same way.

   Example **Info Agent → Instructions**:
   ```
   Answer questions about City Hospital using ONLY these facts:
   - OPD timings: Mon–Sat, 9 AM – 5 PM. Sunday closed.
   - Departments: General Medicine, Dermatology, Cardiology, Orthopaedics, Paediatrics.
   - Address: 12 MG Road, Bengaluru.
   - Insurance: Star Health, HDFC Ergo, ICICI Lombard accepted.
   If the answer isn't here, say you'll connect them to staff.
   ```

> 💡 **Writing good instructions IS the main skill of this hackathon.** Treat them like code: be specific, list rules, give examples.

---

### STEP 3: Test it by chatting (no phone needed!)

1. Click **Test** on your orchestration.
2. Type like a patient: *"I want to see a skin doctor tomorrow."*
3. Check that it went to the right agent and that the reply was short and correct.
4. Try tricky cases:
   - *"I have chest pain"* → should go to Emergency
   - *"What's your address?"* → should go to Info
   - *"Do you sell pizza?"* → should politely say no
   - Talk in Hindi or Kannada → see what happens
5. Fix the instructions and test again. **You'll spend most of your time in this loop.**
6. When it's good, click **Publish**. Only published bots can become voice bots.

---

### STEP 4: Give the bot real abilities (skills)

Right now the Booking Agent only *pretends* to book. To make it **actually** book, give it a **skill** (a tool it can use).

There are 3 types of skill:

| Skill type | What it is | Code needed? |
|---|---|---|
| **Workflow** | Visual drag-and-drop logic inside Talkdesk | ❌ No |
| **Integration** | Calls an outside API | Little |
| **MCP** | Connects to **your own server** that has tools like `book_appointment` | ✅ Yes, this is our edge |

#### Option A, no code: Reference hub table
**Studio → Reference hub → Create table** → `Doctors_TeamX`:

| doctor | department | slot | booked |
|---|---|---|---|
| Dr. Mehta | Dermatology | 2026-11-05 10:30 | no |
| Dr. Mehta | Dermatology | 2026-11-05 15:00 | no |
| Dr. Rao | Cardiology | 2026-11-05 11:00 | no |

The bot can read this data through workflow skills.

#### Option B, our own code: an MCP server ⭐
We write a small Python server (Claude Code can help) with tools like:
```
find_slots(department, date)                → list of free slots
book_appointment(name, phone, doctor, slot) → booking ID
cancel_appointment(booking_id)              → done / not found
```
Then:
1. Run it and give it a public URL (ngrok on a laptop, or Render/Railway).
2. In Talkdesk: **AI Agent Platform → MCP Servers → + New MCP Server** → **Custom** → paste the URL → add a secret token → **Test connection**. Name it `MCP_TeamX`.
3. Open your orchestration → **Booking Agent** → **+ Add Skill** → **MCP** → pick your server → pick ONE tool (1 skill = 1 tool) → give it a clear name and description → **Save**.
4. Add more skills for the other tools.
5. **Test** again. Now the bot really books, and the booking shows up in your database.

> ⚠️ MCP rules: the server must use **Streamable HTTP**, have a **public URL**, and use a **Bearer token or OAuth2** for security.

---

### STEP 5: Turn it into a voice bot (AI Launchpad)

1. **Admin → AI Launchpad → AI Resources**
2. Under **Agentic Autopilot models** → **Create new**
3. Fill in:
   - Name: `Autopilot_TeamX`
   - Service provider: **Talkdesk**
   - AI Agent Orchestration: **CityHospital_TeamX** (must be published)
4. **Create AI Model**

---

### STEP 6: Design what happens on a call (Studio)

1. **Studio → Flows → Create flow** → name it `HospitalFlow_TeamX`
2. Build this path:
   ```
   📞 Incoming Call
        ▼
   🤖 Connect to Autopilot Voice → choose Autopilot_TeamX
        ▼ (bot says it needs a human)
   👩 Assignment and Dial → sends the call to a human agent
   ```
3. Publish the flow.

---

### STEP 7: Connect a phone number and call 📞

⚠️ **The sandbox has no numbers right now.** On the day, the organisers will tell you which number to use. Then:
1. The number gets pointed at `HospitalFlow_TeamX`
2. Call it from your phone
3. Talk to your bot 🎉

**Until then, test everything using the chat Test button (Step 3).**

---

### STEP 8: Show off in the demo

| Show this | Where |
|---|---|
| Live call with the bot | Your phone, on speaker |
| The booking appearing in your database | Your backend / a simple dashboard |
| Emergency → human transfer | Conversations app on a teammate's laptop |
| Bot quality scores | AI Agent Platform → **Agent Evaluation** |
| Conversation analytics | AI Agent Platform → **Agent Observability** |

**A judge-winning story has 4 parts:**
1. **Problem:** "Hospitals waste X hours on booking calls"
2. **Live demo:** a call that actually books something real
3. **Smart handling:** emergency detection, multi-language, confirmations
4. **Impact:** "This saves receptionists Y hours a day"

---

## Part 6: Team plan (3 people)

| Person | Before 4 Nov | On the day |
|---|---|---|
| **A: Bot builder** | Learn AI Agent Platform, build TestBot, master the instructions | Builds all agents, instructions and testing |
| **B: Backend** | Build a starter MCP server, test connecting it | Builds the real tools for the problem, hosts them |
| **C: Flow + demo** | Learn Studio, AI Launchpad, Reference hub | Voice setup, Studio flow, slides, demo script |

---

## Part 7: Before-Monday checklist

- [ ] Everyone logs in and clicks every sidebar item (**look, don't change Admin**)
- [ ] Build `TestBot_TeamX` (Receptionist + 2 child agents) and chat with it in **Test**
- [ ] Make a `Doctors_TeamX` table in Studio → Reference hub
- [ ] Get a hello-world MCP server connected as `MCP_TeamX`
- [ ] Shortlist 2–3 ideas (hospital, bank, food delivery, college admissions…)
- [ ] Questions for the briefing:
  - What exactly is the problem statement?
  - How will it be judged?
  - Is our own code / MCP server allowed?
  - **Which phone number does each team use? The sandbox has none.**
  - Is there a usage limit on AI or calls?

---

## Part 8: Mini dictionary

| Word | Meaning |
|---|---|
| **Sandbox** | Practice copy of Talkdesk, shared by all teams |
| **Orchestration** | One complete bot made of several agents |
| **Supervisor** | The top agent, the only one that talks to the customer |
| **Action Agent** | A child agent that does one job using skills |
| **Conditions node** | Rules for which child agent handles what |
| **Skill** | A tool an agent can use (workflow, integration or MCP) |
| **MCP server** | Your own small server that gives the bot tools |
| **Autopilot** | Your bot turned into a voice/chat virtual agent |
| **AI Launchpad** | Admin page where you create the Autopilot |
| **Studio flow** | The call path: what happens step by step when someone calls |
| **Reference hub** | Simple data tables inside Studio |
| **Queue** | A group of human agents who receive transferred calls |
| **Contact** | A caller saved in the address book |
| **Publish** | Make your bot or flow "live" so other parts can use it |
| **AppConnect** | Talkdesk's app store of add-ons from other companies |

---

## Useful links
- AI Agent Platform help: https://support.talkdesk.com/hc/en-us/sections/39090037609883-Talkdesk-AI-Agent-Platform
- Core concepts (agents, skills, hierarchy): https://support.talkdesk.com/hc/en-us/articles/39100265145371-AI-Agent-Platform-Core-Concepts
- MCP skill setup: https://support.talkdesk.com/hc/en-us/articles/46063702440475-AI-Agent-Platform-Build-Skill-MCP
- Create an Agentic Autopilot: https://support.talkdesk.com/hc/en-us/articles/40273031755675-Creating-an-Agentic-Autopilot-in-AI-Launchpad
- Studio: Connect to Autopilot Voice: https://studio.talkdesk.com/docs/connect-to-autopilot-voice
- Developer docs (give this to Claude Code): https://docs.talkdesk.com/llms.txt

*Note: exact button names may differ slightly in the sandbox. If you can't find one, look for a similar "Create / New / +" button on that page.*
