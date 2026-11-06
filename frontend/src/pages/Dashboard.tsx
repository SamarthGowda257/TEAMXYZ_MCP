import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertTriangle, CalendarDays, CircleDot, Gauge, LayoutGrid,
  MessageSquare, PhoneOutgoing, RefreshCw, Search, Users,
} from "lucide-react";
import { Mark } from "../components/Site";
import { rupees, session } from "../lib/api";

/* ------------------------------------------------------------------ types */
type Summary = {
  date: string; now: string; email_mode?: string; db?: string;
  summary: Record<string, number>;
  schedule: { department: string; booked: number; capacity: number }[];
};
type Feed = {
  activity: { day: string; at: string; action: string; patient: string; summary: string; ref: string; channel: string }[];
  offers: { code: string; patient: string; doctor: string; slot: string; status: string; seconds_left: number }[];
  handoffs: { code: string; summary: string; at: string; phone: string; priority: string; status: string }[];
  outbox: { template: string; channel: string; to: string; at: string; status: string }[];
  nurse_alerts: { reason: string }[];
};
type Metrics = {
  tools: { tool: string; count: number; errors: number; p50_ms: number; p95_ms: number }[];
  p50_ms: number; p95_ms: number; total_calls: number; uptime_s: number;
};
type Appts = { total: number; appointments: {
  booking_code: string; status: string; channel: string; full_name: string; phone: string;
  doctor: string; room: string; date_label: string; time_label: string; reason: string }[] };
type Handoffs = { counts: Record<string, number>; open_urgent: number; handoffs: {
  handoff_code: string; priority: string; reason_code: string; summary: string; status: string;
  assigned_to: string | null; created_at: string; phone: string; full_name: string }[] };
type Convos = { total: number; by_channel: Record<string, number>; conversations: {
  id: number; channel: string; summary: string; topics: string; outcome: string;
  created_at: string; phone: string; full_name: string; escalated: boolean }[] };
type Patients = { total: number; patients: {
  id: number; patient_code: string; full_name: string; phone: string; email: string;
  preferred_language: string; caregiver_name: string | null; appointments: number }[] };
type Outbound = { mode: string; test_number: string | null; calls: {
  call_id: string; kind: string; patient: string; to: string; status: string;
  attempts: number; outcome: string | null; updated: string }[] };
type SystemInfo = {
  blackboard: { backend: string; patients_in_memory: number; cache_hit_rate: number | null; hits: number; misses: number };
  events: { backend: string; published: number; processed: number; failed: number; dead_lettered: number;
            lag_ms_last: number; worker_alive: boolean; pending?: number; dlq_length?: number };
};

const ACTION: Record<string, string> = {
  book_appointment: "Booked", cancel_appointment: "Cancelled", reschedule_appointment: "Moved",
  accept_waitlist_offer: "Waitlist booked", waitlist_offer: "Slot offered", join_waitlist: "Joined waitlist",
  create_handoff: "Escalated", email_lab_report: "Report emailed", request_assistance: "Help arranged",
  register_patient: "Registered", web_signup: "Signed up", request_callback: "Call back",
  set_patient_preferences: "Preferences", send_payment_link: "Payment link",
  send_caregiver_update: "Caregiver told", request_prescription_refill: "Refill asked",
  flag_nurse_alert: "Nurse alert", record_checkin: "Check-in", outbound_call: "Outbound call",
};

/* ------------------------------------------------------------------ data */
function useOps<T>(path: string | null, token: string, everyMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<"auth" | "fail" | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!path || !token) return;
    try {
      const r = await fetch(path, { headers: { "X-Dashboard-Token": token } });
      if (r.status === 401) { setErr("auth"); return; }
      if (!r.ok) { setErr("fail"); setLoading(false); return; }
      setData(await r.json()); setErr(null);
    } catch { setErr("fail"); } finally { setLoading(false); }
  }, [path, token]);

  useEffect(() => {
    load();
    if (!everyMs) return;
    const t = window.setInterval(load, everyMs);
    return () => window.clearInterval(t);
  }, [load, everyMs]);

  return { data, err, loading, reload: load };
}

