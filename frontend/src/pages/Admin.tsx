/*
  WellNest staff console — one place to run the hospital.

  This is not a read-only board. Every section here writes through /api/admin/*, guarded by the
  signed admin cookie, and every write lands in the same `resolutions` audit trail as the AI's own
  actions, with actor "staff". The old /dashboard is folded in as the Today view and its route now
  redirects here.

  What this console honestly cannot show: word-for-word chat and call transcripts. Talkdesk never
  sends them to WellNest. What it does show is complete — every action the assistant took, and the
  summary it wrote at the end of each conversation. The patient timeline makes that distinction
  explicit rather than faking a transcript.
*/
import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import {
  BookOpen, Building2, CalendarDays, ExternalLink, FlaskConical, Gauge, LayoutDashboard, LifeBuoy,
  LogOut, MessagesSquare, PhoneOutgoing, Pill, ShieldCheck, Stethoscope, Users, Wallet,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import { Mark } from "../components/Site";
import { Loading } from "./adminKit";
import { AdminInsurance, AdminKnowledge, AdminTests } from "./AdminHospital";
import { Today } from "./admin/Today";
import { Escalations } from "./admin/Escalations";
import { Appointments } from "./admin/Appointments";
import { Conversations } from "./admin/Conversations";
import { Outbound } from "./admin/Outbound";
import { Patients } from "./admin/Patients";
import { Doctors } from "./admin/Doctors";
import { Departments } from "./admin/Departments";
import { Pharmacy } from "./admin/Pharmacy";
import { Wallets } from "./admin/Wallets";
import { SystemView } from "./admin/SystemView";

/* The human's actual replies happen in Talkdesk Conversations; this console is the context,
   the control surface and the record beside it. */
const TALKDESK_CONVERSATIONS = "https://pesit-hackathon.mytalkdesk.com/atlas/apps/conversations";

export function AdminLogin({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await api("/api/admin/login", { method: "POST", body: { username, password } }); onDone(); }
    catch (e2) { setErr(e2 instanceof ApiError ? e2.message : "Could not sign in."); }
    finally { setBusy(false); }
  };

  return (
    <div className="ad-login">
      <form className="ad-login-card" onSubmit={submit}>
        <Mark size={44} />
        <h1>WellNest staff console</h1>
        <p className="ad-login-sub">Appointments, escalations, the pharmacy, wallets and the whole patient record.</p>
        <div className="field">
          <label htmlFor="au">Admin ID</label>
          <input id="au" className="input" autoComplete="username" value={username}
                 onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="ap">Password</label>
          <input id="ap" className="input" type="password" autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {err && <p className="error-text" role="alert">{err}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="ad-login-note">Patients sign in on the main site. This console is for hospital staff.</p>
      </form>
    </div>
  );
}

const NAV = [
  { to: "/admin", end: true, label: "Today", icon: LayoutDashboard },
  { to: "/admin/escalations", label: "Escalations", icon: LifeBuoy },
  { to: "/admin/appointments", label: "Appointments", icon: CalendarDays },
  { to: "/admin/conversations", label: "Conversations", icon: MessagesSquare },
  { to: "/admin/outbound", label: "Outbound calls", icon: PhoneOutgoing },
  { to: "/admin/patients", label: "Patients", icon: Users },
];

const REF_NAV = [
  { to: "/admin/doctors", label: "Doctors", icon: Stethoscope },
  { to: "/admin/departments", label: "Departments", icon: Building2 },
  { to: "/admin/pharmacy", label: "Pharmacy", icon: Pill },
  { to: "/admin/wallets", label: "HealthCredits", icon: Wallet },
  { to: "/admin/tests", label: "Tests & scans", icon: FlaskConical },
  { to: "/admin/insurance", label: "Insurance", icon: ShieldCheck },
  { to: "/admin/knowledge", label: "Knowledge base", icon: BookOpen },
  { to: "/admin/system", label: "System", icon: Gauge },
];

export function Admin() {
  const [who, setWho] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  /* Lifted here so Escalations, Conversations and Wallets can all open the same patient record. */
  const [openPatient, setOpenPatient] = useState<number | null>(null);
  const nav = useNavigate();

  const check = useCallback(async () => {
    try { const r = await api<{ user: string }>("/api/admin/me"); setWho(r.user); }
    catch { setWho(null); }
    finally { setChecked(true); }
  }, []);
  useEffect(() => { check(); document.title = "Staff console — WellNest Hospitals"; }, [check]);

  const out = async () => {
    try { await api("/api/admin/logout", { method: "POST" }); } catch { /* cookie may already be gone */ }
    setWho(null); nav("/admin");
  };

  const toPatient = (id: number) => { setOpenPatient(id); nav("/admin/patients"); };

  if (!checked) return <div className="ad-boot"><Loading rows={3} /></div>;
  if (!who) return <AdminLogin onDone={check} />;

  return (
    <div className="ad-shell">
      <aside className="ad-side">
        <div className="ad-brand"><Mark size={30} /><span>WellNest<small>Staff console</small></span></div>
        <nav aria-label="Admin">
          <p className="ad-nav-h">Operations</p>
          {NAV.map(({ to, end, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={end}><Icon size={18} aria-hidden="true" /> {label}</NavLink>
          ))}
          <p className="ad-nav-h">The hospital</p>
          {REF_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}><Icon size={18} aria-hidden="true" /> {label}</NavLink>
          ))}
        </nav>
        <a className="ad-side-out" href={TALKDESK_CONVERSATIONS} target="_blank" rel="noreferrer">
          <ExternalLink size={16} aria-hidden="true" /> Talkdesk Conversations
        </a>
      </aside>

      <div className="ad-main">
        <header className="ad-top">
          <span className="ad-live"><i /> Live</span>
          <span className="ad-who">{who}</span>
          <button type="button" className="btn btn-quiet btn-sm" onClick={out}>
            <LogOut size={15} aria-hidden="true" /> Sign out
          </button>
        </header>
        <div className="ad-body">
          <Routes>
            <Route index element={<Today />} />
            <Route path="today" element={<Navigate to="/admin" replace />} />
            <Route path="escalations" element={<Escalations onPatient={toPatient} />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="conversations" element={<Conversations onPatient={toPatient} />} />
            <Route path="outbound" element={<Outbound />} />
            <Route path="reminders" element={<Navigate to="/admin/outbound" replace />} />
            <Route path="patients" element={<Patients open={openPatient} onOpen={setOpenPatient} />} />
            <Route path="doctors" element={<Doctors />} />
            <Route path="departments" element={<Departments />} />
            <Route path="pharmacy" element={<Pharmacy />} />
            <Route path="orders" element={<Navigate to="/admin/pharmacy" replace />} />
            <Route path="wallets" element={<Wallets onPatient={toPatient} />} />
            <Route path="tests" element={<AdminTests />} />
            <Route path="insurance" element={<AdminInsurance />} />
            <Route path="knowledge" element={<AdminKnowledge />} />
            <Route path="system" element={<SystemView />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
