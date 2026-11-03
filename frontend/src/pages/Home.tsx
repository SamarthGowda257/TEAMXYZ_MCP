import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, CalendarCheck, CheckCircle2, ClipboardList, FileText, MessageCircle, Phone, Quote, Search, ShieldCheck,
  Siren, Stethoscope } from "lucide-react";
import { api, istDay, rupees, shortDate, type DoctorCard } from "../lib/api";
import { useApi, useReveal } from "../lib/hooks";
import { openChat } from "../lib/chat";
import { HospitalArt } from "../components/HospitalArt";
import { Icon } from "../components/Icon";
import { CENTRES, FACILITIES, HOSPITAL, PACKAGES, STATS, STORIES, TIPS } from "../content";

// ------------------------------------------------------------------ hero with quick appointment
const DEPTS = ["Cardiology", "Orthopaedics", "General Medicine", "Paediatrics", "Gynaecology & Obstetrics", "Dermatology", "ENT",
  "Neurology", "Ophthalmology", "Gastroenterology", "Pulmonology", "Endocrinology", "Nephrology"];
type Next = { doctor: string; date: string; label: string; fee: number; time: string } | null;

async function nextFree(dept: string, from: number): Promise<Next> {
  for (let off = from; off < from + 5; off++) {
    const r = await api<any>(`/api/slots?date=${istDay(off)}&department=${encodeURIComponent(dept)}`);
    let best: Next = null;
    for (const d of r.doctors) {
      const s = d.slots[0];
      if (s && (!best || s.time < best.time)) best = { doctor: d.name, date: r.date_iso, label: s.label, fee: d.fee_inr, time: s.time };
    }
    if (best) return best;
  }
  return null;
}

