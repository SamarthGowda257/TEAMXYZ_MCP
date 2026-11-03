import { useEffect, useState } from "react";
import { Activity, ArrowDown, ArrowRight, Bot, Database, Globe, Layers, Lock, MessageCircle, PhoneCall, Radio, Server, ShieldCheck,
  Zap } from "lucide-react";
import { PageHero } from "./Public";

type Health = { db_kind: string; db: boolean; blackboard: string; events: string; email: string; version: string };

function Status({ label, value, good }: { label: string; value: string; good: boolean }) {
  return <div className={good ? "st st-ok" : "st st-warn"}><span className="st-dot" aria-hidden="true" /><div><strong>{label}</strong><span>{value}</span></div></div>;
}

const LAYERS = [
  { icon: MessageCircle, title: "Patients", items: ["Website chat (Talkdesk widget)", "Phone (Talkdesk voice)", "Website and patient portal"] },
  { icon: Bot, title: "Talkdesk AI Agent Platform", items: ["Receptionist supervisor: emergencies first, routing", "8 specialist agents, max 5 skills each", "Human handoff to Talkdesk Conversations"] },
  { icon: Lock, title: "WellNest MCP gateway (/mcp)", items: ["34 tools over Streamable HTTP", "Bearer token, constant-time check, rate limits", "Every reply: ok + speakable message + small data"] },
  { icon: Server, title: "Services (one set of rules)", items: ["Same code for bot, website and jobs", "Identity: phone + date of birth checked on the server", "Waitlist auto-offer, coverage, reports, memory"] },
];

const SIDE = [
  { icon: Layers, title: "Blackboard (Redis)", text: "Shared working memory: P0 live facts, P1 patient snapshot, P2 profile, P3 memory digest, plus a context registry (READY / LOADING / MISSING). Facts reach agents inside normal tool replies: zero extra hops." },
  { icon: Radio, title: "Event stream (Redis Streams)", text: "Every booking, cancellation and verification is an event. Workers preload context, refresh caches, send notifications and keep analytics. Acks, retries and a dead-letter stream." },
  { icon: Database, title: "Supabase Postgres", text: "Source of truth. A unique index makes double booking impossible; Row Level Security closes the public API; an outbox keeps emails consistent with bookings." },
];

const PROOF = [
  { v: "1 of 50", l: "patients won the race for the same slot; 49 told it was taken, 0 double bookings" },
  { v: "30 / 30", l: "acceptance checks over the real MCP connection, on Postgres and Redis, on every code push" },
  { v: "0 errors", l: "in 600 tool calls from 25 simultaneous patients" },
  { v: "< 30 ms", l: "typical server time per tool call on its own (measured on the test server)" },
];

const SCALE = [
  ["One FastAPI service on Render, one worker", "Several API instances behind a load balancer; blackboard already shared through Redis"],
  ["Workers run inside the web service", "Separate worker services (same code, no changes)"],
  ["Redis Streams event backbone", "Kafka, behind the same publish interface, when several services need the events"],
  ["Keyword search over conversation notes", "Hybrid search with pgvector embeddings in the same Supabase database"],
  ["Email by SMTP; SMS, WhatsApp and reminder calls simulated", "Talkdesk SMS and outbound voice, WhatsApp Business API"],
  ["Demo hospital data", "Integration with the hospital's HIS / EHR, lab (LIS) and billing systems"],
];

