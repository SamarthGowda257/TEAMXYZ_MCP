import { MessageCircle, Phone } from "lucide-react";
import { chatConfigured, openChat, voiceNumber } from "../lib/chat";

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

export const PROMPTS = [
  "Book a skin doctor this week",
  "Reschedule my appointment",
  "Is my lab report ready?",
  "Does Star Health cover an MRI knee?",
  "I want to talk to a person",
];

/**
 * What sits in the corner of every page.
 *
 * When the Talkdesk widget is configured it renders its own launcher bottom-right, and that launcher's iframe
 * takes the pointer events in that corner. A second button of ours underneath it would be invisible to clicks
 * and would read as two chat bubbles, so we render nothing and let Talkdesk's own bubble open the panel —
 * exactly as this site worked before. Our branding lives on the inline buttons that call openChat(): the header,
 * the /assistant prompts and the calls to action through the site.
 *
 * With no touchpoint configured there is no Talkdesk launcher, so we offer the phone number instead of a chat
 * button that cannot open anything.
 */
export function AILauncher() {
  if (chatConfigured()) return null;
  return <ChatUnavailable />;
}

/** Shown instead of the launcher when no Talkdesk touchpoint is configured, so the page never lies. */
function ChatUnavailable() {
  const phone = voiceNumber();
  return (
    <a className="ai-launcher ai-launcher-call" href={phone.href} aria-label={`Call WellNest on ${phone.label}`}>
      <Phone size={22} aria-hidden="true" />
    </a>
  );
}

/** Inline button other pages use to start a chat. */
export function ChatCta({ label = "Chat with WellNest AI", className = "btn btn-primary" }: { label?: string; className?: string }) {
  return (
    <button type="button" className={className} onClick={openChat}>
      <MessageCircle size={17} aria-hidden="true" /> {label}
    </button>
  );
}
