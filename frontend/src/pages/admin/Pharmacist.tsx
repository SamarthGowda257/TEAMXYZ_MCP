import { useState } from "react";
import { Check, ExternalLink, X } from "lucide-react";
import {
  Chip, Empty, F, Filters, Mini, Panel, Shown, Status, Table, rupees, when, useOps, useWrite, type Col,
} from "../adminKit";
import { BLANK_LINE, RxItems, toItems, useFormulary, type Line } from "./RxItems";

/**
 * Pharmacist desk. Nothing on a prescription leaves the pharmacy until it's checked here.
 *   Queue       orders waiting for a check: approve, or reject with a reason (credits, stock, days go back)
 *   Uploads     prescriptions from other hospitals: read the file, enter the medicines, approve or reject
 *   Deliveries  parcels with the courier (simulated courier: play the rider's events)
 *   Register    the Schedule H1 register (who, what, how much, checked by whom)
 *   Limits      the per-order, weekly and daily limits per ingredient, and the sign-off
 */

type QOrder = {
  id: number; order_code: string; patient: string; allergies: string | null; status: string; notes: string | null;
  total_inr: number; created_at: string;
  lines: { name: string; qty: number; schedule: string; days: number | null; rx: string | null; prescriber: string | null }[];
};
type Upload = { id: number; upload_code: string; full_name: string; file_name: string; content_type: string; note: string; created_at: string };
type Del = { id: number; order_code: string; provider: string; job_id: string; status: string; attempts: number; needs_code: boolean };
type Queue = { orders: QOrder[]; uploads: Upload[]; deliveries: Del[]; simulated_courier: boolean };
type Rule = Record<string, any> & { ingredient: string };
type Reg = { order: string; patient: string; medicine: string; schedule: string; packs: number; units: number; pharmacist: string; verified_at: string };

export function Pharmacist() {
  const [tab, setTab] = useState("queue");
  const q = useOps<Queue>("/api/staff/pharmacist/queue", 20000);
  const counts = q.data ? { queue: q.data.orders.length, uploads: q.data.uploads.length, deliveries: q.data.deliveries.length } : null;
  return (
    <div className="ad-stack">
      <header className="ad-page-head">
        <h1>Pharmacist desk</h1>
        <p>Prescription medicines wait here for a check before they're packed. Every decision is recorded.</p>
      </header>
      <Filters label="Section" value={tab} onChange={setTab} options={[
        ["queue", `Orders to check${counts ? ` (${counts.queue})` : ""}`],
        ["uploads", `Uploaded prescriptions${counts ? ` (${counts.uploads})` : ""}`],
        ["deliveries", `Deliveries${counts ? ` (${counts.deliveries})` : ""}`],
        ["register", "H1 register"], ["limits", "Limits"],
      ]} />
      {tab === "queue" && <OrdersToCheck q={q} />}
      {tab === "uploads" && <Uploads q={q} />}
      {tab === "deliveries" && <Deliveries q={q} />}
      {tab === "register" && <Register />}
      {tab === "limits" && <Limits />}
    </div>
  );
}

