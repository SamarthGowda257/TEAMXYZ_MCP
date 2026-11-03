import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Pill } from "../components/Bits";
import { Mark } from "../components/Site";
import { session } from "../lib/api";

type Summary = { date: string; now: string; email_mode: string; db: string;
  summary: Record<string, number>; schedule: { department: string; booked: number; capacity: number }[] };
type Feed = { activity: any[]; offers: any[]; handoffs: any[]; outbox: any[]; nurse_alerts: any[] };
type Metrics = { tools: { tool: string; count: number; errors: number; p50_ms: number; p95_ms: number }[]; p50_ms: number; p95_ms: number; total_calls: number; uptime_s: number };

const ACTION: Record<string, string> = {
  book_appointment: "Booked", cancel_appointment: "Cancelled", reschedule_appointment: "Moved", accept_waitlist_offer: "Waitlist booked",
  waitlist_offer: "Slot offered", join_waitlist: "Joined waitlist", create_handoff: "Handed to staff", email_lab_report: "Report emailed",
  request_assistance: "Help arranged", register_patient: "Registered", web_signup: "Signed up", request_callback: "Call back",
  set_patient_preferences: "Preferences", send_payment_link: "Payment link", send_caregiver_update: "Caregiver told",
  request_prescription_refill: "Refill asked", flag_nurse_alert: "Nurse alert", record_checkin: "Check-in",
};

async function get<T>(path: string, token: string): Promise<T> {
  const r = await fetch(path, { headers: { "X-Dashboard-Token": token } });
  if (r.status === 401) throw new Error("unauthorized");
  if (!r.ok) throw new Error("failed");
  return r.json();
}

