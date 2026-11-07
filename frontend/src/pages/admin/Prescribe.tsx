import { useState } from "react";
import { FilePlus2 } from "lucide-react";
import {
  Confirm, Empty, F, Panel, SearchBox, Shown, Status, Table, when, useOps, useWrite, type Col,
} from "../adminKit";
import { BLANK_LINE, RxItems, toItems, useFormulary, type Line } from "./RxItems";

/**
 * Doctor → Prescribe. Find the patient, read what they already take and their safety notes, write a prescription.
 * It's signed as the signed-in doctor on the server; the patient gets an SMS and can order it on chat or the web.
 * A new prescription for a medicine they already take replaces the old one (a dose change).
 */

type Found = { id: number; code: string; name: string; phone: string; dob: string | null; allergies: string | null };
type Item = {
  item_id: number; rx_code: string; ingredient: string; dose: string; instructions: string | null; doctor: string | null;
  valid_until: string | null; days_left: number; next_refill_from: string | null; status: string; stop_reason: string | null;
};
type Card = {
  patient: { id: number; code: string; name: string; phone: string; dob: string | null; age: number | null;
             allergies: string; pregnant_until: string | null; weight_kg: number | null };
  prescriptions: Item[];
};

export function Prescribe() {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const found = useOps<{ patients: Found[] }>(`/api/staff/patients?q=${encodeURIComponent(term)}`);
  const [pid, setPid] = useState<number | null>(null);

  return (
    <div className="ad-stack">
      <header className="ad-page-head">
        <h1>Prescribe</h1>
        <p>Prescriptions written here are signed as you. The pharmacy counts every supply against them.</p>
      </header>
      <Panel title="Find the patient">
        <SearchBox label="Search patients" placeholder="Name, patient ID or mobile number" value={q} onChange={setQ}
                   onSubmit={() => setTerm(q.trim())} />
        {term.length >= 2 && (
          <Shown state={found} empty={{ title: "No match", hint: "Try the patient ID or the mobile number." }}>
            {(d) => d.patients.length ? (
              <ul className="ad-pick">
                {d.patients.map((p) => (
                  <li key={p.id}>
                    <button type="button" className={pid === p.id ? "is-on" : ""} onClick={() => setPid(p.id)}>
                      <strong>{p.name}</strong>
                      <span className="ad-sub">{p.code} · {p.phone}{p.dob ? ` · born ${when(p.dob, false)}` : ""}</span>
                      {p.allergies && <span className="ad-sub ad-warn">Allergies: {p.allergies}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            ) : <Empty title="No match" hint="Try the patient ID or the mobile number." />}
          </Shown>
        )}
      </Panel>
      {pid && <PatientRx key={pid} pid={pid} />}
    </div>
  );
}

function PatientRx({ pid }: { pid: number }) {
  const card = useOps<Card>(`/api/staff/patients/${pid}`);
  const meds = useFormulary();
  const { send, busy } = useWrite();
  const [lines, setLines] = useState<Line[]>([{ ...BLANK_LINE }]);
  const [validDays, setValidDays] = useState("182");
  const [stopReason, setStopReason] = useState("");
  const [safety, setSafety] = useState<{ allergies: string; pregnant_until: string; weight_kg: string } | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const items = toItems(lines);
    if (!items.length) return;
    const r = await send("/api/staff/prescriptions", { method: "POST", body: { patient_id: pid, items, valid_days: Number(validDays) } });
    if (r) { setLines([{ ...BLANK_LINE }]); card.reload(); }
  };
  const stop = async (it: Item) => {
    const r = await send(`/api/staff/prescription-items/${it.item_id}/stop`, { method: "POST", body: { reason: stopReason } });
    if (r) { setStopReason(""); card.reload(); }
  };
  const saveSafety = async () => {
    if (!safety) return;
    const r = await send(`/api/staff/patients/${pid}/safety`, { method: "POST", body: {
      allergies: safety.allergies, pregnant_until: safety.pregnant_until,
      ...(safety.weight_kg ? { weight_kg: Number(safety.weight_kg) } : {}),
    } });
    if (r) { setSafety(null); card.reload(); }
  };

  const cols: Col<Item>[] = [
    { key: "m", head: "Medicine", cell: (i) => <><strong>{i.ingredient}</strong><span className="ad-sub">{i.dose}{i.instructions ? ` · ${i.instructions}` : ""}</span></> },
    { key: "r", head: "Prescription", cell: (i) => <><code className="ad-code">{i.rx_code}</code><span className="ad-sub">{i.doctor || "—"}</span></> },
    { key: "l", head: "Left", cell: (i) => <>{i.days_left} days{i.next_refill_from && <span className="ad-sub">refill from {when(i.next_refill_from, false)}</span>}</> },
    { key: "v", head: "Valid until", cell: (i) => when(i.valid_until, false) },
    { key: "s", head: "Status", cell: (i) => <><Status value={i.status} />{i.stop_reason && <span className="ad-sub">{i.stop_reason}</span>}</> },
    { key: "a", head: "", cell: (i) => i.status === "active" ? (
      <span className="ad-row-actions">
        <input className="input ad-input-sm" placeholder="Reason to stop" value={stopReason} aria-label="Reason to stop"
               onChange={(e) => setStopReason(e.target.value)} />
        <Confirm label="Stop" question="Stop this medicine? Waiting orders are cancelled and refunded." busy={busy}
                 onYes={() => stop(i)} />
      </span>
    ) : null },
  ];

  return (
    <Shown state={card} empty={{ title: "Patient not found", hint: "Search again." }}>
      {(d) => (
        <>
          <Panel title={d.patient.name} action={
            <button type="button" className="ad-mini" onClick={() => setSafety({
              allergies: d.patient.allergies, pregnant_until: d.patient.pregnant_until || "",
              weight_kg: d.patient.weight_kg ? String(d.patient.weight_kg) : "" })}>Edit safety notes</button>}>
            <p className="ad-sub">
              {d.patient.code} · {d.patient.phone} · {d.patient.age != null ? `${d.patient.age} years` : "age unknown"}
              {d.patient.weight_kg ? ` · ${d.patient.weight_kg} kg` : ""}
            </p>
            <p className={d.patient.allergies ? "ad-warn" : "ad-sub"}>
              Allergies: {d.patient.allergies || "none recorded"}
              {d.patient.pregnant_until && <> · Pregnant (until {when(d.patient.pregnant_until, false)})</>}
            </p>
            {safety && (
              <div className="ad-form-grid">
                <F label="Allergies (ingredients, comma separated)" value={safety.allergies} span
                   onChange={(v) => setSafety({ ...safety, allergies: v })} placeholder="penicillin, sulfa" />
                <F label="Pregnant until" type="date" value={safety.pregnant_until}
                   onChange={(v) => setSafety({ ...safety, pregnant_until: v })} hint="Leave empty if not pregnant" />
                <F label="Weight (kg)" type="number" value={safety.weight_kg} onChange={(v) => setSafety({ ...safety, weight_kg: v })} />
                <div className="ad-field-span ad-row-actions">
                  <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={saveSafety}>Save</button>
                  <button type="button" className="btn btn-quiet btn-sm" onClick={() => setSafety(null)}>Cancel</button>
                </div>
              </div>
            )}
          </Panel>
          <Panel title="Prescriptions on file" count={d.prescriptions.length}>
            {d.prescriptions.length ? <Table cols={cols} rows={d.prescriptions} rowKey={(i) => String(i.item_id)} />
              : <Empty title="Nothing on file" hint="Write the first prescription below." />}
          </Panel>
          <Panel title="New prescription">
            <form onSubmit={save} className="ad-stack">
              <Shown state={meds} empty={{ title: "No medicines", hint: "The pharmacy list is empty." }}>
                {(m) => <RxItems lines={lines} onChange={setLines} meds={m.medicines} />}
              </Shown>
              <div className="ad-form-grid">
                <F label="Valid for (days)" type="number" min={1} value={validDays} onChange={setValidDays}
                   hint="At most 182 days (6 months)" />
              </div>
              <button className="btn btn-primary" disabled={busy || !toItems(lines).length}>
                <FilePlus2 size={16} aria-hidden="true" /> {busy ? "Signing…" : "Sign and save"}
              </button>
            </form>
          </Panel>
        </>
      )}
    </Shown>
  );
}
