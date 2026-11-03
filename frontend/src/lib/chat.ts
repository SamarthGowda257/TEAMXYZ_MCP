// Talkdesk Chat Widget V2 loader. Config (touchpoint ID, region) comes from /config.js (env on the server).
// After login we pass flat context params; they show on the human agent's Context card.
// They come from the browser and can be spoofed, so the AI agents still verify phone + date of birth.
import { session } from "./api";

declare global {
  interface Window {
    CARELINE_CONFIG?: { touchpointId: string; region: string; publicBaseUrl: string };
    TalkdeskChatSDK?: (node: string, props: unknown) => any;
    webchat?: any;
  }
}

let patient: { name: string; phone: string } | null = null;
const listeners = new Set<() => void>();

export function chatConfigured(): boolean {
  return !!window.CARELINE_CONFIG?.touchpointId;
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

export function loadChat() {
  const cfg = window.CARELINE_CONFIG;
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
      styles: { chatTitle: "CareLine Assistant", chatSubtitle: "Bookings, reports, insurance", chatThemeColor: "#0A7C74" },
    });
    try {
      window.webchat.onOpenWebchat = () => { pushContext(); warm(); };
      window.webchat.onConversationStart = () => pushContext();
    } catch { /* older SDK */ }
    pushContext();
  };
  document.head.appendChild(script);
}