function Hero() {
  const nav = useNavigate();
  const [dept, setDept] = useState("Cardiology");
  const [day, setDay] = useState("0");
  const [res, setRes] = useState<Next | "none" | "loading" | "error" | undefined>();
  async function check(e: FormEvent) {
    e.preventDefault();
    setRes("loading");
    try { const n = await nextFree(dept, Number(day)); setRes(n || "none"); } catch { setRes("error"); }
  }
  return (
    <section className="hero">
      <div className="wrap hero-in">
        <div className="hero-copy">
          <p className="hero-kicker"><ShieldCheck size={18} aria-hidden="true" /> Trusted multi-speciality care in Marathahalli since 2009</p>
          <h1>Expert doctors. Gentle care. Close to home.</h1>
          <p className="hero-lead">CareLine Hospitals brings 45 senior specialists, 24-hour emergency care and advanced diagnostics together under one roof, and lets you book, reschedule or get your reports in a minute by chat, phone or online.</p>
          <div className="hero-actions">
            <Link className="btn btn-primary" to="/portal/book"><CalendarCheck size={18} aria-hidden="true" /> Book appointment</Link>
            <Link className="btn btn-quiet" to="/doctors"><Search size={18} aria-hidden="true" /> Find a doctor</Link>
          </div>
          <ul className="hero-points">
            <li><CheckCircle2 size={18} aria-hidden="true" /> 10 insurers, mostly cashless</li>
            <li><CheckCircle2 size={18} aria-hidden="true" /> Reports online the same day</li>
            <li><CheckCircle2 size={18} aria-hidden="true" /> Senior citizen desk</li>
          </ul>
        </div>
        <div className="hero-visual">
          <HospitalArt />
          <form className="quick-card" onSubmit={check} aria-labelledby="qa-h">
            <h2 id="qa-h">Quick appointment</h2>
            <div className="qa-row">
              <div className="field"><label htmlFor="qa-dept">Speciality</label>
                <select id="qa-dept" className="input" value={dept} onChange={(e) => { setDept(e.target.value); setRes(undefined); }}>
                  {DEPTS.map((d) => <option key={d}>{d}</option>)}</select></div>
              <div className="field"><label htmlFor="qa-day">From</label>
                <select id="qa-day" className="input" value={day} onChange={(e) => { setDay(e.target.value); setRes(undefined); }}>
                  <option value="0">Today</option><option value="1">Tomorrow</option><option value="3">In 3 days</option><option value="7">Next week</option></select></div>
            </div>
            <div aria-live="polite" className="qa-result">
              {res === "loading" && <p className="muted-line">Checking the OPD schedule…</p>}
              {res === "error" && <p className="error-text">Couldn't check right now. Please try again.</p>}
              {res === "none" && <p>Fully booked for these days. <Link to="/portal/waitlist">Join the waitlist</Link> and we'll message you when a slot opens.</p>}
              {res && typeof res === "object" && (
                <div className="qa-found">
                  <p><strong>{res.doctor}</strong><br />{shortDate(res.date)} at {res.label} · Consultation {rupees(res.fee)}</p>
                  <button type="button" className="btn btn-primary btn-sm"
                    onClick={() => nav(`/portal/book?doctor=${encodeURIComponent(res.doctor)}&date=${res.date}&time=${res.time}`)}>Book this slot</button>
                </div>
              )}
            </div>
            {(!res || res === "error") && <button className="btn btn-primary qa-btn">Check earliest slot <ArrowRight size={18} aria-hidden="true" /></button>}
          </form>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ quick links
function QuickLinks() {
  const items = [
    { to: "/portal/book", icon: CalendarCheck, title: "Book an appointment", text: "Choose a doctor, day and time" },
    { to: "/doctors", icon: Stethoscope, title: "Find a doctor", text: "45 specialists, 8 languages" },
    { to: "/portal/reports", icon: FileText, title: "Lab reports", text: "View or email your results" },
    { to: "/specialities#packages", icon: ClipboardList, title: "Health check-ups", text: "Packages from ₹2,499" },
  ];
  return (
    <section className="quick-links" aria-label="Quick links">
      <div className="wrap ql-grid">
        {items.map(({ to, icon: I, title, text }) => (
          <Link key={title} to={to} className="ql"><span className="ql-icon"><I size={24} aria-hidden="true" /></span><span><strong>{title}</strong><small>{text}</small></span></Link>
        ))}
        <a href="tel:108" className="ql ql-alert"><span className="ql-icon"><Siren size={24} aria-hidden="true" /></span><span><strong>Emergency 24×7</strong><small>Call 108 or come to entrance B</small></span></a>
      </div>
    </section>
  );
}

function Stats() {
  return (
    <section className="stats" aria-label="CareLine in numbers">
      <div className="wrap stats-grid">
        {STATS.map((s) => <div key={s.label} className="stat"><strong>{s.value}</strong><span>{s.label}</span></div>)}
      </div>
    </section>
  );
}

function About() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section" ref={ref} aria-labelledby="about-h">
      <div className="wrap about-grid">
        <div className="rise">
          <p className="section-label">About CareLine</p>
          <h2 id="about-h">A neighbourhood hospital with the depth of a medical centre</h2>
          <p className="section-lead">CareLine Hospitals opened on Outer Ring Road in 2009 with one promise: that families in East Bengaluru should not have to cross the city for serious care. Today our 350-bed hospital treats more than 1,200 outpatients every day across 14 specialities.</p>
          <p>Our doctors work in teams around the patient: a cardiologist, physician and dietitian review a heart patient together, and every admitted patient has a named nurse. We publish our prices, explain insurance before treatment, and keep you informed in the language you are most comfortable with.</p>
          <Link className="text-link" to="/about">More about our hospital <ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
        <ul className="value-list rise" style={{ ["--d" as string]: "100ms" }}>
          <li><strong>Patient first</strong><span>Clear explanations, published prices and no unnecessary tests.</span></li>
          <li><strong>Safe by design</strong><span>Identity checks before every change to your booking or records.</span></li>
          <li><strong>Always reachable</strong><span>An AI front desk on chat and phone 24 hours, with a person a tap away.</span></li>
          <li><strong>Care for every age</strong><span>Paediatric, adult and dedicated senior citizen services.</span></li>
        </ul>
      </div>
    </section>
  );
}

function Centres() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section tinted" ref={ref} aria-labelledby="centres-h">
      <div className="wrap">
        <div className="section-head">
          <div><p className="section-label">Centres of excellence</p><h2 id="centres-h">Specialised care, led by senior consultants</h2></div>
          <Link className="btn btn-quiet btn-sm" to="/specialities">All 14 specialities</Link>
        </div>
        <div className="centre-grid">
          {CENTRES.map((c, i) => (
            <Link key={c.key} to={`/specialities#${c.key}`} className="centre rise" style={{ ["--d" as string]: `${i * 60}ms` }}>
              <span className="centre-icon"><Icon name={c.icon} size={28} /></span>
              <h3>{c.name}</h3>
              <p>{c.summary}</p>
              <span className="centre-more">Learn more <ArrowRight size={16} aria-hidden="true" /></span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

function Facilities() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section" ref={ref} aria-labelledby="fac-h">
      <div className="wrap">
        <div className="section-head"><div><p className="section-label">Facilities</p><h2 id="fac-h">Everything you need, under one roof</h2></div></div>
        <div className="fac-grid">
          {FACILITIES.map((f, i) => (
            <div key={f.title} className="fac rise" style={{ ["--d" as string]: `${i * 60}ms` }}>
              <span className="fac-icon"><Icon name={f.icon} size={26} /></span>
              <div><h3>{f.title}</h3><p>{f.text}</p></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FrontDesk() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section tinted" ref={ref} aria-labelledby="fd-h">
      <div className="wrap fd-grid">
        <div className="rise">
          <p className="section-label">Patient services</p>
          <h2 id="fd-h">Our front desk never closes</h2>
          <p className="section-lead">Talk to the CareLine Assistant on our website chat or on the phone, at any hour. It books with real doctors' schedules, never gives medical advice, and passes you to a person whenever you ask.</p>
          <ul className="check-list">
            <li><CheckCircle2 size={20} aria-hidden="true" /> Book, reschedule or cancel, after checking your mobile number and date of birth</li>
            <li><CheckCircle2 size={20} aria-hidden="true" /> Fully booked? Join the waitlist and get the next cancelled slot within minutes</li>
            <li><CheckCircle2 size={20} aria-hidden="true" /> Ask if your lab report is ready and have it emailed securely</li>
            <li><CheckCircle2 size={20} aria-hidden="true" /> Check what your insurance covers before an MRI or CT</li>
            <li><CheckCircle2 size={20} aria-hidden="true" /> Chest pain or breathlessness? It tells you to call 108 and connects a staff member at once</li>
          </ul>
          <div className="hero-actions">
            <button type="button" className="btn btn-primary" onClick={openChat}><MessageCircle size={18} aria-hidden="true" /> Chat with us</button>
            <a className="btn btn-quiet" href={HOSPITAL.phoneHref}><Phone size={18} aria-hidden="true" /> {HOSPITAL.phone}</a>
          </div>
        </div>
        <div className="chat-demo rise" style={{ ["--d" as string]: "120ms" }} aria-label="Example conversation">
          <div className="cd-head"><span className="cd-dot" aria-hidden="true" /> CareLine Assistant · online</div>
          <p className="msg me">I need a heart doctor on Wednesday morning.</p>
          <p className="msg bot">Sure. On Wednesday 4 November, Dr. Rajesh Iyer is free at 10:00 AM and 11:15 AM. The consultation fee is 1,200 rupees. Which time suits you?</p>
          <p className="msg me">10 AM please. My number is 98450 00001.</p>
          <p className="msg bot">Booked. Dr. Rajesh Iyer, Wednesday 4 November at 10:00 AM, room OPD-310. Your booking ID is CL-48213. A confirmation is on its way by email.</p>
        </div>
      </div>
    </section>
  );
}

const FEATURED = ["Dr. Rajesh Iyer", "Dr. Kavya Reddy", "Dr. Kiran Shetty", "Dr. Lakshmi Nair"];

function Doctors() {
  const { data } = useApi<DoctorCard[]>("/api/doctors");
  const ref = useReveal<HTMLElement>();
  const docs = (data || []).filter((d) => FEATURED.includes(d.name));
  const initials = (n: string) => n.replace("Dr. ", "").split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <section className="section" ref={ref} aria-labelledby="doc-h">
      <div className="wrap">
        <div className="section-head">
          <div><p className="section-label">Our doctors</p><h2 id="doc-h">Meet some of our specialists</h2></div>
          <Link className="btn btn-quiet btn-sm" to="/doctors">View all doctors</Link>
        </div>
        <div className="doc-feature">
          {docs.map((d, i) => (
            <article key={d.name} className="doc-card rise" style={{ ["--d" as string]: `${i * 60}ms` }}>
              <div className="doc-photo" aria-hidden="true"><span>{initials(d.name)}</span><Stethoscope size={22} /></div>
              <h3>{d.name}</h3>
              <p className="doc-dept">{d.department}</p>
              <p className="doc-qual">{d.qualification} · {d.experience_years} years</p>
              <p className="doc-time">{d.days}<br />{d.hours}</p>
              <Link className="btn btn-quiet btn-sm" to={`/portal/book?doctor=${encodeURIComponent(d.name)}`}>Book appointment</Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function Packages() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section tinted" ref={ref} aria-labelledby="pk-h" id="packages">
      <div className="wrap">
        <div className="section-head"><div><p className="section-label">Preventive health</p><h2 id="pk-h">Health check-up packages</h2></div></div>
        <div className="pk-grid">
          {PACKAGES.map((p, i) => (
            <div key={p.code} className={i === 1 ? "pk pk-main rise" : "pk rise"} style={{ ["--d" as string]: `${i * 80}ms` }}>
              <h3>{p.name}</h3>
              <p className="pk-price">{rupees(p.price)} <span>{p.tests}</span></p>
              <ul>{p.items.map((it) => <li key={it}><CheckCircle2 size={18} aria-hidden="true" />{it}</li>)}</ul>
              <Link className={i === 1 ? "btn btn-primary" : "btn btn-quiet"} to="/portal/book">Book this check-up</Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Stories() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section" ref={ref} aria-labelledby="st-h">
      <div className="wrap">
        <div className="section-head"><div><p className="section-label">Patient stories</p><h2 id="st-h">What our patients say</h2></div></div>
        <div className="story-grid">
          {STORIES.map((s, i) => (
            <figure key={s.name} className="story rise" style={{ ["--d" as string]: `${i * 80}ms` }}>
              <Quote size={28} aria-hidden="true" />
              <blockquote>{s.text}</blockquote>
              <figcaption><strong>{s.name}</strong><span>{s.place} · {s.dept}</span></figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

function Tips() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section tinted" ref={ref} aria-labelledby="tp-h">
      <div className="wrap">
        <div className="section-head"><div><p className="section-label">Health library</p><h2 id="tp-h">Health tips from our doctors</h2></div></div>
        <div className="tip-grid">
          {TIPS.map((t, i) => (
            <article key={t.title} className="tip rise" style={{ ["--d" as string]: `${i * 80}ms` }}>
              <span className="tip-tag">{t.tag}</span><h3>{t.title}</h3><p>{t.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const FAQ = [
  ["How do I book an appointment?", "Book online in under a minute, chat with the CareLine Assistant on this site, or call 080 4000 1234 at any hour. You'll get a booking ID and an email confirmation."],
  ["Can someone else cancel my appointment?", "No. Cancelling or moving a visit needs your registered mobile number and your date of birth, checked by the hospital system."],
  ["Which insurance do you accept?", "Star Health, HDFC ERGO, ICICI Lombard, Niva Bupa, Care Health, Aditya Birla, Tata AIG, Bajaj Allianz, CGHS and ECHS. Most are cashless; our TPA desk handles pre-approvals."],
  ["How do I get my lab report?", "Most reports are ready the same day. Log in to see them with normal ranges, or ask the assistant to email a summary to your registered address."],
  ["Is the emergency department open at night?", "Yes, 24 hours, every day, at entrance B. For a life-threatening emergency call 108 first."],
];

function Faq() {
  return (
    <section className="section" aria-labelledby="faq-h">
      <div className="wrap faq-grid">
        <div><p className="section-label">Questions</p><h2 id="faq-h">Frequently asked questions</h2>
          <p className="section-lead">Can't find your answer? Chat with us or call {HOSPITAL.phone}.</p></div>
        <div className="faq-list">
          {FAQ.map(([q, a], i) => (
            <details key={q} name="faq" open={i === 0} className="faq-item">
              <summary>{q}<i aria-hidden="true" /></summary><p>{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function Callback() {
  const [state, setState] = useState<{ ok?: string; err?: string; busy?: boolean }>({});
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setState({ busy: true });
    try {
      const r = await api<any>("/api/callback", { method: "POST", body: Object.fromEntries(new FormData(form).entries()) });
      setState({ ok: r.message }); form.reset();
    } catch (err: any) { setState({ err: err.message }); }
  }
  return (
    <section className="section callback" aria-labelledby="cb-h">
      <div className="wrap cb-grid">
        <div>
          <h2 id="cb-h">Request a call back</h2>
          <p className="section-lead">Questions about surgery costs, admissions or a second opinion? Leave your number and our patient care team will call you, Monday to Saturday, 8 AM to 8 PM.</p>
        </div>
        <form className="cb-form" onSubmit={submit} noValidate>
          <div className="field"><label htmlFor="cb-name">Your name</label><input id="cb-name" name="name" className="input" autoComplete="name" /></div>
          <div className="field"><label htmlFor="cb-phone">Mobile number</label><input id="cb-phone" name="phone" className="input" inputMode="tel" autoComplete="tel" required /></div>
          <div className="field"><label htmlFor="cb-time">Best time to call</label>
            <select id="cb-time" name="preferred_time" className="input" defaultValue="Today, as soon as possible">
              <option>Today, as soon as possible</option><option>Tomorrow morning</option><option>Tomorrow afternoon</option><option>After 6 PM</option></select></div>
          <div className="field"><label htmlFor="cb-reason">What is it about?</label><input id="cb-reason" name="reason" className="input" placeholder="e.g. knee replacement cost" /></div>
          <button className="btn btn-primary" disabled={state.busy}>{state.busy ? "Sending…" : "Request call back"}</button>
          <p className={state.err ? "error-text" : "ok-text"} aria-live="polite">{state.ok || state.err}</p>
        </form>
      </div>
    </section>
  );
}

export default function Home() {
  useEffect(() => { document.title = "CareLine Hospitals, Bengaluru · Multi-speciality hospital in Marathahalli"; }, []);
  return (
    <>
      <Hero />
      <QuickLinks />
      <Stats />
      <About />
      <Centres />
      <Facilities />
      <FrontDesk />
      <Doctors />
      <Packages />
      <Stories />
      <Tips />
      <Faq />
      <Callback />
    </>
  );
}
