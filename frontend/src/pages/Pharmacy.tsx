/*
  Patient pharmacy. The same rules the chat and voice agents work under, shown on screen:
  prescription classes, cold chain, stock and the credit split are all decided by the server
  (app/services/pharmacy.py) — this page never computes a price or a refusal of its own.

  Ordering is two steps on purpose, exactly like the bot: ask for a quote, read the total and
  the credits it would use, then confirm.
*/
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, Check, FileUp, Minus, Package, Plus, Search, Snowflake, Trash2, Truck,
} from "lucide-react";
import { PortalShell } from "../components/PortalShell";
import { api, rupees } from "../lib/api";
import { useApi } from "../lib/hooks";
import { openChat } from "../lib/chat";

type Medicine = {
  code: string; brand: string; generic: string; strength: string; pack: string;
  price_inr: number; schedule: string; schedule_note: string;
  prescription_needed: boolean; prescription_on_file: boolean | null;
  chronic: boolean; cold_chain: boolean; in_stock: boolean; stock_qty: number;
  restock?: string | null; alternative?: { code: string; brand: string; price_inr: number } | null;
};
type Catalogue = { ok: boolean; message: string; medicines: Medicine[] };
type OrderView = {
  order_id: string; items: { name?: string; qty?: number }[]; subtotal_inr: number;
  delivery_fee_inr: number; total_inr: number; credits_used: number; amount_due_inr: number;
  status: string; cold_chain: boolean; delivery_address: string; eta: string | null;
  placed: string | null; cancellable: boolean; payment_url: string | null; tracking_url: string;
};
type Quote = {
  ok?: boolean; message?: string; error_code?: string;
  data?: Record<string, unknown> & { needs?: string };
};

type MyRx = {
  item_id: number; rx_code: string; ingredient: string; dose: string; doctor: string | null; valid_until: string | null;
  days_left: number; next_refill_from: string | null; status: string; stop_reason: string | null;
};
type MyRxResp = { message: string; prescriptions: MyRx[]; uploads: { upload_code: string; file_name: string; status: string; reason: string | null }[] };

const STATUS_WORDS: Record<string, string> = {
  awaiting_payment: "waiting for payment", awaiting_stock: "waiting for stock", awaiting_review: "pharmacist checking",
  confirmed: "being packed", dispatched: "on the way", delivered: "delivered", cancelled: "cancelled",
  ready_for_pickup: "ready to collect", returned: "returned and refunded",
};

const SCHEDULE_TONE: Record<string, string> = { OTC: "chip-ok", H: "chip-warn", H1: "chip-warn", X: "chip-alert" };

