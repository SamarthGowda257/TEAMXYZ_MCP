import { useState } from "react";
import { Empty, Loading, Mini, Panel, RowActions, Table, when, useOps, useWrite, type Col } from "../adminKit";

/**
 * Wallets — HealthCredits balances, and the manual credit or debit a front desk sometimes has to make:
 * a goodwill refund after a long wait, a counter top-up, a correction. A reason is required, because
 * the reason is what the audit trail and the patient's timeline will show.
 */

type Wallet = { patient_id: number; pid: number; balance: number; updated_at: string; full_name: string; phone: string };
type Resp = { total: number; wallets: Wallet[] };

export function Wallets({ onPatient }: { onPatient: (id: number) => void }) {
  const { data, loading, error, reload } = useOps<Resp>("/api/admin/wallets?limit=120");
  const { send, busy } = useWrite();
  const [row, setRow] = useState<{ id: number; amount: string; reason: string } | null>(null);

  const adjust = async (w: Wallet, sign: 1 | -1) => {
    if (!row) return;
    const n = Math.abs(parseInt(row.amount, 10) || 0);
    if (!n) return;
    const r = await send(`/api/admin/wallets/${w.patient_id}/adjust`, {
      method: "POST", body: { amount: sign * n, reason: row.reason.trim() || "Front desk adjustment" },
    });
    if (r) { setRow(null); reload(); }
  };

  const cols: Col<Wallet>[] = [
    { key: "p", head: "Patient", cell: (w) => <>{w.full_name}<span className="ad-sub ad-num">{w.phone}</span></> },
    {
      key: "b", head: "Balance", num: true,
      cell: (w) => <span className="ad-num ad-big">{w.balance.toLocaleString("en-IN")}</span>,
    },
    { key: "u", head: "Last changed", cell: (w) => when(w.updated_at) },
    {
      key: "do", head: "Adjust", wide: true,
      cell: (w) => (
        row?.id === w.patient_id ? (
          <div className="ad-adjust">
            <label className="sr-only" htmlFor={`amt-${w.patient_id}`}>Amount in credits</label>
            <input id={`amt-${w.patient_id}`} className="input" type="number" min={1} placeholder="Credits" autoFocus
                   value={row.amount} onChange={(e) => setRow({ ...row, amount: e.target.value })} />
            <label className="sr-only" htmlFor={`rsn-${w.patient_id}`}>Reason for this adjustment</label>
            <input id={`rsn-${w.patient_id}`} className="input" placeholder="Reason — shown on the audit trail"
                   value={row.reason} onChange={(e) => setRow({ ...row, reason: e.target.value })} />
            <Mini tone="accent" disabled={busy || !row.amount} onClick={() => adjust(w, 1)}>Credit</Mini>
            <Mini tone="danger" disabled={busy || !row.amount} onClick={() => adjust(w, -1)}>Debit</Mini>
            <Mini onClick={() => setRow(null)}>Cancel</Mini>
          </div>
        ) : (
          <RowActions>
            <Mini tone="accent" onClick={() => setRow({ id: w.patient_id, amount: "", reason: "" })}>Credit or debit</Mini>
            <Mini onClick={() => onPatient(w.patient_id)}>Open record</Mini>
          </RowActions>
        )
      ),
    },
  ];

  return (
    <Panel
      title="HealthCredits wallets"
      count={data ? data.total : undefined}
      action={<span className="ad-panel-note">1 credit = ₹1 · highest balance first</span>}
    >
      {loading && !data ? <Loading rows={8} />
        : error ? <Empty title="Could not load wallets" hint={error} />
        : !data?.wallets.length ? (
          <Empty title="No wallets yet"
                 hint="A wallet is created the first time a patient earns or is given credits." />
        ) : <Table cols={cols} rows={data.wallets} rowKey={(w) => String(w.patient_id)} isOn={(w) => row?.id === w.patient_id} />}
      <p className="ad-note">
        A debit that would take a balance below zero is refused by the server, and you will see its message here.
      </p>
    </Panel>
  );
}
