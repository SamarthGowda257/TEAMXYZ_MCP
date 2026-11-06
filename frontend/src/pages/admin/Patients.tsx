import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft, BadgeIndianRupee, CalendarDays, FileText, Info, MessagesSquare, Receipt, Wrench,
} from "lucide-react";
import {
  Chip, Empty, F, FArea, FCheck, FSelect, Loading, Mini, Panel, SearchBox, Status, Table, when,
  pretty, rupees, useOps, useWrite, type Col,
} from "../adminKit";

/**
 * Patients — search, then the whole record.
 *
 * The record is the honest one. Talkdesk never sends chat or voice transcripts to this backend, so
 * there is no verbatim conversation to show and we never draw a chat bubble. What is real, and what
 * this timeline shows, is every action the AI took (the resolutions trail) and the summary the bot
 * wrote when a conversation ended (interaction notes). The wording lives in Talkdesk; we say so.
 */

type Row = {
  id: number; patient_code: string; full_name: string; phone: string; email: string;
  preferred_language: string; caregiver_name: string | null; created_at: string; appointments: number;
};
type ListResp = { total: number; patients: Row[] };

type Patient = {
  id: number; patient_code: string; full_name: string; phone: string; date_of_birth: string | null;
  gender: string | null; email: string | null; address: string | null; preferred_language: string;
  preferred_time: string; insurer_id: number | null; policy_number: string | null;
  caregiver_name: string | null; caregiver_relation: string | null; caregiver_phone: string | null;
  caregiver_email: string | null; caregiver_consent: boolean; mobility_needs: string | null; is_guest: boolean;
};
type Timeline = {
  patient: Patient; credits: number;
  conversations: { id: number; channel: string; summary: string; topics: string; outcome: string; created_at: string }[];
  trail: { id: number; actor: string; action: string; ref: string; ok: boolean; summary: string; channel: string; created_at: string }[];
  appointments: { booking_code: string; appt_date: string; appt_time: string; status: string; reason: string; channel: string; doctor: string | null }[];
  reports: { report_code: string; test_name: string; status: string; ordered_at: string; expected_at: string | null; ready_at: string | null; summary: string | null }[];
  bills: { bill_code: string; description: string; amount_inr: number; insurer_paid_inr: number; status: string; due_date: string; created_at: string }[];
  orders: { order_code: string; status: string; total_inr: number; created_at: string }[];
  handoffs: { handoff_code: string; priority: string; summary: string; status: string; created_at: string }[];
  departments: Record<string, string>;
  transcripts_available: boolean; transcript_note: string;
};

const LANGS: [string, string][] = [["English", "English"], ["Kannada", "Kannada"], ["Hindi", "Hindi"],
  ["Tamil", "Tamil"], ["Telugu", "Telugu"], ["Malayalam", "Malayalam"], ["Marathi", "Marathi"], ["Bengali", "Bengali"]];
const TIMES: [string, string][] = [["morning", "Morning"], ["afternoon", "Afternoon"], ["evening", "Evening"], ["any", "Any time"]];

/* ------------------------------------------------------------------ list */

export function Patients({ open, onOpen }: { open: number | null; onOpen: (id: number | null) => void }) {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const path = `/api/ops/patients?limit=100${term ? `&q=${encodeURIComponent(term)}` : ""}`;
  const { data, loading, error } = useOps<ListResp>(path);

  if (open != null) return <PatientRecord id={open} onBack={() => onOpen(null)} />;

  const cols: Col<Row>[] = [
    { key: "who", head: "Patient", cell: (p) => <>{p.full_name}<span className="ad-sub">{p.patient_code}</span></> },
    { key: "phone", head: "Mobile", cell: (p) => <span className="ad-num">{p.phone}</span> },
    { key: "email", head: "Email", cell: (p) => p.email || <span className="ad-dim">none on file</span> },
    { key: "lang", head: "Speaks", cell: (p) => p.preferred_language || "—" },
    { key: "cg", head: "Caregiver", cell: (p) => p.caregiver_name || <span className="ad-dim">none</span> },
    { key: "n", head: "Visits", num: true, cell: (p) => <span className="ad-num">{p.appointments}</span> },
    { key: "do", head: "Record", width: "1%", cell: (p) => <Mini tone="accent" onClick={() => onOpen(p.id)}>Open</Mini> },
  ];

  return (
    <Panel
      title="Patients"
      count={data ? data.total : undefined}
      action={
        <SearchBox value={q} onChange={setQ} onSubmit={() => setTerm(q.trim())}
                   placeholder="Name or mobile number" label="Search patients by name or number" />
      }
    >
      {loading && !data ? <Loading rows={10} />
        : error ? <Empty title="Could not load patients" hint={error} />
        : !data?.patients.length ? (
          <Empty title="No patients match" hint="Search by name, or by the last digits of a mobile number, then press Enter." />
        ) : <Table cols={cols} rows={data.patients} rowKey={(p) => String(p.id)} onRow={(p) => onOpen(p.id)} />}
    </Panel>
  );
}

