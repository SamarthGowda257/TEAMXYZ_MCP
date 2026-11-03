import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowUpRight, BellRing, CalendarCheck, CheckCircle2, FileText, Languages, MessageCircle, PhoneCall,
  ShieldCheck, Siren, Sparkles, Stethoscope, UserRoundCheck } from "lucide-react";
import { api, rupees, type DoctorCard } from "../lib/api";
import { useApi, useReveal } from "../lib/hooks";
import { openChat, voiceNumber } from "../lib/chat";
import { Icon } from "../components/Icon";
import { Photo } from "../components/Photo";
import { ReachButtons } from "../components/Reach";
import { CENTRES, CENTRE_IMAGES, FACILITIES, HOSPITAL, IMAGES, PACKAGES, STATS, STORIES, TIPS } from "../content";

// ------------------------------------------------------------------ hero: the conversation is the booking
const SCRIPT: { who: "me" | "bot"; text: string }[] = [
  { who: "me", text: "Hi, I need a heart doctor this Wednesday morning." },
  { who: "bot", text: "Dr. Rajesh Iyer, Cardiology, is free on Wednesday 4 November at 10:00 AM and 11:15 AM. The fee is ₹1,200. Which suits you?" },
  { who: "me", text: "10 AM please. 98450 00001, born 4 March 1959." },
  { who: "bot", text: "Thank you, Shanthamma, you're verified. Booked for 10:00 AM, room OPD-310. Your booking ID is CL-48213. I've also arranged wheelchair help at entrance B." },
];

function LiveChat() {
  const [n, setN] = useState(1);
  const [typing, setTyping] = useState(false);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(SCRIPT.length); return; }
    let i = 1;
    const tick = () => {
      if (i >= SCRIPT.length) { window.setTimeout(() => { i = 1; setN(1); tick(); }, 6000); return; }
      setTyping(SCRIPT[i].who === "bot");
      window.setTimeout(() => { i += 1; setTyping(false); setN(i); tick(); }, SCRIPT[i].who === "bot" ? 1700 : 1300);
    };
    const t = window.setTimeout(tick, 900);
    return () => window.clearTimeout(t);
  }, []);
  return (
    <div className="live-chat" aria-label="Example: booking with the CareLine Assistant">
      <div className="lc-head">
        <span className="lc-avatar"><Sparkles size={18} aria-hidden="true" /></span>
        <div><strong>CareLine Assistant</strong><span><i className="lc-dot" /> Online now · on Talkdesk</span></div>
      </div>
      <div className="lc-body" aria-live="off">
        {SCRIPT.slice(0, n).map((m, i) => <p key={i} className={`bubble ${m.who}`}>{m.text}</p>)}
        {typing && <p className="bubble bot typing" aria-hidden="true"><i /><i /><i /></p>}
      </div>
      <button type="button" className="lc-input" onClick={openChat}>Type your message… <span>Send</span></button>
    </div>
  );
}

