import { useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  Chip, Confirm, Empty, Filters, Loading, Mini, Panel, RowActions, SearchBox, Status, Table,
  useOps, useWrite, type Col,
} from "../adminKit";

/**
 * Appointments — the clinic day, and the three things a front desk actually does to a booking:
 * mark it completed, mark it a no-show, cancel it. Cancelling goes through the same service the
 * bot uses, so the freed slot is offered to the waitlist exactly as it would be on a call.
 */

type Appt = {
  booking_code: string; appt_date: string; appt_time: string; status: string; channel: string;
  reason: string; full_name: string; phone: string; doctor: string; room: string;
  date_label: string; time_label: string;
};
type Resp = { total: number; appointments: Appt[] };

export function Appointments() {
  const [status, setStatus] = useState("");
  const [day, setDay] = useState("today");
  const [q, setQ] = useState("");
  const path = `/api/ops/appointments?limit=200${status ? `&status=${status}` : ""}${day ? `&day=${day}` : ""}`;
  const { data, loading, error, reload } = useOps<Resp>(path, 20000);
  const { send, busy } = useWrite();

  const term = q.trim().toLowerCase();
  const rows = (data?.appointments || []).filter((a) =>
    !term || `${a.booking_code} ${a.full_name} ${a.phone} ${a.doctor} ${a.reason}`.toLowerCase().includes(term));

  const mark = async (code: string, to: string) => {
    const r = await send(`/api/admin/appointments/${code}/status`, { method: "POST", body: { status: to } });
    if (r) reload();
  };

  const cols: Col<Appt>[] = [
    { key: "code", head: "Booking", cell: (a) => <code className="ad-code">{a.booking_code}</code> },
    { key: "when", head: "When", cell: (a) => <>{a.date_label}<span className="ad-sub ad-num">{a.time_label}</span></> },
    { key: "who", head: "Patient", cell: (a) => <>{a.full_name}<span className="ad-sub ad-num">{a.phone}</span></> },
    {
      key: "doc", head: "Doctor",
      cell: (a) => <>{a.doctor || <span className="ad-dim">procedure</span>}{a.reason && <span className="ad-sub">{a.reason}</span>}</>,
    },
    { key: "room", head: "Room", cell: (a) => <span className="ad-num">{a.room || "—"}</span> },
    { key: "via", head: "Booked via", cell: (a) => <Chip kind="plain">{a.channel}</Chip> },
    { key: "status", head: "Status", cell: (a) => <Status value={a.status} /> },
    {
      key: "do", head: "Change", width: "1%",
      cell: (a) => (
        <RowActions>
          {a.status === "booked" && <Mini tone="accent" disabled={busy} onClick={() => mark(a.booking_code, "completed")}>Completed</Mini>}
          {a.status === "booked" && <Mini disabled={busy} onClick={() => mark(a.booking_code, "no_show")}>No show</Mini>}
          {a.status === "booked" && (
            <Confirm label="Cancel" busy={busy}
                     question={`Cancel ${a.booking_code}? The slot is offered to the waitlist.`}
                     onYes={() => mark(a.booking_code, "cancelled")} />
          )}
          {a.status !== "booked" && a.status !== "cancelled" && (
            <Mini disabled={busy} onClick={() => mark(a.booking_code, "booked")}>Back to booked</Mini>
          )}
          {a.status === "cancelled" && <span className="ad-dim">cancelled</span>}
        </RowActions>
      ),
    },
  ];

  return (
    <Panel
      title="Appointments"
      count={data ? rows.length : undefined}
      action={
        <div className="ad-head-tools">
          <Filters label="Day" value={day} onChange={setDay}
                   options={[["", "Any day"], ["today", "Today"], ["tomorrow", "Tomorrow"]]} />
          <Filters label="Status" value={status} onChange={setStatus}
                   options={[["", "All"], ["booked", "Booked"], ["completed", "Completed"], ["cancelled", "Cancelled"], ["no_show", "No show"]]} />
          <SearchBox value={q} onChange={setQ} placeholder="Booking ID, name, doctor" label="Filter the list shown" />
          <button type="button" className="ad-icon" onClick={reload} aria-label="Refresh appointments">
            <RefreshCw size={15} aria-hidden="true" />
          </button>
        </div>
      }
    >
      {loading && !data ? <Loading rows={10} />
        : error ? <Empty title="Could not load appointments" hint={error} />
        : !rows.length ? (
          <Empty title="No appointments match"
                 hint="Try a different day or status, or clear the search box." />
        ) : <Table cols={cols} rows={rows} rowKey={(a) => a.booking_code} />}
    </Panel>
  );
}
