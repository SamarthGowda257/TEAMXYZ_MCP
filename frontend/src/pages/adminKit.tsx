import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../lib/api";

/** Shared pieces of the staff console, used by both the operations pages and the hospital reference. */

export type Loaded<T> = { data: T | null; error: string | null; loading: boolean };

/** Read an ops endpoint with the admin cookie. `everyMs` turns it into a poll. */
export function useOps<T>(path: string, everyMs = 0): Loaded<T> & { reload: () => void } {
  const [state, setState] = useState<Loaded<T>>({ data: null, error: null, loading: true });
  const load = useCallback(async () => {
    try {
      const d = await api<T>(path);
      setState({ data: d, error: null, loading: false });
    } catch (e) {
      setState({ data: null, error: e instanceof ApiError ? e.message : "Could not load this.", loading: false });
    }
  }, [path]);
  useEffect(() => {
    load();
    if (!everyMs) return;
    const t = window.setInterval(load, everyMs);
    return () => window.clearInterval(t);
  }, [load, everyMs]);
  return { ...state, reload: load };
}

export function Chip({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`ad-chip ad-chip-${kind}`}>{children}</span>;
}

/** Status vocabularies in this system: appointments use booked/completed/cancelled, handoffs open/assigned/closed. */
export function statusKind(s: string) {
  if (s === "cancelled" || s === "no_show") return "off";
  if (s === "completed" || s === "closed") return "ok";
  if (s === "assigned") return "work";
  return "live";
}

export function Empty({ title, hint }: { title: string; hint: string }) {
  return <div className="ad-empty"><strong>{title}</strong><p>{hint}</p></div>;
}

export function Loading({ rows = 5 }: { rows?: number }) {
  return <div className="ad-skel">{Array.from({ length: rows }, (_, i) => <i key={i} />)}</div>;
}

export function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="ad-panel">
      <div className="ad-panel-head"><h2>{title}</h2>{action}</div>
      {children}
    </section>
  );
}

export const rupees = (n: number | undefined | null) => "₹" + Number(n || 0).toLocaleString("en-IN");
