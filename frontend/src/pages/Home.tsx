/*
  WellNest home page.

  The structure follows the product rather than the hospital-website genre. WellNest's one
  real mechanism is that a single brain answers every channel: the same nine Talkdesk agents
  and the same tools serve the chat on this page, the phone line and this website, reading one
  schedule and writing one record. So the page is built as a set of *documents* rather than a
  deck of cards — a switchboard, a case sheet, a register of tomorrow's open list, an index of
  centres, a statement of scale, a price list, and a close.

  Pacing is deliberate: dark opening, a moving rail, a dense sheet, a quiet photograph, a dense
  live register, an index with imagery, a quiet dark statement, a price list, voices, a close.
*/
import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowUpRight, MessageCircle, PhoneCall, Siren, SquarePen } from "lucide-react";
import { api, rupees } from "../lib/api";
import { useApi } from "../lib/hooks";
import { openChat, voiceNumber } from "../lib/chat";
import { InsurerRail } from "../components/site/Insurers";
import {
  CASE_SHEET, CENTRES, CENTRE_IMAGES, HOSPITAL, IMAGES, LEDGER_DEPTS, PACKAGES, STORIES, TIPS,
} from "../content";

type SlotsResponse = {
  ok: boolean; date: string; date_iso: string;
  doctors: {
    name: string; department: string; room: string; fee_inr: number; hours: string;
    days: string; unavailable: string | null; slots: { time: string; label: string }[];
  }[];
};

/* ----------------------------------------------------------------- 1. the switchboard
   The opening. No photograph and nothing floating over one: the first viewport is type,
   three ruled channels, and the drawing of them converging on a single record. */
/*
  The switchboard's right-hand side, and the page's one authored motion.

  The three channels take it in turns to be the live one. Each time, the record below is
  re-written — the field values sweep in, left to right, exactly as the assistant fills them.
  The point of the loop is what does NOT change: whichever channel is lit, the booking, the
  doctor, the time, the room and the fee are identical. That is the product in one movement,
  so the motion carries the argument rather than decorating it.

  Under prefers-reduced-motion the cycle stops on the chat channel and the row is simply shown.
*/
const CHANNELS = [
  { key: "chat", name: "Website chat", hint: "Bottom-right of every page", cta: "Open", wrote: "written from the chat on this page" },
  { key: "voice", name: "The phone line", hint: "It books on the call itself", cta: "Call", wrote: "written while you were still on the call" },
  { key: "web", name: "This website", hint: "Choose the doctor and the time", cta: "Book", wrote: "written when you picked the time yourself" },
] as const;

const RECORD = [
  ["Booking", "WN-48213", "code"],
  ["Visit", "Dr. Rajesh Iyer · Cardiology", ""],
  ["When", "Friday 6 November, 10:30 AM", "num"],
  ["Room", "OPD-310", "num"],
  ["Fee", "₹1,200", "num"],
] as const;

function Switchboard3() {
  const v = voiceNumber();
  const [live, setLive] = useState(0);
  const [still, setStill] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) { setStill(true); return; }
    const t = window.setInterval(() => setLive((n) => (n + 1) % CHANNELS.length), 3200);
    return () => window.clearInterval(t);
  }, []);

  const current = CHANNELS[live];

  return (
    <>
      <ul className="sw-rail">
        {CHANNELS.map((c, i) => (
          <li key={c.key} data-live={!still && i === live ? "" : undefined}>
            <span className="sw-ch"><i className="sw-dot" aria-hidden="true" />{c.name}</span>
            <span className="sw-de">{c.hint}</span>
            {c.key === "chat" ? (
              <button type="button" className="sw-go" onClick={openChat}>
                {c.cta} <ArrowRight size={15} aria-hidden="true" />
              </button>
            ) : c.key === "voice" ? (
              <a className="sw-go" href={v.href}>{c.cta} <ArrowRight size={15} aria-hidden="true" /></a>
            ) : (
              <Link className="sw-go" to="/portal/book">{c.cta} <ArrowRight size={15} aria-hidden="true" /></Link>
            )}
          </li>
        ))}
      </ul>

      <figure className="sw-rec" aria-live="off">
        <figcaption>
          <span className="sw-rec-k">One record</span>
          <span className="sw-rec-w" key={still ? "s" : live}>
            {still ? "the same row, whichever way you ask" : current.wrote}
          </span>
        </figcaption>
        <dl>
          {RECORD.map(([k, val, cls], i) => (
            <div key={k} className="sw-rec-f" style={{ "--i": i } as CSSProperties}>
              <dt>{k}</dt>
              <dd key={still ? k : `${live}-${k}`} className={cls}>{val}</dd>
            </div>
          ))}
        </dl>
        <p className="sw-rec-note">
          Nothing is re-typed between the phone, the chat and this site — so nothing disagrees,
          and the counter sees what you were told.
        </p>
      </figure>
    </>
  );
}

