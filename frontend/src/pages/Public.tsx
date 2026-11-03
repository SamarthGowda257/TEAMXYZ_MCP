import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Clock, Mail, MapPin, Phone, Stethoscope } from "lucide-react";
import { api, rupees, type DoctorCard } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ErrorNote, Loading } from "../components/Bits";
import { ReachButtons } from "../components/Reach";
import { openChat } from "../lib/chat";
import { Icon } from "../components/Icon";
import { CENTRES, FACILITIES, HOSPITAL, MILESTONES, PACKAGES, STATS, VISITOR_INFO } from "../content";

export function PageHero({ title, lead, crumb }: { title: string; lead: ReactNode; crumb: string }) {
  return (
    <div className="page-hero">
      <div className="wrap">
        <p className="crumbs"><Link to="/">Home</Link> / {crumb}</p>
        <h1>{title}</h1>
        <p>{lead}</p>
      </div>
    </div>
  );
}

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// ------------------------------------------------------------------ doctors
export function Doctors() {
  useEffect(() => { document.title = "Find a doctor · WellNest Hospitals"; }, []);
  const [qs, setQs] = useSearchParams();
  const depts = useApi<{ name: string; doctors: number }[]>("/api/departments");
  const all = useApi<DoctorCard[]>("/api/doctors");
  const [lang, setLang] = useState("");
  const [day, setDay] = useState("");
  const [q, setQ] = useState("");
  const dept = qs.get("department") || "";
  const langs = useMemo(() => [...new Set((all.data || []).flatMap((d) => d.languages.split(", ")))].sort(), [all.data]);
  const list = useMemo(() => (all.data || []).filter((d) =>
    (!dept || d.department === dept) && (!lang || d.languages.includes(lang)) &&
    (!day || (d.day_codes || []).includes(DAYS.indexOf(day) + 1)) && (!q || d.name.toLowerCase().includes(q.toLowerCase()))), [all.data, dept, lang, day, q]);
  const initials = (n: string) => n.replace("Dr. ", "").split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <>
      <PageHero crumb="Find a doctor" title="Find a doctor"
        lead={`${all.data?.length || 45} senior consultants across ${depts.data?.length || 14} specialities. Search by name, speciality, the language you speak or the day you can visit.`} />
      <div className="wrap page">
        <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter doctors">
          <div className="field"><label htmlFor="f-q">Doctor's name</label><input id="f-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Iyer" /></div>
          <div className="field"><label htmlFor="f-dept">Speciality</label>
            <select id="f-dept" className="input" value={dept} onChange={(e) => setQs(e.target.value ? { department: e.target.value } : {})}>
              <option value="">All specialities</option>{depts.data?.map((d) => <option key={d.name}>{d.name}</option>)}</select></div>
          <div className="field"><label htmlFor="f-lang">Language</label>
            <select id="f-lang" className="input" value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="">Any language</option>{langs.map((l) => <option key={l}>{l}</option>)}</select></div>
          <div className="field"><label htmlFor="f-day">Day</label>
            <select id="f-day" className="input" value={day} onChange={(e) => setDay(e.target.value)}>
              <option value="">Any day</option>{DAYS.map((d) => <option key={d}>{d}</option>)}</select></div>
        </form>
        <p className="count" aria-live="polite">{all.data ? `Showing ${list.length} doctor${list.length === 1 ? "" : "s"}` : ""}</p>
        {all.loading && <Loading label="Loading doctors" />}
        {all.error && <ErrorNote message={all.error} onRetry={all.reload} />}
        <ul className="doc-grid">
          {list.map((d) => (
            <li key={d.code} className="doc">
              <div className="doc-avatar" aria-hidden="true">{initials(d.name)}</div>
              <div className="doc-body">
                <h2>{d.name}</h2>
                <p className="doc-dept">{d.department}</p>
                <p className="doc-meta">{d.qualification} · {d.experience_years} years experience</p>
                <dl className="doc-facts">
                  <div><dt>OPD days</dt><dd>{d.days}</dd></div>
                  <div><dt>Timings</dt><dd>{d.hours}</dd></div>
                  <div><dt>Room</dt><dd>{d.room}</dd></div>
                  <div><dt>Languages</dt><dd>{d.languages}</dd></div>
                </dl>
                <div className="doc-foot"><span>Consultation <strong>{rupees(d.fee_inr)}</strong></span>
                  <span className="row">
                    <button type="button" className="btn btn-primary btn-sm" onClick={openChat}>Chat to book</button>
                    <Link className="btn btn-quiet btn-sm" to={`/portal/book?doctor=${encodeURIComponent(d.name)}`}>Book online</Link>
                  </span></div>
              </div>
            </li>
          ))}
        </ul>
        {all.data && !list.length && <p className="empty-title">No doctor matches these filters. Try any day or another language.</p>}
      </div>
    </>
  );
}

