import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { api, istDay, rupees, shortDate } from "../lib/api";
import { useApi, useReveal, useTextSize } from "../lib/hooks";
import { openChat } from "../lib/chat";
import { TokenSlip } from "../components/Bits";

// ------------------------------------------------------------------ hero: giant token + live slot finder
const FINDER_DEPTS = ["Cardiology", "Orthopaedics", "General Medicine", "Paediatrics", "Dermatology", "ENT"];
type Next = { doctor: string; date: string; dateLabel: string; time: string; label: string; fee: number; room: string } | null;

async function nextFree(dept: string): Promise<Next> {
  for (const off of [0, 1, 2, 3]) {
    const r = await api<any>(`/api/slots?date=${istDay(off)}&department=${encodeURIComponent(dept)}`);
    let best: Next = null;
    for (const d of r.doctors) {
      const s = d.slots[0];
      if (s && (!best || s.time < best.time)) {
        best = { doctor: d.name, date: r.date_iso, dateLabel: off === 0 ? "Today" : off === 1 ? "Tomorrow" : shortDate(r.date_iso),
                 time: s.time, label: s.label, fee: d.fee_inr, room: d.room };
      }
    }
    if (best) return best;
  }
  return null;
}

function Hero() {
  const [dept, setDept] = useState(FINDER_DEPTS[0]);
  const [res, setRes] = useState<Record<string, Next | "loading" | "error">>({});
  useEffect(() => {
    if (res[dept]) return;
    setRes((r) => ({ ...r, [dept]: "loading" }));
    nextFree(dept).then((n) => setRes((r) => ({ ...r, [dept]: n }))).catch(() => setRes((r) => ({ ...r, [dept]: "error" })));
  }, [dept, res]);
  const cur = res[dept];
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <h1 id="hero-title">Skip the<br />OPD queue.</h1>
        <p className="hero-lead">Book a doctor, move a visit or get your lab report in under a minute, by chat, phone or this site, at CareLine Hospitals in Marathahalli.</p>
        <div className="hero-actions">
          <Link className="btn btn-primary token-shape" to="/portal/book">Book a visit</Link>
          <button type="button" className="btn btn-quiet token-shape" onClick={openChat}>Ask the assistant</button>
        </div>
      </div>
      <div className="hero-token token-shape" aria-hidden="false">
        <div className="finder" aria-live="polite" data-ui>
          <h2 className="finder-h">Next free slot</h2>
          <div className="finder-depts" role="group" aria-label="Department">
            {FINDER_DEPTS.map((d) => (
              <button key={d} type="button" aria-pressed={dept === d} onClick={() => setDept(d)}>{d}</button>
            ))}
          </div>
          <div className="finder-result">
            {cur === "loading" || cur === undefined ? <p className="finder-wait">Checking today's OPD…</p>
              : cur === "error" ? <p className="finder-wait">We couldn't load slots. Try again in a moment.</p>
              : cur === null ? <p className="finder-wait">Fully booked this week. <Link to="/portal/waitlist">Join the waitlist</Link></p>
              : (
                <>
                  <p className="finder-when"><span>{cur.dateLabel}</span> {cur.label}</p>
                  <p className="finder-who">{cur.doctor} · Room {cur.room} · {rupees(cur.fee)}</p>
                  <Link className="btn btn-primary token-shape finder-book"
                        to={`/portal/book?doctor=${encodeURIComponent(cur.doctor)}&date=${cur.date}&time=${cur.time}`}>
                    Take this slot <ArrowRight size={18} aria-hidden="true" />
                  </Link>
                </>
              )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ showcase: three ways in
const CHANNELS = {
  chat: { title: "Book by chat", text: "Type it the way you'd say it: \"skin doctor tomorrow morning\". The assistant checks real slots, books, and reads back your token number, room and fee.", primary: "Open the chat", secondary: "How it decides" },
  phone: { title: "Book by phone", text: "Call the front desk and the same assistant answers, any hour. It confirms your mobile number and date of birth before it changes anything.", primary: "Call 080 4000 1234", secondary: "Emergency? Call 108" },
  web: { title: "Book on the web", text: "Pick a department, a day and a time. The booking lands in the same hospital system, so the chat, the phone line and the desk all see it.", primary: "Book on the web", secondary: "See doctors" },
} as const;

function Showcase() {
  const [tab, setTab] = useState<keyof typeof CHANNELS>("chat");
  const c = CHANNELS[tab];
  const ref = useReveal<HTMLElement>();
  return (
    <section className="showcase" aria-labelledby="show-title" ref={ref}>
      <div className="show-plate rise">
        <TokenSlip id="CL-48213" spoken="C L 4 8 2 1 3"
          lines={[<strong key="a">Dr. Rajesh Iyer · Cardiology</strong>, "Wednesday, 10:30 AM", "Room OPD-310 · 3rd floor", "Fee ₹1,200 · arrive 15 min early"]} />
        <p className="plate-caption">Every booking gets a token like this, by email and in your portal.</p>
      </div>
      <div className="show-copy">
        <div className="show-tabs rise" role="tablist" aria-label="Ways to book">
          {(Object.keys(CHANNELS) as (keyof typeof CHANNELS)[]).map((k) => (
            <button key={k} role="tab" type="button" aria-selected={tab === k} onClick={() => setTab(k)}>{k === "chat" ? "Chat" : k === "phone" ? "Phone" : "Web"}</button>
          ))}
        </div>
        <div className="rise" style={{ ["--d" as string]: "80ms" }} role="tabpanel">
          <h2 id="show-title">{c.title}</h2>
          <p className="show-text">{c.text}</p>
        </div>
        <div className="show-cells rise" style={{ ["--d" as string]: "160ms" }}>
          {tab === "chat" && <><button type="button" className="cell cell-ink" onClick={openChat}>{c.primary}</button><a className="cell" href="#how">{c.secondary}</a></>}
          {tab === "phone" && <><a className="cell cell-ink" href="tel:+918040001234">{c.primary}</a><a className="cell cell-alert" href="tel:108">{c.secondary}</a></>}
          {tab === "web" && <><Link className="cell cell-ink" to="/portal/book">{c.primary}</Link><Link className="cell" to="/doctors">{c.secondary}</Link></>}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ how it works: the waitlist refill
const STAGES = [
  { name: "Someone cancels", text: "A patient cancels their Thursday cardiology visit by phone. The slot doesn't go back on the shelf.",
    ui: <div className="frag frag-row" data-ui><span><strong>Dr. Rajesh Iyer</strong><br />Thu, 10:30 AM · CL-48213</span><span className="pill pill-muted">Cancelled</span></div> },
  { name: "Slot held", text: "The next person on the waitlist gets an email and a text within seconds. The slot is held for them for 30 minutes.",
    ui: <div className="frag frag-sms" data-ui><span className="frag-from">CareLine · SMS</span>Slot with Dr. Rajesh Iyer, Thu 10:30 AM, held for you for 30 min. Accept: careline.in/w/YDLQ5F7NAR</div> },
  { name: "You accept", text: "One tap on the link, or say the offer code in chat. If you're too late, we offer you the next opening.",
    ui: <div className="frag frag-accept" data-ui><strong>Arjun, a slot opened.</strong><span>Held for you for 24 min 10 s</span><span className="frag-btn">Accept this slot</span></div> },
  { name: "Reminded", text: "A reminder the day before and two hours before, with the room and what to bring.",
    ui: <div className="frag frag-sms" data-ui><span className="frag-from">CareLine · Email</span>Tomorrow 10:30 AM with Dr. Rajesh Iyer, room OPD-310, 3rd floor. Please bring old ECG reports.</div> },
];

function HowItWorks() {
  const [open, setOpen] = useState(0);
  const ref = useReveal<HTMLElement>();
  return (
    <section className="how" id="how" aria-labelledby="how-title" ref={ref}>
      <div className="how-intro">
        <h2 id="how-title" className="rise">No empty slots</h2>
        <p className="rise" style={{ ["--d" as string]: "80ms" }}>A late cancellation usually means an empty chair while someone else waits a week. At CareLine a freed slot is offered straight to the patient who has been waiting for it.</p>
      </div>
      <div className="how-row rise" style={{ ["--d" as string]: "160ms" }}>
        {STAGES.map((s, i) => (
          <div key={s.name} className={i === open ? "stage open" : "stage"} style={{ ["--i" as string]: i }}>
            <button type="button" aria-expanded={i === open} onClick={() => setOpen(i)}><span>{s.name}</span></button>
            <div className="stage-body" hidden={i !== open}><div><h3>{s.name}</h3><p>{s.text}</p></div>{s.ui}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ features: senior care, as switches
function Features() {
  const [lg, setLg] = useTextSize();
  const [on, setOn] = useState<Record<string, boolean>>({ short: true, morning: true, family: false, wheel: false });
  const ref = useReveal<HTMLElement>();
  const rows: { k: string; text: string; more: string; ui?: JSX.Element; value?: boolean; set?: (v: boolean) => void }[] = [
    { k: "size", text: "Larger text on every page", more: "Body text grows from 17 to 20 pixels; this choice is remembered in this browser.", value: lg, set: (v: boolean) => setLg(v) },
    { k: "short", text: "Shorter answers from the assistant", more: "Patients over 60 get two short sentences, one fact each, and never more than two options.",
      ui: <div className="thread" data-ui><p className="msg me"><span>Shanthamma, 67</span>Book the heart doctor for Wednesday morning, 10:30 is fine.</p>
        <p className="msg bot"><span>CareLine Assistant</span>Booked with Dr. Rajesh Iyer, Wednesday 4 November at 10:30 AM. Booking ID C L 4 8 2 1 3.</p></div> },
    { k: "morning", text: "Morning slots offered first", more: "For patients over 60, slots before 12 PM come first unless you ask otherwise.",
      ui: <div className="thread" data-ui><p className="msg me"><span>Shanthamma, 67</span>Any heart doctor free on Wednesday?</p>
        <p className="msg bot"><span>CareLine Assistant</span>On Wednesday 4 November, Dr. Farzana Begum is free at 9:30 AM and 9:45 AM.</p></div> },
    { k: "family", text: "Your son or daughter kept informed", more: "With your consent, your caregiver gets every booking and change by email and text." },
    { k: "wheel", text: "A wheelchair waiting at entrance B", more: "Ask once by chat, phone or in your profile; it is noted on every visit's token." },
  ];
  return (
    <section className="features" aria-labelledby="feat-title" ref={ref}>
      <h2 id="feat-title" className="sr-only">Care that adjusts for older patients</h2>
      {rows.map((r, i) => {
        const val = r.value ?? on[r.k];
        const set = r.set ?? ((v: boolean) => setOn((o) => ({ ...o, [r.k]: v })));
        return (
          <div key={r.k} className={val ? "band on rise" : "band rise"} style={{ ["--band" as string]: `var(--field-${(i % 4) + 1})`, ["--d" as string]: `${i * 70}ms` }}>
            <div className="band-text">
              <p className="band-sentence" id={`band-${r.k}`}>{r.text}</p>
              {val && <p className="band-more">{r.more}</p>}
              {val && r.ui}
            </div>
            <button type="button" role="switch" data-ui aria-checked={val} aria-labelledby={`band-${r.k}`} className="switch"
                    onClick={() => set(!val)}><span /></button>
          </div>
        );
      })}
    </section>
  );
}

// ------------------------------------------------------------------ list: tests and scans with prices
type Proc = { code: string; name: string; category: string; price_inr: number; preauth_required: boolean; instructions: string };
const GROUPS: [string, string[]][] = [["Scans", ["MRI", "CT", "XRAY", "USG"]], ["Heart and lungs", ["CARDIO"]], ["Lab tests", ["LAB"]], ["Health checks", ["PKG"]]];

function PriceList() {
  const { data } = useApi<Proc[]>("/api/procedures");
  const [g, setG] = useState(0);
  const ref = useReveal<HTMLElement>();
  const items = useMemo(() => (data || []).filter((p) => GROUPS[g][1].includes(p.category)), [data, g]);
  return (
    <section className="prices" aria-labelledby="price-title" ref={ref}>
      <div className="prices-head">
        <h2 id="price-title" className="rise">Tests and scans, priced</h2>
        <p className="rise">Prices you pay without insurance. <Link to="/insurance">Check what your insurer covers</Link>.</p>
      </div>
      <div className="price-tabs" role="tablist" aria-label="Category">
        {GROUPS.map(([name, cats], i) => (
          <button key={name} role="tab" type="button" aria-selected={g === i} onClick={() => setG(i)}>
            {name} <span>{(data || []).filter((p) => cats.includes(p.category)).length}</span>
          </button>
        ))}
      </div>
      <ul className="price-list" role="tabpanel">
        {items.map((p, i) => (
          <li key={p.code} className="rise in" style={{ ["--d" as string]: `${i * 40}ms` }}>
            <span className="token-bullet" aria-hidden="true" />
            <div>
              <p className="price-row"><strong>{p.name}</strong><span>{rupees(p.price_inr)}</span></p>
              <p className="price-desc">{p.instructions}</p>
              {p.preauth_required && <p className="price-note">Insurers usually need pre-approval first.</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ------------------------------------------------------------------ faq
const FAQ = [
  ["Can someone else cancel my appointment?", "No. Cancelling or moving a visit needs your registered mobile number and your date of birth, and the hospital system checks both. After five wrong tries the number is locked for 15 minutes."],
  ["Will the assistant give me medical advice?", "No. It books, explains preparation and suggests which department to see, but it never diagnoses or recommends medicines. For chest pain, breathlessness, stroke signs or heavy bleeding it tells you to call 108 and brings in a person."],
  ["How do I get my lab report?", "Ask the assistant whether it's ready. Ready reports can be emailed to your registered address as a summary with a secure link; the full values are only in your portal."],
  ["Which insurance do you accept?", "Star Health, HDFC ERGO, ICICI Lombard, Niva Bupa, Care Health, Aditya Birla, Tata AIG, Bajaj Allianz, CGHS and ECHS. MRI, CT and endoscopy usually need pre-approval; our insurance desk raises it."],
  ["What languages can I speak?", "The assistant replies in English, Hindi, Kannada and other Indian languages, and our doctors' languages are listed on every profile."],
  ["Is there parking?", "Yes, free for 3 hours in Basement 2, with valet at the main entrance. Wheelchairs are kept at entrance B."],
  ["What happens to my data?", "This is a hackathon demo: every patient here is invented. A real deployment would need your consent, clear retention rules and compliance with India's DPDP Act."],
];

function Faq() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="faq" aria-labelledby="faq-title" ref={ref}>
      <h2 id="faq-title" className="rise">Questions people ask</h2>
      <div className="faq-list">
        {FAQ.map(([q, a], i) => (
          <details key={q} name="faq" open={i === 0} className="faq-tile rise" style={{ ["--d" as string]: `${i * 60}ms` }}>
            <summary><span>{q}</span><i aria-hidden="true" /></summary>
            <p>{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ contact: call-back coupon
function Coupon() {
  const [state, setState] = useState<{ ok?: string; err?: string; busy?: boolean }>({});
  const ref = useReveal<HTMLElement>();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setState({ busy: true });
    try {
      const r = await api<any>("/api/callback", { method: "POST", body: Object.fromEntries(f.entries()) });
      setState({ ok: r.message });
      (e.target as HTMLFormElement).reset();
    } catch (err: any) { setState({ err: err.message }); }
  }
  return (
    <section className="coupon-wrap" aria-labelledby="coupon-title" ref={ref}>
      <form className="coupon rise" onSubmit={submit} noValidate>
        <div className="coupon-left">
          <h2 id="coupon-title">Rather talk<br />to a person?</h2>
          <p>Leave your number and a good time. Our front desk calls you back, Monday to Saturday, 8 AM to 8 PM.</p>
        </div>
        <div className="coupon-perf" aria-hidden="true" />
        <div className="coupon-right">
          <label className="sr-only" htmlFor="cb-name">Your name</label>
          <input id="cb-name" name="name" className="coupon-input" placeholder="Your name" autoComplete="name" />
          <label className="sr-only" htmlFor="cb-phone">Mobile number</label>
          <input id="cb-phone" name="phone" className="coupon-input" placeholder="Mobile number" inputMode="tel" autoComplete="tel" required />
          <label className="sr-only" htmlFor="cb-time">When to call</label>
          <select id="cb-time" name="preferred_time" className="coupon-input" defaultValue="Today, as soon as possible">
            <option>Today, as soon as possible</option><option>Tomorrow morning</option><option>Tomorrow afternoon</option><option>After 6 PM</option>
          </select>
          <label className="sr-only" htmlFor="cb-reason">What it's about</label>
          <input id="cb-reason" name="reason" className="coupon-input" placeholder="What it's about, e.g. surgery cost" />
          <button className="coupon-submit" disabled={state.busy}>{state.busy ? "Sending…" : "Call me back"}</button>
          <p className="coupon-status" aria-live="polite">{state.ok || state.err}</p>
        </div>
      </form>
    </section>
  );
}

export default function Home() {
  useEffect(() => { document.title = "CareLine Hospitals, Bengaluru · Book, reschedule, reports"; }, []);
  return (
    <>
      <Hero />
      <Showcase />
      <HowItWorks />
      <Features />
      <PriceList />
      <Faq />
      <Coupon />
    </>
  );
}
