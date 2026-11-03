import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Ambulance, Clock, Mail, MapPin, Menu, MessageCircle, Phone, X } from "lucide-react";
import { session } from "../lib/api";
import { chatConfigured, onChatFallback, openChat, resetChat, voiceNumber } from "../lib/chat";
import { useLoggedIn, useTextSize } from "../lib/hooks";
import { CENTRES, HOSPITAL } from "../content";

/** CareLine logo: a medical cross inside a rounded shield. */
export function Mark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" className="mark">
      <path d="M20 2l15 5.5v11.2c0 9.3-6.3 16.6-15 19.3C11.3 35.3 5 28 5 18.7V7.5z" fill="var(--accent)" />
      <path d="M17 11h6v6h6v6h-6v6h-6v-6h-6v-6h6z" fill="#fff" />
    </svg>
  );
}

function TopBar() {
  return (
    <div className="topbar">
      <div className="wrap topbar-in">
        <span className="tb-item tb-hide"><Clock size={15} aria-hidden="true" /> OPD Mon–Sat, 8 AM – 8 PM</span>
        <a className="tb-item" href={HOSPITAL.phoneHref}><Phone size={15} aria-hidden="true" /> Helpline {HOSPITAL.phone}</a>
        <a className="tb-item tb-hide" href={`mailto:${HOSPITAL.email}`}><Mail size={15} aria-hidden="true" /> {HOSPITAL.email}</a>
        <a className="tb-emergency" href="tel:108"><Ambulance size={16} aria-hidden="true" /> Emergency: call 108</a>
      </div>
    </div>
  );
}

export function SiteHeader() {
  const li = useLoggedIn();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const f = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", f, { passive: true }); f();
    return () => window.removeEventListener("scroll", f);
  }, []);
  const [lg, setLg] = useTextSize();
  const nav = useNavigate();
  const logout = () => { session.set(null); resetChat(); nav("/"); };
  return (
    <>
    <a className="skip" href="#main">Skip to content</a>
    <TopBar />
    <header className={scrolled ? "site-header scrolled" : "site-header"}>
      <div className="wrap bar">
        <Link to="/" className="logo" aria-label="CareLine Hospitals, home">
          <Mark />
          <span className="logo-text"><strong>CareLine</strong><small>Hospitals · Bengaluru</small></span>
        </Link>
        <button className="menu-btn" aria-expanded={open} aria-controls="site-nav" onClick={() => setOpen(!open)}>
          {open ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}<span>{open ? "Close" : "Menu"}</span>
        </button>
        <nav id="site-nav" className={open ? "site-nav open" : "site-nav"} aria-label="Main" onClick={() => setOpen(false)}>
          <NavLink to="/about">About us</NavLink>
          <NavLink to="/specialities">Specialities</NavLink>
          <NavLink to="/doctors">Find a doctor</NavLink>
          <NavLink to="/visitors">Patients &amp; visitors</NavLink>
          <NavLink to="/insurance">Insurance</NavLink>
          <NavLink to="/contact">Contact</NavLink>
          <button type="button" className="size-btn" aria-pressed={lg} onClick={(e) => { e.stopPropagation(); setLg(!lg); }} title="Change text size">
            {lg ? "A−" : "A+"}<span className="sr-only">{lg ? " Normal text size" : " Larger text"}</span>
          </button>
          {li ? (
            <>
              <NavLink to="/portal" className="nav-strong">My CareLine</NavLink>
              <button type="button" className="btn btn-quiet btn-sm" onClick={logout}>Log out</button>
            </>
          ) : (
            <>
              <NavLink to="/login" className="nav-strong">Patient login</NavLink>
            </>
          )}
          <button type="button" className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); setOpen(false); openChat(); }}>
            <MessageCircle size={17} aria-hidden="true" /> Chat to book
          </button>
        </nav>
      </div>
    </header>
    </>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-emergency">
        <div className="wrap fe-in">
          <div className="fe-text"><Ambulance size={28} aria-hidden="true" /><div><strong>Medical emergency?</strong><span>Our emergency department at entrance B is open 24 hours, every day.</span></div></div>
          <div className="fe-actions"><a className="btn btn-emergency" href="tel:108">Call 108</a><a className="btn btn-quiet" href={`tel:${HOSPITAL.ambulance.replace(/\s/g, "")}`}>Ambulance {HOSPITAL.ambulance}</a></div>
        </div>
      </div>
      <div className="wrap footer-cols">
        <div className="footer-brand">
          <Link to="/" className="logo"><Mark /><span className="logo-text"><strong>CareLine</strong><small>Hospitals · Bengaluru</small></span></Link>
          <p>A 350-bed multi-speciality hospital caring for East Bengaluru since 2009: 14 departments, 24-hour emergency and an AI front desk on chat, phone and web.</p>
        </div>
        <div>
          <h2 className="footer-h">Centres of excellence</h2>
          {CENTRES.map((c) => <Link key={c.key} to={`/specialities#${c.key}`}>{c.name}</Link>)}
        </div>
        <div>
          <h2 className="footer-h">For patients</h2>
          <Link to="/portal/book">Book an appointment</Link>
          <Link to="/doctors">Find a doctor</Link>
          <Link to="/portal/reports">Lab reports</Link>
          <Link to="/insurance">Insurance &amp; TPA</Link>
          <Link to="/visitors">Visitor information</Link>
          <Link to="/portal">Patient login</Link>
        </div>
        <div className="footer-contact">
          <h2 className="footer-h">Reach us</h2>
          <p><MapPin size={16} aria-hidden="true" /> {HOSPITAL.address}</p>
          <p><Phone size={16} aria-hidden="true" /> <a href={HOSPITAL.phoneHref}>{HOSPITAL.phone}</a></p>
          <p><Mail size={16} aria-hidden="true" /> <a href={`mailto:${HOSPITAL.email}`}>{HOSPITAL.email}</a></p>
          <p><Clock size={16} aria-hidden="true" /> OPD Mon–Sat 8 AM – 8 PM · Emergency 24×7</p>
        </div>
      </div>
      <div className="footer-last">
        <div className="wrap fl-in">
          <p>© {new Date().getFullYear()} CareLine Hospitals. A Talkdesk AI Hackday demo by TeamXYZ: the hospital, doctors and patients are fictional. A real deployment would need consent, retention rules and DPDP Act compliance.</p>
          <p>The information on this site is general and is not medical advice.</p>
        </div>
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
        <button type="button" className="chat-fab" onClick={() => setOpen(!open)} aria-expanded={open}>
          <MessageCircle size={22} aria-hidden="true" /> <span>Chat with us</span>
        </button>
      )}
      {open && (
        <div className="chat-panel" role="dialog" aria-label="CareLine Assistant">
          <h2>CareLine Assistant</h2>
          <p>Our 24-hour AI assistant runs on Talkdesk and books, moves or cancels visits, finds your reports and checks insurance. The chat window is being connected on this site; until then, call it on <a href={voiceNumber().href}>{voiceNumber().label}</a>.</p>
          <div className="row">
            <Link className="btn btn-primary btn-sm" to="/portal/book" onClick={() => setOpen(false)}>Book online</Link>
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => setOpen(false)}>Close</button>
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

export { openChat };
