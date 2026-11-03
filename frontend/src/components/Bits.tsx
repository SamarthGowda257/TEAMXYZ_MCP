import type { ReactNode } from "react";

const PILL: Record<string, [string, string]> = {
  booked: ["Booked", "ok"], cancelled: ["Cancelled", "muted"], completed: ["Completed", "muted"], no_show: ["Missed", "warn"],
  rescheduled: ["Moved", "muted"], pending: ["Being processed", "warn"], ready: ["Ready", "ok"], collected: ["Viewed", "muted"],
  waiting: ["Waiting", "warn"], offered: ["Slot offered", "ok"], expired: ["Expired", "muted"], due: ["Due", "bad"], paid: ["Paid", "ok"],
  partially_paid: ["Part paid", "warn"], open: ["Open", "warn"], accepted: ["Accepted", "ok"], simulated: ["Simulated", "muted"],
  sent: ["Sent", "ok"], queued: ["Queued", "warn"], failed: ["Failed", "bad"], assigned: ["With staff", "ok"], closed: ["Closed", "muted"],
  urgent: ["Urgent", "bad"], normal: ["Normal", "muted"], superseded: ["Passed on", "muted"],
};

export function Pill({ status, children }: { status: string; children?: ReactNode }) {
  const [label, tone] = PILL[status] || [status, "muted"];
  return <span className={`pill pill-${tone}`}>{children ?? label}</span>;
}

/** The booking token slip: how WellNest prints a booking ID everywhere. */
export function TokenSlip({ id, spoken, lines, tone = "card" }: { id: string; spoken?: string; lines: ReactNode[]; tone?: "card" | "accent" }) {
  return (
    <div className={`token-slip token-shape tone-${tone}`} data-ui>
      <div className="slip-id">
        <span className="slip-no" aria-label={spoken ? `Booking ID ${spoken}` : undefined}>{id}</span>
      </div>
      <div className="slip-perf" aria-hidden="true" />
      <div className="slip-lines">{lines.map((l, i) => <div key={i}>{l}</div>)}</div>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><p className="empty-title">{title}</p>{children}</div>;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="loading" role="status"><span className="loading-token token-shape" aria-hidden="true" />{label}…</div>;
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="note note-bad" role="alert">
      <p>{message}</p>
      {onRetry && <button type="button" className="btn btn-quiet btn-sm token-shape" onClick={onRetry}>Try again</button>}
    </div>
  );
}
