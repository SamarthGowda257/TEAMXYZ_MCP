import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { HeartPulse } from "lucide-react";
import { api } from "../lib/api";

type Visit = { first_name: string; with: string; department: string; date: string };

/** Post-visit check-in, opened from the day-2 email link (signed, expiring token; no login needed). */
export function Checkin() {
  const [qs] = useSearchParams();
  const t = qs.get("t") || "";
  const [visit, setVisit] = useState<Visit | null>(null);
  const [err, setErr] = useState("");
  const [pain, setPain] = useState(2);
  const [fever, setFever] = useState("no");
  const [worse, setWorse] = useState("no");
  const [notes, setNotes] = useState("");
  const [done, setDone] = useState<{ msg: string; alert: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    document.title = "How are you feeling? · WellNest Hospitals";
    if (!t) { setErr("This link is incomplete. Please open it again from your email."); return; }
    api<Visit>(`/api/checkin/${encodeURIComponent(t)}`).then(setVisit).catch((e) => setErr(e.message));
  }, [t]);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const r = await api<any>(`/api/checkin/${encodeURIComponent(t)}`, { method: "POST",
        body: { pain_score: String(pain), fever, symptoms_worse: worse, notes } });
      setDone({ msg: r.message, alert: !!r.data?.alert_raised });
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="accept">
      <div className="accept-card">
        {done ? (
          <>
            <h1>{done.alert ? "A nurse will call you." : "Thank you."}</h1>
            <p className={done.alert ? "note note-warn" : ""}>{done.msg}</p>
            <Link className="btn btn-quiet" to="/">Back to WellNest</Link>
          </>
        ) : visit ? (
          <form onSubmit={submit} className="checkin">
            <HeartPulse size={32} aria-hidden="true" className="ci-icon" />
            <h1>{visit.first_name}, how are you feeling?</h1>
            <p>After your visit with {visit.with} ({visit.department}) on {visit.date}. It takes 30 seconds; a nurse reads every answer that needs attention.</p>
            <div className="field">
              <label htmlFor="pain">Pain right now: <strong>{pain}</strong> / 10</label>
              <input id="pain" type="range" min={0} max={10} value={pain} onChange={(e) => setPain(Number(e.target.value))} className="ci-range" />
              <div className="ci-scale" aria-hidden="true"><span>No pain</span><span>Worst</span></div>
            </div>
            <fieldset className="ci-q"><legend>Do you have a fever?</legend>
              {["no", "yes"].map((v) => <label key={v} className="check"><input type="radio" name="fever" value={v} checked={fever === v} onChange={() => setFever(v)} />{v === "yes" ? "Yes" : "No"}</label>)}
            </fieldset>
            <fieldset className="ci-q"><legend>Are your symptoms worse than at the visit?</legend>
              {["no", "yes"].map((v) => <label key={v} className="check"><input type="radio" name="worse" value={v} checked={worse === v} onChange={() => setWorse(v)} />{v === "yes" ? "Yes" : "No"}</label>)}
            </fieldset>
            <div className="field"><label htmlFor="notes">Anything else? <span className="hint">optional</span></label>
              <textarea id="notes" className="input" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={300} /></div>
            <p className="error-text" role="alert">{err}</p>
            <button className="btn btn-primary" disabled={busy}>{busy ? "Sending…" : "Send to my care team"}</button>
            <p className="hint">Feeling much worse, chest pain or trouble breathing? Don't wait: call 108.</p>
          </form>
        ) : err ? (<><h1>We couldn't open this check-in.</h1><p className="error-text">{err}</p><Link to="/">Back to WellNest</Link></>)
          : <p>Opening your check-in…</p>}
      </div>
    </div>
  );
}