export function Dashboard() {
  const [qs, setQs] = useSearchParams();
  const [token, setToken] = useState(qs.get("token") || session.opsToken() || "");
  const [bad, setBad] = useState(false);
  const [s, setS] = useState<Summary | null>(null);
  const [f, setF] = useState<Feed | null>(null);
  const [m, setM] = useState<Metrics | null>(null);
  const [stamp, setStamp] = useState("");
  const seen = useRef<Set<string>>(new Set());
  const [fresh, setFresh] = useState<Set<string>>(new Set());

  useEffect(() => { document.title = "Front desk live · WellNest"; }, []);
  useEffect(() => { if (qs.get("token")) { session.setOps(qs.get("token")); setQs({}, { replace: true }); } }, []); // eslint-disable-line

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [a, b, c] = await Promise.all([get<Summary>("/api/ops/summary", token), get<Feed>("/api/ops/feed", token), get<Metrics>("/api/metrics", token)]);
      const keys = b.activity.map((x) => `${x.day}${x.at}${x.ref}${x.action}`);
      const nu = new Set(seen.current.size ? keys.filter((k) => !seen.current.has(k)) : []);
      keys.forEach((k) => seen.current.add(k));
      setFresh(nu); setS(a); setF(b); setM(c); setBad(false); session.setOps(token);
      setStamp(new Date().toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit" }));
    } catch (e: any) { if (e.message === "unauthorized") { setBad(true); session.setOps(null); } }
  }, [token]);
  useEffect(() => { load(); const t = window.setInterval(load, 5000); return () => window.clearInterval(t); }, [load]);

  if (!token || bad) return <TokenGate bad={bad} onToken={(t) => { setBad(false); setToken(t); }} />;
  const k = s?.summary || {};
  return (
    <div className="dash">
      <header className="dash-top">
        <Link to="/" className="wordmark small"><Mark size={28} /> <span>WellNest</span></Link>
        <h1>Front desk, live</h1>
        <p className="row-sub">{s ? `${s.date} · updated ${stamp} · email ${s.email_mode}, SMS and WhatsApp simulated · ${s.db}` : "Loading…"}</p>
      </header>

      <section className="kpis" aria-label="Today">
        <div><span>Bookings today</span><strong>{k.bookings_today ?? "–"}</strong></div>
        <div><span>Cancellations today</span><strong>{k.cancellations_today ?? "–"}</strong></div>
        <div><span>Refilled from waitlist</span><strong className={k.refilled_from_waitlist ? "pos" : ""}>{k.refilled_from_waitlist ?? "–"}</strong></div>
        <div><span>Offers open</span><strong>{k.open_offers ?? "–"}</strong></div>
        <div><span>Handoffs open</span><strong className={k.urgent_handoffs_today ? "neg" : ""}>{k.open_handoffs ?? "–"}</strong>
          {k.urgent_handoffs_today ? <em>{k.urgent_handoffs_today} urgent today</em> : null}</div>
        <div><span>Tool time p95</span><strong>{m && m.total_calls ? `${Math.round(m.p95_ms)} ms` : "–"}</strong><em>{m ? `${m.total_calls} tool calls since start` : ""}</em></div>
      </section>

      <div className="dash-grid">
        <section className="panel span-2" aria-labelledby="opd-h">
          <div className="panel-top"><h2 id="opd-h" className="panel-h">OPD fill today</h2><span className="row-sub">booked of slots, by department</span></div>
          <ul className="fill">
            {s?.schedule.filter((d) => d.capacity).map((d) => {
              const pct = Math.min(100, Math.round((d.booked / d.capacity) * 100));
              return (
                <li key={d.department}>
                  <span className="fill-name">{d.department}</span>
                  <span className="fill-bar" aria-hidden="true"><i style={{ width: `${pct}%` }} className={pct >= 90 ? "full" : ""} /></span>
                  <span className="num">{d.booked}/{d.capacity}</span>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="panel span-2 row-2" aria-labelledby="act-h">
          <div className="panel-top"><h2 id="act-h" className="panel-h">Activity</h2><span className="row-sub">chat, voice and web</span></div>
          <ul className="feed">
            {f?.activity.map((a) => {
              const key = `${a.day}${a.at}${a.ref}${a.action}`;
              return (
                <li key={key + Math.random()} className={fresh.has(key) ? "flash" : ""}>
                  <span className="num feed-t">{a.at.slice(0, 5)}</span>
                  <span className={`ch ch-${a.channel}`}>{a.channel === "web" ? "Web" : a.channel === "voice" ? "Voice" : a.channel === "system" ? "Auto" : "Chat"}</span>
                  <span className="feed-what"><strong>{ACTION[a.action] || a.action}</strong> {a.patient} · {a.summary}</span>
                  {a.ref && <span className="id">{a.ref}</span>}
                </li>
              );
            })}
          </ul>
        </section>

        <section className="panel" aria-labelledby="off-h">
          <h2 id="off-h" className="panel-h">Waitlist offers</h2>
          {f?.offers.length ? <ul className="rows">{f.offers.map((o) => (
            <li key={o.code}><div><span>{o.patient} · {o.doctor}</span><span className="row-sub">{o.slot}{o.status === "open" ? ` · ${Math.ceil(o.seconds_left / 60)} min left` : ""}</span></div><Pill status={o.status} /></li>
          ))}</ul> : <p className="quiet">No offers yet today. Cancel a booking to see one appear.</p>}
        </section>

        <section className="panel" aria-labelledby="ho-h">
          <h2 id="ho-h" className="panel-h">Handoffs to staff</h2>
          {f?.handoffs.length ? <ul className="rows">{f.handoffs.map((h) => (
            <li key={h.code} className={h.priority === "urgent" && h.status === "open" ? "is-urgent" : ""}>
              <div><span>{h.summary}</span><span className="row-sub">{h.at} · {h.phone || "no number"}</span></div><Pill status={h.priority === "urgent" ? "urgent" : h.status} /></li>
          ))}</ul> : <p className="quiet">None open.</p>}
        </section>

        <section className="panel" aria-labelledby="ob-h">
          <h2 id="ob-h" className="panel-h">Outbox</h2>
          <ul className="rows">{f?.outbox.map((n, i) => (
            <li key={i}><div><span>{n.template.replace(/_/g, " ")}</span><span className="row-sub">{n.channel === "voice_call" ? "reminder call" : n.channel} to {n.to} · {n.at}</span></div><Pill status={n.status} /></li>
          ))}</ul>
        </section>

        <section className="panel" aria-labelledby="lat-h">
          <div className="panel-top"><h2 id="lat-h" className="panel-h">Tool latency</h2><span className="row-sub">server time</span></div>
          {m?.tools.length ? (
            <table className="table compact">
              <thead><tr><th scope="col">Tool</th><th scope="col" className="num">Calls</th><th scope="col" className="num">p50</th><th scope="col" className="num">p95</th></tr></thead>
              <tbody>{m.tools.slice(0, 10).map((t) => <tr key={t.tool}><th scope="row">{t.tool}</th><td className="num">{t.count}</td><td className="num">{t.p50_ms} ms</td><td className="num">{t.p95_ms} ms</td></tr>)}</tbody>
            </table>
          ) : <p className="quiet">No tool calls since the server started.</p>}
          {f?.nurse_alerts.length ? <p className="note note-bad">{f.nurse_alerts.length} nurse alert open: {f.nurse_alerts[0].reason}</p> : null}
        </section>
      </div>
    </div>
  );
}

function TokenGate({ bad, onToken }: { bad: boolean; onToken: (t: string) => void }) {
  const [v, setV] = useState("");
  const submit = (e: FormEvent) => { e.preventDefault(); if (v.trim()) onToken(v.trim()); };
  return (
    <div className="accept">
      <form className="accept-card" onSubmit={submit}>
        <h1>Front desk, live</h1>
        <p>Enter the dashboard token. It's kept in this browser only.</p>
        <div className="field"><label htmlFor="tk">Dashboard token</label><input id="tk" className="input" type="password" value={v} onChange={(e) => setV(e.target.value)} autoComplete="off" /></div>
        {bad && <p className="error-text" role="alert">That token didn't work.</p>}
        <button className="btn btn-primary token-shape">Open dashboard</button>
      </form>
    </div>
  );
}

export function Pay() {
  const [qs] = useSearchParams();
  useEffect(() => { document.title = "Pay a bill · WellNest"; }, []);
  return (
    <div className="accept">
      <div className="accept-card">
        <h1>Pay bill {qs.get("bill") || ""}</h1>
        <p>This is a hackathon demo, so no payment is taken here. In a real deployment this page would hand over to the hospital's payment gateway. WellNest never asks for card details by chat or phone.</p>
        <Link className="btn btn-primary token-shape" to="/portal">Back to My WellNest</Link>
      </div>
    </div>
  );
}