export function Pharmacy() {
  useEffect(() => { document.title = "Pharmacy · My WellNest"; }, []);

  const [raw, setRaw] = useState("");
  const [q, setQ] = useState("");
  const { data, loading } = useApi<Catalogue>(`/api/me/pharmacy${q ? `?q=${encodeURIComponent(q)}` : ""}`, [q]);
  const orders = useApi<{ orders: OrderView[] }>("/api/me/orders");

  const [basket, setBasket] = useState<Record<string, number>>({});
  const [address, setAddress] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [placed, setPlaced] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);

  const meds = data?.medicines || [];
  const byCode = useMemo(() => Object.fromEntries(meds.map((m) => [m.code, m])), [meds]);
  const lines = Object.entries(basket).filter(([, n]) => n > 0);
  const roughTotal = lines.reduce((s, [c, n]) => s + (byCode[c]?.price_inr || 0) * n, 0);

  const bump = (code: string, by: number) =>
    setBasket((b) => {
      const next = Math.max(0, (b[code] || 0) + by);
      const out = { ...b };
      if (next) out[code] = next; else delete out[code];
      return out;
    });

  async function send(confirm: boolean) {
    setBusy(true);
    try {
      const r = await api<Quote>("/api/me/pharmacy/order", {
        method: "POST",
        body: {
          items: lines.map(([code, qty]) => ({ code, qty })),
          delivery_address: address,
          payment_method: "health_credits",
          confirm,
        },
      });
      if (confirm && r.ok) { setPlaced(r); setQuote(null); setBasket({}); orders.reload?.(); }
      else setQuote(r);
    } catch {
      setQuote({ ok: false, message: "We couldn't reach the pharmacy just now. Please try again, or ask on chat." });
    } finally { setBusy(false); }
  }

  return (
    <PortalShell title="Pharmacy">
      {() => (<>
      {placed && (
        <div className="shop-done" role="status">
          <Check size={22} aria-hidden="true" />
          <div>
            <strong>{placed.message}</strong>
            <p>You can follow it under “Your orders” below, or ask the assistant where it is.</p>
          </div>
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => setPlaced(null)}>Dismiss</button>
        </div>
      )}

      <div className="shop">
        <section className="shop-cat">
          <form className="shop-search" role="search" onSubmit={(e) => { e.preventDefault(); setQ(raw.trim()); }}>
            <label htmlFor="mq" className="sr-only">Search medicines</label>
            <Search size={18} aria-hidden="true" />
            <input id="mq" className="input" value={raw} placeholder="Brand or generic name, e.g. Dolo or paracetamol"
                   onChange={(e) => setRaw(e.target.value)} />
            <button className="btn btn-primary btn-sm">Search</button>
          </form>

          {loading && !data ? (
            <p className="quiet">Reading the pharmacy list…</p>
          ) : meds.length ? (
            <ul className="shop-list">
              {meds.map((m) => (
                <li key={m.code} className={m.in_stock ? "" : "is-out"}>
                  <div className="shop-id">
                    <h3>{m.brand}</h3>
                    <p className="shop-gen">{m.generic} · {m.strength} · {m.pack}</p>
                    <p className="shop-flags">
                      <span className={`chip ${SCHEDULE_TONE[m.schedule] || "chip-quiet"}`}>
                        {m.schedule === "OTC" ? "No prescription" : `Schedule ${m.schedule}`}
                      </span>
                      {m.chronic && <span className="chip chip-quiet">Long-term</span>}
                      {m.cold_chain && <span className="chip chip-quiet"><Snowflake size={12} aria-hidden="true" /> Cold chain</span>}
                    </p>
                    {!m.in_stock && (
                      <p className="shop-out">
                        Out of stock{m.restock ? ` · back ${m.restock}` : ""}.
                        {m.alternative && <> In-stock generic: <strong>{m.alternative.brand}</strong> at {rupees(m.alternative.price_inr)}.</>}
                      </p>
                    )}
                    {m.prescription_needed && m.prescription_on_file === false && (
                      <p className="shop-note"><AlertTriangle size={14} aria-hidden="true" /> No prescription on file — the pharmacy will refuse this one.</p>
                    )}
                  </div>
                  <div className="shop-buy">
                    <span className="shop-price num">{rupees(m.price_inr)}</span>
                    {basket[m.code] ? (
                      <div className="shop-step">
                        <button type="button" onClick={() => bump(m.code, -1)} aria-label={`One fewer ${m.brand}`}><Minus size={15} /></button>
                        <span className="num">{basket[m.code]}</span>
                        <button type="button" onClick={() => bump(m.code, 1)} aria-label={`One more ${m.brand}`}><Plus size={15} /></button>
                      </div>
                    ) : (
                      <button type="button" className="btn btn-quiet btn-sm" disabled={!m.in_stock}
                              onClick={() => bump(m.code, 1)}>
                        {m.in_stock ? "Add" : "Unavailable"}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="shop-empty">
              <strong>Nothing matched “{q}”</strong>
              <p>Try the generic name, or <button type="button" className="lnk" onClick={openChat}>ask the assistant</button> — it can check the full list.</p>
            </div>
          )}
        </section>

        <aside className="shop-side">
          <section className="shop-cart">
            <h2>Your basket</h2>
            {lines.length ? (
              <>
                <ul>
                  {lines.map(([code, n]) => (
                    <li key={code}>
                      <span>{byCode[code]?.brand || code}</span>
                      <span className="num">{n} × {rupees(byCode[code]?.price_inr || 0)}</span>
                      <button type="button" onClick={() => bump(code, -n)} aria-label={`Remove ${byCode[code]?.brand || code}`}>
                        <Trash2 size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="shop-sub">
                  <span>Medicines</span><span className="num">{rupees(roughTotal)}</span>
                </p>
                <div className="field">
                  <label htmlFor="addr">Deliver to</label>
                  <input id="addr" className="input" value={address} placeholder="Leave empty to use the address on file"
                         onChange={(e) => setAddress(e.target.value)} />
                </div>

                {quote && (
                  <div className={quote.ok ? "shop-quote" : "shop-quote is-bad"} role="status">
                    <p>{quote.message}</p>
                  </div>
                )}

                {quote?.ok && quote.data?.needs === "confirm" ? (
                  <div className="shop-acts">
                    <button className="btn btn-primary" disabled={busy} onClick={() => send(true)}>
                      {busy ? "Placing…" : "Confirm and pay with credits"}
                    </button>
                    <button className="btn btn-quiet btn-sm" disabled={busy} onClick={() => setQuote(null)}>Change the basket</button>
                  </div>
                ) : (
                  <button className="btn btn-primary" disabled={busy} onClick={() => send(false)}>
                    {busy ? "Checking…" : "Get the total"}
                  </button>
                )}
                <p className="shop-fine">
                  The pharmacy confirms the price, the delivery fee and what your HealthCredits cover before anything is charged.
                </p>
              </>
            ) : (
              <p className="quiet">Nothing added yet. Prices and the credit split are confirmed before you pay.</p>
            )}
          </section>

          <MyPrescriptions />

          <section className="shop-orders">
            <h2>Your orders</h2>
            {orders.data?.orders?.length ? (
              <ul>
                {orders.data.orders.map((o) => (
                  <li key={o.order_id}>
                    <div>
                      <strong className="code">{o.order_id}</strong>
                      <span className="chip chip-quiet">{STATUS_WORDS[o.status] || o.status.replace(/_/g, " ")}</span>
                    </div>
                    <p className="num">{rupees(o.total_inr)} · {o.credits_used ? `${o.credits_used.toLocaleString("en-IN")} credits` : "unpaid"}</p>
                    {o.eta && <p className="shop-eta"><Truck size={14} aria-hidden="true" /> {o.eta}</p>}
                    {o.amount_due_inr > 0 && o.payment_url && (
                      <a className="btn btn-quiet btn-sm" href={o.payment_url}>Pay {rupees(o.amount_due_inr)}</a>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="quiet"><Package size={16} aria-hidden="true" /> No orders yet.</p>
            )}
          </section>

          <p className="shop-link">
            Paying from <Link to="/portal/wallet">HealthCredits</Link>. Schedule X medicines are never sold by chat, phone or web.
          </p>
        </aside>
      </div>
      </>)}
    </PortalShell>
  );
}

/* What the patient can order on their prescriptions, and uploading one from another hospital. The pharmacist
   checks every upload; nothing here decides what may be sent. */
function MyPrescriptions() {
  const mine = useApi<MyRxResp>("/api/me/prescriptions");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) { setMsg({ ok: false, text: "The file must be under 4 MB." }); return; }
    setBusy(true); setMsg(null);
    try {
      const data = await new Promise<string>((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(String(r.result).split(",")[1] || "");
        r.onerror = () => rej(new Error("read"));
        r.readAsDataURL(file);
      });
      const r = await api<{ message: string }>("/api/me/prescriptions/upload", {
        method: "POST", body: { file_name: file.name, content_type: file.type, data } });
      setMsg({ ok: true, text: r.message });
      mine.reload?.();
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "That didn't upload. Please try again." });
    } finally { setBusy(false); }
  };

  const active = mine.data?.prescriptions.filter((p) => p.status === "active") || [];
  return (
    <section className="shop-orders">
      <h2>My prescriptions</h2>
      {mine.loading && !mine.data ? <p className="quiet">Reading your prescriptions…</p> : active.length ? (
        <ul>
          {active.map((p) => (
            <li key={p.item_id}>
              <div><strong>{p.ingredient}</strong> <span className="chip chip-quiet">{p.dose}</span></div>
              <p className="quiet">{p.doctor || "Your doctor"} · {p.rx_code} · about {p.days_left} days left</p>
              {p.next_refill_from && <p className="shop-note">Next refill from {p.next_refill_from}.</p>}
            </li>
          ))}
        </ul>
      ) : <p className="quiet">No active prescriptions on file. Medicines that need one can't be sent without it.</p>}
      {!!mine.data?.uploads.length && (
        <ul>
          {mine.data.uploads.slice(0, 3).map((u) => (
            <li key={u.upload_code}>
              <div><strong className="code">{u.upload_code}</strong> <span className="chip chip-quiet">{u.status}</span></div>
              {u.reason && <p className="shop-note">{u.reason}</p>}
            </li>
          ))}
        </ul>
      )}
      <label className="btn btn-quiet btn-sm shop-upload">
        <FileUp size={15} aria-hidden="true" /> {busy ? "Uploading…" : "Upload a prescription"}
        <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="sr-only" disabled={busy}
               onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      <p className="shop-fine">From another hospital? A photo or PDF, under 4 MB. Our pharmacist checks it, usually within a few hours.</p>
      {msg && <p className={msg.ok ? "shop-fine" : "error-text"} role="status">{msg.text}</p>}
    </section>
  );
}

export default Pharmacy;
