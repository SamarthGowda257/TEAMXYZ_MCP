import { Link } from "react-router-dom";
import { MessageCircle, PhoneCall } from "lucide-react";
import { openChat, voiceNumber } from "../lib/chat";

/** The main way to book: talk to the WellNest Assistant on Talkdesk (chat or phone). The form is the fallback. */
export function ReachButtons({ form = true, light = false, size = "" }: { form?: boolean; light?: boolean; size?: "" | "sm" }) {
  const v = voiceNumber();
  return (
    <div className={`reach ${light ? "reach-light" : ""}`}>
      <button type="button" className={`btn btn-primary ${size ? "btn-sm" : ""}`} onClick={openChat}>
        <MessageCircle size={18} aria-hidden="true" /> Chat to book
      </button>
      <a className={`btn btn-quiet ${size ? "btn-sm" : ""}`} href={v.href}>
        <PhoneCall size={18} aria-hidden="true" /> Call {v.label}
      </a>
      {form && <Link className="reach-form" to="/portal/book">or book online yourself</Link>}
    </div>
  );
}
