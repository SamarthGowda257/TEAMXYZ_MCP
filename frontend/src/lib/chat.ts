// Talkdesk Chat Widget V2 loader. Config (touchpoint ID, region) comes from /config.js (env on the server).
// After login we pass flat context params; they show on the human agent's Context card.
// They come from the browser and can be spoofed, so the AI agents still verify phone + date of birth.
import { session } from "./api";

declare global {
  interface Window {
    WELLNEST_CONFIG?: { touchpointId: string; region: string; publicBaseUrl: string };
    TalkdeskChatSDK?: (node: string, props: unknown) => any;
    webchat?: any;
  }
}

let patient: { name: string; phone: string } | null = null;
const listeners = new Set<() => void>();

/** The phone number that reaches the Talkdesk AI receptionist (falls back to the hospital helpline). */
export function voiceNumber(): { label: string; href: string } {
  const n = (window.WELLNEST_CONFIG as any)?.voiceNumber || "080 4000 1234";
  return { label: n, href: "tel:" + n.replace(/[^\d+]/g, "") };
}

export function chatConfigured(): boolean {
  return !!window.WELLNEST_CONFIG?.touchpointId;
}

function pushContext() {
  if (!patient || !window.webchat) return;
  try {
    window.webchat.setContextParam({ patient_name: patient.name, patient_phone: patient.phone, td_contact_person_identification: patient.phone });
  } catch { /* widget not ready yet */ }
}

function warm() {
  const t = session.token();
  if (t) fetch("/api/session/warm", { method: "POST", headers: { Authorization: `Bearer ${t}` } }).catch(() => {});
}

export function setChatPatient(p: { name: string; phone: string } | null) {
  patient = p;
  pushContext();
}

export function resetChat() {
  try { window.webchat?.reset(); } catch { /* ignore */ }
}

export function onChatFallback(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function openChat() {
  if (window.webchat) {
    try { window.webchat.open(); return; } catch { /* fall through */ }
  }
  listeners.forEach((fn) => fn());
}

/* ---- hosting the Talkdesk panel inside our own frame ----
   The widget has no headless mode: it renders its own UI into #tdWebchat, which loadChat() appends to <body>.
   To show it inside the branded modal or the /assistant page we move that same node into our container and let
   CSS drop its fixed positioning, so it is still the same widget, same touchpoint, same conversation.
   Moving the node is the only safe lever; nothing inside the panel is ours to restyle. */

let homeParent: HTMLElement | null = null;

export function chatNode(): HTMLElement | null {
  return document.getElementById("tdWebchat");
}

/** Move the live widget into `el`. Returns false if the widget isn't there, so callers can show a fallback. */
export function hostChat(el: HTMLElement): boolean {
  const node = chatNode();
  if (!node) return false;
  if (!homeParent) homeParent = node.parentElement;
  if (node.parentElement !== el) el.appendChild(node);
  document.documentElement.setAttribute("data-chat-hosted", "true");
  try { window.webchat?.open(); } catch { /* widget decides */ }
  return true;
}

/** Put the widget back on <body> so the floating launcher keeps working on other pages. */
export function unhostChat() {
  const node = chatNode();
  document.documentElement.removeAttribute("data-chat-hosted");
  if (node && homeParent && node.parentElement !== homeParent) homeParent.appendChild(node);
}

/** Drop a line into the composer if the patient taps a suggested prompt. Best effort: the SDK may not allow it. */
export function suggestToChat(text: string): boolean {
  try {
    const w = window.webchat as any;
    if (w?.sendMessage) { w.sendMessage(text); return true; }
  } catch { /* not supported on this SDK build */ }
  return false;
}

export function loadChat() {
  const cfg = window.WELLNEST_CONFIG;
  if (!cfg?.touchpointId || window.TalkdeskChatSDK || document.getElementById("tdWebchat")) return;
  const node = "tdWebchat";
  const div = document.createElement("div");
  div.id = node;
  document.body.appendChild(div);
  const script = document.createElement("script");
  script.src = "https://talkdeskchatsdk.talkdeskapp.com/v2/talkdeskchatsdk.js";
  script.async = true;
  script.onload = () => {
    if (!window.TalkdeskChatSDK) return;
    window.webchat = window.TalkdeskChatSDK(node, { touchpointId: cfg.touchpointId, accountId: "", region: cfg.region });
    window.webchat.init({
      enableEmoji: false, enableAttachments: false, enableResponsiveLayout: true,
      styles: { chatTitle: "WellNest Assistant", chatSubtitle: "Bookings, reports, insurance", chatThemeColor: "#0B5CAD" },
    });
    try {
      window.webchat.onOpenWebchat = () => { pushContext(); warm(); };
      window.webchat.onConversationStart = () => pushContext();
    } catch { /* older SDK */ }
    pushContext();
  };
  document.head.appendChild(script);
}