/* ------------------------------------------------------------------ one record */

type Tab = "timeline" | "profile" | "visits" | "money";

function PatientRecord({ id, onBack }: { id: number; onBack: () => void }) {
  const { data, loading, error, reload } = useOps<Timeline>(`/api/admin/patients/${id}/timeline`);
  const [tab, setTab] = useState<Tab>("timeline");

  useEffect(() => { setTab("timeline"); }, [id]);

  if (loading && !data) return <Panel title="Loading the record"><Loading rows={8} /></Panel>;
  if (error || !data) return <Panel title="Record"><Empty title="Could not open this record" hint={error || "Try again."} /></Panel>;

  const p = data.patient;
  const tabs: [Tab, string, typeof Info][] = [
    ["timeline", "End-to-end record", MessagesSquare],
    ["profile", "Profile and caregiver", Wrench],
    ["visits", "Visits and reports", CalendarDays],
    ["money", "Bills, orders, wallet", BadgeIndianRupee],
  ];

  return (
    <div className="ad-stack">
      <Panel flat>
        <div className="ad-record-head">
          <button type="button" className="ad-back" onClick={onBack}>
            <ArrowLeft size={16} aria-hidden="true" /> All patients
          </button>
          <div className="ad-record-id">
            <h2>{p.full_name}</h2>
            <p>
              <code className="ad-code">{p.patient_code}</code>
              <span className="ad-num">{p.phone}</span>
              {p.date_of_birth && <span>born {when(p.date_of_birth, false)}</span>}
              {p.gender && <span>{p.gender}</span>}
              {p.is_guest && <Chip kind="work">guest record</Chip>}
            </p>
          </div>
          <div className="ad-record-credits">
            <span>HealthCredits</span>
            <strong className="ad-num">{data.credits.toLocaleString("en-IN")}</strong>
          </div>
        </div>
        <div className="ad-tabs" role="tablist" aria-label="Record sections">
          {tabs.map(([k, label, Icon]) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k}
                    className={tab === k ? "is-on" : ""} onClick={() => setTab(k)}>
              <Icon size={15} aria-hidden="true" /> {label}
            </button>
          ))}
        </div>
      </Panel>

      {tab === "timeline" && <RecordTimeline d={data} />}
      {tab === "profile" && <ProfileForm p={p} onSaved={reload} />}
      {tab === "visits" && <Visits d={data} />}
      {tab === "money" && <Money d={data} onChanged={reload} />}
    </div>
  );
}

/* ------------------------------------------------------------------ the timeline */

type Entry =
  | { at: string; kind: "action"; actor: string; channel: string; action: string; ref: string; ok: boolean; text: string }
  | { at: string; kind: "summary"; channel: string; outcome: string; topics: string; text: string }
  | { at: string; kind: "handoff"; code: string; priority: string; status: string; text: string };

