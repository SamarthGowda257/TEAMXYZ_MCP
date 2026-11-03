import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PortalShell } from "../components/PortalShell";
import { ErrorNote, Loading, TokenSlip } from "../components/Bits";
import { DateStrip, SlotGrid } from "./Portal";
import { api, istDay, longDate, newKey, rupees, type DoctorCard, type Me, type Slot } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ReachButtons } from "../components/Reach";

type Target = { kind: "dept" | "doctor" | "proc"; value: string; label: string };
type Choice = { doctor?: string; time: string; label: string; fee: number; room?: string };

export function Book() {
  return <PortalShell title="Book a visit">{(me) => <BookFlow me={me} />}</PortalShell>;
}

function BookFlow({ me }: { me: Me }) {
  const [qs] = useSearchParams();
  const depts = useApi<{ name: string; description: string }[]>("/api/departments");
  const procs = useApi<{ code: string; name: string; category: string; price_inr: number; preauth_required: boolean; instructions: string }[]>("/api/procedures");
  const [target, setTarget] = useState<Target | null>(qs.get("doctor") ? { kind: "doctor", value: qs.get("doctor")!, label: qs.get("doctor")! } : null);
  const [date, setDate] = useState(qs.get("date") || istDay(1));
  const [choice, setChoice] = useState<Choice | null>(null);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [cover, setCover] = useState<string>("");
  const key = useRef(newKey());
  const pre = useRef(qs.get("time"));

  const q = target ? (target.kind === "proc" ? `procedure=${encodeURIComponent(target.value)}` : target.kind === "doctor" ? `doctor=${encodeURIComponent(target.value)}` : `department=${encodeURIComponent(target.value)}`) : "";
  const slots = useApi<any>(target ? `/api/slots?date=${date}&${q}` : null, [date, q]);

  useEffect(() => { setChoice(null); }, [target, date]);
  // a slot handed over from the home page finder
  useEffect(() => {
    if (!pre.current || !slots.data?.doctors) return;
    const d = slots.data.doctors.find((x: any) => x.slots.some((s: Slot) => s.time === pre.current));
    const s = d?.slots.find((x: Slot) => x.time === pre.current);
    if (d && s) setChoice({ doctor: d.name, time: s.time, label: s.label, fee: d.fee_inr, room: d.room });
    pre.current = null;
  }, [slots.data]);
  useEffect(() => {
    setCover("");
    if (!choice || !me.insurer) return;
    const body = target?.kind === "proc" ? { insurer: me.insurer, procedure: target.value } : { insurer: me.insurer, department: slots.data?.doctors?.find((d: any) => d.name === choice.doctor)?.department };
    api<any>("/api/coverage/estimate", { method: "POST", body }).then((r) => setCover(r.message)).catch(() => {});
  }, [choice]); // eslint-disable-line react-hooks/exhaustive-deps

  const proc = useMemo(() => target?.kind === "proc" ? procs.data?.find((p) => p.code === target.value) : undefined, [target, procs.data]);

  async function confirm() {
    if (!choice) return;
    setBusy(true); setErr("");
    try {
      const body = { date, time: choice.time, doctor: choice.doctor || "", procedure: target?.kind === "proc" ? target.value : "", reason };
      setResult(await api<any>("/api/me/appointments", { method: "POST", body, headers: { "Idempotency-Key": key.current } }));
    } catch (e: any) { setErr(e.message); key.current = newKey(); slots.reload(); } finally { setBusy(false); }
  }

  if (result) {
    const d = result.data;
    return (
      <div className="booked">
        <TokenSlip id={d.booking_id} spoken={d.booking_id_spoken} tone="accent"
          lines={[<strong key="w">{d.with}</strong>, `${d.date} · ${d.time}`, `Room ${d.room}`, `Fee ${rupees(d.fee_inr)}`]} />
        <p className="booked-msg">{result.message}</p>
        {d.instructions_short && <p className="row-sub">Before your visit: {d.instructions_short}</p>}
        {result.related?.map((r: any) => <p key={r.kind} className="note note-warn">{r.text}</p>)}
        <div className="row"><Link className="btn btn-primary token-shape" to="/portal/appointments">See my appointments</Link>
          <button type="button" className="btn btn-quiet token-shape" onClick={() => { setResult(null); setChoice(null); key.current = newKey(); slots.reload(); }}>Book another</button></div>
      </div>
    );
  }

  const step = !target ? 1 : !choice ? 2 : 3;
  return (
    <div className="book">
      <div className="assist-banner compact">
        <div><h2>Quickest: just tell the CareLine Assistant</h2><p>"Heart doctor on Wednesday morning" on chat or phone. It checks you, books a real slot and sends your booking ID.</p></div>
        <ReachButtons form={false} size="sm" />
      </div>
      <p className="or-line"><span>or pick a slot yourself</span></p>
      <ol className="steps" aria-label="Booking steps">
        <li aria-current={step === 1 ? "step" : undefined}>What</li>
        <li aria-current={step === 2 ? "step" : undefined}>When</li>
        <li aria-current={step === 3 ? "step" : undefined}>Confirm</li>
      </ol>

      <section className="panel" aria-labelledby="b-what">
        <div className="panel-top"><h2 id="b-what" className="panel-h">What do you need?</h2>
          {target && <button type="button" className="link-btn" onClick={() => setTarget(null)}>Change</button>}</div>
        {target ? <p className="chosen">{target.label}</p> : (
          <>
            {depts.loading && <Loading />}
            <div className="pick-grid">
              {depts.data?.filter((d) => d.name !== "Radiology").map((d) => (
                <button key={d.name} type="button" onClick={() => setTarget({ kind: "dept", value: d.name, label: d.name })}>
                  <strong>{d.name}</strong><span>{d.description}</span></button>
              ))}
            </div>
            <h3 className="sub-h">Tests and scans</h3>
            <div className="chip-row">
              {procs.data?.filter((p) => ["MRI", "CT", "XRAY", "USG", "CARDIO", "PKG"].includes(p.category)).map((p) => (
                <button key={p.code} type="button" onClick={() => setTarget({ kind: "proc", value: p.code, label: p.name })}>{p.name}</button>
              ))}
            </div>
          </>
        )}
      </section>

      {target && (
        <section className="panel" aria-labelledby="b-when">
          <h2 id="b-when" className="panel-h">When?</h2>
          <DateStrip value={date} onChange={setDate} />
          <p className="row-sub date-label">{longDate(date)}</p>
          {slots.loading && <Loading label="Finding free times" />}
          {slots.error && <ErrorNote message={slots.error} onRetry={slots.reload} />}
          {slots.data?.slots && (
            <SlotGrid slots={slots.data.slots} value={choice?.time}
              onPick={(s) => setChoice({ time: s.time, label: s.label, fee: slots.data.price_inr })} />
          )}
          {slots.data?.doctors && (
            <div className="doc-slots">
              {slots.data.doctors.map((d: DoctorCard & { slots: Slot[]; unavailable: string | null }) => (
                <div key={d.name} className="doc-slot">
                  <div className="doc-slot-head"><strong>{d.name}</strong><span className="row-sub">{d.days}, {d.hours} · {rupees(d.fee_inr)} · {d.languages}</span></div>
                  {d.unavailable ? <p className="quiet">{d.unavailable}</p> :
                    <SlotGrid slots={d.slots} value={choice?.doctor === d.name ? choice.time : undefined}
                      onPick={(s) => setChoice({ doctor: d.name, time: s.time, label: s.label, fee: d.fee_inr, room: d.room })} />}
                </div>
              ))}
              {slots.data.doctors.every((d: any) => !d.slots.length) && (
                <p className="note note-warn">Nothing free on this day. Try another date, or <Link to="/portal/waitlist">join the waitlist</Link> and we'll offer you the next cancellation.</p>
              )}
            </div>
          )}
        </section>
      )}

      {choice && (
        <section className="panel confirm" aria-labelledby="b-ok">
          <h2 id="b-ok" className="panel-h">Confirm</h2>
          <dl className="facts">
            <div><dt>With</dt><dd>{choice.doctor || target?.label}</dd></div>
            <div><dt>When</dt><dd>{longDate(date)}, {choice.label}</dd></div>
            <div><dt>Fee</dt><dd>{rupees(choice.fee)}</dd></div>
            <div><dt>Patient</dt><dd>{me.name}</dd></div>
          </dl>
          {proc && <p className="row-sub">Preparation: {proc.instructions}</p>}
          {cover && <p className="note note-info">{cover}</p>}
          <div className="field"><label htmlFor="b-reason">Reason for the visit <span className="hint">optional, helps the doctor prepare</span></label>
            <input id="b-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. knee pain for two weeks" /></div>
          <p className="error-text" role="alert">{err}</p>
          <button type="button" className="btn btn-primary token-shape" disabled={busy} onClick={confirm}>{busy ? "Booking…" : `Book ${choice.label}`}</button>
        </section>
      )}
    </div>
  );
}