function OrdersToCheck({ q }: { q: ReturnType<typeof useOps<Queue>> }) {
  const { send, busy } = useWrite();
  const [reason, setReason] = useState<Record<number, string>>({});
  const act = async (o: QOrder, ok: boolean) => {
    const r = await send(`/api/staff/pharmacist/orders/${o.id}/${ok ? "approve" : "reject"}`, {
      method: "POST", body: { reason: reason[o.id] || "" } });
    if (r) q.reload();
  };
  return (
    <Shown state={q} empty={{ title: "Nothing to check", hint: "New orders appear here within seconds." }}>
      {(d) => d.orders.length ? (
        <div className="ad-stack">
          {d.orders.map((o) => (
            <Panel key={o.id} title={`${o.order_code} · ${o.patient}`} action={<Status value={o.status} />}>
              {o.allergies && <p className="ad-warn">Allergies: {o.allergies}</p>}
              {o.notes && <p className="ad-sub">Why it's here: {o.notes}</p>}
              <ul className="ad-lines">
                {o.lines.map((l, i) => (
                  <li key={i}>
                    <strong>{l.qty} × {l.name}</strong> <Chip kind={l.schedule === "OTC" ? "ok" : "work"}>{l.schedule}</Chip>
                    <span className="ad-sub">
                      {l.rx ? `${l.rx} · ${l.prescriber || "prescriber unknown"}` : "no prescription needed"}
                      {l.days ? ` · ${l.days} days of supply` : ""}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="ad-sub">{rupees(o.total_inr)} · ordered {when(o.created_at)}</p>
              <div className="ad-row-actions">
                <Mini tone="accent" disabled={busy} onClick={() => act(o, true)}><Check size={14} aria-hidden="true" /> Approve</Mini>
                <input className="input ad-input-sm" placeholder="Reason, shown to the patient" aria-label="Reason to reject"
                       value={reason[o.id] || ""} onChange={(e) => setReason({ ...reason, [o.id]: e.target.value })} />
                <Mini tone="danger" disabled={busy || !(reason[o.id] || "").trim()} onClick={() => act(o, false)}>
                  <X size={14} aria-hidden="true" /> Reject and refund
                </Mini>
              </div>
            </Panel>
          ))}
        </div>
      ) : <Empty title="Nothing to check" hint="New orders appear here within seconds." />}
    </Shown>
  );
}

function Uploads({ q }: { q: ReturnType<typeof useOps<Queue>> }) {
  const meds = useFormulary();
  const { send, busy } = useWrite();
  const [open, setOpen] = useState<number | null>(null);
  const [lines, setLines] = useState<Line[]>([{ ...BLANK_LINE }]);
  const [doctor, setDoctor] = useState("");
  const [reason, setReason] = useState("");
  const review = async (u: Upload, approve: boolean) => {
    const r = await send(`/api/staff/pharmacist/uploads/${u.id}/review`, { method: "POST", body: {
      approve, reason, doctor_name: doctor, items: approve ? toItems(lines) : [] } });
    if (r) { setOpen(null); setLines([{ ...BLANK_LINE }]); setDoctor(""); setReason(""); q.reload(); }
  };
  return (
    <Shown state={q} empty={{ title: "No uploads", hint: "Patients upload outside prescriptions from the website." }}>
      {(d) => d.uploads.length ? (
        <div className="ad-stack">
          {d.uploads.map((u) => (
            <Panel key={u.id} title={`${u.upload_code} · ${u.full_name}`} action={
              <a className="ad-mini" href={`/api/staff/pharmacist/uploads/${u.id}/file`} target="_blank" rel="noreferrer">
                <ExternalLink size={14} aria-hidden="true" /> Open the file
              </a>}>
              <p className="ad-sub">{u.file_name} · uploaded {when(u.created_at)}{u.note ? ` · “${u.note}”` : ""}</p>
              {open === u.id ? (
                <div className="ad-stack">
                  <F label="Prescribing doctor and hospital" value={doctor} onChange={setDoctor} placeholder="Dr. Rao, Apollo Hospitals" />
                  <Shown state={meds} empty={{ title: "No medicines", hint: "" }}>
                    {(m) => <RxItems lines={lines} onChange={setLines} meds={m.medicines} />}
                  </Shown>
                  <div className="ad-row-actions">
                    <Mini tone="accent" disabled={busy || !toItems(lines).length} onClick={() => review(u, true)}>Approve as entered</Mini>
                    <Mini onClick={() => setOpen(null)}>Cancel</Mini>
                  </div>
                </div>
              ) : (
                <div className="ad-row-actions">
                  <Mini tone="accent" onClick={() => setOpen(u.id)}>Enter the medicines</Mini>
                  <input className="input ad-input-sm" placeholder="Reason, e.g. unreadable or older than 6 months"
                         aria-label="Reason to reject" value={reason} onChange={(e) => setReason(e.target.value)} />
                  <Mini tone="danger" disabled={busy || !reason.trim()} onClick={() => review(u, false)}>Reject</Mini>
                </div>
              )}
            </Panel>
          ))}
        </div>
      ) : <Empty title="No uploads" hint="Patients upload outside prescriptions from the website." />}
    </Shown>
  );
}

function Deliveries({ q }: { q: ReturnType<typeof useOps<Queue>> }) {
  const { send, busy } = useWrite();
  const [code, setCode] = useState<Record<number, string>>({});
  const ev = async (d: Del, event: string) => {
    const r = await send(`/api/staff/pharmacist/deliveries/${d.id}/event`, { method: "POST", body: { event, otp: code[d.id] || "" } });
    if (r) q.reload();
  };
  const cols: Col<Del>[] = [
    { key: "o", head: "Order", cell: (d) => <code className="ad-code">{d.order_code}</code> },
    { key: "c", head: "Courier", cell: (d) => <>{d.provider}<span className="ad-sub">{d.job_id}</span></> },
    { key: "s", head: "Status", cell: (d) => <><Status value={d.status} />{d.attempts ? <span className="ad-sub">{d.attempts} missed</span> : null}</> },
    { key: "a", head: "Rider events", cell: (d) => (
      <span className="ad-row-actions">
        <Mini disabled={busy} onClick={() => ev(d, "picked_up")}>Picked up</Mini>
        {d.needs_code && <input className="input ad-input-sm" placeholder="Code" inputMode="numeric" aria-label="Delivery code"
                                value={code[d.id] || ""} onChange={(e) => setCode({ ...code, [d.id]: e.target.value })} />}
        <Mini tone="accent" disabled={busy} onClick={() => ev(d, "delivered")}>Delivered</Mini>
        <Mini disabled={busy} onClick={() => ev(d, "failed_attempt")}>Missed</Mini>
        <Mini disabled={busy} onClick={() => ev(d, "no_rider")}>No rider</Mini>
      </span>
    ) },
  ];
  return (
    <Shown state={q} empty={{ title: "No parcels out", hint: "Dispatched orders appear here." }}>
      {(d) => (
        <Panel title="Parcels with the courier" count={d.deliveries.length}>
          {!d.simulated_courier && <p className="ad-sub">A real courier reports these by webhook; the buttons are for the simulated courier.</p>}
          {d.deliveries.length ? <Table cols={d.simulated_courier ? cols : cols.slice(0, 3)} rows={d.deliveries} rowKey={(x) => String(x.id)} />
            : <Empty title="No parcels out" hint="Dispatched orders appear here." />}
        </Panel>
      )}
    </Shown>
  );
}

function Register() {
  const reg = useOps<{ register: Reg[] }>("/api/staff/pharmacist/register?schedule=H1");
  const cols: Col<Reg>[] = [
    { key: "w", head: "Checked", cell: (r) => <>{when(r.verified_at)}<span className="ad-sub">{r.pharmacist}</span></> },
    { key: "p", head: "Patient", cell: (r) => r.patient },
    { key: "m", head: "Medicine", cell: (r) => <>{r.medicine}<span className="ad-sub">{r.packs} packs · {r.units} units</span></> },
    { key: "o", head: "Order", cell: (r) => <code className="ad-code">{r.order}</code> },
  ];
  return (
    <Shown state={reg} empty={{ title: "Empty register", hint: "Schedule H1 supplies appear here once checked." }}>
      {(d) => (
        <Panel title="Schedule H1 register" count={d.register.length}>
          {d.register.length ? <Table cols={cols} rows={d.register} rowKey={(r) => r.order + r.medicine} />
            : <Empty title="Empty register" hint="Schedule H1 supplies appear here once checked." />}
        </Panel>
      )}
    </Shown>
  );
}

const RULE_COLS: [string, string][] = [
  ["otc_max_mg_per_order", "OTC mg / order"], ["otc_max_mg_per_7d", "OTC mg / 7 days"],
  ["otc_max_units_per_order", "OTC units / order"], ["otc_max_units_per_7d", "OTC units / 7 days"],
  ["max_daily_mg_adult", "Max mg / day"], ["min_age_years", "Min age"], ["early_refill_pct", "Refill from %"],
  ["max_days_per_order", "Max days / order"],
];

function Limits() {
  const rules = useOps<{ rules: Rule[] }>("/api/staff/drug-rules");
  const { send, busy } = useWrite();
  const [edit, setEdit] = useState<Rule | null>(null);
  const save = async (signOff: boolean) => {
    if (!edit) return;
    const body: Record<string, any> = { sign_off: signOff, pregnancy_caution: !!edit.pregnancy_caution,
                                        requires_pharmacist: !!edit.requires_pharmacist };
    for (const [k] of RULE_COLS) body[k] = edit[k] === "" || edit[k] == null ? null : Number(edit[k]);
    const r = await send(`/api/staff/drug-rules/${encodeURIComponent(edit.ingredient)}`, { method: "POST", body });
    if (r) { setEdit(null); rules.reload(); }
  };
  const cols: Col<Rule>[] = [
    { key: "i", head: "Ingredient", cell: (r) => <><strong>{r.ingredient}</strong>{r.signed_off_by
      ? <span className="ad-sub">signed off by {r.signed_off_by}</span> : <span className="ad-sub ad-warn">demo default · not signed off</span>}</> },
    ...RULE_COLS.slice(0, 6).map(([k, h]) => ({ key: k, head: h, num: true, cell: (r: Rule) => r[k] ?? "—" })),
    { key: "e", head: "", cell: (r) => <Mini onClick={() => setEdit({ ...r })}>Edit</Mini> },
  ];
  return (
    <Shown state={rules} empty={{ title: "No limits", hint: "" }}>
      {(d) => (
        <div className="ad-stack">
          <Panel title="Limits per ingredient" count={d.rules.length}>
            <p className="ad-sub">These numbers decide what the chat, the phone line and the website may send. Demo defaults
              must be checked and signed off by the hospital pharmacist before real patients use the service.</p>
            <Table cols={cols} rows={d.rules} rowKey={(r) => r.ingredient} />
          </Panel>
          {edit && (
            <Panel title={`Limits for ${edit.ingredient}`}>
              <div className="ad-form-grid">
                {RULE_COLS.map(([k, h]) => (
                  <F key={k} label={h} type="number" value={edit[k] ?? ""} onChange={(v) => setEdit({ ...edit, [k]: v })} />
                ))}
              </div>
              <div className="ad-row-actions">
                <Mini disabled={busy} onClick={() => save(false)}>Save</Mini>
                <Mini tone="accent" disabled={busy} onClick={() => save(true)}>Save and sign off</Mini>
                <Mini onClick={() => setEdit(null)}>Cancel</Mini>
              </div>
            </Panel>
          )}
        </div>
      )}
    </Shown>
  );
}