function RecordTimeline({ d }: { d: Timeline }) {
  const entries = useMemo<Entry[]>(() => {
    const all: Entry[] = [
      ...d.trail.map((t) => ({
        at: t.created_at, kind: "action" as const, actor: t.actor, channel: t.channel,
        action: t.action, ref: t.ref, ok: t.ok, text: t.summary,
      })),
      ...d.conversations.map((c) => ({
        at: c.created_at, kind: "summary" as const, channel: c.channel,
        outcome: c.outcome, topics: c.topics, text: c.summary,
      })),
      ...d.handoffs.map((h) => ({
        at: h.created_at, kind: "handoff" as const, code: h.handoff_code,
        priority: h.priority, status: h.status, text: h.summary,
      })),
    ];
    return all.sort((a, b) => (a.at < b.at ? 1 : -1));
  }, [d]);

  return (
    <Panel title="End-to-end record" count={entries.length}
           action={<span className="ad-panel-note">newest first</span>}>
      <div className="ad-truth">
        <Info size={16} aria-hidden="true" />
        <p>
          <strong>There are no transcripts here, and none are invented.</strong> {d.transcript_note} This
          timeline is the real record: each <em>action</em> is a tool call the AI or a staff member
          actually made, and each <em>summary</em> is the note the bot saved when a conversation ended.
        </p>
      </div>

      {!entries.length ? (
        <Empty title="Nothing recorded for this patient yet"
               hint="The moment the AI books, cancels, emails a report or escalates for this patient, it appears here." />
      ) : (
        <ol className="ad-tl">
          {entries.map((e, i) => (
            <li key={`${e.kind}${e.at}${i}`} className={`ad-tl-${e.kind}`}>
              <span className="ad-tl-dot" aria-hidden="true" />
              <div className="ad-tl-meta">
                <time dateTime={e.at}>{when(e.at)}</time>
                {e.kind === "action" && <Chip kind={e.actor === "staff" ? "work" : "plain"}>{e.actor === "staff" ? "staff action" : "AI action"}</Chip>}
                {e.kind === "summary" && <Chip kind="live">conversation summary</Chip>}
                {e.kind === "handoff" && <Chip kind="urgent">handed to a person</Chip>}
                {"channel" in e && e.channel && <span className="ad-tl-ch">{e.channel}</span>}
              </div>
              <div className="ad-tl-body">
                {e.kind === "action" && (
                  <>
                    <strong>{pretty(e.action)}</strong>
                    <p>{e.text}</p>
                    {e.ref && <code className="ad-code">{e.ref}</code>}
                    {!e.ok && <Chip kind="urgent">the tool reported a failure</Chip>}
                  </>
                )}
                {e.kind === "summary" && (
                  <>
                    <p>{e.text}</p>
                    <span className="ad-sub">
                      {e.outcome ? `outcome: ${pretty(e.outcome)}` : ""}
                      {e.topics ? ` · ${e.topics.split(",").map((t) => t.trim()).join(", ")}` : ""}
                    </span>
                  </>
                )}
                {e.kind === "handoff" && (
                  <>
                    <strong>{e.priority === "urgent" ? "Urgent handoff" : "Handoff"} · {e.status}</strong>
                    <p>{e.text}</p>
                    <code className="ad-code">{e.code}</code>
                  </>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ profile editing */

function ProfileForm({ p, onSaved }: { p: Patient; onSaved: () => void }) {
  const ins = useOps<{ insurers: { id: number; code: string; name: string }[] }>("/api/admin/insurers");
  const { send, busy } = useWrite();
  const [f, setF] = useState(() => ({
    full_name: p.full_name || "", email: p.email || "", address: p.address || "",
    preferred_language: p.preferred_language || "English", preferred_time: p.preferred_time || "any",
    policy_number: p.policy_number || "", insurer_id: p.insurer_id == null ? "" : String(p.insurer_id),
    caregiver_name: p.caregiver_name || "", caregiver_relation: p.caregiver_relation || "",
    caregiver_phone: p.caregiver_phone || "", caregiver_email: p.caregiver_email || "",
    caregiver_consent: !!p.caregiver_consent, mobility_needs: p.mobility_needs || "",
  }));
  useEffect(() => {
    setF({
      full_name: p.full_name || "", email: p.email || "", address: p.address || "",
      preferred_language: p.preferred_language || "English", preferred_time: p.preferred_time || "any",
      policy_number: p.policy_number || "", insurer_id: p.insurer_id == null ? "" : String(p.insurer_id),
      caregiver_name: p.caregiver_name || "", caregiver_relation: p.caregiver_relation || "",
      caregiver_phone: p.caregiver_phone || "", caregiver_email: p.caregiver_email || "",
      caregiver_consent: !!p.caregiver_consent, mobility_needs: p.mobility_needs || "",
    });
  }, [p]);
  const set = (k: keyof typeof f) => (v: any) => setF((s) => ({ ...s, [k]: v }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { ...f };
    body.insurer_id = f.insurer_id ? Number(f.insurer_id) : null;
    const r = await send(`/api/admin/patients/${p.id}`, { method: "PATCH", body });
    if (r) onSaved();
  };

  return (
    <form onSubmit={save}>
      <Panel title="Profile" action={<span className="ad-panel-note">the phone number and date of birth identify this patient and are not editable here</span>}>
        <div className="ad-form-grid">
          <F label="Full name" value={f.full_name} onChange={set("full_name")} required />
          <F label="Email" type="email" value={f.email} onChange={set("email")}
             hint="Confirmations and lab reports go to this address." />
          <FSelect label="Preferred language" value={f.preferred_language} onChange={set("preferred_language")} options={LANGS} />
          <FSelect label="Preferred time of day" value={f.preferred_time} onChange={set("preferred_time")} options={TIMES} />
          <F label="Address" value={f.address} onChange={set("address")} span />
          <FSelect label="Insurer" value={f.insurer_id} onChange={set("insurer_id")}
                   options={[["", "No insurance on file"], ...(ins.data?.insurers || []).map((i) => [String(i.id), i.name] as [string, string])]} />
          <F label="Policy number" value={f.policy_number} onChange={set("policy_number")} />
          <FArea label="Mobility and assistance needs" value={f.mobility_needs} onChange={set("mobility_needs")}
                 hint="Read out to the staff member who meets them at the entrance." rows={2} />
        </div>
      </Panel>

      <Panel title="Caregiver">
        <div className="ad-form-grid">
          <F label="Caregiver name" value={f.caregiver_name} onChange={set("caregiver_name")} />
          <F label="Relation" value={f.caregiver_relation} onChange={set("caregiver_relation")} placeholder="son, daughter, spouse" />
          <F label="Caregiver mobile" value={f.caregiver_phone} onChange={set("caregiver_phone")} />
          <F label="Caregiver email" type="email" value={f.caregiver_email} onChange={set("caregiver_email")} />
          <div className="ad-field-span">
            <FCheck label="The patient consents to updates being shared with this caregiver"
                    checked={f.caregiver_consent} onChange={set("caregiver_consent")} />
          </div>
        </div>
        <div className="ad-actions">
          <button className="btn btn-primary btn-sm" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save this record"}
          </button>
        </div>
      </Panel>
    </form>
  );
}

/* ------------------------------------------------------------------ visits, reports */

function Visits({ d }: { d: Timeline }) {
  const { send, busy } = useWrite();
  const [done, setDone] = useState<Record<string, string>>({});
  const mark = async (code: string, to: string) => {
    const r = await send(`/api/admin/appointments/${code}/status`, { method: "POST", body: { status: to } });
    if (r) setDone((s) => ({ ...s, [code]: to }));
  };
  return (
    <div className="ad-stack">
      <Panel title="Appointments" count={d.appointments.length}>
        {!d.appointments.length ? (
          <Empty title="No appointments on this record" hint="Bookings made in chat, by phone or on the website all appear here." />
        ) : (
          <Table
            rows={d.appointments}
            rowKey={(a) => a.booking_code}
            cols={[
              { key: "c", head: "Booking", cell: (a) => <code className="ad-code">{a.booking_code}</code> },
              { key: "w", head: "When", cell: (a) => <>{when(a.appt_date, false)}<span className="ad-sub ad-num">{a.appt_time}</span></> },
              { key: "d", head: "With", cell: (a) => a.doctor || <span className="ad-dim">procedure</span> },
              { key: "r", head: "Reason", wide: true, cell: (a) => a.reason || "—" },
              { key: "ch", head: "Via", cell: (a) => <Chip kind="plain">{a.channel}</Chip> },
              { key: "s", head: "Status", cell: (a) => <Status value={done[a.booking_code] || a.status} /> },
              {
                key: "do", head: "Change", width: "1%",
                cell: (a) => (done[a.booking_code] || a.status) === "booked" ? (
                  <span className="ad-row-actions">
                    <Mini tone="accent" disabled={busy} onClick={() => mark(a.booking_code, "completed")}>Completed</Mini>
                    <Mini disabled={busy} onClick={() => mark(a.booking_code, "no_show")}>No show</Mini>
                  </span>
                ) : <span className="ad-dim">—</span>,
              },
            ]}
          />
        )}
      </Panel>

      <Panel title="Lab reports and scans" count={d.reports.length}>
        {!d.reports.length ? (
          <Empty title="No reports on this record" hint="Reports appear when a test is ordered; the AI emails them once they are ready." />
        ) : (
          <Table
            rows={d.reports}
            rowKey={(r) => r.report_code}
            cols={[
              { key: "c", head: "Report", cell: (r) => <code className="ad-code">{r.report_code}</code> },
              { key: "t", head: "Test", cell: (r) => r.test_name },
              { key: "o", head: "Ordered", cell: (r) => when(r.ordered_at) },
              { key: "e", head: "Expected", cell: (r) => (r.expected_at ? when(r.expected_at) : <span className="ad-dim">—</span>) },
              { key: "rd", head: "Ready", cell: (r) => (r.ready_at ? when(r.ready_at) : <span className="ad-dim">not yet</span>) },
              { key: "s", head: "Status", cell: (r) => <Status value={r.status} /> },
              { key: "sm", head: "Note", wide: true, cell: (r) => r.summary || <span className="ad-dim">—</span> },
            ]}
          />
        )}
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ money */

function Money({ d, onChanged }: { d: Timeline; onChanged: () => void }) {
  const { send, busy } = useWrite();
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");

  const adjust = async (sign: 1 | -1) => {
    const n = Math.abs(parseInt(amount, 10) || 0);
    if (!n) { setAmount(""); return; }
    const r = await send(`/api/admin/wallets/${d.patient.id}/adjust`, {
      method: "POST", body: { amount: sign * n, reason: reason.trim() || "Front desk adjustment" },
    });
    if (r) { setAmount(""); setReason(""); onChanged(); }
  };

  return (
    <div className="ad-stack">
      <Panel title="HealthCredits wallet" action={<span className="ad-panel-note">1 credit = ₹1</span>}>
        <div className="ad-wallet">
          <div className="ad-wallet-bal">
            <span>Balance now</span>
            <strong className="ad-num">{d.credits.toLocaleString("en-IN")}</strong>
          </div>
          <div className="ad-form-grid ad-wallet-form">
            <F label="Amount in credits" type="number" min={1} value={amount} onChange={setAmount} placeholder="500" />
            <F label="Reason" value={reason} onChange={setReason} placeholder="Goodwill refund for the delayed scan" />
          </div>
          <div className="ad-actions">
            <Mini tone="accent" disabled={busy || !amount} onClick={() => adjust(1)}>Credit this amount</Mini>
            <Mini tone="danger" disabled={busy || !amount} onClick={() => adjust(-1)}>Debit this amount</Mini>
          </div>
          <p className="ad-note">Every adjustment is written to the audit trail with your reason, and shows up on the patient's timeline.</p>
        </div>
      </Panel>

      <Panel title="Bills" count={d.bills.length}>
        {!d.bills.length ? <Empty title="No bills on this record" hint="Bills are raised when a visit or a procedure completes." /> : (
          <Table
            rows={d.bills}
            rowKey={(b) => b.bill_code}
            cols={[
              { key: "c", head: "Bill", cell: (b) => <code className="ad-code">{b.bill_code}</code> },
              { key: "d", head: "For", wide: true, cell: (b) => b.description },
              { key: "a", head: "Amount", num: true, cell: (b) => <span className="ad-num">{rupees(b.amount_inr)}</span> },
              { key: "i", head: "Insurer paid", num: true, cell: (b) => <span className="ad-num">{rupees(b.insurer_paid_inr)}</span> },
              { key: "due", head: "Due", cell: (b) => when(b.due_date, false) },
              { key: "s", head: "Status", cell: (b) => <Status value={b.status} /> },
            ]}
          />
        )}
      </Panel>

      <Panel title="Pharmacy orders" count={d.orders.length}>
        {!d.orders.length ? (
          <Empty title="No pharmacy orders" hint="Refills ordered in chat or by phone appear here with their delivery status." />
        ) : (
          <Table
            rows={d.orders}
            rowKey={(o) => o.order_code}
            cols={[
              { key: "c", head: "Order", cell: (o) => <code className="ad-code">{o.order_code}</code> },
              { key: "t", head: "Total", num: true, cell: (o) => <span className="ad-num">{rupees(o.total_inr)}</span> },
              { key: "w", head: "Placed", cell: (o) => when(o.created_at) },
              { key: "s", head: "Status", cell: (o) => <Status value={o.status} /> },
            ]}
          />
        )}
      </Panel>

      <p className="ad-note ad-note-foot">
        <Receipt size={14} aria-hidden="true" /> Bills, orders and reports are read from the same tables the AI
        reads on a call, so what a patient is told and what you see here cannot drift apart.
        <FileText size={14} aria-hidden="true" />
      </p>
    </div>
  );
}
