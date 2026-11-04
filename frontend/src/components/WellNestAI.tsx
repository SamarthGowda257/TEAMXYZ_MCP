import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Maximize2, MessageCircle, Phone, X } from "lucide-react";
import { chatConfigured, hostChat, openChat, unhostChat, voiceNumber } from "../lib/chat";

/**
 * WellNest AI mark: a nest arc cradling a pulse line. The pulse is the only motif, and the same line is
 * reused by the thinking indicator. No face, no robot.
 */
export function AIAvatar({ size = 32, online = false }: { size?: number; online?: boolean }) {
  return (
    <span className="ai-avatar" style={{ width: size, height: size }}>
      <svg viewBox="0 0 40 40" width={size} height={size} role="img" aria-label="WellNest AI">
        <circle cx="20" cy="20" r="20" fill="var(--sky)" />
        <path d="M7.5 20.5a12.5 11 0 0 0 25 0" fill="none" stroke="var(--accent)" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M10 18.5h4.2l2.4-5.2 3.4 10 2.3-4.8H30" fill="none" stroke="var(--accent)" strokeWidth="2.4"
              strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {online && <i className="ai-dot" aria-hidden="true" />}
    </span>
  );
}

/** The three-dot wait state, drawn from the same pulse language. */
export function AIThinking() {
  return (
    <span className="ai-thinking" aria-label="WellNest AI is connecting">
      <i /><i /><i />
    </span>
  );
}

const PROMPTS = [
  "Book a skin doctor this week",
  "Reschedule my appointment",
  "Is my lab report ready?",
  "Does Star Health cover an MRI knee?",
  "I want to talk to a person",
];

/**
 * The branded frame around the real Talkdesk panel. We own the header, the prompt rail and the shell;
 * the panel itself is the Talkdesk widget, moved into `slot`. If it cannot be hosted we say so plainly
 * and give the phone number rather than faking a conversation.
 */
export function ChatFrame({ variant, onClose }: { variant: "page" | "modal"; onClose?: () => void }) {
  const slot = useRef<HTMLDivElement>(null);
  const [hosted, setHosted] = useState(false);

  useEffect(() => {
    let tries = 0;
    const attempt = () => {
      if (!slot.current) return;
      if (hostChat(slot.current)) { setHosted(true); return; }
      if (tries++ < 20) window.setTimeout(attempt, 300);   // the SDK script may still be loading
    };
    attempt();
    return () => unhostChat();
  }, []);

  const phone = voiceNumber();
  return (
    <div className={`ai-frame ai-frame-${variant}`}>
      <div className="ai-head">
        <AIAvatar size={38} online />
        <div className="ai-head-text">
          <strong>WellNest AI</strong>
          <span>{hosted ? "Usually replies in seconds" : "Connecting…"}</span>
        </div>
        {variant === "modal" && (
          <>
            <Link className="ai-icon-btn" to="/assistant" onClick={onClose} title="Open the full page">
              <Maximize2 size={18} aria-hidden="true" /><span className="sr-only">Open full page</span>
            </Link>
            <button type="button" className="ai-icon-btn" onClick={onClose} title="Close">
              <X size={20} aria-hidden="true" /><span className="sr-only">Close chat</span>
            </button>
          </>
        )}
      </div>

      <div className="ai-slot" ref={slot}>
        {!hosted && (
          <div className="ai-waiting">
            {chatConfigured() ? (
              <><AIThinking /><p>Opening the WellNest AI chat.</p></>
            ) : (
              <>
                <p><strong>The chat window isn't connected on this site yet.</strong></p>
                <p>The same assistant answers on the phone, around the clock.</p>
                <a className="btn btn-primary btn-sm" href={phone.href}><Phone size={16} aria-hidden="true" /> Call {phone.label}</a>
              </>
            )}
          </div>
        )}
      </div>

      <div className="ai-foot">
        <p className="ai-foot-note">WellNest AI can book, move and cancel visits, check reports and insurance, and pass you to a person. It never gives medical advice.</p>
      </div>
    </div>
  );
}

/** The suggested-prompt rail that sits beside the chat on /assistant. */
export function PromptRail() {
  return (
    <aside className="ai-rail">
      <h2>Things people ask</h2>
      <ul className="ai-prompts">
        {PROMPTS.map((p) => (
          <li key={p}><button type="button" onClick={openChat}>{p}</button></li>
        ))}
      </ul>
      <div className="ai-rail-card">
        <h3>Prefer to talk?</h3>
        <p>The same assistant answers the phone, 24 hours a day.</p>
        <a className="btn btn-quiet btn-sm" href={voiceNumber().href}><Phone size={16} aria-hidden="true" /> {voiceNumber().label}</a>
      </div>
      <div className="ai-rail-card ai-rail-urgent">
        <h3>Medical emergency</h3>
        <p>Don't wait for the chat. Call 108, or come to emergency at entrance B — open 24 hours.</p>
        <a className="btn btn-emergency btn-sm" href="tel:108">Call 108</a>
      </div>
    </aside>
  );
}

/** Floating launcher plus the side-sheet it opens. Rendered once by the site layout. */
export function AILauncher() {
  const [open, setOpen] = useState(false);
  const [hint, setHint] = useState(false);

  useEffect(() => {
    let seen = false;
    try { seen = localStorage.getItem("wellnest_ai_hint") === "seen"; } catch { /* private mode */ }
    if (seen) return;
    const t = window.setTimeout(() => setHint(true), 2600);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);

  const launch = () => {
    setOpen(true);
    setHint(false);
    try { localStorage.setItem("wellnest_ai_hint", "seen"); } catch { /* private mode */ }
  };

  return (
    <>
      {hint && !open && (
        <button type="button" className="ai-hint" onClick={launch}>
          Ask WellNest AI
        </button>
      )}
      <button type="button" className={open ? "ai-launcher is-open" : "ai-launcher"} onClick={() => (open ? setOpen(false) : launch())}
              aria-expanded={open} aria-label={open ? "Close WellNest AI chat" : "Open WellNest AI chat"}>
        {open ? <X size={24} aria-hidden="true" /> : <AIAvatar size={40} online />}
      </button>
      {open && (
        <>
          <div className="ai-scrim" onClick={() => setOpen(false)} />
          <div className="ai-sheet" role="dialog" aria-modal="true" aria-label="WellNest AI">
            <ChatFrame variant="modal" onClose={() => setOpen(false)} />
          </div>
        </>
      )}
    </>
  );
}

/** Small inline button other pages use to start a chat. */
export function ChatCta({ label = "Chat with WellNest AI", className = "btn btn-primary" }: { label?: string; className?: string }) {
  return (
    <button type="button" className={className} onClick={openChat}>
      <MessageCircle size={17} aria-hidden="true" /> {label}
    </button>
  );
}