function Switchboard() {
  const v = voiceNumber();
  return (
    <section className="sw">
      <div className="wrap sw-in">
        <div className="sw-copy" data-reveal>
          <h1>Ask once.<br /><em>We take it from there.</em></h1>
          <p className="sw-lead">
            Say what you need in your own words — in English, Hindi, Kannada and five more. One
            assistant answers the chat on this page and the phone line, reads the doctors' real
            schedules, and writes to the same record the counter staff see. A person is always one
            sentence away.
          </p>
          <div className="sw-acts">
            <button type="button" className="btn btn-primary btn-lg" onClick={openChat}>
              <MessageCircle size={18} aria-hidden="true" /> Chat to book
            </button>
            <a className="btn btn-lg sw-call" href={v.href}>
              <PhoneCall size={18} aria-hidden="true" /> Call {v.label}
            </a>
          </div>
          <p className="sw-fine">
            Twenty-four hours, every day. The number above reaches WellNest AI, not a switchboard —
            it answers, books and reads your booking ID back to you.
          </p>
        </div>

        <div className="sw-rig">
          <Switchboard3 />
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 2. the case sheet
   Replaces the old four-step strip. Not four columns of icon and caption but a two-column
   ruled sheet: the words a patient actually uses on the left, what the system actually does
   with them on the right. The mapping is the information. */
function CaseSheet() {
  return (
    <section className="cs">
      <div className="wrap">
        <div className="sec-rule" data-reveal>
          <h2>What you say, and what happens next.</h2>
          <p>
            No menus, no “press 1 for appointments”. Six things the assistant is actually built to
            do — and the limits it works inside, which matter just as much.
          </p>
        </div>
        <dl className="cs-sheet">
          {CASE_SHEET.map((r) => (
            <div className="cs-row" key={r.tag}>
              <dt>
                <span className="cs-tag">{r.tag}</span>
                <span className="cs-said">{r.said}</span>
              </dt>
              <dd>{r.does}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 3. the quiet plate
   A breath after the sheet: one wide photograph, nothing laid over it, caption in the margin
   underneath. The curtain unmask is the page's one signature scroll moment. */
function Plate() {
  return (
    <section className="plate">
      <figure className="plate-frame" data-curtain>
        <img
          src={IMAGES.team}
          alt="A daylit four-bed ward at WellNest Hospitals, made up and empty between admissions"
          loading="lazy" decoding="async" data-parallax="1"
        />
      </figure>
      <div className="wrap plate-cap">
        <p>
          A ward made up between admissions. <strong>350</strong> beds, sixty of them critical care —
          and every admission, like every outpatient visit, is one row in the same register the
          assistant reads when you ask it a question on the phone.
        </p>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 4. tomorrow's open list
   The proof, and it is live: /api/slots is the identical endpoint the booking agent calls.
   A register, not a card — doctor, consulting hours, the free times themselves, the fee. */
function OpenList() {
  const [dept, setDept] = useState(LEDGER_DEPTS[0]);
  const path = `/api/slots?date=tomorrow&department=${encodeURIComponent(dept)}`;
  const { data, loading, error } = useApi<SlotsResponse>(path, [dept]);
  const rows = data?.doctors || [];
  const free = rows.reduce((n, d) => n + (d.slots?.length || 0), 0);

  return (
    <section className="ol">
      <div className="wrap">
        <div className="sec-rule ol-head" data-reveal>
          <h2>Tomorrow's open list.</h2>
          <p>
            Read straight from the consultants' own schedules — the same endpoint the assistant
            calls when you ask it on the phone. If a time is on this page, it is genuinely free.
          </p>
        </div>

        <div className="ol-bar">
          <div className="ol-tabs" role="tablist" aria-label="Department">
            {LEDGER_DEPTS.map((d) => (
              <button
                key={d} type="button" role="tab" aria-selected={d === dept}
                className={d === dept ? "ol-tab is-on" : "ol-tab"}
                onClick={() => setDept(d)}
              >
                {d}
              </button>
            ))}
          </div>
          <p className="ol-count" aria-live="polite">
            {error ? "Schedule unavailable just now" :
              loading && !data ? "Reading the schedule…" :
                `${free} free ${free === 1 ? "slot" : "slots"} · ${data?.date || ""}`}
          </p>
        </div>

        <table className="ol-table">
          <caption className="sr-only">Free appointment times tomorrow in {dept}</caption>
          <thead>
            <tr>
              <th scope="col">Consultant</th>
              <th scope="col">Consults</th>
              <th scope="col">Free tomorrow</th>
              <th scope="col" className="ol-r">Fee</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.name}>
                <th scope="row" data-label="Consultant">
                  {d.name}
                  <small>Room {d.room}</small>
                </th>
                <td data-label="Consults">{d.hours}<small>{d.days}</small></td>
                <td data-label="Free tomorrow">
                  {d.slots?.length ? (
                    <span className="ol-times">
                      {d.slots.slice(0, 5).map((s) => (
                        <Link key={s.time} className="ol-time num" to="/portal/book">{s.label}</Link>
                      ))}
                      {d.slots.length > 5 && <span className="ol-more num">+{d.slots.length - 5}</span>}
                    </span>
                  ) : (
                    <span className="ol-shut">{d.unavailable ? "Not consulting tomorrow" : "Fully booked"}</span>
                  )}
                </td>
                <td data-label="Fee" className="ol-r num">{rupees(d.fee_inr)}</td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={4} className="ol-empty">{error ? error : "Reading the schedule…"}</td></tr>
            )}
          </tbody>
        </table>

        <p className="ol-foot">
          Not the department you need? <button type="button" className="lnk" onClick={openChat}>Ask the assistant</button> —
          it reads all fourteen, or <Link to="/doctors">browse all 45 consultants</Link>.
        </p>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 5. the index
   Six centres as an index with a facing plate, the way a reference book sets them, rather
   than six equal image cards. Pointing at a line changes the plate; clicking opens it. */
function Index() {
  const [key, setKey] = useState(CENTRES[0].key);
  const active = CENTRES.find((c) => c.key === key) || CENTRES[0];
  return (
    <section className="ix">
      <div className="wrap ix-in">
        <div className="ix-list">
          <div className="sec-rule" data-reveal>
            <h2>Six centres where<br />the hard cases go.</h2>
          </div>
          <ul>
            {CENTRES.map((c) => (
              <li key={c.key}>
                <Link
                  to={`/specialities#${c.key}`}
                  aria-current={c.key === key ? "true" : undefined}
                  onMouseEnter={() => setKey(c.key)}
                  onFocus={() => setKey(c.key)}
                >
                  <img className="ix-thumb" src={CENTRE_IMAGES[c.key]} alt="" aria-hidden="true" loading="lazy" decoding="async" />
                  <span className="ix-name">{c.name}</span>
                  <span className="ix-dept">{c.dept}</span>
                  <ArrowUpRight className="ix-arr" size={18} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
          <Link className="lnk-strong" to="/specialities">
            All fourteen departments <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </div>

        <figure className="ix-plate">
          <img key={active.key} src={CENTRE_IMAGES[active.key]} alt="" aria-hidden="true" loading="lazy" decoding="async" />
          <figcaption>
            <h3>{active.name}</h3>
            <p>{active.summary}</p>
            <ul>{active.treats.map((t) => <li key={t}>{t}</li>)}</ul>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 6. the statement
   The hospital's scale as one sentence rather than a row of big numbers. The facts are set
   in the display face so the eye still catches them while reading. */
function Statement() {
  return (
    <section className="ms">
      <img src={IMAGES.building} alt="" aria-hidden="true" data-parallax="2" />
      <div className="wrap ms-in">
        <p className="ms-say" data-reveal data-reveal-self>
          Since <b>2009</b> WellNest has grown from a hundred and twenty beds to <b>350</b>, sixty of
          them critical care, with two <b>3 Tesla</b> MRI scanners, two <b>128-slice</b> CT scanners,
          a cath lab that never closes and a level III neonatal ICU — so families in Marathahalli,
          Whitefield and Bellandur no longer cross the city for serious care.
        </p>
        <p className="ms-foot">
          Seventeen years · Fourteen departments · 45 senior consultants
          <Link to="/about">The whole story <ArrowRight size={16} aria-hidden="true" /></Link>
        </p>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 7. the price list */
function Checks() {
  return (
    <section className="pkl">
      <div className="wrap">
        <div className="sec-rule" data-reveal>
          <h2>Three health checks, priced in the open.</h2>
          <p>Most reports the same day, each one reviewed with a physician before you leave.</p>
        </div>
        <ul className="pkl-rows">
          {PACKAGES.map((p) => (
            <li key={p.code}>
              <div className="pkl-id">
                <h3>{p.name}</h3>
                <span className="pkl-code code">{p.code}</span>
              </div>
              <p className="pkl-what">
                <span className="pkl-n num">{p.tests}</span>
                {p.items.join(" · ")}
              </p>
              <div className="pkl-act">
                <span className="pkl-rate num">{rupees(p.price)}</span>
                <button type="button" className="btn btn-quiet btn-sm" onClick={openChat}>Book this</button>
              </div>
            </li>
          ))}
        </ul>
        <p className="pkl-note">
          <SquarePen size={17} aria-hidden="true" />
          <span>
            Pay from <strong>HealthCredits</strong> — one family wallet for consultations, scans and
            medicines, spendable on chat, on the phone or at the counter, with a limit you set for
            each member. <Link to="/portal">Open the wallet</Link>
          </span>
        </p>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 8. voices
   Real content from the hospital's own notes: three patients, then three things the doctors
   here keep repeating. Quiet after the price list. */
function Voices() {
  const [i, setI] = useState(0);
  const s = STORIES[i];
  return (
    <section className="vo">
      <div className="wrap vo-in">
        <blockquote className="vo-quote" key={s.name}>
          <p>“{s.text}”</p>
          <footer><strong>{s.name}</strong><span>{s.place} · {s.dept}</span></footer>
        </blockquote>
        <div className="vo-pick">
          <h2>In our patients' words</h2>
          <ul>
            {STORIES.map((st, n) => (
              <li key={st.name}>
                <button type="button" aria-current={n === i} onClick={() => setI(n)}>{st.name}</button>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="wrap vo-notes">
        {TIPS.map((t) => (
          <article key={t.title}>
            <h3>{t.title}</h3>
            <p>{t.text}</p>
            <span className="vo-tag">{t.tag}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- 9. the close
   A real ending: the one thing left to ask for, and the one thing that must never be
   mistaken for it. */
function Close() {
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setState("sending");
    try {
      const r = await api<{ ok?: boolean; message?: string }>("/api/callback", {
        method: "POST",
        body: {
          phone: String(f.get("phone") || ""),
          preferred_time: String(f.get("when") || ""),
          reason: String(f.get("reason") || ""),
        },
      });
      setMsg(r.message || "We'll call you back.");
      setState(r.ok === false ? "error" : "done");
    } catch {
      setMsg("We couldn't reach the hospital system just now. Please call us instead.");
      setState("error");
    }
  }
  return (
    <section className="cl">
      <div className="wrap cl-in">
        <div className="cl-say" data-reveal>
          <h2>Would you rather we called you?</h2>
          <p>
            Leave a number and a time that suits you. WellNest AI makes the call, and hands you to
            a member of staff the moment you ask for one.
          </p>
        </div>
        {state === "done" ? (
          <p className="cl-done" role="status">{msg}</p>
        ) : (
          <form className="cl-form" onSubmit={submit}>
            <div className="field">
              <label htmlFor="cb-phone">Mobile number</label>
              <input id="cb-phone" name="phone" className="input" inputMode="tel" required placeholder="98450 00001" />
            </div>
            <div className="field">
              <label htmlFor="cb-when">When should we call?</label>
              <input id="cb-when" name="when" className="input" required placeholder="Tomorrow morning" />
            </div>
            <div className="field">
              <label htmlFor="cb-reason">What is it about?</label>
              <input id="cb-reason" name="reason" className="input" placeholder="Booking a cardiology visit" />
            </div>
            {state === "error" && <p className="error-text" role="alert">{msg}</p>}
            <button className="btn btn-primary" disabled={state === "sending"}>
              {state === "sending" ? "Requesting…" : "Request a call back"}
            </button>
          </form>
        )}
      </div>

      <div className="wrap cl-sos">
        <Siren size={28} aria-hidden="true" />
        <div>
          <h2>Chest pain, breathlessness or a stroke? Do not book.</h2>
          <p>
            Call <a href="tel:108">108</a> now. Our emergency department at entrance B is open 24
            hours, and the assistant will not try to make you an appointment if you say this.
          </p>
        </div>
        <a className="btn btn-emergency" href={`tel:${HOSPITAL.ambulance.replace(/\s/g, "")}`}>
          Ambulance {HOSPITAL.ambulance}
        </a>
      </div>
    </section>
  );
}

export default function Home() {
  useEffect(() => { document.title = "WellNest Hospitals, Bengaluru · Book by chat, phone or web"; }, []);
  return (
    <>
      <Switchboard />
      <InsurerRail />
      <CaseSheet />
      <Plate />
      <OpenList />
      <Index />
      <Statement />
      <Checks />
      <Voices />
      <Close />
    </>
  );
}
