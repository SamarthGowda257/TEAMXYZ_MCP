// API client for the CareLine backend (/api). Same services as the Talkdesk MCP tools.
const TOKEN_KEY = "careline_token";
const OPS_KEY = "careline_ops_token";

function readStore(k: string): string | null {
  try { return localStorage.getItem(k); } catch { return null; }
}
function writeStore(k: string, v: string | null) {
  try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* private mode */ }
}

export const session = {
  token: () => readStore(TOKEN_KEY),
  set: (t: string | null) => { writeStore(TOKEN_KEY, t); window.dispatchEvent(new Event("careline-auth")); },
  loggedIn: () => !!readStore(TOKEN_KEY),
  opsToken: () => readStore(OPS_KEY),
  setOps: (t: string | null) => writeStore(OPS_KEY, t),
};

export class ApiError extends Error {
  status: number;
  code?: string;
  data?: Record<string, unknown>;
  constructor(message: string, status: number, code?: string, data?: Record<string, unknown>) {
    super(message); this.status = status; this.code = code; this.data = data;
  }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const tok = session.token();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  let res: Response;
  try {
    res = await fetch(path, { method: opts.method || "GET", headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  } catch {
    throw new ApiError("We couldn't reach CareLine. Check your connection and try again.", 0, "network");
  }
  let data: any = {};
  try { data = await res.json(); } catch { /* empty */ }
  if (res.status === 401 && path.startsWith("/api/me")) {
    session.set(null);
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
  if (!res.ok || data?.ok === false) {
    throw new ApiError(data?.message || "Something went wrong. Please try again.", res.status, data?.error_code, data?.data);
  }
  return data as T;
}

export const rupees = (n: number | undefined | null) => "₹" + Number(n || 0).toLocaleString("en-IN");

/** YYYY-MM-DD for a day offset in the hospital's timezone (IST). */
export function istDay(offset = 0): string {
  return new Date(Date.now() + 5.5 * 3600e3 + offset * 864e5).toISOString().slice(0, 10);
}
export function shortDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}
export function longDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
}
export function newKey(): string {
  return (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2)) + "";
}

// -------- shared types
export type DoctorCard = { name: string; department: string; days: string; hours: string; fee_inr: number; room: string; languages: string;
  code?: string; qualification?: string; experience_years?: number; gender?: string; day_codes?: number[] };
export type Slot = { time: string; label: string };
export type Appointment = { booking_id: string; booking_id_spoken: string; with: string; department: string; date_iso: string; date: string;
  time: string; room: string; fee_inr: number; status: string; channel?: string; reason?: string; assistance?: string[]; is_procedure?: boolean };
export type Me = { id: string; name: string; phone: string; email: string | null; date_of_birth: string | null; age: number | null;
  gender: string | null; insurer: string | null; insurer_code: string | null; policy_number: string | null; preferred_language: string;
  preferred_time: string; caregiver_name: string | null; caregiver_relation: string | null; caregiver_phone: string | null;
  caregiver_email: string | null; caregiver_consent: boolean; mobility_needs: string | null; is_senior: boolean;
  snapshot: { upcoming?: { booking_id: string; date: string; time: string; with: string }[]; pending_reports?: number; ready_reports?: number;
    recent_notes?: string[]; open_offer?: { offer_code: string; doctor: string; date: string; time: string; held_until: string } | null } };
