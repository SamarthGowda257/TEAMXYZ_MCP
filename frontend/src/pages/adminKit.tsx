import {
  createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState,
  type ReactNode,
} from "react";
import { AlertTriangle, Check, ChevronDown, Search, X } from "lucide-react";
import { api, ApiError } from "../lib/api";

/**
 * The staff console toolkit: reads, writes, and the small set of controls every section is built from.
 *
 * Two rules the whole console follows:
 *   1. A write never guesses. It posts, it shows the server's own `message`, then it re-reads the list.
 *   2. Anything destructive asks first, inline, next to the thing it would destroy.
 */

/* ============================================================ reading */

export type Loaded<T> = { data: T | null; error: string | null; loading: boolean };

/** Read an admin or ops endpoint with the signed-in admin cookie. `everyMs` turns it into a poll. */
export function useOps<T>(path: string, everyMs = 0): Loaded<T> & { reload: () => void } {
  const [state, setState] = useState<Loaded<T>>({ data: null, error: null, loading: true });
  const alive = useRef(true);
  // StrictMode mounts, cleans up, then mounts again. Without re-arming this on the second mount
  // it stays false for the rest of the component's life and every setState below is dropped,
  // which leaves the view stuck on its loading skeleton forever.
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const load = useCallback(async () => {
    try {
      const d = await api<T>(path);
      if (alive.current) setState({ data: d, error: null, loading: false });
    } catch (e) {
      if (alive.current) {
        setState({ data: null, error: e instanceof ApiError ? e.message : "Could not load this.", loading: false });
      }
    }
  }, [path]);

  useEffect(() => {
    setState((s) => ({ ...s, loading: true }));
    load();
    if (!everyMs) return;
    const t = window.setInterval(load, everyMs);
    return () => window.clearInterval(t);
  }, [load, everyMs]);

  return { ...state, reload: load };
}

/* ============================================================ writing */

type Note = { id: number; text: string; kind: "ok" | "bad" };
const NoteBox = createContext<{ say: (text: string, kind?: "ok" | "bad") => void }>({ say: () => {} });

/** Server messages land here. Every write shows one — the server's words, not ours. */
export function Notices({ children }: { children: ReactNode }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const n = useRef(0);
  const say = useCallback((text: string, kind: "ok" | "bad" = "ok") => {
    const id = ++n.current;
    setNotes((all) => [...all, { id, text, kind }]);
    window.setTimeout(() => setNotes((all) => all.filter((x) => x.id !== id)), kind === "bad" ? 9000 : 5500);
  }, []);
  const drop = (id: number) => setNotes((all) => all.filter((x) => x.id !== id));

  return (
    <NoteBox.Provider value={useMemo(() => ({ say }), [say])}>
      {children}
      <div className="ad-notes" role="status" aria-live="polite">
        {notes.map((x) => (
          <div key={x.id} className={`ad-note-card ad-note-${x.kind}`}>
            {x.kind === "ok" ? <Check size={16} aria-hidden="true" /> : <AlertTriangle size={16} aria-hidden="true" />}
            <p>{x.text}</p>
            <button type="button" onClick={() => drop(x.id)} aria-label="Dismiss"><X size={14} aria-hidden="true" /></button>
          </div>
        ))}
      </div>
    </NoteBox.Provider>
  );
}

/**
 * Run a write and report it. Returns the server body on success, null on failure — so callers
 * can reload only when something actually changed. Never throws.
 */
export function useWrite() {
  const { say } = useContext(NoteBox);
  const [busy, setBusy] = useState(false);
  const send = useCallback(async <T = any>(
    path: string,
    opts: { method: string; body?: unknown },
  ): Promise<T | null> => {
    setBusy(true);
    try {
      const r = await api<any>(path, opts);
      say(r?.message || "Saved.", "ok");
      return r as T;
    } catch (e) {
      say(e instanceof ApiError ? e.message : "That did not go through. Try again.", "bad");
      return null;
    } finally {
      setBusy(false);
    }
  }, [say]);
  return { send, busy };
}

/* ============================================================ status language */

/** Status vocabularies here: appointments booked/completed/cancelled/no_show, handoffs open/assigned/closed,
    orders awaiting_payment…delivered, calls queued/completed/failed. One chip colour per meaning. */
export function statusKind(s: string) {
  const v = (s || "").toLowerCase();
  if (["cancelled", "no_show", "failed", "expired", "superseded", "declined"].includes(v)) return "off";
  if (["completed", "closed", "delivered", "paid", "sent", "accepted", "resolved", "ok"].includes(v)) return "ok";
  if (["urgent", "emergency", "alert"].includes(v)) return "urgent";
  if (["assigned", "dialing", "in_progress", "retry", "awaiting_payment", "awaiting_stock", "pending", "dispatched"].includes(v)) return "work";
  return "live";
}