function Hero() {
  return (
    <section className="hero">
      <div className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow-pill"><ShieldCheck size={16} aria-hidden="true" /> Multi-speciality hospital · Marathahalli, Bengaluru</p>
          <h1 className="serif">Exceptional care,<br /><em>one conversation away.</em></h1>
          <p className="hero-lead">Tell our 24-hour assistant what you need, in your own words, on chat or on the phone. It finds the right specialist, books a real slot and sends your booking ID in under a minute.</p>
          <ReachButtons />
          <div className="hero-trust">
            <div><strong>45</strong><span>senior specialists</span></div>
            <div><strong>24×7</strong><span>emergency &amp; assistant</span></div>
            <div><strong>8</strong><span>languages spoken</span></div>
          </div>
        </div>
        <div className="hero-media">
          <Photo src={IMAGES.hero} alt="A doctor walking through a bright hospital corridor" className="hero-photo" eager />
          <LiveChat />
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ insurers marquee
const INSURERS = ["Star Health", "HDFC ERGO", "ICICI Lombard", "Niva Bupa", "Care Health", "Aditya Birla Health", "Tata AIG", "Bajaj Allianz", "CGHS", "ECHS"];
function Marquee() {
  return (
    <section className="marquee" aria-label="Insurers we accept">
      <p>Cashless with</p>
      <div className="mq-track"><div className="mq-row">{[...INSURERS, ...INSURERS].map((n, i) => <span key={i} aria-hidden={i >= INSURERS.length}>{n}</span>)}</div></div>
    </section>
  );
}

// ------------------------------------------------------------------ how booking works (Talkdesk-first)
function HowItWorks() {
  const ref = useReveal<HTMLElement>();
  const v = voiceNumber();
  const steps = [
    { icon: MessageCircle, title: "Say what you need", text: "\"Skin doctor tomorrow evening\", \"move my MRI\", \"is my thyroid report ready?\" In English, Hindi, Kannada and more." },
    { icon: UserRoundCheck, title: "We confirm it's you", text: "For anything about your records, the assistant checks your mobile number and date of birth with the hospital system." },
    { icon: CalendarCheck, title: "It's done, in real time", text: "Real slots from our doctors' schedules. Your booking ID is read out and sent by email and SMS." },
    { icon: BellRing, title: "We keep you posted", text: "Reminders a day and two hours before, and a waitlist that offers you the next cancelled slot." },
  ];
  return (
    <section className="section how" ref={ref} aria-labelledby="how-h">
      <div className="wrap">
        <div className="split-head">
          <h2 id="how-h" className="serif rise">Booking at CareLine is a conversation, not a queue</h2>
          <p className="rise" style={{ ["--d" as string]: "80ms" }}>Our AI front desk runs on <strong>Talkdesk</strong>, the same platform large contact centres use. It answers the website chat and our phone line {v.label}, day and night, and hands you to a person whenever you ask.</p>
        </div>
        <ol className="how-steps">
          {steps.map((s, i) => (
            <li key={s.title} className="rise" style={{ ["--d" as string]: `${120 + i * 90}ms` }}>
              <span className="how-num">{i + 1}</span>
              <span className="how-icon"><s.icon size={26} aria-hidden="true" /></span>
              <h3>{s.title}</h3><p>{s.text}</p>
            </li>
          ))}
        </ol>
        <div className="how-cta rise">
          <div className="channel">
            <MessageCircle size={28} aria-hidden="true" />
            <div><strong>Website chat</strong><span>Bottom-right of every page</span></div>
            <button type="button" className="btn btn-primary btn-sm" onClick={openChat}>Start chat</button>
          </div>
          <div className="channel">
            <PhoneCall size={28} aria-hidden="true" />
            <div><strong>Phone, 24 hours</strong><span>The same assistant answers {v.label}</span></div>
            <a className="btn btn-quiet btn-sm" href={v.href}>Call now</a>
          </div>
          <div className="channel channel-alt">
            <CalendarCheck size={28} aria-hidden="true" />
            <div><strong>Prefer a form?</strong><span>Pick a doctor and a time yourself</span></div>
            <Link className="btn btn-quiet btn-sm" to="/portal/book">Book online</Link>
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ numbers
function Numbers() {
  const ref = useRef<HTMLElement>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); io.disconnect(); } }, { threshold: 0.3 });
    io.observe(el); return () => io.disconnect();
  }, []);
  return (
    <section className="numbers" ref={ref} aria-label="CareLine in numbers">
      <Photo src={IMAGES.building} alt="Hospital building exterior" icon="Hospital" className="numbers-bg" />
      <div className="wrap numbers-grid">
        {STATS.map((s) => <div key={s.label} className={on ? "num-item on" : "num-item"}><strong className="serif">{s.value}</strong><span>{s.label}</span></div>)}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ centres with photos
function Centres() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section" ref={ref} aria-labelledby="centres-h">
      <div className="wrap">
        <div className="split-head">
          <h2 id="centres-h" className="serif rise">Centres of excellence</h2>
          <p className="rise">Six specialist centres where surgeons, physicians, nurses and therapists work as one team around you. <Link to="/specialities">See all 14 specialities <ArrowRight size={16} aria-hidden="true" /></Link></p>
        </div>
        <div className="centre-mosaic">
          {CENTRES.map((c, i) => (
            <Link key={c.key} to={`/specialities#${c.key}`} className={`tile rise tile-${i}`} style={{ ["--d" as string]: `${i * 70}ms` }}>
              <Photo src={CENTRE_IMAGES[c.key]} alt="" icon={c.icon} className="tile-photo" />
              <div className="tile-shade" aria-hidden="true" />
              <div className="tile-text">
                <span className="tile-icon"><Icon name={c.icon} size={22} /></span>
                <h3>{c.name}</h3>
                <p>{c.summary}</p>
                <span className="tile-more">Explore <ArrowUpRight size={16} aria-hidden="true" /></span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ why CareLine (photo + facilities)
function WhyUs() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section why" ref={ref} aria-labelledby="why-h">
      <div className="wrap why-grid">
        <div className="why-media rise">
          <Photo src={IMAGES.care} alt="A nurse caring for a patient" icon="Accessibility" className="why-photo" />
          <div className="why-badge"><Siren size={22} aria-hidden="true" /><div><strong>Emergency in 5 minutes</strong><span>Triage time at entrance B, round the clock</span></div></div>
        </div>
        <div>
          <h2 id="why-h" className="serif rise">Everything a family needs, under one roof</h2>
          <p className="lead rise">Since {HOSPITAL.founded}, CareLine has grown from a 120-bed neighbourhood hospital into a 350-bed medical centre, so patients in Marathahalli, Whitefield and Bellandur no longer cross the city for serious care.</p>
          <ul className="fac-list">
            {FACILITIES.map((f, i) => (
              <li key={f.title} className="rise" style={{ ["--d" as string]: `${i * 60}ms` }}>
                <span className="fac-ic"><Icon name={f.icon} size={22} /></span>
                <div><strong>{f.title}</strong><span>{f.text}</span></div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ doctors (horizontal, drag/scroll)
const FEATURED = ["Dr. Rajesh Iyer", "Dr. Kavya Reddy", "Dr. Kiran Shetty", "Dr. Lakshmi Nair", "Dr. Harish Gowda", "Dr. Nandini Rao", "Dr. Priya Mehta", "Dr. Divya Bhat"];
const TINTS = ["#e8f2fd", "#e7f6f1", "#fff4dc", "#eef1fb", "#fdecef", "#e9f7fb"];

function Doctors() {
  const { data } = useApi<DoctorCard[]>("/api/doctors");
  const ref = useReveal<HTMLElement>();
  const docs = FEATURED.map((n) => (data || []).find((d) => d.name === n)).filter(Boolean) as DoctorCard[];
  const initials = (n: string) => n.replace("Dr. ", "").split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <section className="section tinted" ref={ref} aria-labelledby="doc-h">
      <div className="wrap">
        <div className="split-head">
          <h2 id="doc-h" className="serif rise">Meet our specialists</h2>
          <p className="rise">Senior consultants with 5 to 30 years of experience, who speak your language. <Link to="/doctors">Find a doctor <ArrowRight size={16} aria-hidden="true" /></Link></p>
        </div>
      </div>
      <div className="doc-rail" tabIndex={0} aria-label="Featured doctors, scroll sideways">
        {docs.map((d, i) => (
          <article key={d.name} className="doc-card">
            <div className="doc-portrait" style={{ background: TINTS[i % TINTS.length] }} aria-hidden="true">
              <span className="serif">{initials(d.name)}</span><Stethoscope size={22} />
            </div>
            <div className="doc-info">
              <p className="doc-dept">{d.department}</p>
              <h3>{d.name}</h3>
              <p className="doc-qual">{d.qualification}</p>
              <p className="doc-time">{d.days} · {d.hours}</p>
              <p className="doc-lang"><Languages size={15} aria-hidden="true" /> {d.languages}</p>
              <button type="button" className="btn btn-quiet btn-sm" onClick={openChat}>Ask to book with {d.name.split(" ").slice(-1)[0]}</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ stories
function Stories() {
  const ref = useReveal<HTMLElement>();
  const [i, setI] = useState(0);
  const s = STORIES[i];
  return (
    <section className="section stories" ref={ref} aria-labelledby="st-h">
      <div className="wrap stories-grid">
        <div className="rise">
          <h2 id="st-h" className="serif">In our patients' words</h2>
          <div className="st-tabs" role="tablist" aria-label="Patient stories">
            {STORIES.map((x, k) => <button key={x.name} role="tab" type="button" aria-selected={k === i} onClick={() => setI(k)}>{x.name}</button>)}
          </div>
        </div>
        <figure className="st-quote rise" key={i} style={{ ["--d" as string]: "80ms" }}>
          <blockquote className="serif">“{s.text}”</blockquote>
          <figcaption><strong>{s.name}</strong> · {s.place} · {s.dept}</figcaption>
        </figure>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ packages
function Packages() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section" ref={ref} aria-labelledby="pk-h" id="packages">
      <div className="wrap">
        <div className="split-head">
          <h2 id="pk-h" className="serif rise">Preventive health check-ups</h2>
          <p className="rise">Most reports the same day, reviewed with a physician. Ask the assistant to book one, or call us.</p>
        </div>
        <div className="pk-grid">
          {PACKAGES.map((p, i) => (
            <div key={p.code} className={i === 1 ? "pk pk-main rise" : "pk rise"} style={{ ["--d" as string]: `${i * 90}ms` }}>
              {i === 1 && <span className="pk-flag">Most chosen</span>}
              <h3>{p.name}</h3>
              <p className="pk-price serif">{rupees(p.price)}</p>
              <p className="pk-tests">{p.tests}</p>
              <ul>{p.items.map((it) => <li key={it}><CheckCircle2 size={18} aria-hidden="true" />{it}</li>)}</ul>
              <button type="button" className={i === 1 ? "btn btn-primary" : "btn btn-quiet"} onClick={openChat}>Book with the assistant</button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ health library + portal
function Library() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="section tinted" ref={ref} aria-labelledby="tp-h">
      <div className="wrap lib-grid">
        <div>
          <h2 id="tp-h" className="serif rise">From our doctors</h2>
          <div className="tips">
            {TIPS.map((t, i) => (
              <article key={t.title} className="tip rise" style={{ ["--d" as string]: `${i * 80}ms` }}>
                <span className="tip-tag">{t.tag}</span><h3>{t.title}</h3><p>{t.text}</p>
              </article>
            ))}
          </div>
        </div>
        <aside className="portal-promo rise" style={{ ["--d" as string]: "120ms" }}>
          <Photo src={IMAGES.lab} alt="Laboratory technician at work" icon="FlaskConical" className="promo-photo" />
          <div className="promo-text">
            <FileText size={26} aria-hidden="true" />
            <h3>Your reports, the moment they're ready</h3>
            <p>See lab results with normal ranges, your visits and your waitlist in My CareLine. Or just ask the assistant, "is my report ready?"</p>
            <Link className="btn btn-primary btn-sm" to="/login">Open My CareLine</Link>
          </div>
        </aside>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ emergency + callback
function Emergency() {
  return (
    <section className="emergency-band" aria-labelledby="em-h">
      <div className="wrap em-in">
        <Siren size={40} aria-hidden="true" />
        <div><h2 id="em-h">Chest pain, breathlessness, stroke signs or heavy bleeding?</h2>
          <p>Don't wait for an appointment. Call 108 now or come to emergency entrance B, open 24 hours. If you tell our assistant, it says the same and connects a staff member at once.</p></div>
        <a className="btn btn-white" href="tel:108">Call 108</a>
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
    <section className="section" aria-labelledby="cb-h">
      <div className="wrap cb-grid">
        <div>
          <h2 id="cb-h" className="serif">Rather we call you?</h2>
          <p className="lead">Leave your number for surgery estimates, admissions or a second opinion. Our patient care team calls back Monday to Saturday, 8 AM to 8 PM.</p>
          <ReachButtons form={false} size="sm" />
        </div>
        <form className="cb-form" onSubmit={submit} noValidate>
          <div className="two">
            <div className="field"><label htmlFor="cb-name">Your name</label><input id="cb-name" name="name" className="input" autoComplete="name" /></div>
            <div className="field"><label htmlFor="cb-phone">Mobile number</label><input id="cb-phone" name="phone" className="input" inputMode="tel" autoComplete="tel" required /></div>
          </div>
          <div className="two">
            <div className="field"><label htmlFor="cb-time">Best time</label>
              <select id="cb-time" name="preferred_time" className="input" defaultValue="Today, as soon as possible">
                <option>Today, as soon as possible</option><option>Tomorrow morning</option><option>Tomorrow afternoon</option><option>After 6 PM</option></select></div>
            <div className="field"><label htmlFor="cb-reason">About</label><input id="cb-reason" name="reason" className="input" placeholder="e.g. knee replacement cost" /></div>
          </div>
          <button className="btn btn-primary" disabled={state.busy}>{state.busy ? "Sending…" : "Request a call back"}</button>
          <p className={state.err ? "error-text" : "ok-text"} aria-live="polite">{state.ok || state.err}</p>
        </form>
      </div>
    </section>
  );
}

export default function Home() {
  useEffect(() => { document.title = "CareLine Hospitals, Bengaluru · Book by chat or phone, 24 hours"; }, []);
  return (
    <>
      <Hero />
      <Marquee />
      <HowItWorks />
      <Numbers />
      <Centres />
      <WhyUs />
      <Doctors />
      <Stories />
      <Packages />
      <Library />
      <Emergency />
      <Callback />
    </>
  );
}