/* ------------------------------------------------------------------ small parts */
function Pill({ status, children }: { status: string; children?: ReactNode }) {
  const kind =
    ["cancelled", "no_show", "failed", "expired", "superseded"].includes(status) ? "off"
    : ["completed", "closed", "sent", "accepted", "resolved", "booked"].includes(status) ? "ok"
    : ["urgent", "alert"].includes(status) ? "bad"
    : ["assigned", "dialing", "in_progress", "retry"].includes(status) ? "work"
    : "live";
  return <span className={`dpill dpill-${kind}`}>{children || status.replace(/_/g, " ")}</span>;
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
}) {
  const id = `f-${label.replace(/\s/g, "-").toLowerCase()}`;
  return (
    <div className="dfilter">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

function Empty({ title, hint }: { title: string; hint: string }) {
  return <div className="dempty"><strong>{title}</strong><p>{hint}</p></div>;
}

function Skeleton({ rows = 6 }: { rows?: number }) {
  return <div className="dskel" aria-hidden="true">{Array.from({ length: rows }, (_, i) => <i key={i} />)}</div>;
}

/** Inline SVG column chart. No charting library: DESIGN.md keeps the admin dependency-free. */
function Columns({ data }: { data: { label: string; value: number; of: number }[] }) {
  if (!data.length) return null;
  return (
    <div className="dcols" role="img" aria-label={data.map((d) => `${d.label} ${d.value} of ${d.of}`).join("; ")}>
      {data.map((d) => {
        const pct = d.of ? Math.round((d.value / d.of) * 100) : 0;
        return (
          <div key={d.label} className="dcol">
            <div className="dcol-track">
              <div className={`dcol-fill${pct >= 85 ? " is-full" : ""}`} style={{ height: `${Math.max(pct, 2)}%` }} />
            </div>
            <span className="dcol-val num">{d.value}</span>
            <span className="dcol-lab">{d.label.length > 11 ? `${d.label.slice(0, 10)}…` : d.label}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ views */
function Today({ token }: { token: string }) {
  const { data: s } = useOps<Summary>("/api/ops/summary", token, 10000);
  const { data: f } = useOps<Feed>("/api/ops/feed", token, 10000);
  const { data: m } = useOps<Metrics>("/api/metrics", token, 10000);
  const [channel, setChannel] = useState("all");

  const k = s?.summary || {};
  const activity = (f?.activity || []).filter((a) => channel === "all" || a.channel === channel);
  const sched = (s?.schedule || []).filter((d) => d.capacity).map((d) => ({ label: d.department, value: d.booked, of: d.capacity }));

  const kpis = [
    { label: "Bookings today", value: k.bookings_today, note: `${k.upcoming_bookings ?? 0} upcoming in all` },
    { label: "Cancellations", value: k.cancellations_today, note: "freed slots go to the waitlist" },
    { label: "Refilled from waitlist", value: k.refilled_from_waitlist, note: "cancelled slots saved", good: true },
    { label: "Offers open", value: k.open_offers, note: "waiting for an answer" },
    { label: "Escalations open", value: k.open_handoffs, note: k.urgent_handoffs_today ? `${k.urgent_handoffs_today} urgent today` : "none urgent", bad: !!k.urgent_handoffs_today },
    { label: "Tool time p95", value: m?.total_calls ? `${Math.round(m.p95_ms)} ms` : "—", note: m?.total_calls ? `${m.total_calls} calls since restart` : "no tool calls yet" },
  ];

  return (
    <>
      <ul className="dkpis">
        {kpis.map((x) => (
          <li key={x.label}>
            <span>{x.label}</span>
            <strong className={`num${x.bad ? " is-bad" : x.good && Number(x.value) > 0 ? " is-good" : ""}`}>
              {x.value ?? "—"}
            </strong>
            <em>{x.note}</em>
          </li>
        ))}
      </ul>

      <div className="dgrid">
        <section className="dpanel dspan2">
          <header><h2>OPD fill today</h2><span>booked of available slots, by department</span></header>
          {sched.length ? <Columns data={sched} /> : <Skeleton rows={3} />}
        </section>

        <section className="dpanel dspan2">
          <header>
            <h2>Activity</h2>
            <Select label="Channel" value={channel} onChange={setChannel}
              options={[["all", "All channels"], ["chat", "Chat"], ["voice", "Voice"], ["web", "Web"], ["system", "Automatic"]]} />
          </header>
          {activity.length ? (
            <ul className="dfeed">
              {activity.slice(0, 14).map((a, i) => (
                <li key={`${a.day}${a.at}${a.ref}${i}`}>
                  {/* the date matters: without it yesterday's 17:20 reads as out of order */}
                  <time className="num" dateTime={`${a.day}T${a.at}`}>
                    <b>{a.at.slice(0, 5)}</b>
                    <span>{new Date(a.day).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
                  </time>
                  <span className={`dch dch-${a.channel}`}>{a.channel}</span>
                  <p><strong>{ACTION[a.action] || a.action.replace(/_/g, " ")}</strong> {a.patient} · {a.summary}</p>
                  {a.ref && <span className="code">{a.ref}</span>}
                </li>
              ))}
            </ul>
          ) : <Empty title="Nothing on this channel yet" hint="Switch the filter, or make a booking in chat to see it land here." />}
        </section>

        <section className="dpanel">
          <header><h2>Waitlist offers</h2></header>
          {f?.offers.length ? (
            <ul className="drows">
              {f.offers.map((o) => (
                <li key={o.code}>
                  <div><strong>{o.patient}</strong><span>{o.doctor} · {o.slot}</span></div>
                  <Pill status={o.status}>
                    {o.status === "open" ? `${Math.ceil(o.seconds_left / 60)} min left` : o.status}
                  </Pill>
                </li>
              ))}
            </ul>
          ) : <Empty title="No offers out right now" hint="When a booking is cancelled the freed slot is offered here within seconds." />}
        </section>

        <section className="dpanel">
          <header><h2>Outbox</h2><span>email real, SMS and WhatsApp simulated</span></header>
          {f?.outbox.length ? (
            <ul className="drows">
              {f.outbox.slice(0, 7).map((n, i) => (
                <li key={i}>
                  <div>
                    <strong>{n.template.replace(/_/g, " ")}</strong>
                    <span>{n.channel === "voice_call" ? "reminder call" : n.channel} to {n.to} · {n.at}</span>
                  </div>
                  <Pill status={n.status} />
                </li>
              ))}
            </ul>
          ) : <Empty title="Outbox is clear" hint="Confirmations and reminders appear here as they are queued." />}
        </section>
      </div>
    </>
  );
}

function Escalations({ token }: { token: string }) {
  const [status, setStatus] = useState("");
  const { data, loading } = useOps<Handoffs>(`/api/ops/handoffs?limit=120${status ? `&status=${status}` : ""}`, token, 10000);
  return (
    <>
      <div className="dbar">
        <Select label="Status" value={status} onChange={setStatus}
          options={[["", "All"], ["open", "Open"], ["assigned", "Assigned"], ["closed", "Closed"]]} />
        <p className="dcount">
          {data ? `${data.counts.open || 0} open · ${data.counts.assigned || 0} assigned · ${data.counts.closed || 0} closed` : ""}
        </p>
      </div>
      {loading ? <Skeleton /> : data?.handoffs.length ? (
        <div className="dtable-wrap">
          <table className="dtable">
            <thead><tr><th>Reference</th><th>Priority</th><th>Why</th><th>Patient</th><th>Assigned</th><th>Status</th></tr></thead>
            <tbody>
              {data.handoffs.map((h) => (
                <tr key={h.handoff_code} className={h.priority === "urgent" && h.status === "open" ? "is-urgent" : ""}>
                  <th scope="row" className="code">{h.handoff_code}</th>
                  <td><Pill status={h.priority === "urgent" ? "urgent" : "normal"} /></td>
                  <td className="dwide">{h.summary}<small>{h.reason_code?.replace(/_/g, " ")}</small></td>
                  <td>{h.full_name || "—"}<small className="num">{h.phone}</small></td>
                  <td>{h.assigned_to || <span className="dmuted">unassigned</span>}</td>
                  <td><Pill status={h.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty title="No escalations match this filter" hint="Urgent handoffs from the AI land here the moment they are raised." />}
    </>
  );
}

function AppointmentsView({ token }: { token: string }) {
  const [status, setStatus] = useState("");
  const [day, setDay] = useState("");
  const q = `/api/ops/appointments?limit=150${status ? `&status=${status}` : ""}${day ? `&day=${day}` : ""}`;
  const { data, loading } = useOps<Appts>(q, token);
  return (
    <>
      <div className="dbar">
        <Select label="Status" value={status} onChange={setStatus}
          options={[["", "All"], ["booked", "Booked"], ["completed", "Completed"], ["cancelled", "Cancelled"], ["no_show", "No show"]]} />
        <Select label="Day" value={day} onChange={setDay}
          options={[["", "Any day"], ["today", "Today"], ["tomorrow", "Tomorrow"]]} />
        <p className="dcount">{data ? `${data.total} shown` : ""}</p>
      </div>
      {loading ? <Skeleton /> : data?.appointments.length ? (
        <div className="dtable-wrap">
          <table className="dtable">
            <thead><tr><th>Booking</th><th>When</th><th>Patient</th><th>Doctor</th><th>Room</th><th>Via</th><th>Status</th></tr></thead>
            <tbody>
              {data.appointments.map((a) => (
                <tr key={a.booking_code}>
                  <th scope="row" className="code">{a.booking_code}</th>
                  <td>{a.date_label}<small className="num">{a.time_label}</small></td>
                  <td>{a.full_name}<small className="num">{a.phone}</small></td>
                  <td>{a.doctor}{a.reason && <small>{a.reason}</small>}</td>
                  <td className="num">{a.room}</td>
                  <td><span className={`dch dch-${a.channel}`}>{a.channel}</span></td>
                  <td><Pill status={a.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty title="No appointments match" hint="Try a different status or day." />}
    </>
  );
}

function Calls({ token }: { token: string }) {
  const [kind, setKind] = useState("");
  const { data, loading } = useOps<Outbound>("/api/ops/outbound?limit=60", token, 15000);
  const rows = (data?.calls || []).filter((c) => !kind || c.kind === kind);
  return (
    <>
      <div className="dbar">
        <Select label="Reason" value={kind} onChange={setKind}
          options={[["", "All calls"], ["appointment_reminder", "Reminder"], ["post_visit_followup", "Follow-up"],
                    ["waitlist_offer", "Waitlist offer"], ["lab_report_ready", "Report ready"]]} />
        {data && (
          <p className="dcount">
            Mode <strong>{data.mode}</strong>
            {data.mode === "simulated" && " — no real calls are placed"}
            {data.test_number && <> · every call routed to <span className="num">{data.test_number}</span></>}
          </p>
        )}
      </div>
      {loading ? <Skeleton /> : rows.length ? (
        <div className="dtable-wrap">
          <table className="dtable">
            <thead><tr><th>Call</th><th>Reason</th><th>Patient</th><th>To</th><th>Tries</th><th>Outcome</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.call_id}>
                  <th scope="row" className="code">{c.call_id}</th>
                  <td>{c.kind.replace(/_/g, " ")}</td>
                  <td>{c.patient}</td>
                  <td className="num">{c.to}</td>
                  <td className="num">{c.attempts}</td>
                  <td>{c.outcome?.replace(/_/g, " ") || <span className="dmuted">—</span>}<small>{c.updated}</small></td>
                  <td><Pill status={c.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty title="No calls of this kind" hint="Outbound calls are planned by the jobs runner every minute." />}
    </>
  );
}

function Conversations({ token }: { token: string }) {
  const [channel, setChannel] = useState("");
  const { data, loading } = useOps<Convos>(`/api/ops/conversations?limit=80${channel ? `&channel=${channel}` : ""}`, token);
  return (
    <>
      <div className="dbar">
        <Select label="Channel" value={channel} onChange={setChannel}
          options={[["", "All channels"], ["chat", "Chat"], ["voice", "Voice"], ["web", "Web"]]} />
        <p className="dcount">
          {data && Object.entries(data.by_channel).map(([c, n]) => `${n} ${c}`).join(" · ")}
        </p>
      </div>
      {loading ? <Skeleton /> : data?.conversations.length ? (
        <ul className="dconvos">
          {data.conversations.map((c) => (
            <li key={c.id}>
              <span className={`dch dch-${c.channel}`}>{c.channel}</span>
              <div>
                <p>{c.summary}</p>
                <small>
                  {c.full_name} · <span className="num">{c.phone}</span>
                  {c.topics && <> · {c.topics.split(",").map((t) => <em key={t}>{t.trim()}</em>)}</>}
                </small>
              </div>
              {c.escalated ? <Pill status="urgent">escalated</Pill> : <Pill status={c.outcome || "resolved"} />}
            </li>
          ))}
        </ul>
      ) : <Empty title="No conversations yet" hint="Every chat and call the AI handles is summarised here." />}
    </>
  );
}

function PatientsView({ token }: { token: string }) {
  const [raw, setRaw] = useState("");
  const [q, setQ] = useState("");
  const { data, loading } = useOps<Patients>(`/api/ops/patients?limit=80${q ? `&q=${encodeURIComponent(q)}` : ""}`, token);
  const submit = (e: FormEvent) => { e.preventDefault(); setQ(raw.trim()); };
  return (
    <>
      <div className="dbar">
        <form className="dsearch" onSubmit={submit} role="search">
          <label htmlFor="pq" className="sr-only">Search patients by name or number</label>
          <Search size={17} aria-hidden="true" />
          <input id="pq" value={raw} onChange={(e) => setRaw(e.target.value)} placeholder="Name or mobile number" />
          <button className="btn btn-sm btn-primary">Search</button>
        </form>
        <p className="dcount">{data ? `${data.total} shown` : ""}</p>
      </div>
      {loading ? <Skeleton /> : data?.patients.length ? (
        <div className="dtable-wrap">
          <table className="dtable">
            <thead><tr><th>Patient</th><th>Mobile</th><th>Language</th><th>Caregiver</th><th>Visits</th></tr></thead>
            <tbody>
              {data.patients.map((p) => (
                <tr key={p.id}>
                  <th scope="row">{p.full_name}<small className="code">{p.patient_code}</small></th>
                  <td className="num">{p.phone}</td>
                  <td>{p.preferred_language}</td>
                  <td>{p.caregiver_name || <span className="dmuted">none on file</span>}</td>
                  <td className="num">{p.appointments}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty title="No patients match" hint="Search by name or the last digits of a mobile number." />}
    </>
  );
}

function System({ token }: { token: string }) {
  const { data: sys } = useOps<SystemInfo>("/api/ops/system", token, 15000);
  const { data: m } = useOps<Metrics>("/api/metrics", token, 10000);
  return (
    <>
      <ul className="dkpis">
        <li><span>Context cache hit rate</span>
          <strong className="num">{sys?.blackboard.cache_hit_rate != null ? `${Math.round(sys.blackboard.cache_hit_rate * 100)}%` : "—"}</strong>
          <em>{sys ? `${sys.blackboard.hits} hits · ${sys.blackboard.misses} misses` : "warming up"}</em></li>
        <li><span>Patients in working memory</span><strong className="num">{sys?.blackboard.patients_in_memory ?? "—"}</strong>
          <em>{sys?.blackboard.backend === "connected" ? "Redis" : sys?.blackboard.backend || ""}</em></li>
        <li><span>Events processed</span><strong className="num">{sys?.events.processed ?? "—"}</strong>
          <em>{sys ? `of ${sys.events.published} · lag ${sys.events.lag_ms_last} ms` : ""}</em></li>
        <li><span>Pending / dead-lettered</span>
          <strong className={`num${sys && (sys.events.dead_lettered || sys.events.failed) ? " is-bad" : ""}`}>
            {sys ? `${sys.events.pending ?? 0} / ${sys.events.dlq_length ?? sys.events.dead_lettered}` : "—"}
          </strong>
          <em>{sys?.events.worker_alive ? "workers running" : "workers stalled"}</em></li>
      </ul>

      <section className="dpanel">
        <header><h2>Tool latency</h2><span>server time, per MCP tool</span></header>
        {m?.tools.length ? (
          <div className="dtable-wrap">
            <table className="dtable">
              <thead><tr><th>Tool</th><th className="num">Calls</th><th className="num">Errors</th><th className="num">p50</th><th className="num">p95</th></tr></thead>
              <tbody>
                {m.tools.slice(0, 14).map((t) => (
                  <tr key={t.tool}>
                    <th scope="row" className="code">{t.tool}</th>
                    <td className="num">{t.count}</td>
                    <td className={`num${t.errors ? " is-bad" : ""}`}>{t.errors}</td>
                    <td className="num">{t.p50_ms} ms</td>
                    <td className="num">{t.p95_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No tool calls since the server started"
            hint="Latency appears as soon as a Talkdesk agent calls a tool. This is a cold counter, not an error."
          />
        )}
      </section>
    </>
  );
}

/* ------------------------------------------------------------------ shell */
const VIEWS = [
  { id: "today", label: "Today", Icon: LayoutGrid },
  { id: "escalations", label: "Escalations", Icon: AlertTriangle },
  { id: "appointments", label: "Appointments", Icon: CalendarDays },
  { id: "calls", label: "Outbound calls", Icon: PhoneOutgoing },
  { id: "conversations", label: "Conversations", Icon: MessageSquare },
  { id: "patients", label: "Patients", Icon: Users },
  { id: "system", label: "System", Icon: Gauge },
] as const;

export function Dashboard() {
  const [qs, setQs] = useSearchParams();
  const [token, setToken] = useState(qs.get("token") || session.opsToken() || "");
  const [bad, setBad] = useState(false);
  const [view, setView] = useState<string>(qs.get("view") || "today");
  const [stamp, setStamp] = useState("");
  const first = useRef(true);

  useEffect(() => { document.title = "Front desk, live · WellNest"; }, []);
  useEffect(() => {
    if (qs.get("token")) { session.setOps(qs.get("token")); setQs({}, { replace: true }); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const { data: s, err } = useOps<Summary>(token ? "/api/ops/summary" : null, token, 10000);
  useEffect(() => {
    if (err === "auth") { setBad(true); session.setOps(null); }
    else if (s) { setBad(false); if (first.current) { session.setOps(token); first.current = false; } }
  }, [err, s, token]);
  useEffect(() => {
    if (s) setStamp(new Date().toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit" }));
  }, [s]);

  if (!token || bad) return <TokenGate bad={bad} onToken={(t) => { setBad(false); first.current = true; setToken(t); }} />;

  const Current = useMemo(() => ({
    today: Today, escalations: Escalations, appointments: AppointmentsView,
    calls: Calls, conversations: Conversations, patients: PatientsView, system: System,
  } as Record<string, (p: { token: string }) => JSX.Element>)[view] || Today, [view]);

  return (
    <div className="dash">
      <aside className="dnav">
        <Link to="/" className="dbrand"><Mark size={30} /> <span>WellNest</span></Link>
        <nav aria-label="Dashboard sections">
          {VIEWS.map(({ id, label, Icon }) => (
            <button key={id} type="button" aria-current={view === id} onClick={() => setView(id)}>
              <Icon size={18} aria-hidden="true" /> {label}
            </button>
          ))}
        </nav>
        <p className="dnav-foot">
          Read-only. Every figure is live from the same database the AI writes to.
        </p>
      </aside>

      <div className="dmain">
        <header className="dtop">
          <div>
            <h1>Front desk, live</h1>
            <p>
              {s ? `${s.date} · ${s.db || "database"} · email ${s.email_mode || "simulated"}, SMS and WhatsApp simulated` : "Connecting…"}
            </p>
          </div>
          <p className="dstamp">
            <CircleDot size={13} aria-hidden="true" className="dlive" />
            updated <span className="num">{stamp || "—"}</span>
            <RefreshCw size={13} aria-hidden="true" /> every 10s
          </p>
        </header>
        <div className="dbody">
          <Current token={token} />
        </div>
      </div>
    </div>
  );
}

function TokenGate({ bad, onToken }: { bad: boolean; onToken: (t: string) => void }) {
  const [v, setV] = useState("");
  const submit = (e: FormEvent) => { e.preventDefault(); if (v.trim()) onToken(v.trim()); };
  return (
    <div className="dgate">
      <form className="dgate-card" onSubmit={submit}>
        <Mark size={40} />
        <h1>Front desk, live</h1>
        <p>The operations board for WellNest staff. Enter the dashboard token — it is kept in this browser only.</p>
        <div className="field">
          <label htmlFor="tk">Dashboard token</label>
          <input id="tk" className="input" type="password" value={v} autoComplete="off"
            onChange={(e) => setV(e.target.value)} />
        </div>
        {bad && <p className="error-text" role="alert">That token didn't work.</p>}
        <button className="btn btn-primary">Open dashboard</button>
      </form>
    </div>
  );
}

export function Pay() {
  const [qs] = useSearchParams();
  useEffect(() => { document.title = "Pay a bill · WellNest"; }, []);
  return (
    <div className="dgate">
      <div className="dgate-card">
        <h1>Pay bill {qs.get("bill") || ""}</h1>
        <p>
          This is a hackathon demo, so no payment is taken here. In a real deployment this page
          would hand over to the hospital's payment gateway. WellNest never asks for card details
          by chat or phone.
        </p>
        <Link className="btn btn-primary" to="/portal">Back to My WellNest</Link>
      </div>
    </div>
  );
}

export { rupees };
