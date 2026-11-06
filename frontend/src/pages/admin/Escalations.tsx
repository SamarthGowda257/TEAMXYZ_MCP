import { useEffect, useRef, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import {
  Chip, Empty, Filters, Loading, Mini, Panel, RowActions, Status, Table, when, useOps, useWrite, type Col,
} from "../adminKit";

/** The human-handoff queue. Staff change status here; the reply itself happens in Talkdesk. */

const TALKDESK = "https://pesit-hackathon.mytalkdesk.com/atlas/apps/conversations";

type Handoff = {
  handoff_code: string; priority: string; reason_code: string; summary: string; status: string;
  assigned_to: string | null; created_at: string; phone: string; full_name: string;
  patient_code?: string; patient_id?: number;
};
type Resp = { counts: Record<string, number>; open_urgent: number; handoffs: Handoff[] };

export function Escalations({ onPatient }: { onPatient?: (id: number) => void }) {
  const [status, setStatus] = useState("open");
  const q = `/api/ops/handoffs?limit=120${status ? `&status=${status}` : ""}`;
  const { data, loading, error, reload } = useOps<Resp>(q, 8000);
  const { send, busy } = useWrite();
  const [picked, setPicked] = useState<string | null>(null);

  // A new open ticket must announce itself: staff are not staring at this screen.
  const seen = useRef<Set<string>>(new Set());
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    const open = (data?.handoffs || []).filter((h) => h.status === "open");
    const fresh = open.filter((h) => !seen.current.has(h.handoff_code));
    if (seen.current.size && fresh.length) {
      setFlash(true);
      const t = window.setTimeout(() => setFlash(false), 2000);
      open.forEach((h) => seen.current.add(h.handoff_code));
      return () => window.clearTimeout(t);
    }
    open.forEach((h) => seen.current.add(h.handoff_code));
  }, [data]);

  const rows = data?.handoffs || [];
  const current = rows.find((h) => h.handoff_code === picked) || null;

  const move = async (code: string, to: string) => {
    const r = await send(`/api/ops/handoffs/${code}/status`, { method: "POST", body: { status: to } });
    if (r) reload();
  };

  const cols: Col<Handoff>[] = [
    { key: "code", head: "Ticket", cell: (h) => <code className="ad-code">{h.handoff_code}</code> },
    {
      key: "pri", head: "Priority",
      cell: (h) => <Chip kind={h.priority === "urgent" ? "urgent" : "plain"}>{h.priority}</Chip>,
    },
    {
      key: "why", head: "Why", wide: true,
      cell: (h) => <>{h.summary}<span className="ad-sub">{(h.reason_code || "").replace(/_/g, " ")}</span></>,
    },
    {
      key: "who", head: "Patient",
      cell: (h) => <>{h.full_name || "Caller"}<span className="ad-sub ad-num">{h.phone}</span></>,
    },
    { key: "raised", head: "Raised", cell: (h) => <span className="ad-num">{when(h.created_at)}</span> },
    {
      key: "assigned", head: "Taken by",
      cell: (h) => h.assigned_to || <span className="ad-dim">unassigned</span>,
    },
    { key: "status", head: "Status", cell: (h) => <Status value={h.status} /> },
    {
      key: "do", head: "Change", width: "1%",
      cell: (h) => (
        <RowActions>
          {h.status !== "assigned" && <Mini onClick={() => move(h.handoff_code, "assigned")} disabled={busy} tone="accent">In progress</Mini>}
          {h.status !== "closed" && <Mini onClick={() => move(h.handoff_code, "closed")} disabled={busy}>Resolve</Mini>}
          {h.status !== "open" && <Mini onClick={() => move(h.handoff_code, "open")} disabled={busy}>Reopen</Mini>}
        </RowActions>
      ),
    },
  ];

  return (
    <div className={flash ? "ad-stack ad-flash" : "ad-stack"}>
      <Panel
        title="Escalations"
        count={data ? `${data.counts.open || 0} open` : undefined}
        action={
          <div className="ad-head-tools">
            <Filters label="Status" value={status} onChange={setStatus}
                     options={[["", "All"], ["open", "Open"], ["assigned", "In progress"], ["closed", "Closed"]]} />
            <a className="ad-mini ad-mini-accent" href={TALKDESK} target="_blank" rel="noreferrer">
              <ExternalLink size={13} aria-hidden="true" /> Talkdesk
            </a>
            <button type="button" className="ad-icon" onClick={reload} aria-label="Refresh the queue">
              <RefreshCw size={15} aria-hidden="true" />
            </button>
          </div>
        }
      >
        {loading && !data ? <Loading rows={8} />
          : error ? <Empty title="Could not load the queue" hint={error} />
          : !rows.length ? (
            <Empty title="Queue is clear"
                   hint="When a patient asks for a person, or the AI meets an emergency, the ticket lands here within seconds." />
          ) : (
            <Table cols={cols} rows={rows} rowKey={(h) => h.handoff_code}
                   onRow={(h) => setPicked(h.handoff_code === picked ? null : h.handoff_code)}
                   isOn={(h) => h.handoff_code === picked} />
          )}
      </Panel>

      {current && (
        <Panel title={current.full_name || "Caller"} action={<Status value={current.status} />}>
          <dl className="ad-facts">
            <div><dt>Ticket</dt><dd><code className="ad-code">{current.handoff_code}</code></dd></div>
            <div><dt>Priority</dt><dd>{current.priority}</dd></div>
            <div><dt>Reason</dt><dd>{(current.reason_code || "—").replace(/_/g, " ")}</dd></div>
            <div><dt>Phone</dt><dd className="ad-num">{current.phone || "—"}</dd></div>
            <div><dt>Patient file</dt><dd>{current.patient_code || "not registered"}</dd></div>
            <div><dt>Raised</dt><dd>{when(current.created_at)}</dd></div>
          </dl>
          <div className="ad-quote">
            <h3>What the AI passed on</h3>
            <p>{current.summary}</p>
          </div>
          <p className="ad-note">
            Reply to the patient in Talkdesk Conversations — that is where Talkdesk routes the chat or the call.
            This console is the record beside it.
          </p>
          {current.patient_id != null && onPatient && (
            <div className="ad-actions">
              <Mini tone="accent" onClick={() => onPatient(current.patient_id!)}>Open the patient's full record</Mini>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
