/*
  The public pages, rebuilt on one grammar.

  WellNest's product is a single brain answering every channel over one record, so the website
  is set like the hospital's own paperwork: hairline-ruled registers, an index with a facing
  plate, and prose in a single column of real measure. No card decks, no four-column strips.

  Every page opens with the same asymmetric head (PageHero — also used by /architecture) and
  every list of real data is a table or a ruled row, because that is what the data is.
*/
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  ArrowRight, ArrowUpRight, CheckCircle2, Clock, Mail, MapPin, MessageCircle, Phone, Siren,
} from "lucide-react";
import { api, rupees, type DoctorCard } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ErrorNote, Loading } from "../components/Bits";
import { openChat, voiceNumber } from "../lib/chat";
import { Icon } from "../components/Icon";
import { InsurerRail } from "../components/site/Insurers";
import { CENTRES, CENTRE_IMAGES, FACILITIES, HOSPITAL, MILESTONES, PACKAGES, VISITOR_INFO } from "../content";

/** Page head: the title at full display size, the lead set beside it, one gold hairline under. */
export function PageHero({ title, lead, crumb }: { title: string; lead: ReactNode; crumb: string }) {
  return (
    <div className="pt">
      <div className="wrap pt-in">
        <nav className="pt-crumb" aria-label="Breadcrumb">
          <Link to="/">Home</Link><span aria-hidden="true">/</span>{crumb}
        </nav>
        <h1>{title}</h1>
        <p className="pt-lead">{lead}</p>
      </div>
    </div>
  );
}

/** The three health-check packages as a price list of rows. Shared by /specialities. */
function PriceRows() {
  return (
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
  );
}

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// ------------------------------------------------------------------ doctors
/**
 * The register. Forty-five consultants as one ruled list with the department index as a rail,
 * because this is the same list the assistant reads out on the phone — so it should look like
 * a list, not like forty-five identical cards.
 */
