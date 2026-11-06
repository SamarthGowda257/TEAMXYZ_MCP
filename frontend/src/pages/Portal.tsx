import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Accessibility, CalendarPlus, Mail, MessageCircle } from "lucide-react";
import { PortalShell } from "../components/PortalShell";
import { Empty, ErrorNote, Loading, Pill } from "../components/Bits";
import { api, istDay, longDate, rupees, shortDate, type Appointment, type Me, type Slot } from "../lib/api";
import { useApi } from "../lib/hooks";
import { openChat } from "../lib/chat";

// ------------------------------------------------------------------ overview
export function Overview() {
  return (
    <PortalShell title="Overview" actions={<Link className="btn btn-primary btn-sm token-shape" to="/portal/book"><CalendarPlus size={18} aria-hidden="true" />Book a visit</Link>}>
      {(me) => <OverviewBody me={me} />}
    </PortalShell>
  );
}

/*
  The overview is the patient's own record, set as a document rather than a board of cards:
  the next visit as a full-width ruled row (the same shape the assistant reads back on the
  phone), then the rest of the record in ruled columns beneath it.
*/
function OverviewBody({ me }: { me: Me }) {
  const appts = useApi<Appointment[]>("/api/me/appointments?scope=upcoming", [], { live: true });
  const reports = useApi<any[]>("/api/me/reports", [], { live: true });
  const wallet = useApi<{ balance_credits: number; spendable_credits: number }>("/api/me/wallet");
  const next = appts.data?.find((a) => a.status === "booked");
  const offer = me.snapshot.open_offer;
  const later = (appts.data || []).filter((a) => a.status === "booked" && a !== next).slice(0, 3);
  const recentReports = (reports.data || []).slice(0, 4);
  const pending = me.snapshot.pending_reports || 0;

  return (
    <div className="rec">
      {offer && (
        <div className="rec-offer" role="status">
          <div>
            <strong>A waitlist slot is being held for you</strong>
            <span>{offer.doctor}, {offer.date} at {offer.time}. Held until {offer.held_until}.</span>
          </div>
          <Link className="btn btn-primary btn-sm" to={`/waitlist/accept?code=${offer.offer_code}`}>Review and accept</Link>
        </div>
      )}

      {/* the next visit, as the row it actually is in the hospital register */}
      <section className="rec-next" aria-labelledby="next-h">
        <h2 id="next-h" className="rec-h">Your next visit</h2>
        {appts.loading && !appts.data ? <Loading /> : next ? (
          <>
            <dl className="rec-row">
              <div><dt>Booking</dt><dd className="code rec-id">{next.booking_id}</dd></div>
              <div><dt>With</dt><dd>{next.with}<small>{next.department}</small></dd></div>
              <div><dt>When</dt><dd className="num">{longDate(next.date_iso)}<small className="num">{next.time}</small></dd></div>
              <div><dt>Room</dt><dd className="num">{next.room}</dd></div>
              <div><dt>Fee</dt><dd className="num">{rupees(next.fee_inr)}</dd></div>
            </dl>
            <div className="rec-next-act">
              {next.assistance?.length
                ? <span className="chip chip-ok">{next.assistance.map((a) => a.replace("_", " ")).join(", ")} arranged</span>
                : null}
              <Link className="btn btn-quiet btn-sm" to="/portal/appointments">Change or cancel</Link>
              <span className="rec-spoken">Read out on the phone as “{next.booking_id_spoken}”</span>
            </div>
          </>
        ) : (
          <div className="rec-empty">
            <strong>Nothing booked yet</strong>
            <p>Book here, ask on chat, or call — all three write the same row.</p>
            <Link className="btn btn-primary btn-sm" to="/portal/book">Book a visit</Link>
          </div>
        )}
      </section>

      <div className="rec-cols">
        <section aria-labelledby="rep-h">
          <div className="rec-head">
            <h2 id="rep-h" className="rec-h">Lab reports</h2>
            <Link className="lnk-strong" to="/portal/reports">All reports</Link>
          </div>
          {reports.loading && !reports.data ? <Loading /> : recentReports.length ? (
            <ul className="rec-list">
              {recentReports.map((r) => (
                <li key={r.report_id}>
                  <Link to={`/portal/reports?open=${r.report_id}`}>
                    <span>{r.test}<small>{r.ordered}</small></span>
                    <Pill status={r.status} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : <p className="rec-quiet">No reports on file yet.</p>}
          {pending > 0 && <p className="rec-quiet">{pending} still being processed.</p>}
        </section>

        <section aria-labelledby="later-h">
          <div className="rec-head">
            <h2 id="later-h" className="rec-h">Also booked</h2>
            <Link className="lnk-strong" to="/portal/appointments">All appointments</Link>
          </div>
          {later.length ? (
            <ul className="rec-list">
              {later.map((a) => (
                <li key={a.booking_id}>
                  <Link to="/portal/appointments">
                    <span>{a.with}<small className="num">{shortDate(a.date_iso)} · {a.time}</small></span>
                    <span className="code">{a.booking_id}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : <p className="rec-quiet">Nothing else booked.</p>}
        </section>
      </div>

      <section className="rec-strip" aria-label="Wallet and pharmacy">
        <Link to="/portal/wallet">
          <span className="rec-strip-k">HealthCredits</span>
          <strong className="num">{wallet.data ? wallet.data.balance_credits.toLocaleString("en-IN") : "—"}</strong>
          <span className="rec-strip-s">Pay for visits, scans and medicines</span>
        </Link>
        <Link to="/portal/pharmacy">
          <span className="rec-strip-k">Pharmacy</span>
          <strong>Order medicines</strong>
          <span className="rec-strip-s">Delivered in about 90 minutes</span>
        </Link>
        <Link to="/portal/waitlist">
          <span className="rec-strip-k">Waitlist</span>
          <strong>{offer ? "A slot is held" : "Join a list"}</strong>
          <span className="rec-strip-s">We offer you the next cancelled slot</span>
        </Link>
      </section>

      <section className="rec-mem" aria-labelledby="mem-h">
        <h2 id="mem-h" className="rec-h">What WellNest remembers</h2>
        {me.snapshot.recent_notes?.length ? (
          <ol className="rec-notes">
            {me.snapshot.recent_notes.map((n) => <li key={n}>{n}</li>)}
          </ol>
        ) : (
          <p className="rec-quiet">
            Your conversations with the assistant are summarised here, so you never have to
            explain the same thing twice.
          </p>
        )}
        <button type="button" className="btn btn-quiet btn-sm" onClick={openChat}>
          <MessageCircle size={17} aria-hidden="true" /> Ask WellNest
        </button>
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ slot picker (shared with reschedule)
export function DateStrip({ value, onChange, days = 14 }: { value: string; onChange: (d: string) => void; days?: number }) {
  const list = Array.from({ length: days }, (_, i) => istDay(i));
  return (
    <div className="date-strip" role="radiogroup" aria-label="Date">
      {list.map((d) => {
        const dt = new Date(d + "T00:00:00");
        const sun = dt.getDay() === 0;
        return (
          <button key={d} type="button" role="radio" aria-checked={value === d} disabled={sun} onClick={() => onChange(d)}
                  aria-label={`${longDate(d)}${sun ? ", closed" : ""}`}>
            <span>{dt.toLocaleDateString("en-IN", { weekday: "short" })}</span><strong>{dt.getDate()}</strong>
          </button>
        );
      })}
    </div>
  );
}

export function SlotGrid({ slots, value, onPick }: { slots: Slot[]; value?: string; onPick: (s: Slot) => void }) {
  if (!slots.length) return <p className="quiet">No free times on this day.</p>;
  return (
    <div className="slot-grid">
      {slots.map((s) => <button key={s.time} type="button" aria-pressed={value === s.time} onClick={() => onPick(s)}>{s.label}</button>)}
    </div>
  );
}

// ------------------------------------------------------------------ appointments
export function Appointments() {
  const [scope, setScope] = useState<"upcoming" | "past">("upcoming");
  return (
    <PortalShell title="Appointments" actions={<Link className="btn btn-primary btn-sm token-shape" to="/portal/book"><CalendarPlus size={18} aria-hidden="true" />Book a visit</Link>}>
      {() => (
        <>
          <div className="tabs" role="tablist" aria-label="Which appointments">
            <button role="tab" type="button" aria-selected={scope === "upcoming"} onClick={() => setScope("upcoming")}>Upcoming</button>
            <button role="tab" type="button" aria-selected={scope === "past"} onClick={() => setScope("past")}>Past</button>
          </div>
          <ApptList scope={scope} />
        </>
      )}
    </PortalShell>
  );
}

function ApptList({ scope }: { scope: "upcoming" | "past" }) {
  const { data, loading, error, reload } = useApi<Appointment[]>(`/api/me/appointments?scope=${scope}`, [scope], { live: true });
  if (loading) return <Loading />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!data?.length) return <Empty title={scope === "upcoming" ? "No upcoming visits" : "No past visits yet"}>{scope === "upcoming" && <Link className="btn btn-primary btn-sm token-shape" to="/portal/book">Book a visit</Link>}</Empty>;
  return <ul className="appt-list">{data.map((a) => <ApptRow key={a.booking_id} a={a} onChange={reload} />)}</ul>;
}

function ApptRow({ a, onChange }: { a: Appointment; onChange: () => void }) {
  const [mode, setMode] = useState<"" | "cancel" | "move" | "help">("");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);
  const [date, setDate] = useState(a.date_iso);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [pick, setPick] = useState<Slot | null>(null);
  const active = a.status === "booked";
  useEffect(() => {
    if (mode !== "move" || a.is_procedure) return;
    setSlots(null); setPick(null);
    api<any>(`/api/slots?date=${date}&doctor=${encodeURIComponent(a.with)}`).then((r) => setSlots(r.doctors?.[0]?.slots || [])).catch(() => setSlots([]));
  }, [mode, date, a.with, a.is_procedure]);
  async function act(path: string, body: unknown) {
    setBusy(true); setMsg({});
    try { const r = await api<any>(path, { method: "POST", body }); setMsg({ ok: r.message }); setMode(""); onChange(); }
    catch (e: any) { setMsg({ err: e.message }); } finally { setBusy(false); }
  }
  return (
    <li className="appt">
      <div className="appt-main">
        <div className="appt-when"><strong>{shortDate(a.date_iso)}</strong><span>{a.time}</span></div>
        <div className="appt-what">
          <p className="appt-with">{a.with}</p>
          <p className="row-sub">{a.department} · Room {a.room} · {rupees(a.fee_inr)}</p>
          {a.assistance?.length ? <p className="row-sub"><Accessibility size={14} aria-hidden="true" /> {a.assistance.map((x) => x.replace("_", " ")).join(", ")} arranged</p> : null}
        </div>
        <div className="appt-side"><span className="id">{a.booking_id}</span><Pill status={a.status} /></div>
      </div>
      {active && !mode && (
        <div className="row appt-actions">
          <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setMode("move")}>Reschedule</button>
          <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setMode("help")}>Request help</button>
          <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setMode("cancel")}>Cancel</button>
        </div>
      )}
      {mode === "cancel" && (
        <div className="inline-confirm is-bad">
          <p>Cancel {a.with} on {shortDate(a.date_iso)} at {a.time}? The slot goes to the next patient on the waitlist.</p>
          <div className="row">
            <button type="button" className="btn btn-danger btn-sm token-shape" disabled={busy} onClick={() => act(`/api/me/appointments/${a.booking_id}/cancel`, {})}>Yes, cancel it</button>
            <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setMode("")}>Keep it</button>
          </div>
        </div>
      )}
      {mode === "move" && (
        <div className="inline-confirm">
          {a.is_procedure ? <p>To move a scan, ask WellNest by chat or call 080 4000 1234.</p> : (
            <>
              <DateStrip value={date} onChange={setDate} />
              {slots ? <SlotGrid slots={slots} value={pick?.time} onPick={setPick} /> : <Loading label="Finding times" />}
            </>
          )}
          <div className="row">
            {!a.is_procedure && <button type="button" className="btn btn-primary btn-sm token-shape" disabled={!pick || busy}
                    onClick={() => pick && act(`/api/me/appointments/${a.booking_id}/reschedule`, { date, time: pick.time })}>
              {pick ? `Move to ${shortDate(date)}, ${pick.label}` : "Choose a time"}</button>}
            <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setMode("")}>Back</button>
          </div>
        </div>
      )}
      {mode === "help" && (
        <div className="inline-confirm">
          <p>What should be ready when you arrive?</p>
          <div className="row">
            {["wheelchair", "escort", "interpreter", "transport_desk"].map((t) => (
              <button key={t} type="button" className="btn btn-quiet btn-sm token-shape" disabled={busy}
                      onClick={() => act(`/api/me/appointments/${a.booking_id}/assistance`, { type: t })}>{t.replace("_", " ")}</button>
            ))}
            <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setMode("")}>Back</button>
          </div>
        </div>
      )}
      {(msg.ok || msg.err) && <p className={msg.err ? "error-text" : "ok-text"} role="status">{msg.ok || msg.err}</p>}
    </li>
  );
}

// ------------------------------------------------------------------ reports
type Report = { report_id: string; test: string; status: string; ordered: string; ready_at: string | null; expected_at: string | null; doctor: string | null };

export function Reports() {
  return <PortalShell title="Lab reports">{() => <ReportsBody />}</PortalShell>;
}

function ReportsBody() {
  const list = useApi<Report[]>("/api/me/reports", [], { live: true });
  const initial = new URLSearchParams(window.location.search).get("open");
  const [open, setOpen] = useState<string | null>(initial);
  const detail = useApi<any>(open ? `/api/me/reports/${open}` : null, [open]);
  const [mail, setMail] = useState<{ ok?: string; err?: string }>({});
  useEffect(() => { if (!open && list.data?.length) setOpen(list.data[0].report_id); }, [list.data, open]);
  async function email(code: string) {
    setMail({});
    try { const r = await api<any>(`/api/me/reports/${code}/email`, { method: "POST" }); setMail({ ok: r.message }); list.reload(); }
    catch (e: any) { setMail({ err: e.message }); }
  }
  if (list.loading) return <Loading />;
  if (list.error) return <ErrorNote message={list.error} onRetry={list.reload} />;
  if (!list.data?.length) return <Empty title="No reports yet">Reports from tests at WellNest appear here as soon as the lab finishes them.</Empty>;
  const d = detail.data;
  return (
    <div className="split">
      <ul className="rows rows-select" aria-label="Reports">
        {list.data.map((r) => (
          <li key={r.report_id}>
            <button type="button" aria-current={open === r.report_id} onClick={() => { setOpen(r.report_id); setMail({}); }}>
              <span><span>{r.test}</span><span className="row-sub">{r.ordered}{r.doctor ? ` · ${r.doctor}` : ""}</span></span><Pill status={r.status} />
            </button>
          </li>
        ))}
      </ul>
      <section className="panel report" aria-live="polite">
        {detail.loading ? <Loading /> : d ? (
          <>
            <div className="panel-top"><h2 className="panel-h">{d.test}</h2><span className="id">{d.report_id}</span></div>
            <p className="row-sub">Ordered {d.ordered}{d.doctor ? ` by ${d.doctor}` : ""}</p>
            {d.status === "pending" ? (
              <p className="pending-note">The lab is still working on this. Expected {d.expected_at ? new Date(d.expected_at).toLocaleString("en-IN", { weekday: "long", hour: "numeric", minute: "2-digit" }) : "soon"}; we'll email you when it's ready.</p>
            ) : (
              <>
                {d.summary && <p className="summary">{d.summary}</p>}
                {d.results && (
                  <table className="table">
                    <thead><tr><th scope="col">Test</th><th scope="col" className="num">Result</th><th scope="col" className="num">Reference range</th></tr></thead>
                    <tbody>{Object.entries(d.results).map(([k, v]: any) => <tr key={k}><th scope="row">{k}</th><td className="num">{v.value}</td><td className="num muted">{v.range}</td></tr>)}</tbody>
                  </table>
                )}
                <p className="row-sub">Your doctor will explain what these numbers mean for you. This page is not medical advice.</p>
                <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => email(d.report_id)}><Mail size={18} aria-hidden="true" />Email me this report</button>
                {(mail.ok || mail.err) && <p className={mail.err ? "error-text" : "ok-text"}>{mail.ok || mail.err}</p>}
              </>
            )}
          </>
        ) : null}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ waitlist
export function Waitlist() {
  return <PortalShell title="Waitlist">{() => <WaitlistBody />}</PortalShell>;
}

function WaitlistBody() {
  const wl = useApi<{ entries: any[]; offers: any[] }>("/api/me/waitlist", [], { live: true });
  const depts = useApi<{ name: string }[]>("/api/departments");
  const docs = useApi<{ name: string; department: string }[]>("/api/doctors");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [dept, setDept] = useState("");
  async function join(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget).entries());
    try { const r = await api<any>("/api/me/waitlist", { method: "POST", body }); setMsg({ ok: r.message }); wl.reload(); }
    catch (x: any) { setMsg({ err: x.message }); }
  }
  return (
    <div className="split">
      <div className="stack">
        {wl.data?.offers?.map((o) => (
          <div key={o.offer_code} className="offer-banner token-shape">
            <div><p className="offer-title">{o.doctor}, {o.date} at {o.time}</p><p>Held for you for {Math.ceil(o.seconds_left / 60)} more minutes.</p></div>
            <Link className="btn btn-primary btn-sm token-shape" to={`/waitlist/accept?code=${o.offer_code}`}>Accept</Link>
          </div>
        ))}
        <section className="panel">
          <h2 className="panel-h">Your waitlist</h2>
          {wl.loading ? <Loading /> : wl.data?.entries.length ? (
            <ul className="rows">{wl.data.entries.map((e) => (
              <li key={e.id}><div><span>{e.for}</span><span className="row-sub">{shortDate(e.from)} to {shortDate(e.to)} · {e.time_preference}</span></div><Pill status={e.status} /></li>
            ))}</ul>
          ) : <p className="quiet">You're not waiting for any slot.</p>}
        </section>
      </div>
      <form className="panel" onSubmit={join}>
        <h2 className="panel-h">Join a waitlist</h2>
        <p className="row-sub">When someone cancels, we hold the slot for you for 30 minutes and email you a link.</p>
        <div className="field"><label htmlFor="w-dept">Department</label>
          <select id="w-dept" name="department" className="input" value={dept} onChange={(e) => setDept(e.target.value)} required>
            <option value="">Choose a department</option>{depts.data?.map((d) => <option key={d.name}>{d.name}</option>)}</select></div>
        <div className="field"><label htmlFor="w-doc">Doctor <span className="hint">optional</span></label>
          <select id="w-doc" name="doctor" className="input"><option value="">Any doctor</option>
            {docs.data?.filter((d) => !dept || d.department === dept).map((d) => <option key={d.name}>{d.name}</option>)}</select></div>
        <div className="two">
          <div className="field"><label htmlFor="w-from">From</label><input id="w-from" name="date_from" type="date" className="input" defaultValue={istDay(0)} /></div>
          <div className="field"><label htmlFor="w-to">To</label><input id="w-to" name="date_to" type="date" className="input" defaultValue={istDay(7)} /></div>
        </div>
        <div className="field"><label htmlFor="w-pref">Time of day</label>
          <select id="w-pref" name="time_preference" className="input"><option value="any">Any time</option><option value="morning">Morning</option><option value="afternoon">Afternoon</option><option value="evening">Evening</option></select></div>
        <button className="btn btn-primary token-shape">Join waitlist</button>
        {(msg.ok || msg.err) && <p className={msg.err ? "error-text" : "ok-text"} role="status">{msg.ok || msg.err}</p>}
      </form>
    </div>
  );
}

// ------------------------------------------------------------------ profile
export function Profile() {
  return <PortalShell title="Profile">{(me, reload) => <ProfileBody me={me} reload={reload} />}</PortalShell>;
}

function ProfileBody({ me, reload }: { me: Me; reload: () => void }) {
  const ins = useApi<{ name: string }[]>("/api/insurers");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setMsg({});
    const f = new FormData(e.currentTarget);
    const body: Record<string, string> = {};
    f.forEach((v, k) => { body[k] = String(v); });
    body.caregiver_consent = f.get("caregiver_consent") ? "yes" : "no";
    try { const r = await api<any>("/api/me/preferences", { method: "PATCH", body }); setMsg({ ok: r.message }); reload(); }
    catch (x: any) { setMsg({ err: x.message }); } finally { setBusy(false); }
  }
  return (
    <form className="settings" onSubmit={save}>
      <section className="set-group">
        <div className="set-intro"><h2 className="panel-h">You</h2><p className="row-sub">From your hospital record. To change your name, mobile number or date of birth, please visit the front desk.</p></div>
        <dl className="facts">
          <div><dt>Name</dt><dd>{me.name}</dd></div><div><dt>Mobile</dt><dd>{me.phone}</dd></div>
          <div><dt>Date of birth</dt><dd>{me.date_of_birth ? longDate(me.date_of_birth) : "Not on record"}</dd></div><div><dt>Patient ID</dt><dd className="id">{me.id}</dd></div>
        </dl>
      </section>
      <section className="set-group">
        <div className="set-intro"><h2 className="panel-h">Contact and insurance</h2></div>
        <div className="set-fields">
          <div className="field"><label htmlFor="p-email">Email for confirmations and reports</label><input id="p-email" name="email" type="email" className="input" defaultValue={me.email || ""} /></div>
          <div className="two">
            <div className="field"><label htmlFor="p-ins">Insurer</label><select id="p-ins" name="insurer" className="input" defaultValue={me.insurer || ""}><option value="">No insurance</option>{ins.data?.map((i) => <option key={i.name}>{i.name}</option>)}</select></div>
            <div className="field"><label htmlFor="p-pol">Policy number</label><input id="p-pol" name="policy_number" className="input" defaultValue={me.policy_number || ""} /></div>
          </div>
        </div>
      </section>
      <section className="set-group">
        <div className="set-intro"><h2 className="panel-h">How we look after you</h2><p className="row-sub">The assistant uses these on chat and on the phone.</p></div>
        <div className="set-fields">
          <div className="two">
            <div className="field"><label htmlFor="p-lang">Preferred language</label><select id="p-lang" name="preferred_language" className="input" defaultValue={me.preferred_language}>
              {["English", "Kannada", "Hindi", "Tamil", "Telugu", "Malayalam", "Marathi", "Bengali"].map((l) => <option key={l}>{l}</option>)}</select></div>
            <div className="field"><label htmlFor="p-time">Preferred time</label><select id="p-time" name="preferred_time" className="input" defaultValue={me.preferred_time}>
              <option value="any">Any time</option><option value="morning">Morning</option><option value="afternoon">Afternoon</option><option value="evening">Evening</option></select></div>
          </div>
          <div className="field"><label htmlFor="p-mob">Mobility needs <span className="hint">e.g. wheelchair at the entrance</span></label><input id="p-mob" name="mobility_needs" className="input" defaultValue={me.mobility_needs || ""} /></div>
        </div>
      </section>
      <section className="set-group">
        <div className="set-intro"><h2 className="panel-h">Family member or caregiver</h2><p className="row-sub">Only sent updates if you tick the box.</p></div>
        <div className="set-fields">
          <div className="field"><label htmlFor="p-cg">Name</label><input id="p-cg" name="caregiver_name" className="input" defaultValue={me.caregiver_name || ""} /></div>
          <div className="two">
            <div className="field"><label htmlFor="p-cgp">Mobile</label><input id="p-cgp" name="caregiver_phone" className="input" inputMode="tel" defaultValue={me.caregiver_phone || ""} /></div>
            <div className="field"><label htmlFor="p-cge">Email</label><input id="p-cge" name="caregiver_email" type="email" className="input" defaultValue={me.caregiver_email || ""} /></div>
          </div>
          <label className="check"><input type="checkbox" name="caregiver_consent" defaultChecked={me.caregiver_consent} />Send them my booking details and changes</label>
        </div>
      </section>
      <div className="row save-row">
        <button className="btn btn-primary token-shape" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        {(msg.ok || msg.err) && <p className={msg.err ? "error-text" : "ok-text"} role="status">{msg.ok || msg.err}</p>}
      </div>
    </form>
  );
}
