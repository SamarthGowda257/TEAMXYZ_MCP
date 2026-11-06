/*
  HealthCredits — the patient's own view of the wallet the chat and voice agents already spend from.

  Every number here comes from /api/me/wallet, which reads the same ledger (app/services/wallet.py)
  the bot uses. The page never computes a balance, a bonus or a limit of its own; it shows what the
  server says and reports the server's message back verbatim.
*/
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowDownLeft, ArrowUpRight, Info, Users, Wallet as WalletIcon } from "lucide-react";
import { PortalShell } from "../components/PortalShell";
import { api, rupees } from "../lib/api";
import { useApi } from "../lib/hooks";

type Txn = {
  txn_id?: string; direction: "credit" | "debit"; amount: number; balance_after: number;
  service: string; reference?: string | null; at?: string | null;
};
type WalletData = {
  ok: boolean; message: string;
  balance_credits: number; spendable_credits: number; pool_credits: number;
  pool: { owner_name: string; available_credits: number } | null;
  is_minor: boolean; transactions: Txn[];
  bonus_tiers: { from_inr: number; percent: number }[];
  topup_min_inr: number; topup_max_inr: number;
};
type Member = {
  name: string; patient_id: string; phone: string;
  per_txn_limit: number | null; daily_limit: number | null;
  active: boolean; available_credits: number;
};
type Sharing = { ok: boolean; message: string; members: Member[]; drawing_from: { owner_name: string; available_credits: number } | null };

