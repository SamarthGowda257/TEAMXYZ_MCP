import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { Empty, Filters, Loading, Panel, Status, Table, when, useOps, type Col } from "../adminKit";

/** Outbound calls — reminders, follow-ups and waitlist offers the jobs runner plans every minute. */

type Call = {
  call_id: string; kind: string; patient: string; to: string; status: string;
  attempts: number; outcome: string | null; updated: string; due_at?: string;
};
type Resp = {
  mode: string; test_number: string | null; missing_settings?: string[];
  allowlist?: number; calling_hours_ist?: string; kinds?: string[]; calls: Call[];
};

export function Outbound() {
  const { data, loading, error, reload } = useOps<Resp>("/api/ops/outbound?limit=80", 20000);
  const [kind, setKind] = useState("");
  const rows = (data?.calls || []).filter((c) => !kind || c.kind === kind);

  const cols: Col<Call>[] = [
    { key: "c", head: "Call", cell: (c) => <code className="ad-code">{c.call_id}</code> },
    { key: "k", head: "Reason", cell: (c) => c.kind.replace(/_/g, " ") },
    { key: "p", head: "Patient", cell: (c) => <>{c.patient}<span className="ad-sub ad-num">{c.to}</span></> },
    { key: "d", head: "Due", cell: (c) => (c.due_at ? when(c.due_at) : <span className="ad-dim">—</span>) },
    { key: "a", head: "Tries", num: true, cell: (c) => <span className="ad-num">{c.attempts}</span> },
    {
      key: "o", head: "Outcome", wide: true,
      cell: (c) => <>{c.outcome?.replace(/_/g, " ") || <span className="ad-dim">no answer recorded</span>}
        {c.updated && <span className="ad-sub">{c.updated}</span>}</>,
    },
    { key: "s", head: "Status", cell: (c) => <Status value={c.status} /> },
  ];

  return (
    <Panel
      title="Outbound calls"
      count={data ? rows.length : undefined}
      action={
        <div className="ad-head-tools">
          <Filters label="Reason" value={kind} onChange={setKind}
                   options={[["", "All"], ["appointment_reminder", "Reminder"], ["post_visit_followup", "Follow-up"],
                             ["waitlist_offer", "Waitlist offer"], ["lab_report_ready", "Report ready"],
                             ["caregiver_update", "Caregiver"]]} />
          <button type="button" className="ad-icon" onClick={reload} aria-label="Refresh the call queue">
            <RefreshCw size={15} aria-hidden="true" />
          </button>
        </div>
      }
    >
      <dl className="ad-facts">
        <div><dt>Mode</dt><dd>{data?.mode ?? "—"}{data?.mode === "simulated" && " — no real calls are placed"}</dd></div>
        <div><dt>Calling hours (IST)</dt><dd>{data?.calling_hours_ist ?? "—"}</dd></div>
        <div><dt>Allowlisted numbers</dt><dd className="ad-num">{data?.allowlist ?? "—"}</dd></div>
        <div><dt>Test number</dt><dd className="ad-num">{data?.test_number ?? "not set"}</dd></div>
      </dl>
      {!!data?.missing_settings?.length && (
        <p className="ad-note">
          Real dialling is off until these are set on the server: {data.missing_settings.join(", ")}.
        </p>
      )}
      {loading && !data ? <Loading rows={6} />
        : error ? <Empty title="Could not load the call queue" hint={error} />
        : !rows.length ? (
          <Empty title="No calls of this kind queued"
                 hint="Reminder and follow-up calls are planned once appointments fall inside the reminder window." />
        ) : <Table cols={cols} rows={rows} rowKey={(c) => c.call_id} />}
    </Panel>
  );
}
