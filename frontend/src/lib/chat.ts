// Talkdesk Chat Widget V2 loader. Config (touchpoint ID, region) comes from /config.js (env on the server).
// After login we pass flat context params; they show on the human agent's Context card.
// Anything from the browser can be forged, so only `wellnest_session` proves who this is: a random code the server
// issued to the signed-in patient, which reaches the AI through Studio and is checked by open_signed_in_session.
import { api, session } from "./api";

declare global {
  interface Window {
    WELLNEST_CONFIG?: { touchpointId: string; region: string; publicBaseUrl: string };
    TalkdeskChatSDK?: (node: string, props: unknown) => any;
    webchat?: any;
  }
}

let patient: { name: string; phone: string } | null = null;
let sessionCode = "";
let linking = false;
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
  if (!window.webchat) return;
  try {
    window.webchat.setContextParam({
      patient_name: patient?.name || "", patient_phone: patient?.phone || "",
      td_contact_person_identification: patient?.phone || "", wellnest_session: sessionCode,
    });
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

/* How the code reaches the AI: in a web chat Talkdesk passes the page address as the Caller ID system variable, read
   when each conversation starts (verified live 8 Nov: the Studio context field never reached Application Input).
   So while signed in the address carries #wn=<code>; the fragment never goes to any server in a request, and the
   server only accepts a live code it issued itself, revoked at sign-out. */
const TAG = "#wn=";

/** Put the session code in the page address (call after every navigation, since routing drops the fragment). */
export function tagChatUrl() {
  if (!sessionCode || !session.loggedIn()) return;
  if (location.hash === TAG + sessionCode) return;
  try { history.replaceState(history.state, "", location.pathname + location.search + TAG + sessionCode); } catch { /* ignore */ }
}

function untagChatUrl() {
  if (!location.hash.startsWith(TAG)) return;
  try { history.replaceState(history.state, "", location.pathname + location.search); } catch { /* ignore */ }
}

/** A conversation started before sign-in (Talkdesk keeps it across reloads) has no code: start one fresh chat,
 *  once per sign-in, so the first thing the signed-in patient types already carries it. */
const LINKED = "wn_chat_linked";
function freshChatOnce(widgetReady: boolean) {
  let done = "";
  try { done = localStorage.getItem(LINKED) || ""; } catch { /* private mode */ }
  if (done === sessionCode) return;
  if (!widgetReady) { pendingFresh = true; return; }    // loadChat() resets once the widget is up
  resetChat();
  try { localStorage.setItem(LINKED, sessionCode); } catch { /* ignore */ }
}
let pendingFresh = false;

/** Tell the chat who is signed in. Safe to call on every navigation: it asks the server once per sign-in. */
export async function linkChatToLogin() {
  if (session.loggedIn() && sessionCode) { tagChatUrl(); return; }
  if (!session.loggedIn() || sessionCode || linking) return;
  linking = true;
  const hadAnonymousChat = !!window.webchat;      // signing in mid-visit: start a fresh chat so it carries the login
  try {
    const r = await api<{ session_code: string; name: string; phone: string }>("/api/chat/session", { method: "POST" });
    if (!session.loggedIn()) return;
    sessionCode = r.session_code;
    patient = { name: r.name, phone: r.phone };
    tagChatUrl();                                  // before the reset, so the new conversation starts with the code
    freshChatOnce(hadAnonymousChat);
    pushContext();
  } catch { /* the chat still works; it asks for mobile and date of birth */ } finally {
    linking = false;
  }
}

/** Sign-out: the server forgets the code first, so a chat left open can't reopen the record. */
export function unlinkChat() {
  if (session.loggedIn()) api("/api/chat/session", { method: "DELETE" }).catch(() => {});
  sessionCode = "";
  patient = null;
  untagChatUrl();
  resetChat();                                     // the open conversation was started with the code: end it
  pushContext();
}

export function resetChat() {
  try { window.webchat?.reset(); } catch { /* ignore */ }
}

export function onChatFallback(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Is the Talkdesk panel on screen? Its wrapper stays in the DOM and is toggled by visibility. */
function panelOpen(): boolean {
  const el = document.querySelector("#tdWebchat .tdw-widget");
  return !!el && getComputedStyle(el).visibility !== "hidden";
}

/**
 * Open the chat.
 *
 * `webchat.open()` exists on this SDK build but does nothing — verified against the live
 * touchpoint: the method is present, calling it leaves `.tdw-widget` at 0x0 and
 * `visibility: hidden`, while clicking the widget's own trigger opens it at 360x680. So the
 * trigger is the real control, and every "Chat to book" on the site routes through it.
 * `open()` is still tried first, in case a later SDK build fixes it.
 */
export function openChat() {
  if (window.webchat) {
    try { window.webchat.open(); } catch { /* keep going */ }
    if (panelOpen()) return;
    const trigger = document.querySelector<HTMLElement>("#tdWebchat .tdw-widget-trigger");
    if (trigger) {
      trigger.click();
      // the panel animates in; only report failure if it never appears
      window.setTimeout(() => { if (!panelOpen()) listeners.forEach((fn) => fn()); }, 1200);
      return;
    }
  }
  listeners.forEach((fn) => fn());
}

/* ---- where the panel lives ----
   The widget renders its own UI into #tdWebchat, which loadChat() appends to <body>, and that UI contains an
   iframe. Re-parenting an iframe makes the browser reload it, which would drop a live conversation mid-sentence,
   so we never move the node. The panel opens where Talkdesk puts it; what we own is the launcher that opens it
   and the pages that lead to it. openChat() is the single way in, and it is the call the old site already used. */

export function chatReady(): boolean {
  return !!window.webchat;
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
      // chatThemeColor is the one colour Talkdesk lets us set inside the panel: match the site's teal.
      styles: { chatTitle: "WellNest Assistant", chatSubtitle: "Bookings, reports, insurance", chatThemeColor: "#0D6E63" },
    });
    if (pendingFresh) { pendingFresh = false; freshChatOnce(true); }
    try {
      window.webchat.onOpenWebchat = () => { pushContext(); tagChatUrl(); warm(); };
      window.webchat.onConversationStart = () => pushContext();
    } catch { /* older SDK */ }
    pushContext();
  };
  document.head.appendChild(script);
}
