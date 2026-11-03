import { useEffect, type ReactNode } from "react";
import { Link, NavLink, Navigate, useLocation } from "react-router-dom";
import { CalendarPlus, CalendarDays, FileText, Hourglass, Home, MessageCircle, UserRound } from "lucide-react";
import { session, type Me } from "../lib/api";
import { useApi } from "../lib/hooks";
import { openChat, setChatPatient } from "../lib/chat";
import { Loading } from "./Bits";

const NAV = [
  { to: "/portal", label: "Overview", icon: Home, end: true },
  { to: "/portal/book", label: "Book", icon: CalendarPlus },
  { to: "/portal/appointments", label: "Appointments", icon: CalendarDays },
  { to: "/portal/reports", label: "Lab reports", icon: FileText },
  { to: "/portal/waitlist", label: "Waitlist", icon: Hourglass },
  { to: "/portal/profile", label: "Profile", icon: UserRound },
];

/** Logged-in shell: names the product and the patient, keeps the main job (booking) one click away. */
export function PortalShell({ title, children, actions }: { title: string; children: (me: Me, reloadMe: () => void) => ReactNode; actions?: ReactNode }) {
  const loc = useLocation();
  const me = useApi<Me>(session.loggedIn() ? "/api/me" : null);
  useEffect(() => { document.title = `${title} · My CareLine`; }, [title]);
  useEffect(() => { if (me.data) setChatPatient({ name: me.data.name, phone: me.data.phone }); }, [me.data]);
  if (!session.loggedIn()) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return (
    <div className="portal has-mobile-bar">
      <aside className="portal-side" aria-label="My CareLine">
        <div className="who">
          <p className="who-name">{me.data?.name || " "}</p>
          <p className="who-meta">{me.data ? `${me.data.id}${me.data.age != null ? ` · ${me.data.age} yrs` : ""}` : " "}</p>
        </div>
        <nav className="portal-nav">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}><Icon size={18} aria-hidden="true" />{label}</NavLink>
          ))}
        </nav>
        <button type="button" className="side-chat" onClick={openChat}><MessageCircle size={18} aria-hidden="true" />Ask CareLine</button>
      </aside>
      <div className="portal-main">
        <div className="title-row">
          <h1>{title}</h1>
          {actions}
        </div>
        {me.loading && !me.data ? <Loading /> : me.data ? children(me.data, me.reload) : <p className="error-text">{me.error}</p>}
      </div>
      <nav className="mobile-bar" aria-label="Quick actions">
        <Link to="/portal/book"><CalendarPlus size={20} aria-hidden="true" />Book</Link>
        <Link to="/portal/reports"><FileText size={20} aria-hidden="true" />Reports</Link>
        <button type="button" onClick={openChat}><MessageCircle size={20} aria-hidden="true" />Chat</button>
      </nav>
    </div>
  );
}
