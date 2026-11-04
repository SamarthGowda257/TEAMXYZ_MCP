import { useEffect } from "react";
import { MessageCircle, Phone, ShieldCheck, Stethoscope } from "lucide-react";
import { AIAvatar, PROMPTS } from "../components/WellNestAI";
import { chatConfigured, openChat, voiceNumber } from "../lib/chat";

const CAN_DO = [
  { icon: Stethoscope, title: "Book, move or cancel", text: "Finds a free slot with the right specialist, books it and reads the booking ID back. Cancels and reschedules too." },
  { icon: ShieldCheck, title: "Checks who you are", text: "For anything about your own visits, reports or bills it asks for your registered mobile and date of birth, and checks them on the server." },
  { icon: Phone, title: "Hands over to a person", text: "Ask for a person at any point and it passes the whole conversation to the front desk, so you never repeat yourself." },
];

export function Assistant() {
  useEffect(() => { document.title = "WellNest AI — WellNest Hospitals"; }, []);
  const phone = voiceNumber();

  return (
    <div className="assistant-page">
      <div className="wrap">
        <header className="assistant-intro">
          <AIAvatar size={56} online />
          <h1 className="serif">Ask WellNest AI</h1>
          <p className="lead">
            Book, move or cancel a visit, check a lab report, ask what your insurance covers, or ask for a person.
            The same assistant answers here, on the phone and on the hospital's chat line.
          </p>
          <div className="assistant-actions">
            {chatConfigured() ? (
              <button type="button" className="btn btn-primary" onClick={openChat}>
                <MessageCircle size={18} aria-hidden="true" /> Start a chat
              </button>
            ) : null}
            <a className="btn btn-quiet" href={phone.href}><Phone size={17} aria-hidden="true" /> Call {phone.label}</a>
          </div>
          {chatConfigured() && <p className="assistant-where">The chat opens in the WellNest AI panel at the corner of this page.</p>}
        </header>

        <section className="assistant-prompts" aria-labelledby="ap-h">
          <h2 id="ap-h">Things people ask</h2>
          <ul>
            {PROMPTS.map((p) => (
              <li key={p}>
                <button type="button" onClick={openChat}>
                  <span>{p}</span>
                  <MessageCircle size={16} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="assistant-can" aria-labelledby="ac-h">
          <h2 id="ac-h">What it can actually do</h2>
          <div className="assistant-can-grid">
            {CAN_DO.map(({ icon: Icon, title, text }) => (
              <article key={title}>
                <Icon size={22} aria-hidden="true" />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
          <p className="assistant-note">
            WellNest AI never gives medical advice or a diagnosis. For symptoms it points you at the right
            department. In an emergency, call <a href="tel:108">108</a> or come to emergency at entrance B, open 24 hours.
          </p>
        </section>
      </div>
    </div>
  );
}