export const pretty = (s: string | null | undefined) => (s || "").replace(/_/g, " ");

export function Chip({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`ad-chip ad-chip-${kind}`}>{children}</span>;
}

export function Status({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="ad-dim">—</span>;
  return <Chip kind={statusKind(value)}>{pretty(value)}</Chip>;
}

export const rupees = (n: number | undefined | null) => "₹" + Number(n || 0).toLocaleString("en-IN");

/** A stamp that always carries the date. Without it, yesterday's 17:20 reads as out of order. */
export function when(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    day: "numeric", month: "short", year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}

/* ============================================================ frames */

export function Panel({ title, count, action, children, flat }: {
  title?: string; count?: ReactNode; action?: ReactNode; children: ReactNode; flat?: boolean;
}) {
  return (
    <section className={flat ? "ad-panel ad-panel-flat" : "ad-panel"}>
      {(title || action) && (
        <div className="ad-panel-head">
          {title && <h2>{title}{count != null && <span className="ad-count">{count}</span>}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Empty({ title, hint }: { title: string; hint: string }) {
  return <div className="ad-empty"><strong>{title}</strong><p>{hint}</p></div>;
}

export function Loading({ rows = 5 }: { rows?: number }) {
  return <div className="ad-skel" aria-label="Loading" role="status">{Array.from({ length: rows }, (_, i) => <i key={i} />)}</div>;
}

/** The one place a section decides between skeleton, error, empty and content. */
export function Shown<T>({ state, empty, rows, children }: {
  state: Loaded<T>; empty: { title: string; hint: string }; rows?: number;
  children: (data: T) => ReactNode;
}) {
  if (state.loading && !state.data) return <Loading rows={rows} />;
  if (state.error) return <Empty title="Could not load this" hint={state.error} />;
  if (!state.data) return <Empty title={empty.title} hint={empty.hint} />;
  return <>{children(state.data)}</>;
}

/* ============================================================ tables
   One table component. Over 860px it is a table; under it, each row becomes a stacked card
   and every cell keeps its column name. No horizontal scrolling on a phone. */

export type Col<R> = { key: string; head: string; cell: (r: R) => ReactNode; width?: string; num?: boolean; wide?: boolean };

export function Table<R>({ cols, rows, rowKey, onRow, isOn, foot }: {
  cols: Col<R>[]; rows: R[]; rowKey: (r: R) => string;
  onRow?: (r: R) => void; isOn?: (r: R) => boolean; foot?: ReactNode;
}) {
  return (
    <div className="ad-table-wrap">
      <table className="ad-table">
        <thead>
          <tr>{cols.map((c) => <th key={c.key} className={c.num ? "ad-num" : undefined} style={c.width ? { width: c.width } : undefined}>{c.head}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} className={isOn?.(r) ? "is-on" : undefined}
                {...(onRow ? {
                  onClick: () => onRow(r), tabIndex: 0, role: "button",
                  onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onRow(r); } },
                } : {})}>
              {cols.map((c) => (
                <td key={c.key} data-label={c.head}
                    className={[c.num ? "ad-num" : "", c.wide ? "ad-wrap-cell" : ""].filter(Boolean).join(" ") || undefined}>
                  {c.cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {foot}
      </table>
    </div>
  );
}

/* ============================================================ controls */

export function Filters({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
}) {
  return (
    <div className="ad-filters" role="group" aria-label={label}>
      {options.map(([v, l]) => (
        <button key={v || "all"} type="button" aria-pressed={value === v}
                className={value === v ? "is-on" : ""} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

export function SearchBox({ value, onChange, onSubmit, placeholder, label }: {
  value: string; onChange: (v: string) => void; onSubmit?: () => void; placeholder: string; label: string;
}) {
  const id = useId();
  return (
    <form className="ad-search-inline" role="search"
          onSubmit={(e) => { e.preventDefault(); onSubmit?.(); }}>
      <Search size={15} aria-hidden="true" />
      <label className="sr-only" htmlFor={id}>{label}</label>
      <input id={id} className="input" placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
    </form>
  );
}

/** A labelled text/number field for the CRUD forms. */
export function F({ label, value, onChange, type = "text", hint, required, placeholder, min, step, span }: {
  label: string; value: string | number; onChange: (v: string) => void;
  type?: string; hint?: string; required?: boolean; placeholder?: string; min?: number; step?: number; span?: boolean;
}) {
  const id = useId();
  return (
    <div className={span ? "field ad-field ad-field-span" : "field ad-field"}>
      <label htmlFor={id}>{label}{required && <em aria-hidden="true"> *</em>}</label>
      <input id={id} className="input" type={type} value={value} required={required} placeholder={placeholder}
             min={min} step={step} onChange={(e) => onChange(e.target.value)} />
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function FArea({ label, value, onChange, hint, rows = 3 }: {
  label: string; value: string; onChange: (v: string) => void; hint?: string; rows?: number;
}) {
  const id = useId();
  return (
    <div className="field ad-field ad-field-span">
      <label htmlFor={id}>{label}</label>
      <textarea id={id} className="input ad-textarea" rows={rows} value={value} onChange={(e) => onChange(e.target.value)} />
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function FSelect({ label, value, onChange, options, hint, span, bare }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
  hint?: string; span?: boolean; bare?: boolean;
}) {
  const id = useId();
  return (
    <div className={[bare ? "ad-field-bare" : "field ad-field", span ? "ad-field-span" : ""].filter(Boolean).join(" ")}>
      <label htmlFor={id} className={bare ? "sr-only" : undefined}>{label}</label>
      <div className="ad-select">
        <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <ChevronDown size={16} aria-hidden="true" />
      </div>
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function FCheck({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check ad-check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Consult days as seven toggles. The server stores them as "1,3,5" — Monday is 1. */
export function DayPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const on = new Set(value.split(",").map((x) => x.trim()).filter(Boolean));
  const flip = (n: number) => {
    const next = new Set(on);
    if (next.has(String(n))) next.delete(String(n)); else next.add(String(n));
    onChange([...next].map(Number).sort((a, b) => a - b).join(","));
  };
  return (
    <div className="field ad-field ad-field-span">
      <span className="ad-field-label">Consulting days</span>
      <div className="ad-daypick" role="group" aria-label="Consulting days">
        {DAY_NAMES.map((d, i) => (
          <button key={d} type="button" aria-pressed={on.has(String(i + 1))}
                  className={on.has(String(i + 1)) ? "is-on" : ""} onClick={() => flip(i + 1)}>{d}</button>
        ))}
      </div>
    </div>
  );
}

/** Read-only week strip, for tables. */
export function Days({ codes }: { codes: string }) {
  const on = new Set(codes.split(",").map((x) => x.trim()));
  return (
    <span className="ad-days" aria-label={`Consults ${DAY_NAMES.filter((_, i) => on.has(String(i + 1))).join(", ") || "no days set"}`}>
      {DAY_NAMES.map((d, i) => <i key={d} className={on.has(String(i + 1)) ? "on" : ""} aria-hidden="true">{d[0]}</i>)}
    </span>
  );
}

/** Destructive actions ask here, in place, and name what they would do. */
export function Confirm({ label, question, onYes, busy, danger = true }: {
  label: string; question: string; onYes: () => void; busy?: boolean; danger?: boolean;
}) {
  const [asking, setAsking] = useState(false);
  useEffect(() => { if (!asking) return; const t = window.setTimeout(() => setAsking(false), 12000); return () => window.clearTimeout(t); }, [asking]);
  if (!asking) {
    return (
      <button type="button" className={danger ? "ad-mini ad-mini-danger" : "ad-mini"} onClick={() => setAsking(true)}>
        {label}
      </button>
    );
  }
  return (
    <span className="ad-confirm">
      <span className="ad-confirm-q">{question}</span>
      <button type="button" className="ad-mini ad-mini-danger" disabled={busy}
              onClick={() => { setAsking(false); onYes(); }}>Yes, {label.toLowerCase()}</button>
      <button type="button" className="ad-mini" onClick={() => setAsking(false)}>Keep</button>
    </span>
  );
}

/** The form surface for create and edit. A sheet, not a modal: it never hides the list behind it. */
export function Sheet({ title, sub, onClose, children, footer }: {
  title: string; sub?: string; onClose: () => void; children: ReactNode; footer?: ReactNode;
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <section className="ad-sheet" aria-label={title}>
      <div className="ad-sheet-head">
        <div>
          <h2>{title}</h2>
          {sub && <p>{sub}</p>}
        </div>
        <button type="button" className="ad-icon" onClick={onClose} aria-label="Close this form"><X size={16} aria-hidden="true" /></button>
      </div>
      <div className="ad-sheet-body">{children}</div>
      {footer && <div className="ad-sheet-foot">{footer}</div>}
    </section>
  );
}

/** Small inline actions row used in table cells. */
export function RowActions({ children }: { children: ReactNode }) {
  return <span className="ad-row-actions">{children}</span>;
}

export function Mini({ onClick, children, disabled, tone }: {
  onClick: () => void; children: ReactNode; disabled?: boolean; tone?: "accent" | "danger";
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick}
            className={`ad-mini${tone === "accent" ? " ad-mini-accent" : tone === "danger" ? " ad-mini-danger" : ""}`}>
      {children}
    </button>
  );
}
