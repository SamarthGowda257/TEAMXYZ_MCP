import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MapPin } from "lucide-react";
import { api, rupees, type DoctorCard } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ErrorNote, Loading } from "../components/Bits";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const FIELD = (s: string) => `var(--field-${(s.charCodeAt(4) % 4) + 1})`;

export function Doctors() {
  useEffect(() => { document.title = "Doctors · CareLine Hospitals"; }, []);
  const [qs, setQs] = useSearchParams();
  const depts = useApi<{ name: string; doctors: number; description: string }[]>("/api/departments");
  const all = useApi<DoctorCard[]>("/api/doctors");
  const [lang, setLang] = useState("");
  const [day, setDay] = useState("");
  const dept = qs.get("department") || "";
  const langs = useMemo(() => [...new Set((all.data || []).flatMap((d) => d.languages.split(", ")))].sort(), [all.data]);
  const list = useMemo(() => (all.data || []).filter((d) =>
    (!dept || d.department === dept) && (!lang || d.languages.includes(lang)) &&
    (!day || (d.day_codes || []).includes(DAYS.indexOf(day) + 1))), [all.data, dept, lang, day]);
  const initials = (n: string) => n.replace("Dr. ", "").split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <div className="page">
      <div className="page-head">
        <h1>Our doctors</h1>
        <p>{all.data ? `${all.data.length} specialists` : "Specialists"} across {depts.data?.length || 14} departments. Filter by the language you speak or the day you can come in.</p>
      </div>
      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter doctors">
        <div className="field"><label htmlFor="f-dept">Department</label>
          <select id="f-dept" className="input" value={dept} onChange={(e) => setQs(e.target.value ? { department: e.target.value } : {})}>
            <option value="">All departments</option>{depts.data?.map((d) => <option key={d.name}>{d.name}</option>)}
          </select></div>
        <div className="field"><label htmlFor="f-lang">Language</label>
          <select id="f-lang" className="input" value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="">Any language</option>{langs.map((l) => <option key={l}>{l}</option>)}
          </select></div>
        <div className="field"><label htmlFor="f-day">Day</label>
          <select id="f-day" className="input" value={day} onChange={(e) => setDay(e.target.value)}>
            <option value="">Any day</option>{DAYS.map((d) => <option key={d}>{d}</option>)}
          </select></div>
      </form>
      <p className="count" aria-live="polite">{all.data ? `${list.length} doctor${list.length === 1 ? "" : "s"}` : ""}</p>
      {all.loading && <Loading label="Loading doctors" />}
      {all.error && <ErrorNote message={all.error} onRetry={all.reload} />}
      <ul className="doc-grid">
        {list.map((d) => (
          <li key={d.code} className="doc">
            <span className="doc-initials token-shape" style={{ background: FIELD(d.name) }} aria-hidden="true">{initials(d.name)}</span>
            <div className="doc-body">
              <h2>{d.name}</h2>
              <p className="doc-meta">{d.department} · {d.qualification} · {d.experience_years} years</p>
              <p className="doc-when"><strong>{d.days}</strong>, {d.hours} · Room {d.room}</p>
              <p className="doc-meta">Speaks {d.languages}</p>
              <div className="doc-foot"><span className="doc-fee">{rupees(d.fee_inr)}</span>
                <Link className="btn btn-primary btn-sm token-shape" to={`/portal/book?doctor=${encodeURIComponent(d.name)}`}>Book</Link></div>
            </div>
          </li>
        ))}
      </ul>
      {all.data && !list.length && <p className="empty-title">No doctor matches all three filters. Try any day, or another language.</p>}
    </div>
  );
}

type Ins = { code: string; name: string; mode: string; tpa: string; documents: string };
type Proc = { code: string; name: string };
const MODE: Record<string, string> = { both: "Cashless or reimbursement", cashless: "Cashless", reimbursement: "Reimbursement" };