export function Wallet() {
  useEffect(() => { document.title = "HealthCredits · My WellNest"; }, []);

  const w = useApi<WalletData>("/api/me/wallet");
  const sharing = useApi<Sharing>("/api/me/wallet/sharing");

  const [amount, setAmount] = useState("2000");
  const [topup, setTopup] = useState<{ ok?: boolean; message?: string; data?: { payment_url?: string } } | null>(null);
  const [busy, setBusy] = useState(false);

  const [mPhone, setMPhone] = useState("");
  const [mTxn, setMTxn] = useState("");
  const [mDay, setMDay] = useState("");
  const [shareMsg, setShareMsg] = useState<{ ok?: boolean; message?: string } | null>(null);

  const bonus = (w.data?.bonus_tiers || [])
    .slice().sort((a, b) => b.from_inr - a.from_inr)
    .find((t) => Number(amount || 0) >= t.from_inr);

  async function addCredits(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setTopup(null);
    try {
      const r = await api<typeof topup>("/api/me/wallet/topup", { method: "POST", body: { amount_inr: Number(amount) } });
      setTopup(r);
    } catch {
      setTopup({ ok: false, message: "We couldn't start that top-up. Please try again, or ask on chat." });
    } finally { setBusy(false); }
  }

  async function saveShare(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setShareMsg(null);
    try {
      const r = await api<{ ok?: boolean; message?: string }>("/api/me/wallet/sharing", {
        method: "POST",
        body: { phone: mPhone, per_txn_limit: Number(mTxn) || null, daily_limit: Number(mDay) || null },
      });
      setShareMsg(r);
      if (r.ok) { setMPhone(""); setMTxn(""); setMDay(""); sharing.reload(); w.reload(); }
    } catch {
      setShareMsg({ ok: false, message: "We couldn't save that just now." });
    } finally { setBusy(false); }
  }

  async function stopShare(phone: string) {
    setBusy(true);
    try {
      const r = await api<{ message?: string }>("/api/me/wallet/sharing", {
        method: "POST", body: { phone, action: "stop" },
      });
      setShareMsg(r); sharing.reload();
    } finally { setBusy(false); }
  }

  return (
    <PortalShell title="HealthCredits">
      {() => (
        <div className="wal">
          <section className="wal-hero">
            <p className="wal-cap"><WalletIcon size={16} aria-hidden="true" /> Balance</p>
            <p className="wal-big num">{(w.data?.balance_credits ?? 0).toLocaleString("en-IN")}</p>
            <p className="wal-sub">
              HealthCredits · one credit is one rupee
              {w.data && w.data.pool_credits > 0 && w.data.pool && (
                <> · plus <strong className="num">{w.data.pool_credits.toLocaleString("en-IN")}</strong> you may draw from {w.data.pool.owner_name}</>
              )}
            </p>
            {w.data?.message && <p className="wal-say">{w.data.message}</p>}
          </section>

          <div className="wal-grid">
            <section className="wal-card">
              <h2>Add credits</h2>
              <form onSubmit={addCredits}>
                <div className="field">
                  <label htmlFor="amt">Amount in rupees</label>
                  <input id="amt" className="input num" inputMode="numeric" value={amount}
                         onChange={(e) => setAmount(e.target.value.replace(/[^\d]/g, ""))} />
                  <span className="hint">
                    {bonus
                      ? `Adds a ${bonus.percent}% bonus at ${rupees(bonus.from_inr)} and above.`
                      : `Between ${rupees(w.data?.topup_min_inr ?? 100)} and ${rupees(w.data?.topup_max_inr ?? 50000)}.`}
                  </span>
                </div>
                <button className="btn btn-primary" disabled={busy || !amount}>
                  {busy ? "Preparing…" : `Add ${rupees(Number(amount) || 0)}`}
                </button>
              </form>
              {topup && (
                <div className={topup.ok ? "wal-note" : "wal-note is-bad"} role="status">
                  <p>{topup.message}</p>
                  {topup.data?.payment_url && (
                    <a className="btn btn-quiet btn-sm" href={topup.data.payment_url}>Open the payment page</a>
                  )}
                </div>
              )}
              <p className="wal-fine">
                <Info size={14} aria-hidden="true" />
                WellNest never asks for card details on chat or on the phone. Payment happens on the
                payment page only. Unused credits are refunded to the account you paid from — never as cash.
              </p>
            </section>

            <section className="wal-card">
              <h2>Recent activity</h2>
              {w.data?.transactions?.length ? (
                <ul className="wal-txns">
                  {w.data.transactions.map((t, i) => (
                    <li key={t.txn_id || i}>
                      <span className={t.direction === "credit" ? "wal-dir is-in" : "wal-dir"}>
                        {t.direction === "credit" ? <ArrowDownLeft size={15} /> : <ArrowUpRight size={15} />}
                      </span>
                      <span className="wal-what">
                        {t.service.replace(/_/g, " ")}
                        {t.reference && <small className="code">{t.reference}</small>}
                      </span>
                      <span className={t.direction === "credit" ? "wal-amt is-in num" : "wal-amt num"}>
                        {t.direction === "credit" ? "+" : "−"}{t.amount.toLocaleString("en-IN")}
                      </span>
                      <span className="wal-bal num">{t.balance_after.toLocaleString("en-IN")}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="quiet">No credits spent or added yet. Pay for a visit, a scan or a
                  medicine order and it appears here.</p>
              )}
            </section>
          </div>

          <section className="wal-card wal-share">
            <h2><Users size={18} aria-hidden="true" /> Family sharing</h2>
            {sharing.data?.message && <p className="wal-say">{sharing.data.message}</p>}

            {sharing.data?.members?.length ? (
              <ul className="wal-members">
                {sharing.data.members.map((m) => (
                  <li key={m.patient_id} className={m.active ? "" : "is-off"}>
                    <div>
                      <strong>{m.name}</strong>
                      <span className="num">{m.phone}</span>
                    </div>
                    <p className="num">
                      {m.per_txn_limit ? `${rupees(m.per_txn_limit)} per order` : "No per-order limit"}
                      {m.daily_limit ? ` · ${rupees(m.daily_limit)} a day` : ""}
                    </p>
                    {m.active
                      ? <button type="button" className="btn btn-quiet btn-sm" disabled={busy}
                                onClick={() => stopShare(m.phone)}>Stop access</button>
                      : <span className="chip chip-quiet">Stopped</span>}
                  </li>
                ))}
              </ul>
            ) : null}

            <form className="wal-addm" onSubmit={saveShare}>
              <div className="field">
                <label htmlFor="mp">Family member's mobile</label>
                <input id="mp" className="input" inputMode="tel" value={mPhone} placeholder="98450 00002"
                       onChange={(e) => setMPhone(e.target.value)} required />
                <span className="hint">They must already be registered at WellNest.</span>
              </div>
              <div className="field">
                <label htmlFor="mt">Limit per order</label>
                <input id="mt" className="input num" inputMode="numeric" value={mTxn} placeholder="No limit"
                       onChange={(e) => setMTxn(e.target.value.replace(/[^\d]/g, ""))} />
              </div>
              <div className="field">
                <label htmlFor="md">Limit each day</label>
                <input id="md" className="input num" inputMode="numeric" value={mDay} placeholder="No limit"
                       onChange={(e) => setMDay(e.target.value.replace(/[^\d]/g, ""))} />
              </div>
              <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Let them pay"}</button>
            </form>

            {shareMsg && (
              <p className={shareMsg.ok === false ? "wal-note is-bad" : "wal-note"} role="status">{shareMsg.message}</p>
            )}
            <p className="wal-fine">
              <Info size={14} aria-hidden="true" />
              You get a message every time someone draws on your wallet. Lab results and medical
              records are never shared by this — only the ability to pay.
            </p>
          </section>

          <p className="wal-link">
            Spend credits in the <Link to="/portal/pharmacy">pharmacy</Link>, on a consultation, or
            on a scan — on this site, on chat or on the phone.
          </p>
        </div>
      )}
    </PortalShell>
  );
}

export default Wallet;