export function Doctors() {
  useEffect(() => { document.title = "Find a doctor · WellNest Hospitals"; }, []);
  const [qs, setQs] = useSearchParams();
  const depts = useApi<{ name: string; doctors: number; floor: string }[]>("/api/departments");
  const all = useApi<DoctorCard[]>("/api/doctors");
  const [lang, setLang] = useState("");
  const [day, setDay] = useState("");
  const [q, setQ] = useState("");
  const dept = qs.get("department") || "";
  const langs = useMemo(
    () => [...new Set((all.data || []).flatMap((d) => d.languages.split(", ")))].sort(),
    [all.data],
  );
  const list = useMemo(() => (all.data || []).filter((d) =>
    (!dept || d.department === dept) &&
    (!lang || d.languages.includes(lang)) &&
    (!day || (d.day_codes || []).includes(DAYS.indexOf(day) + 1)) &&
    (!q || d.name.toLowerCase().includes(q.toLowerCase()))), [all.data, dept, lang, day, q]);

  const total = all.data?.length || 0;
  const pick = (name: string) => setQs(name ? { department: name } : {});

  return (
    <>
      <PageHero
        crumb="Find a doctor"
        title="The consultant register"
        lead={`All ${total || 45} senior consultants across ${depts.data?.length || 14} specialities, with their real OPD days, timings and fees — the same list the assistant reads when you ask it on the phone.`}
      />
      <div className="wrap dr">
        <aside className="dr-rail" aria-label="Specialities">
          <h2>Speciality</h2>
          <ul>
            <li>
              <button type="button" aria-current={!dept || undefined} onClick={() => pick("")}>
                All specialities <span className="num">{total || "—"}</span>
              </button>
            </li>
            {depts.data?.map((d) => (
              <li key={d.name}>
                <button type="button" aria-current={dept === d.name || undefined} onClick={() => pick(d.name)}>
                  {d.name} <span className="num">{d.doctors}</span>
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-primary btn-sm dr-ask" onClick={openChat}>
            <MessageCircle size={16} aria-hidden="true" /> Ask the assistant
          </button>
        </aside>

        <div className="dr-main">
          <form className="dr-filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter the register">
            <div className="field">
              <label htmlFor="f-q">Name</label>
              <input id="f-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Iyer" />
            </div>
            <div className="field">
              <label htmlFor="f-lang">Language</label>
              <select id="f-lang" className="input" value={lang} onChange={(e) => setLang(e.target.value)}>
                <option value="">Any language</option>
                {langs.map((l) => <option key={l}>{l}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="f-day">Consulting day</label>
              <select id="f-day" className="input" value={day} onChange={(e) => setDay(e.target.value)}>
                <option value="">Any day</option>
                {DAYS.map((d) => <option key={d}>{d}</option>)}
              </select>
            </div>
            <div className="dr-f-meta">
              <p className="dr-count" aria-live="polite">
                {all.data ? `${list.length} of ${total}` : ""}
              </p>
              {(dept || lang || day || q) && (
                <button type="button" className="lnk" onClick={() => { pick(""); setLang(""); setDay(""); setQ(""); }}>
                  Clear filters
                </button>
              )}
            </div>
          </form>

          {all.loading && !all.data && <Loading label="Loading the register" />}
          {all.error && <ErrorNote message={all.error} onRetry={all.reload} />}

          {!!list.length && (
            <table className="dr-table">
              <caption className="sr-only">WellNest consultants{dept ? ` in ${dept}` : ""}</caption>
              <thead>
                <tr>
                  <th scope="col">Consultant</th>
                  <th scope="col">Speciality</th>
                  <th scope="col">Consults</th>
                  <th scope="col">Speaks</th>
                  <th scope="col" className="dr-r">Fee</th>
                  <th scope="col"><span className="sr-only">Book</span></th>
                </tr>
              </thead>
              <tbody>
                {list.map((d) => (
                  <tr key={d.code || d.name}>
                    <th scope="row" data-label="Consultant">
                      {d.name}
                      <small>{d.qualification}{d.experience_years ? ` · ${d.experience_years} years` : ""}</small>
                    </th>
                    <td data-label="Speciality">
                      {d.department}
                      <small>Room {d.room}</small>
                    </td>
                    <td data-label="Consults">
                      {d.days}
                      <small className="num">{d.hours}</small>
                    </td>
                    <td data-label="Speaks">{d.languages}</td>
                    <td data-label="Fee" className="dr-r num">{rupees(d.fee_inr)}</td>
                    <td className="dr-act">
                      <Link className="btn btn-quiet btn-sm" to={`/portal/book?doctor=${encodeURIComponent(d.name)}`}>
                        Book
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {all.data && !list.length && (
            <p className="dr-none">
              No consultant matches these filters. Try any day, another language, or{" "}
              <button type="button" className="lnk" onClick={openChat}>ask the assistant</button>.
            </p>
          )}
        </div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ insurance
type Ins = { code: string; name: string; mode: string; tpa: string; documents: string };
const MODE: Record<string, string> = {
  both: "Cashless and reimbursement",
  cashless: "Cashless",
  reimbursement: "Reimbursement only",
};

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
      const r = await api<any>("/api/coverage/estimate", {
        method: "POST",
        body: {
          insurer: f.get("insurer"),
          procedure: what.startsWith("p:") ? what.slice(2) : "",
          department: what.startsWith("d:") ? what.slice(2) : "",
        },
      });
      setRes({ msg: r.message, d: r.data });
    } catch (err: any) { setRes({ err: err.message }); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHero
        crumb="Insurance & TPA"
        title="Insurance and cashless treatment"
        lead="Ten insurers and two government schemes. Our TPA desk raises the pre-approval for you, and the assistant can tell you what you are likely to pay before you come in."
      />
      <InsurerRail label="Empanelled with" />
      <div className="wrap iz">
        <form className="iz-check" onSubmit={check}>
          <h2>What will this cost me?</h2>
          <p className="iz-sub">An estimate for a scan, test or consultation against your own policy.</p>
          <div className="field">
            <label htmlFor="c-ins">Your insurer or scheme</label>
            <select id="c-ins" name="insurer" className="input" required>
              {ins.data?.map((i) => <option key={i.code}>{i.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="c-what">Test, scan or consultation</label>
            <select id="c-what" name="what" className="input" required>
              <optgroup label="Tests and scans">
                {procs.data?.map((p) => <option key={p.code} value={`p:${p.code}`}>{p.name}</option>)}
              </optgroup>
              <optgroup label="Consultations">
                {depts.data?.map((d) => <option key={d.name} value={`d:${d.name}`}>{d.name}</option>)}
              </optgroup>
            </select>
          </div>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Checking…" : "Check my cover"}</button>
          <div aria-live="polite">
            {res && "err" in res && <p className="error-text">{res.err}</p>}
            {res && "msg" in res && (
              <div className={`iz-res cov-${res.d.covered}`}>
                <p className="iz-verdict">
                  {res.d.covered === "yes" ? "Covered" : res.d.covered === "partial" ? "Partly covered" : "Not covered"}
                  {res.d.estimated_patient_share_inr != null && (
                    <span>Your estimated share: {rupees(res.d.estimated_patient_share_inr)}</span>
                  )}
                </p>
                <p>{res.msg}</p>
              </div>
            )}
          </div>
          <p className="iz-fine">An estimate, not a quotation. The final figure comes from your insurer's approval.</p>
        </form>

        <div className="iz-list">
          <h2 className="sec-h">Every insurer and scheme we work with</h2>
          <table className="iz-table">
            <thead>
              <tr>
                <th scope="col">Insurer or scheme</th>
                <th scope="col">Facility</th>
                <th scope="col">Documents to bring</th>
              </tr>
            </thead>
            <tbody>
              {ins.data?.map((i) => (
                <tr key={i.code}>
                  <th scope="row" data-label="Insurer">{i.name}<small>TPA: {i.tpa}</small></th>
                  <td data-label="Facility">{MODE[i.mode]}</td>
                  <td data-label="Documents">{i.documents}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {ins.loading && !ins.data && <Loading label="Loading insurers" />}
          <div className="iz-desk">
            <h3>TPA and insurance desk</h3>
            <dl>
              <div><dt>Where</dt><dd>Ground floor, next to admissions</dd></div>
              <div><dt>Phone</dt><dd className="num">080 4000 1250</dd></div>
              <div><dt>Open</dt><dd>9 AM to 6 PM, Monday to Saturday</dd></div>
            </dl>
            <p>
              MRI, CT, endoscopy and every planned admission need pre-approval from your insurer.
              Send us your policy details at least 24 hours ahead and we will raise it for you.
            </p>
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
  const v = voiceNumber();
  const KEYS: [string, string][] = [
    ["emergency", "Emergency"], ["visiting", "Visiting hours"], ["parking", "Parking"],
    ["pharmacy", "Pharmacy"], ["facilities", "On site"], ["hours", "Clinic hours"],
  ];
  return (
    <>
      <PageHero
        crumb="Contact"
        title="Find us, call us, write to us"
        lead="We are on Outer Ring Road in Marathahalli, next to the Innovative Multiplex. Outpatient clinics run Monday to Saturday; the emergency department never closes."
      />
      <div className="wrap ct">
        <div className="ct-main">
          <dl className="rows">
            <div><dt>Address</dt><dd><MapPin size={17} aria-hidden="true" />{HOSPITAL.address}</dd></div>
            <div>
              <dt>WellNest AI</dt>
              <dd>
                <Phone size={17} aria-hidden="true" />
                <span><a className="num" href={v.href}>{v.label}</a><small>Answers, books and moves appointments, 24 hours</small></span>
              </dd>
            </div>
            <div>
              <dt>Ambulance</dt>
              <dd><Phone size={17} aria-hidden="true" /><a className="num" href="tel:08040001108">{HOSPITAL.ambulance}</a></dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd><Mail size={17} aria-hidden="true" /><a href={`mailto:${HOSPITAL.email}`}>{HOSPITAL.email}</a></dd>
            </div>
            <div>
              <dt>Hours</dt>
              <dd><Clock size={17} aria-hidden="true" />OPD Mon–Sat 8 AM – 8 PM · Emergency and pharmacy 24×7</dd>
            </div>
          </dl>
          <div className="ct-acts">
            <a
              className="btn btn-primary"
              href="https://www.google.com/maps/search/?api=1&query=Outer+Ring+Road+Marathahalli+Bengaluru"
              target="_blank" rel="noopener"
            >
              Get directions <ArrowUpRight size={17} aria-hidden="true" />
            </a>
            <button type="button" className="btn btn-quiet" onClick={openChat}>
              <MessageCircle size={17} aria-hidden="true" /> Ask on chat instead
            </button>
          </div>
          <p className="ct-sos">
            <Siren size={20} aria-hidden="true" />
            <span>For a life-threatening emergency call <a href="tel:108">108</a> first. Emergency is at entrance B, ground floor.</span>
          </p>
        </div>

        <div className="ct-side">
          <h2 className="sec-h">Before you come</h2>
          {info.error && <ErrorNote message={info.error} onRetry={info.reload} />}
          {info.loading && !info.data && <Loading label="Loading hospital information" />}
          <dl className="rows rows-tight">
            {info.data && KEYS.filter(([k]) => info.data![k]).map(([k, label]) => (
              <div key={k} className={k === "emergency" ? "is-alert" : undefined}>
                <dt>{label}</dt><dd>{info.data![k]}</dd>
              </div>
            ))}
          </dl>
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
      <PageHero
        crumb="About us"
        title="About WellNest Hospitals"
        lead="A 350-bed multi-speciality hospital, founded in 2009 by doctors who were tired of watching East Bengaluru drive across the city for serious care."
      />
      <div className="wrap ab">
        <div className="ab-prose">
          <h2>Our story</h2>
          <p>
            WellNest began as a 120-bed hospital on Outer Ring Road, started by a group of doctors
            who were tired of seeing patients from Marathahalli, Whitefield and Bellandur spend
            hours in traffic to reach a hospital for a heart attack, a difficult delivery or a
            stroke.
          </p>
          <p>
            Seventeen years later we are a 350-bed hospital with fourteen specialities, sixty
            critical-care beds, a 24-hour cath lab and a level III neonatal ICU. More than 1,200
            people visit our outpatient clinics every day.
          </p>
          <h2>What we hold ourselves to</h2>
          <ul className="ticks">
            <li><CheckCircle2 size={19} aria-hidden="true" /> Multi-disciplinary teams meet daily for every admitted patient.</li>
            <li><CheckCircle2 size={19} aria-hidden="true" /> Every inpatient has a named nurse and a named consultant.</li>
            <li><CheckCircle2 size={19} aria-hidden="true" /> Prices for consultations, scans and packages are published on this website.</li>
            <li><CheckCircle2 size={19} aria-hidden="true" /> The AI front desk answers chat and phone around the clock, and hands over to a person whenever you ask.</li>
          </ul>
          <h2>Our mission</h2>
          <p>
            To give every patient the right care at the right time, explained clearly and priced
            fairly, with dignity for patients of every age.
          </p>
        </div>

        <aside className="ab-years" aria-label="Milestones">
          <h2>Milestones</h2>
          <ol>
            {MILESTONES.map((m) => (
              <li key={m.year}><span className="ab-y num">{m.year}</span><span>{m.text}</span></li>
            ))}
          </ol>
        </aside>
      </div>

      <section className="ms ms-flat">
        <div className="wrap ms-in">
          <p className="ms-say">
            <b>350</b> beds, <b>60</b> of them critical care. <b>45</b> senior consultants across
            fourteen departments. Two <b>3 Tesla</b> MRI scanners and two <b>128-slice</b> CT
            scanners. Emergency, trauma, pharmacy and lab open <b>24×7</b>.
          </p>
        </div>
      </section>

      <div className="wrap ab-fac">
        <h2 className="sec-h">Facilities</h2>
        <dl className="rows">
          {FACILITIES.map((f) => (
            <div key={f.title}>
              <dt><Icon name={f.icon} size={18} /> {f.title}</dt>
              <dd>{f.text}</dd>
            </div>
          ))}
        </dl>
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
  useEffect(() => {
    if (hash) window.setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), 300);
  }, [hash, depts.data]);
  const floorOf = (name: string) => depts.data?.find((d) => d.name === name)?.floor || "";
  return (
    <>
      <PageHero
        crumb="Specialities"
        title="Specialities and centres"
        lead="Fourteen departments and six centres where the complicated cases go, each with senior consultants, modern theatres and critical care in the same building."
      />

      <div className="sp">
        {CENTRES.map((c, i) => {
          const team = (docs.data || []).filter((d) => d.department === c.dept);
          return (
            <section key={c.key} id={c.key} className={i % 2 ? "sp-plate is-flip" : "sp-plate"}>
              <figure>
                <img src={CENTRE_IMAGES[c.key]} alt="" aria-hidden="true" loading="lazy" decoding="async" />
              </figure>
              <div className="sp-body">
                <h2>{c.name}</h2>
                <p className="sp-dept">{c.dept}{floorOf(c.dept) ? ` · ${floorOf(c.dept)}` : ""}</p>
                <p className="sp-sum">{c.summary}</p>
                <ul className="sp-treats">
                  {c.treats.map((t) => <li key={t}>{t}</li>)}
                </ul>
                {team.length > 0 && (
                  <p className="sp-team">
                    <span>Consultants</span>{team.map((d) => d.name).join(", ")}
                  </p>
                )}
                <div className="sp-acts">
                  <button type="button" className="btn btn-primary btn-sm" onClick={openChat}>Chat to book</button>
                  <Link className="lnk-strong" to={`/doctors?department=${encodeURIComponent(c.dept)}`}>
                    See the {team.length || ""} consultants <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                </div>
              </div>
            </section>
          );
        })}
      </div>

      <div className="wrap sp-tail">
        <h2 className="sec-h">All fourteen departments</h2>
        {depts.loading && !depts.data && <Loading />}
        <ul className="dl-rows">
          {depts.data?.map((d) => (
            <li key={d.name}>
              <Link to={`/doctors?department=${encodeURIComponent(d.name)}`}>
                <span className="dl-name">{d.name}</span>
                <span className="dl-desc">{d.description}</span>
                <span className="dl-meta num">{d.doctors} doctors · {d.floor}</span>
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>

        <h2 className="sec-h" id="packages">Health check-up packages</h2>
        <PriceRows />
      </div>
    </>
  );
}

// ------------------------------------------------------------------ patients & visitors
export function Visitors() {
  useEffect(() => { document.title = "Patients & visitors · WellNest Hospitals"; }, []);
  const v = voiceNumber();
  return (
    <>
      <PageHero
        crumb="Patients & visitors"
        title="Before you come in"
        lead="Timings, what to bring, parking, visiting rules and your rights as a patient — the things people ring us about most, written down."
      />
      <div className="wrap vs">
        <dl className="rows">
          {VISITOR_INFO.map((x) => (
            <div key={x.title}><dt>{x.title}</dt><dd>{x.text}</dd></div>
          ))}
        </dl>

        <p className="vs-ask">
          <span>
            Booking, moving or cancelling a visit takes one conversation — on the chat here, or on{" "}
            <a className="num" href={v.href}>{v.label}</a>, any hour of the day.
          </span>
          <button type="button" className="btn btn-primary btn-sm" onClick={openChat}>
            <MessageCircle size={16} aria-hidden="true" /> Start a chat
          </button>
        </p>

        <div className="vs-two">
          <div>
            <h2 className="sec-h">Your outpatient visit, in order</h2>
            <ol className="vs-steps">
              <li><strong>Book ahead</strong> online, on chat or by phone. A booking ID arrives by email and SMS.</li>
              <li><strong>Arrive fifteen minutes early</strong> at the ground-floor registration desk with photo ID and your old reports.</li>
              <li><strong>Pay or show your insurance card</strong> at billing. Cashless insurers are verified on the spot.</li>
              <li><strong>See your doctor</strong> in the room printed on your booking. Tests are done the same day where possible.</li>
              <li><strong>Collect your reports online</strong> in your portal, or ask the assistant to email them.</li>
            </ol>
          </div>
          <div>
            <h2 className="sec-h">Your rights, and ours</h2>
            <ul className="ticks">
              <li><CheckCircle2 size={19} aria-hidden="true" /> To be treated with dignity and privacy, without discrimination.</li>
              <li><CheckCircle2 size={19} aria-hidden="true" /> To know the cost of treatment in advance and receive an itemised bill.</li>
              <li><CheckCircle2 size={19} aria-hidden="true" /> To see and receive copies of your medical records.</li>
              <li><CheckCircle2 size={19} aria-hidden="true" /> To a second opinion, and to refuse treatment after being informed.</li>
              <li><CheckCircle2 size={19} aria-hidden="true" /> To share an accurate history and follow hospital safety rules.</li>
            </ul>
            <div className="vs-note">
              <h3>Senior citizen desk</h3>
              <p>
                At entrance B: wheelchair help, priority registration and billing, and a staff member
                to walk you to your doctor. Ask for it when you book and it will be waiting.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