export function Insurance() {
  useEffect(() => { document.title = "Insurance · CareLine Hospitals"; }, []);
  const ins = useApi<Ins[]>("/api/insurers");
  const procs = useApi<Proc[]>("/api/procedures");
  const depts = useApi<{ name: string }[]>("/api/departments");
  const [res, setRes] = useState<{ msg: string; d: any } | { err: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function check(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const what = String(f.get("what") || "");
    setBusy(true);
    try {
      const r = await api<any>("/api/coverage/estimate", { method: "POST", body: { insurer: f.get("insurer"),
        procedure: what.startsWith("p:") ? what.slice(2) : "", department: what.startsWith("d:") ? what.slice(2) : "" } });
      setRes({ msg: r.message, d: r.data });
    } catch (err: any) { setRes({ err: err.message }); } finally { setBusy(false); }
  }
  return (
    <div className="page">
      <div className="page-head">
        <h1>Insurance, before the bill</h1>
        <p>Ten insurers, most of them cashless. Check what your plan pays for a scan or a consultation, and whether it needs pre-approval.</p>
      </div>
      <div className="ins-grid">
        <form className="ins-check token-shape" onSubmit={check}>
          <h2>What will I pay?</h2>
          <div className="field"><label htmlFor="c-ins">Insurer</label>
            <select id="c-ins" name="insurer" className="input" required>{ins.data?.map((i) => <option key={i.code}>{i.name}</option>)}</select></div>
          <div className="field"><label htmlFor="c-what">Test, scan or consultation</label>
            <select id="c-what" name="what" className="input" required>
              <optgroup label="Tests and scans">{procs.data?.map((p) => <option key={p.code} value={`p:${p.code}`}>{p.name}</option>)}</optgroup>
              <optgroup label="Consultations">{depts.data?.map((d) => <option key={d.name} value={`d:${d.name}`}>{d.name}</option>)}</optgroup>
            </select></div>
          <button className="btn btn-primary token-shape" disabled={busy}>{busy ? "Checking…" : "Check coverage"}</button>
          <div aria-live="polite">
            {res && "err" in res && <p className="error-text">{res.err}</p>}
            {res && "msg" in res && (
              <div className="ins-result">
                <p className="ins-verdict">{res.d.covered === "yes" ? "Covered" : res.d.covered === "partial" ? "Partly covered" : "Not covered"}
                  {res.d.estimated_patient_share_inr != null && <span>You pay about {rupees(res.d.estimated_patient_share_inr)}</span>}</p>
                <p>{res.msg}</p>
              </div>
            )}
          </div>
        </form>
        <div className="ins-table-wrap">
          <h2>Accepted insurers</h2>
          <table className="ins-table">
            <thead><tr><th scope="col">Insurer</th><th scope="col">How it works</th><th scope="col">Bring</th></tr></thead>
            <tbody>{ins.data?.map((i) => <tr key={i.code}><th scope="row">{i.name}</th><td>{MODE[i.mode]}</td><td>{i.documents}</td></tr>)}</tbody>
          </table>
          <p className="muted-note">Insurance desk: 080 4000 1250, 9 AM to 6 PM, Monday to Saturday. MRI, CT and endoscopy usually need pre-approval; the desk raises it for you, often within 24 hours.</p>
        </div>
      </div>
    </div>
  );
}

const TITLES: Record<string, string> = { address: "Address", hours: "Opening hours", contact: "Phone and email", emergency: "Emergency",
  parking: "Parking", visiting: "Visiting hours", pharmacy: "Pharmacy", facilities: "Facilities" };

export function Contact() {
  useEffect(() => { document.title = "Visit us · CareLine Hospitals"; }, []);
  const info = useApi<Record<string, string>>("/api/hospital-info");
  return (
    <div className="page">
      <div className="page-head">
        <h1>Visit CareLine</h1>
        <p>On Outer Ring Road in Marathahalli, next to the multiplex. Outpatient clinics run Monday to Saturday; emergency never closes.</p>
      </div>
      {info.error && <ErrorNote message={info.error} onRetry={info.reload} />}
      <div className="visit-grid">
        <a className="visit-map token-shape" href="https://www.google.com/maps/search/?api=1&query=Outer+Ring+Road+Marathahalli+Bengaluru" target="_blank" rel="noopener">
          <MapPin size={28} aria-hidden="true" /><strong>42 Outer Ring Road, Marathahalli</strong><span>Open directions in Google Maps</span>
        </a>
        {info.data && Object.keys(TITLES).filter((k) => info.data![k]).map((k) => (
          <section key={k} className={k === "emergency" ? "visit-card is-alert" : "visit-card"}>
            <h2>{TITLES[k]}</h2><p>{info.data![k]}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