export function Architecture() {
  const [h, setH] = useState<Health | null>(null);
  useEffect(() => {
    document.title = "How it works · WellNest Hospitals";
    fetch("/health").then((r) => r.json()).then(setH).catch(() => {});
  }, []);
  return (
    <>
      <PageHero crumb="How it works" title="How WellNest works"
        lead="An AI front desk built on Talkdesk. Patients talk; Talkdesk's agents understand and route; our server does the work safely and remembers." />
      <div className="wrap page arch">
        <section aria-labelledby="live-h">
          <h2 id="live-h" className="sub-title">Running right now</h2>
          <div className="st-row">
            <Status label="Server" value={h ? `online · v${h.version}` : "checking…"} good={!!h} />
            <Status label="Database" value={h ? (h.db_kind === "postgres" ? "Supabase Postgres" : "local fallback") : "…"} good={h?.db_kind === "postgres"} />
            <Status label="Blackboard" value={h ? (h.blackboard === "connected" ? "Redis connected" : h.blackboard) : "…"} good={h?.blackboard === "connected"} />
            <Status label="Events" value={h ? h.events : "…"} good={h?.events === "redis-streams"} />
            <Status label="Email" value={h ? (h.email === "smtp" ? "sending" : "simulated") : "…"} good={h?.email === "smtp"} />
          </div>
        </section>

        <section aria-labelledby="flow-h">
          <h2 id="flow-h" className="sub-title">One request, end to end</h2>
          <div className="arch-flow">
            <div className="arch-main">
              {LAYERS.map((l, i) => (
                <div key={l.title}>
                  <div className="arch-box">
                    <span className="arch-ic"><l.icon size={22} aria-hidden="true" /></span>
                    <div><h3>{l.title}</h3><ul>{l.items.map((x) => <li key={x}>{x}</li>)}</ul></div>
                  </div>
                  {i < LAYERS.length - 1 && <div className="arch-arrow" aria-hidden="true"><ArrowDown size={20} /></div>}
                </div>
              ))}
            </div>
            <div className="arch-side">
              <div className="arch-side-label"><ArrowRight size={18} aria-hidden="true" /> services read and write</div>
              {SIDE.map((s) => (
                <div key={s.title} className="arch-box side"><span className="arch-ic"><s.icon size={22} aria-hidden="true" /></span>
                  <div><h3>{s.title}</h3><p>{s.text}</p></div></div>
              ))}
            </div>
          </div>
          <p className="arch-note"><Zap size={16} aria-hidden="true" /> Design rule: Talkdesk runs agents one after another and each step costs about 1–2 seconds, so tools answer common combined questions in one call (slots come with the doctors' days, fees and rooms) and context travels inside replies instead of extra tool calls.</p>
        </section>

        <section aria-labelledby="proof-h">
          <h2 id="proof-h" className="sub-title">Tested, not assumed</h2>
          <div className="proof-grid">{PROOF.map((p) => <div key={p.v} className="proof"><strong className="serif">{p.v}</strong><span>{p.l}</span></div>)}</div>
        </section>

        <section aria-labelledby="safe-h" className="two-col">
          <div>
            <h2 id="safe-h" className="sub-title">Safety and privacy</h2>
            <ul className="check-list">
              {["Phone + date of birth verified on the server before any record or change; 5 wrong tries lock the number for 15 minutes",
                "Emergency words lead to a 108 message and an urgent human handoff, never to booking",
                "No medical advice; department suggestions only, with a disclaimer",
                "Lab values never sent by email, only a secure portal link",
                "No phone numbers stored in Redis (keyed hashes); phones masked in logs",
                "Row Level Security on every table; secrets only in environment variables"].map((x) => (
                <li key={x}><ShieldCheck size={20} aria-hidden="true" /> {x}</li>))}
            </ul>
          </div>
          <div>
            <h2 className="sub-title">Built today → next at scale</h2>
            <table className="ins-table">
              <thead><tr><th scope="col">Today</th><th scope="col">At hospital scale</th></tr></thead>
              <tbody>{SCALE.map(([a, b]) => <tr key={a}><td>{a}</td><td>{b}</td></tr>)}</tbody>
            </table>
          </div>
        </section>

        <section className="arch-foot">
          <Globe size={18} aria-hidden="true" /> <span>Stack: Talkdesk AI Agent Platform · Python MCP SDK 2.x (Streamable HTTP) · FastAPI · Supabase Postgres · Redis (Render Key Value) · React · Render. All on free tiers.</span>
          <Activity size={18} aria-hidden="true" /> <span>Live operations dashboard for staff at /dashboard.</span>
          <PhoneCall size={18} aria-hidden="true" /> <span>Patients reach the same assistant by chat or phone.</span>
        </section>
      </div>
    </>
  );
}
