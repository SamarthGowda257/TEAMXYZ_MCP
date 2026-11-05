import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import {
  BookOpen, Building2, CalendarDays, ExternalLink, FlaskConical, LayoutDashboard, LifeBuoy, LogOut,
  MessagesSquare, PhoneOutgoing, RefreshCw, ShieldCheck, Stethoscope, Users,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import { Mark } from "../components/Site";
import { Chip, Empty, Loading, Panel, statusKind, useOps } from "./adminKit";
import { AdminDepartments, AdminDoctors, AdminInsurance, AdminKnowledge, AdminTests } from "./AdminHospital";

/* The admin console reads the ops API with the signed admin cookie. It is a context and tracking screen:
   the human's actual replies happen in Talkdesk Conversations, which is where Talkdesk routes the chat. */

const TALKDESK_CONVERSATIONS = "https://pesit-hackathon.mytalkdesk.com/atlas/apps/conversations";

/* ---------------------------------------------------------------- overview */
function Overview() {
  const sum = useOps<any>("/api/ops/summary", 20000);
  const hand = useOps<any>("/api/ops/handoffs", 20000);
  const conv = useOps<any>("/api/ops/conversations?limit=60");

  const s = sum.data?.summary;
  const kpis = [
    { label: "Bookings today", value: s?.bookings_today, sub: `${s?.upcoming_bookings ?? "–"} upcoming in total` },
    { label: "Conversations handled", value: conv.data?.total, sub: Object.entries(conv.data?.by_channel || {}).map(([k, v]) => `${v} ${k}`).join(" · ") || "chat and voice" },
    { label: "Escalations waiting", value: hand.data?.counts?.open, sub: `${hand.data?.open_urgent ?? 0} marked urgent`, urgent: !!hand.data?.counts?.open },
    { label: "Slots refilled from waitlist", value: s?.refilled_from_waitlist, sub: `${s?.open_offers ?? 0} offers still open` },
  ];

  return (
    <>
      <div className="ad-kpis">
        {kpis.map((k) => (
          <div key={k.label} className={k.urgent ? "ad-kpi ad-kpi-urgent" : "ad-kpi"}>
            <span className="ad-kpi-label">{k.label}</span>
            <strong className="ad-kpi-value">{k.value ?? "–"}</strong>
            <span className="ad-kpi-sub">{k.sub}</span>
          </div>
        ))}
      </div>

      <div className="ad-two">
        <Panel title="OPD fill today">
          {sum.loading ? <Loading /> : !sum.data?.schedule?.length ? (
            <Empty title="No clinics today" hint="Department fill appears here once doctors have slots on this date." />
          ) : (
            <ul className="ad-bars">
              {sum.data.schedule.map((d: any) => {
                const pct = d.capacity ? Math.round((d.booked / d.capacity) * 100) : 0;
                return (
                  <li key={d.department}>
                    <span className="ad-bar-name">{d.department}</span>
                    <span className="ad-bar-track"><i style={{ width: `${Math.min(pct, 100)}%` }} /></span>
                    <span className="ad-bar-num">{d.booked}/{d.capacity}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Needs a person now">
          {hand.loading ? <Loading rows={3} /> : !hand.data?.handoffs?.filter((h: any) => h.status === "open").length ? (
            <Empty title="Nobody is waiting" hint="Every conversation is being handled by WellNest AI right now." />
          ) : (
            <ul className="ad-queue">
              {hand.data.handoffs.filter((h: any) => h.status === "open").slice(0, 6).map((h: any) => (
                <li key={h.handoff_code}>
                  <Chip kind={h.priority === "urgent" ? "urgent" : "live"}>{h.priority}</Chip>
                  <div><strong>{h.full_name || "Caller"}</strong><p>{h.summary}</p></div>
                  <code className="ad-code">{h.handoff_code}</code>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="System">
        <dl className="ad-facts">
          <div><dt>Database</dt><dd>{sum.data?.db ?? "–"}</dd></div>
          <div><dt>Email</dt><dd>{sum.data?.email_mode ?? "–"}</dd></div>
          <div><dt>Registered patients</dt><dd>{s?.patients ?? "–"}</dd></div>
          <div><dt>Open nurse alerts</dt><dd>{s?.nurse_alerts_open ?? "–"}</dd></div>
          <div><dt>Messages simulated today</dt><dd>{s?.messages_simulated ?? "–"}</dd></div>
          <div><dt>As of</dt><dd>{sum.data?.date} {sum.data?.now}</dd></div>
        </dl>
      </Panel>
    </>
  );
}

/* ---------------------------------------------------------------- escalations */
function Escalations() {
  const { data, loading, error, reload } = useOps<any>("/api/ops/handoffs", 4000);
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seen = useRef<Set<string>>(new Set());
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    const open = (data?.handoffs || []).filter((h: any) => h.status === "open");
    const fresh = open.filter((h: any) => !seen.current.has(h.handoff_code));
    if (seen.current.size && fresh.length) { setFlash(true); window.setTimeout(() => setFlash(false), 1800); }
    open.forEach((h: any) => seen.current.add(h.handoff_code));
  }, [data]);

  const list = (data?.handoffs || []) as any[];
  const open = list.filter((h) => h.status === "open" || h.status === "assigned");
  const current = list.find((h) => h.handoff_code === picked) || open[0] || null;

  const setStatus = async (code: string, status: string) => {
    setBusy(true);
    try { await api(`/api/ops/handoffs/${code}/status`, { method: "POST", body: { status } }); reload(); }
    catch { /* the list reload will show the truth */ }
    finally { setBusy(false); }
  };

  return (
    <div className={flash ? "ad-escal ad-flash" : "ad-escal"}>
      <div className="ad-escal-list">
        <div className="ad-panel-head">
          <h2>Queue <span className="ad-count">{open.length}</span></h2>
          <button type="button" className="ad-icon" onClick={reload} title="Refresh now"><RefreshCw size={16} aria-hidden="true" /></button>
        </div>
        {loading ? <Loading /> : error ? <Empty title="Could not load the queue" hint={error} /> : !open.length ? (
          <Empty title="Queue is clear" hint="When a patient asks for a person, or the AI hits an emergency, the ticket lands here within seconds." />
        ) : (
          <ul className="ad-tickets">
            {open.sort((a, b) => (a.priority === "urgent" ? -1 : 1) - (b.priority === "urgent" ? -1 : 1)).map((h) => (
              <li key={h.handoff_code}>
                <button type="button" className={current?.handoff_code === h.handoff_code ? "is-on" : ""} onClick={() => setPicked(h.handoff_code)}>
                  <span className="ad-ticket-top">
                    <Chip kind={h.priority === "urgent" ? "urgent" : "live"}>{h.priority}</Chip>
                    <code className="ad-code">{h.handoff_code}</code>
                  </span>
                  <strong>{h.full_name || "Caller"}</strong>
                  <p>{h.summary}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="ad-escal-detail">
        {!current ? (
          <Empty title="No ticket selected" hint="Pick a ticket from the queue to see the patient's context." />
        ) : (
          <>
            <div className="ad-panel-head">
              <h2>{current.full_name || "Caller"}</h2>
              <Chip kind={statusKind(current.status)}>{current.status.replace("_", " ")}</Chip>
            </div>
            <dl className="ad-facts">
              <div><dt>Ticket</dt><dd><code className="ad-code">{current.handoff_code}</code></dd></div>
              <div><dt>Priority</dt><dd>{current.priority}</dd></div>
              <div><dt>Reason</dt><dd>{current.reason_code || "—"}</dd></div>
              <div><dt>Phone</dt><dd>{current.phone || "—"}</dd></div>
              <div><dt>Patient file</dt><dd>{current.patient_code || "not registered"}</dd></div>
              <div><dt>Raised</dt><dd>{current.created_at ? new Date(current.created_at).toLocaleString("en-IN") : "—"}</dd></div>
              {current.assigned_to && <div><dt>Taken by</dt><dd>{current.assigned_to}</dd></div>}
            </dl>
            <div className="ad-summary">
              <h3>What the AI passed on</h3>
              <p>{current.summary}</p>
            </div>
            <p className="ad-note">
              Reply to the patient in Talkdesk Conversations — that is where Talkdesk routes the chat or call.
              This screen is the context beside it.
            </p>
            <div className="ad-actions">
              <a className="btn btn-primary btn-sm" href={TALKDESK_CONVERSATIONS} target="_blank" rel="noreferrer">
                <ExternalLink size={16} aria-hidden="true" /> Open in Talkdesk
              </a>
              <button type="button" className="btn btn-quiet btn-sm" disabled={busy || current.status === "assigned"}
                      onClick={() => setStatus(current.handoff_code, "assigned")}>Mark in progress</button>
              <button type="button" className="btn btn-quiet btn-sm" disabled={busy}
                      onClick={() => setStatus(current.handoff_code, "closed")}>Resolve</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- appointments */
function Appointments() {
  const [status, setStatus] = useState("");
  const { data, loading, error } = useOps<any>(`/api/ops/appointments?limit=150${status ? `&status=${status}` : ""}`);
  const rows = (data?.appointments || []) as any[];
  return (
    <Panel title="Appointments" action={
      <div className="ad-filters">
        {["", "booked", "completed", "cancelled"].map((s) => (
          <button key={s || "all"} type="button" className={status === s ? "is-on" : ""} onClick={() => setStatus(s)}>
            {s || "All"}
          </button>
        ))}
      </div>
    }>
      {loading ? <Loading rows={8} /> : error ? <Empty title="Could not load appointments" hint={error} /> : !rows.length ? (
        <Empty title="No appointments match" hint="Try a different status filter." />
      ) : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Booking</th><th>Patient</th><th>Doctor</th><th>When</th><th>Channel</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.booking_code}>
                  <td><code className="ad-code">{a.booking_code}</code></td>
                  <td>{a.full_name}<span className="ad-sub">{a.phone}</span></td>
                  <td>{a.doctor || "—"}<span className="ad-sub">{a.room || ""}</span></td>
                  <td>{a.date_label}<span className="ad-sub">{a.time_label}</span></td>
                  <td><Chip kind="plain">{a.channel}</Chip></td>
                  <td><Chip kind={statusKind(a.status)}>{a.status}</Chip></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/* ---------------------------------------------------------------- conversations */
function Conversations() {
  const { data, loading, error } = useOps<any>("/api/ops/conversations?limit=100");
  const [openId, setOpenId] = useState<number | null>(null);
  const detail = useOps<any>(openId ? `/api/ops/conversations/${openId}` : "/api/ops/conversations?limit=1");
  const rows = (data?.conversations || []) as any[];

  return (
    <div className="ad-two ad-two-wide">
      <Panel title="Conversations">
        {loading ? <Loading rows={8} /> : error ? <Empty title="Could not load conversations" hint={error} /> : !rows.length ? (
          <Empty title="No conversations recorded yet" hint="The AI saves a short note when a conversation changes something. Run a chat or a call and it appears here." />
        ) : (
          <div className="ad-table-wrap">
            <table className="ad-table">
              <thead><tr><th>Patient</th><th>Channel</th><th>What happened</th><th>Outcome</th><th>When</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className={openId === r.id ? "is-on" : ""} onClick={() => setOpenId(r.id)}>
                    <td>{r.full_name || "Caller"}<span className="ad-sub">{r.phone}</span></td>
                    <td><Chip kind="plain">{r.channel || "chat"}</Chip></td>
                    <td className="ad-wrap-cell">{r.summary}{r.escalated && <> <Chip kind="urgent">escalated</Chip></>}</td>
                    <td>{r.outcome || "—"}</td>
                    <td>{r.created_at ? new Date(r.created_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Activity">
        {!openId ? (
          <Empty title="Pick a conversation" hint="Its recorded actions appear here as a timeline." />
        ) : detail.loading ? <Loading rows={4} /> : (
          <>
            <p className="ad-summary-line">{detail.data?.conversation?.summary}</p>
            <ul className="ad-timeline">
              {(detail.data?.timeline || []).map((t: any, i: number) => (
                <li key={i}>
                  <Chip kind={t.kind === "handoff" ? "urgent" : "live"}>{t.kind}</Chip>
                  <div>
                    <strong>{t.kind === "handoff" ? t.summary : `${t.status} · ${t.doctor || "procedure"} · ${t.when}`}</strong>
                    <span className="ad-sub"><code className="ad-code">{t.code}</code>{t.channel ? ` · ${t.channel}` : ""}</span>
                  </div>
                </li>
              ))}
              {!(detail.data?.timeline || []).length && <li className="ad-sub">No recorded actions for this patient.</li>}
            </ul>
            <p className="ad-note">{detail.data?.note}</p>
          </>
        )}
      </Panel>
    </div>
  );
}

/* ---------------------------------------------------------------- reminders */
function Reminders() {
  const { data, loading, error, reload } = useOps<any>("/api/ops/outbound?limit=60");
  const calls = (data?.calls || []) as any[];
  return (
    <Panel title="Outbound reminders and follow-ups" action={
      <button type="button" className="ad-icon" onClick={reload} title="Refresh"><RefreshCw size={16} aria-hidden="true" /></button>
    }>
      <p className="ad-note">
        Mode: <strong>{data?.mode || "—"}</strong>
        {data?.missing_settings?.length ? ` · waiting on ${data.missing_settings.join(", ")}` : ""}
        {" · "}calling hours {data?.calling_hours_ist || "—"} IST
      </p>
      {loading ? <Loading rows={6} /> : error ? <Empty title="Could not load the call queue" hint={error} /> : !calls.length ? (
        <Empty title="No calls queued" hint="Reminder and post-visit calls appear here once appointments fall inside the reminder window." />
      ) : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Call</th><th>Kind</th><th>Due</th><th>Status</th><th>Outcome</th></tr></thead>
            <tbody>
              {calls.map((c) => (
                <tr key={c.call_id}>
                  <td><code className="ad-code">{c.call_id}</code></td>
                  <td>{String(c.kind || "").replace(/_/g, " ")}</td>
                  <td>{c.due_at || "—"}</td>
                  <td><Chip kind={c.status === "completed" ? "ok" : c.status === "failed" ? "urgent" : "live"}>{c.status}</Chip></td>
                  <td>{c.outcome || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/* ---------------------------------------------------------------- patients */
function Patients() {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const { data, loading, error } = useOps<any>(`/api/ops/patients?limit=80${term ? `&q=${encodeURIComponent(term)}` : ""}`);
  const rows = (data?.patients || []) as any[];
  return (
    <Panel title="Patients" action={
      <form className="ad-search" onSubmit={(e) => { e.preventDefault(); setTerm(q); }}>
        <label className="sr-only" htmlFor="pq">Search patients</label>
        <input id="pq" className="input" placeholder="Name or phone" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn btn-quiet btn-sm" type="submit">Search</button>
      </form>
    }>
      {loading ? <Loading rows={8} /> : error ? <Empty title="Could not load patients" hint={error} /> : !rows.length ? (
        <Empty title="No patients match" hint="Try a different name or phone number." />
      ) : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Patient</th><th>Phone</th><th>Language</th><th>Caregiver</th><th>Visits</th></tr></thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td>{p.full_name}<span className="ad-sub">{p.patient_code}</span></td>
                  <td>{p.phone}</td>
                  <td>{p.preferred_language || "—"}</td>
                  <td>{p.caregiver_name || "—"}</td>
                  <td>{p.appointments}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/* ---------------------------------------------------------------- login + shell */
export function AdminLogin({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await api("/api/admin/login", { method: "POST", body: { username, password } }); onDone(); }
    catch (e2) { setErr(e2 instanceof ApiError ? e2.message : "Could not sign in."); }
    finally { setBusy(false); }
  };

  return (
    <div className="ad-login">
      <form className="ad-login-card" onSubmit={submit}>
        <Mark size={44} />
        <h1>WellNest staff console</h1>
        <p className="ad-login-sub">Sign in to see appointments, conversations and the human-handoff queue.</p>
        <div className="field">
          <label htmlFor="au">Admin ID</label>
          <input id="au" className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="ap">Password</label>
          <input id="ap" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {err && <p className="error-text">{err}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="ad-login-note">Patients sign in on the main site. This console is for hospital staff.</p>
      </form>
    </div>
  );
}

const NAV = [
  { to: "/admin", end: true, label: "Overview", icon: LayoutDashboard },
  { to: "/admin/escalations", label: "Escalations", icon: LifeBuoy },
  { to: "/admin/appointments", label: "Appointments", icon: CalendarDays },
  { to: "/admin/conversations", label: "Conversations", icon: MessagesSquare },
  { to: "/admin/reminders", label: "Reminders", icon: PhoneOutgoing },
  { to: "/admin/patients", label: "Patients", icon: Users },
];

const REF_NAV = [
  { to: "/admin/doctors", label: "Doctors", icon: Stethoscope },
  { to: "/admin/departments", label: "Departments", icon: Building2 },
  { to: "/admin/tests", label: "Tests & scans", icon: FlaskConical },
  { to: "/admin/insurance", label: "Insurance", icon: ShieldCheck },
  { to: "/admin/knowledge", label: "Knowledge base", icon: BookOpen },
];

export function Admin() {
  const [who, setWho] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const nav = useNavigate();

  const check = useCallback(async () => {
    try { const r = await api<any>("/api/admin/me"); setWho(r.user); }
    catch { setWho(null); }
    finally { setChecked(true); }
  }, []);
  useEffect(() => { check(); document.title = "Staff console — WellNest Hospitals"; }, [check]);

  const out = async () => {
    try { await api("/api/admin/logout", { method: "POST" }); } catch { /* cookie may already be gone */ }
    setWho(null); nav("/admin");
  };

  if (!checked) return <div className="ad-boot"><Loading rows={3} /></div>;
  if (!who) return <AdminLogin onDone={check} />;

  return (
    <div className="ad-shell">
      <aside className="ad-side">
        <div className="ad-brand"><Mark size={30} /><span>WellNest<small>Staff console</small></span></div>
        <nav aria-label="Admin">
          <p className="ad-nav-h">Operations</p>
          {NAV.map(({ to, end, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={end}><Icon size={18} aria-hidden="true" /> {label}</NavLink>
          ))}
          <p className="ad-nav-h">The hospital</p>
          {REF_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}><Icon size={18} aria-hidden="true" /> {label}</NavLink>
          ))}
        </nav>
        <a className="ad-side-out" href={TALKDESK_CONVERSATIONS} target="_blank" rel="noreferrer">
          <ExternalLink size={16} aria-hidden="true" /> Talkdesk Conversations
        </a>
      </aside>
      <div className="ad-main">
        <header className="ad-top">
          <span className="ad-live"><i /> Live</span>
          <span className="ad-who">{who}</span>
          <button type="button" className="btn btn-quiet btn-sm" onClick={out}><LogOut size={15} aria-hidden="true" /> Sign out</button>
        </header>
        <div className="ad-body">
          <Routes>
            <Route index element={<Overview />} />
            <Route path="escalations" element={<Escalations />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="conversations" element={<Conversations />} />
            <Route path="reminders" element={<Reminders />} />
            <Route path="patients" element={<Patients />} />
            <Route path="doctors" element={<AdminDoctors />} />
            <Route path="departments" element={<AdminDepartments />} />
            <Route path="tests" element={<AdminTests />} />
            <Route path="insurance" element={<AdminInsurance />} />
            <Route path="knowledge" element={<AdminKnowledge />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