// ------------------------------------------------------------------ insurance
type Ins = { code: string; name: string; mode: string; tpa: string; documents: string };
const MODE: Record<string, string> = { both: "Cashless and reimbursement", cashless: "Cashless", reimbursement: "Reimbursement" };

export function Insurance() {
  useEffect(() => { document.title = "Insurance & TPA · WellNest Hospitals"; }, []);
  const ins = useApi<Ins[]>("/api/insurers");
  const procs = useApi<{ code: string; name: string }[]>("/api/procedures");
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
    <>
      <PageHero crumb="Insurance & TPA" title="Insurance and cashless treatment"
        lead="We work with ten leading insurers and government schemes. Our TPA desk handles pre-approvals so you can focus on getting better." />
      <div className="wrap page ins-grid">
        <form className="ins-check" onSubmit={check}>
          <h2>Check your coverage</h2>
          <p className="muted-line">Get an instant estimate before a scan, test or consultation.</p>
          <div className="field"><label htmlFor="c-ins">Your insurer</label>
            <select id="c-ins" name="insurer" className="input" required>{ins.data?.map((i) => <option key={i.code}>{i.name}</option>)}</select></div>
          <div className="field"><label htmlFor="c-what">Test, scan or consultation</label>
            <select id="c-what" name="what" className="input" required>
              <optgroup label="Tests and scans">{procs.data?.map((p) => <option key={p.code} value={`p:${p.code}`}>{p.name}</option>)}</optgroup>
              <optgroup label="Consultations">{depts.data?.map((d) => <option key={d.name} value={`d:${d.name}`}>{d.name}</option>)}</optgroup>
            </select></div>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Checking…" : "Check coverage"}</button>
          <div aria-live="polite">
            {res && "err" in res && <p className="error-text">{res.err}</p>}
            {res && "msg" in res && (
              <div className={`ins-result cov-${res.d.covered}`}>
                <p className="ins-verdict">{res.d.covered === "yes" ? "Covered" : res.d.covered === "partial" ? "Partly covered" : "Not covered"}
                  {res.d.estimated_patient_share_inr != null && <span>Your estimated share: {rupees(res.d.estimated_patient_share_inr)}</span>}</p>
                <p>{res.msg}</p>
              </div>
            )}
          </div>
        </form>
        <div>
          <h2 className="sub-title">Empanelled insurers</h2>
          <table className="ins-table">
            <thead><tr><th scope="col">Insurer / scheme</th><th scope="col">Facility</th><th scope="col">Documents to bring</th></tr></thead>
            <tbody>{ins.data?.map((i) => <tr key={i.code}><th scope="row">{i.name}</th><td>{MODE[i.mode]}</td><td>{i.documents}</td></tr>)}</tbody>
          </table>
          <div className="info-box">
            <h3>TPA &amp; insurance desk</h3>
            <p>Ground floor, next to admissions · 080 4000 1250 · 9 AM to 6 PM, Monday to Saturday.</p>
            <p>MRI, CT, endoscopy and all planned admissions need pre-approval from your insurer. Send us your policy details at least 24 hours before and we'll raise it for you.</p>
          </div>
        </div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ contact
export function Contact() {
  useEffect(() => { document.title = "Contact us · WellNest Hospitals"; }, []);
  const info = useApi<Record<string, string>>("/api/hospital-info");
  return (
    <>
      <PageHero crumb="Contact" title="Contact us" lead="We're on Outer Ring Road in Marathahalli, next to the Innovative Multiplex. Outpatient clinics run Monday to Saturday; emergency never closes." />
      <div className="wrap page">
        <div className="contact-grid">
          <div className="contact-card">
            <h2>WellNest Hospitals</h2>
            <p><MapPin size={18} aria-hidden="true" /> {HOSPITAL.address}</p>
            <p><Phone size={18} aria-hidden="true" /> Helpline <a href={HOSPITAL.phoneHref}>{HOSPITAL.phone}</a> (24 hours)</p>
            <p><Phone size={18} aria-hidden="true" /> Ambulance <a href="tel:08040001108">{HOSPITAL.ambulance}</a></p>
            <p><Mail size={18} aria-hidden="true" /> <a href={`mailto:${HOSPITAL.email}`}>{HOSPITAL.email}</a></p>
            <p><Clock size={18} aria-hidden="true" /> OPD Mon–Sat 8 AM – 8 PM · Emergency &amp; pharmacy 24×7</p>
            <a className="btn btn-primary" href="https://www.google.com/maps/search/?api=1&query=Outer+Ring+Road+Marathahalli+Bengaluru" target="_blank" rel="noopener">Get directions</a>
          </div>
          <div className="contact-list">
            {info.error && <ErrorNote message={info.error} onRetry={info.reload} />}
            {info.data && ["emergency", "parking", "visiting", "pharmacy", "facilities"].filter((k) => info.data![k]).map((k) => (
              <section key={k} className={k === "emergency" ? "contact-item is-alert" : "contact-item"}>
                <h3>{k === "visiting" ? "Visiting hours" : k[0].toUpperCase() + k.slice(1)}</h3><p>{info.data![k]}</p>
              </section>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ about
export function About() {
  useEffect(() => { document.title = "About us · WellNest Hospitals"; }, []);
  return (
    <>
      <PageHero crumb="About us" title="About WellNest Hospitals" lead="A 350-bed multi-speciality hospital founded in 2009 to bring serious medical care closer to the families of East Bengaluru." />
      <div className="wrap page">
        <div className="about-page">
          <div className="prose">
            <h2>Our story</h2>
            <p>WellNest Hospitals began as a 120-bed hospital on Outer Ring Road, started by a group of doctors who were tired of seeing patients from Marathahalli, Whitefield and Bellandur spend hours in traffic to reach a hospital for a heart attack, a difficult delivery or a stroke.</p>
            <p>Seventeen years later we are a 350-bed hospital with 14 specialities, 60 critical-care beds, a 24-hour cath lab and a level III neonatal ICU. More than 1,200 people visit our outpatient clinics every day.</p>
            <h2>Our mission</h2>
            <p>To give every patient the right care at the right time, explained clearly and priced fairly, with dignity for patients of every age.</p>
            <h2>How we work</h2>
            <ul className="check-list">
              <li><CheckCircle2 size={20} aria-hidden="true" /> Multi-disciplinary teams meet daily for every admitted patient.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> Every inpatient has a named nurse and a named consultant.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> Prices for consultations, scans and packages are published on this website.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> Our AI front desk answers chat and phone 24 hours, and hands over to a person whenever you ask.</li>
            </ul>
          </div>
          <aside className="about-side">
            <div className="stat-box">{STATS.map((s) => <div key={s.label}><strong>{s.value}</strong><span>{s.label}</span></div>)}</div>
            <div className="timeline">
              <h2>Milestones</h2>
              <ol>{MILESTONES.map((m) => <li key={m.year}><strong>{m.year}</strong><span>{m.text}</span></li>)}</ol>
            </div>
          </aside>
        </div>
        <h2 className="sub-title">Facilities</h2>
        <div className="fac-grid">{FACILITIES.map((f) => (
          <div key={f.title} className="fac"><span className="fac-icon"><Icon name={f.icon} size={26} /></span><div><h3>{f.title}</h3><p>{f.text}</p></div></div>
        ))}</div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ specialities
export function Specialities() {
  useEffect(() => { document.title = "Specialities · WellNest Hospitals"; }, []);
  const { hash } = useLocation();
  const depts = useApi<{ name: string; description: string; floor: string; doctors: number }[]>("/api/departments");
  const docs = useApi<DoctorCard[]>("/api/doctors");
  useEffect(() => { if (hash) window.setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), 300); }, [hash, depts.data]);
  return (
    <>
      <PageHero crumb="Specialities" title="Specialities and centres of excellence"
        lead="Fourteen departments and six centres of excellence, with senior consultants, modern operating theatres and critical care on site." />
      <div className="wrap page">
        <div className="spec-centres">
          {CENTRES.map((c) => {
            const team = (docs.data || []).filter((d) => d.department === c.dept);
            return (
              <section key={c.key} id={c.key} className="spec-centre">
                <div className="spec-head"><span className="centre-icon"><Icon name={c.icon} size={28} /></span><div><h2>{c.name}</h2><p className="doc-dept">{c.dept}</p></div></div>
                <p>{c.summary}</p>
                <ul className="spec-treats">{c.treats.map((t) => <li key={t}><CheckCircle2 size={18} aria-hidden="true" />{t}</li>)}</ul>
                {team.length > 0 && <p className="spec-team"><Stethoscope size={18} aria-hidden="true" /> {team.map((d) => d.name).join(", ")}</p>}
                <div className="row">
                  <button type="button" className="btn btn-primary btn-sm" onClick={openChat}>Chat to book</button>
                  <Link className="btn btn-quiet btn-sm" to={`/doctors?department=${encodeURIComponent(c.dept)}`}>See doctors</Link>
                </div>
              </section>
            );
          })}
        </div>
        <h2 className="sub-title">All departments</h2>
        {depts.loading && <Loading />}
        <div className="dept-table">
          {depts.data?.map((d) => (
            <Link key={d.name} to={`/doctors?department=${encodeURIComponent(d.name)}`} className="dept-row">
              <strong>{d.name}</strong><span>{d.description}</span><span className="dept-meta">{d.doctors} doctors · {d.floor}</span><ArrowRight size={18} aria-hidden="true" />
            </Link>
          ))}
        </div>
        <h2 className="sub-title" id="packages">Health check-up packages</h2>
        <div className="pk-grid">
          {PACKAGES.map((p, i) => (
            <div key={p.code} className={i === 1 ? "pk pk-main" : "pk"}>
              <h3>{p.name}</h3><p className="pk-price">{rupees(p.price)} <span>{p.tests}</span></p>
              <ul>{p.items.map((it) => <li key={it}><CheckCircle2 size={18} aria-hidden="true" />{it}</li>)}</ul>
              <button type="button" className={i === 1 ? "btn btn-primary" : "btn btn-quiet"} onClick={openChat}>Book with the assistant</button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ patients & visitors
export function Visitors() {
  useEffect(() => { document.title = "Patients & visitors · WellNest Hospitals"; }, []);
  return (
    <>
      <PageHero crumb="Patients & visitors" title="Patients and visitors" lead="Everything you need to know before your visit: timings, what to bring, parking, visiting rules and your rights as a patient." />
      <div className="wrap page">
        <div className="assist-banner"><div><h2 className="serif">Book, move or cancel a visit in one conversation</h2><p>Our AI assistant on Talkdesk answers the website chat and our phone line 24 hours.</p></div><ReachButtons /></div>
        <div className="visit-cards">{VISITOR_INFO.map((v) => <section key={v.title} className="contact-item"><h3>{v.title}</h3><p>{v.text}</p></section>)}</div>
        <div className="two-col">
          <div className="prose">
            <h2>Your outpatient visit, step by step</h2>
            <ol className="steps-list">
              <li><strong>Book ahead</strong> online, on chat or by phone. You'll get a booking ID by email and SMS.</li>
              <li><strong>Arrive 15 minutes early</strong> at the ground-floor registration desk with photo ID and old reports.</li>
              <li><strong>Pay or show your insurance card</strong> at the billing counter. Cashless insurers are verified on the spot.</li>
              <li><strong>See your doctor</strong> in the room on your booking. Tests are done the same day where possible.</li>
              <li><strong>Get your reports online</strong> in your portal, or ask the assistant to email them.</li>
            </ol>
          </div>
          <div className="prose">
            <h2>Patient rights and responsibilities</h2>
            <ul className="check-list">
              <li><CheckCircle2 size={20} aria-hidden="true" /> To be treated with dignity, privacy and without discrimination.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> To know the cost of treatment in advance and receive an itemised bill.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> To see and receive copies of your medical records.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> To a second opinion and to refuse treatment after being informed.</li>
              <li><CheckCircle2 size={20} aria-hidden="true" /> To share accurate history and follow hospital safety rules.</li>
            </ul>
            <div className="info-box"><h3>Senior citizen desk</h3><p>At entrance B: wheelchair help, priority registration and billing, and a staff member to walk you to your doctor. Ask for it when you book.</p></div>
          </div>
        </div>
      </div>
    </>
  );
}
