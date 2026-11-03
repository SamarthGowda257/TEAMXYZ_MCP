import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, session } from "../lib/api";
import { TokenSlip } from "../components/Bits";

const SIDE = ["Your bookings from chat, phone and web in one place", "Lab reports the moment they're ready", "Waitlist offers you can accept in one tap", "A family member kept informed, if you choose"];

function Side({ title }: { title: string }) {
  return (
    <div className="auth-side">
      <h1>{title}</h1>
      <ul>{SIDE.map((s) => <li key={s}><span className="token-bullet" aria-hidden="true" />{s}</li>)}</ul>
    </div>
  );
}

export function Login() {
  const nav = useNavigate();
  const [qs] = useSearchParams();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  useEffect(() => { document.title = "Log in · CareLine Hospitals"; }, []);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const r = await api<{ token: string }>("/api/auth/login", { method: "POST", body: { email, password: pw } });
      session.set(r.token);
      nav(qs.get("next") || "/portal");
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="auth">
      <Side title="Welcome back to CareLine" />
      <div className="auth-form">
        <h2>Log in</h2>
        <p>New here? <Link to={`/signup${qs.get("next") ? `?next=${encodeURIComponent(qs.get("next")!)}` : ""}`}>Create an account</Link>. If you've visited before, we'll find your record.</p>
        <form onSubmit={submit} noValidate>
          <div className="field"><label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
          <div className="field"><label htmlFor="pw">Password</label>
            <input id="pw" className="input" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required /></div>
          <p className="error-text" role="alert">{err}</p>
          <button className="btn btn-primary token-shape" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
        </form>
        <div className="demo-note">
          Demo patients use the password set on the server (DEMO_PASSWORD). Try{" "}
          <button type="button" onClick={() => setEmail("shanthamma.demo@example.com")}>Shanthamma K</button> (67, senior),{" "}
          <button type="button" onClick={() => setEmail("arjun.demo@example.com")}>Arjun Mehta</button> or{" "}
          <button type="button" onClick={() => setEmail("priya.demo@example.com")}>Priya Nair</button>.
        </div>
      </div>
    </div>
  );
}

export function Signup() {
  const nav = useNavigate();
  const [qs] = useSearchParams();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { document.title = "Create account · CareLine Hospitals"; }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setErr("");
    const body = Object.fromEntries(new FormData(e.currentTarget).entries());
    try {
      const r = await api<{ token: string }>("/api/auth/signup", { method: "POST", body });
      session.set(r.token);
      nav(qs.get("next") || "/portal");
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="auth">
      <Side title="One account for every visit" />
      <div className="auth-form">
        <h2>Create your account</h2>
        <p>Already registered at the hospital or booked by phone? Use the same mobile number and date of birth and we'll link your record.</p>
        <form onSubmit={submit} noValidate>
          <div className="field"><label htmlFor="name">Full name</label><input id="name" name="name" className="input" autoComplete="name" /></div>
          <div className="field"><label htmlFor="phone">Mobile number</label><input id="phone" name="phone" className="input" inputMode="tel" autoComplete="tel" required /></div>
          <div className="field"><label htmlFor="dob">Date of birth</label><input id="dob" name="date_of_birth" type="date" className="input" required /></div>
          <div className="field"><label htmlFor="em">Email</label><input id="em" name="email" type="email" className="input" autoComplete="email" required /></div>
          <div className="field"><label htmlFor="pw">Password <span className="hint">at least 8 characters</span></label>
            <input id="pw" name="password" type="password" minLength={8} className="input" autoComplete="new-password" required /></div>
          <p className="error-text" role="alert">{err}</p>
          <button className="btn btn-primary token-shape" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        </form>
        <p className="auth-alt">Have an account? <Link to="/login">Log in</Link></p>
      </div>
    </div>
  );
}

type Offer = { offer_code: string; doctor: string; department: string; room: string; fee_inr: number; date: string; time: string; status: string;
               seconds_left: number; patient_first_name: string };

export function Accept() {
  const [qs] = useSearchParams();
  const code = qs.get("code") || "";
  const [offer, setOffer] = useState<Offer | null>(null);
  const [err, setErr] = useState("");
  const [left, setLeft] = useState(0);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<any>(null);
  useEffect(() => { document.title = "Accept your slot · CareLine Hospitals"; }, []);
  useEffect(() => {
    if (!code) { setErr("This link has no offer code. Open the link from your email or text message again."); return; }
    api<Offer>(`/api/waitlist/offer/${encodeURIComponent(code)}`).then((o) => { setOffer(o); setLeft(o.seconds_left); }).catch((e) => setErr(e.message));
  }, [code]);
  useEffect(() => {
    if (!left) return;
    const t = window.setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(t);
  }, [left > 0]); // eslint-disable-line react-hooks/exhaustive-deps
  async function accept(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { setDone(await api(`/api/waitlist/offer/${encodeURIComponent(code)}/accept`, { method: "POST", body: { phone } })); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  const live = offer && offer.status === "open" && left > 0;
  return (
    <div className="accept">
      <div className="accept-card">
        {done ? (
          <>
            <h1>You're booked.</h1>
            <TokenSlip id={done.data.booking_id} spoken={done.data.booking_id_spoken}
              lines={[<strong key="a">{done.data.with}</strong>, `${done.data.date}, ${done.data.time}`, `Room ${done.data.room}`]} tone="accent" />
            <p>{done.message} A confirmation is on its way by email.</p>
            <Link className="btn btn-primary token-shape" to="/portal/appointments">See my appointments</Link>
          </>
        ) : offer ? (
          <>
            <h1>{live ? `${offer.patient_first_name}, a slot opened.` : "This offer has closed."}</h1>
            <TokenSlip id={offer.time} lines={[<strong key="a">{offer.doctor}</strong>, `${offer.department} · ${offer.date}`, `Room ${offer.room} · ₹${offer.fee_inr.toLocaleString("en-IN")}`]} tone={live ? "accent" : "card"} />
            {live ? (
              <>
                <p className={left < 300 ? "countdown low" : "countdown"} aria-live="off">Held for you for {Math.floor(left / 60)} min {String(left % 60).padStart(2, "0")} s</p>
                <form onSubmit={accept}>
                  <div className="field"><label htmlFor="ph">Confirm with your mobile number</label>
                    <input id="ph" className="input" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required /></div>
                  <p className="error-text" role="alert">{err}</p>
                  <button className="btn btn-primary token-shape" disabled={busy}>{busy ? "Booking…" : "Accept this slot"}</button>
                </form>
              </>
            ) : (
              <p>The 30 minutes have passed or someone else took the slot. You're still on the waitlist, and we'll offer you the next opening. <Link to="/portal/book">See other free slots</Link>.</p>
            )}
          </>
        ) : err ? (<><h1>We couldn't open this offer.</h1><p className="error-text">{err}</p><Link to="/portal/book">See free slots instead</Link></>)
          : <p>Opening your offer…</p>}
      </div>
    </div>
  );
}
