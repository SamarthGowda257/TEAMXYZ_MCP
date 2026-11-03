import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Menu, MessageCircle, Phone, X } from "lucide-react";
import { session } from "../lib/api";
import { chatConfigured, onChatFallback, openChat, resetChat } from "../lib/chat";
import { useLoggedIn, useTextSize } from "../lib/hooks";

/** The CareLine mark: the OPD token slip with a cross punched through it. */
export function Mark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.72} viewBox="0 0 50 36" aria-hidden="true" className="mark">
      <path d="M8 0h34a8 8 0 0 1 8 8v4.5a5.5 5.5 0 0 0 0 11V28a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8v-4.5a5.5 5.5 0 0 0 0-11V8a8 8 0 0 1 8-8z" fill="var(--accent)" />
      <path d="M22 9h6v6h6v6h-6v6h-6v-6h-6v-6h6z" fill="var(--accent-ink)" />
    </svg>
  );
}

export function EmergencyBand() {
  return (
    <div className="emergency" role="note">
      <span>Chest pain, breathlessness or stroke signs?</span>
      <a href="tel:108"><Phone size={16} aria-hidden="true" /> Call 108 now</a>
      <span className="emergency-more">Emergency entrance B is open 24 hours.</span>
    </div>
  );
}

export function SiteHeader() {
  const li = useLoggedIn();
  const [open, setOpen] = useState(false);
  const [lg, setLg] = useTextSize();
  const nav = useNavigate();
  const logout = () => { session.set(null); resetChat(); nav("/"); };
  return (
    <header className="site-header">
      <a className="skip" href="#main">Skip to content</a>
      <EmergencyBand />
      <div className="bar">
        <Link to="/" className="wordmark" aria-label="CareLine Hospitals, home"><Mark /> <span>CareLine</span></Link>
        <button className="menu-btn" aria-expanded={open} aria-controls="site-nav" onClick={() => setOpen(!open)}>
          {open ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}<span>{open ? "Close" : "Menu"}</span>
        </button>
        <nav id="site-nav" className={open ? "site-nav open" : "site-nav"} aria-label="Main" onClick={() => setOpen(false)}>
          <NavLink to="/doctors">Doctors</NavLink>
          <NavLink to="/insurance">Insurance</NavLink>
          <NavLink to="/contact">Visit us</NavLink>
          {li ? <NavLink to="/portal">My CareLine</NavLink> : <NavLink to="/login">Log in</NavLink>}
          <button type="button" className="size-btn" aria-pressed={lg} onClick={(e) => { e.stopPropagation(); setLg(!lg); }}>
            {lg ? "Normal text" : "Larger text"}
          </button>
          {li ? <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={logout}>Log out</button>
              : <Link className="btn btn-primary btn-sm token-shape" to="/portal/book">Book a visit</Link>}
        </nav>
      </div>
    </header>
  );
}

const LETTERS = ["C", "a", "r", "e", "L", "i", "n", "e"];
const HEIGHTS = [100, 74, 66, 70, 100, 82, 62, 88];
const FIELDS = ["var(--accent)", "var(--field-1)", "var(--field-2)", "var(--field-3)", "var(--accent)", "var(--field-4)", "var(--field-1)", "var(--field-3)"];

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-mark" aria-hidden="true">
        {LETTERS.map((l, i) => (
          <span key={i} style={{ height: `${HEIGHTS[i]}%`, background: FIELDS[i], color: FIELDS[i] === "var(--accent)" ? "var(--accent-ink)" : "var(--ink)" }}>{l}</span>
        ))}
      </div>
      <div className="footer-cols">
        <div><h2 className="footer-h">Patients</h2><Link to="/portal/book">Book a visit</Link><Link to="/portal/reports">Lab reports</Link><Link to="/portal/waitlist">Waitlist</Link><Link to="/portal">My CareLine</Link></div>
        <div><h2 className="footer-h">Hospital</h2><Link to="/doctors">Doctors</Link><Link to="/insurance">Insurance</Link><Link to="/contact">Visit us</Link></div>
        <div className="footer-contact">
          <p><strong>CareLine Hospitals</strong><br />42 Outer Ring Road, Marathahalli<br />Bengaluru 560037</p>
          <p>Front desk <a href="tel:+918040001234">080 4000 1234</a><br />Outpatient Mon–Sat, 8 AM to 8 PM · Emergency 24 hours</p>
        </div>
      </div>
      <div className="footer-last">
        <p>A Talkdesk AI Hackday project by TeamXYZ. CareLine Hospitals is fictional and every patient record is invented; a real deployment would need consent, retention rules and DPDP Act compliance.</p>
        <button type="button" className="btn btn-accent btn-sm token-shape" onClick={openChat}><MessageCircle size={18} aria-hidden="true" /> Ask CareLine</button>
      </div>
    </footer>
  );
}

/** Shown when chat isn't connected yet (no Talkdesk touchpoint configured). */
export function ChatFallback() {
  const [open, setOpen] = useState(false);
  useEffect(() => onChatFallback(() => setOpen((o) => !o)) as () => void, []);
  return (
    <>
      {!chatConfigured() && (
        <button type="button" className="chat-fab btn btn-accent token-shape" onClick={() => setOpen(!open)} aria-expanded={open}>
          <MessageCircle size={20} aria-hidden="true" /> Ask CareLine
        </button>
      )}
      {open && (
        <div className="chat-panel" role="dialog" aria-label="CareLine Assistant">
          <h2>CareLine Assistant</h2>
          <p>Our chat assistant is being connected. You can book online now, or call the front desk on <a href="tel:+918040001234">080 4000 1234</a>.</p>
          <div className="row">
            <Link className="btn btn-primary btn-sm token-shape" to="/portal/book" onClick={() => setOpen(false)}>Book online</Link>
            <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={() => setOpen(false)}>Close</button>
          </div>
        </div>
      )}
    </>
  );
}

export function SiteLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main id="main">{children}</main>
      <SiteFooter />
      <ChatFallback />
    </>
  );
}
