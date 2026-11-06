import { useState } from "react";
import { Plus, Snowflake } from "lucide-react";
import {
  Chip, Confirm, Empty, F, FCheck, FSelect, Filters, Loading, Mini, Panel, RowActions, SearchBox,
  Sheet, Status, Table, when, rupees, useOps, useWrite, type Col,
} from "../adminKit";

/**
 * Pharmacy — the inventory the refill agent quotes from, and the order queue it creates.
 * Stock here is the stock a patient is told about, so restocking is one click on the row.
 */

type Med = {
  id: number; medicine_code: string; brand_name: string; generic_name: string; strength: string;
  pack: string; schedule_class: string; chronic: boolean; stock_qty: number; unit_price_inr: number;
  restock_eta: string | null; cold_chain: boolean; alternative_code: string | null; updated_at: string;
};
type MedResp = { total: number; medicines: Med[] };
type Order = {
  id: number; order_code: string; patient_id: number; full_name: string; phone: string;
  subtotal_inr: number; delivery_fee_inr: number; total_inr: number; credits_used: number;
  amount_due_inr: number; delivery_address: string; zone: string | null; status: string;
  cold_chain: boolean; eta: string | null; created_at: string;
};
type OrderResp = { total: number; orders: Order[] };

const CLASSES: [string, string][] = [
  ["OTC", "OTC — over the counter"],
  ["H", "Schedule H — prescription"],
  ["H1", "Schedule H1 — prescription, register entry"],
  ["X", "Schedule X — narcotic, two copies"],
];
const ORDER_STATES = ["awaiting_payment", "awaiting_stock", "confirmed", "dispatched", "delivered", "cancelled"];

const BLANK = {
  brand_name: "", generic_name: "", strength: "", pack: "strip of 10 tablets", schedule_class: "OTC",
  unit_price_inr: "0", stock_qty: "0", chronic: false, cold_chain: false, alternative_code: "",
};

export function Pharmacy() {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const inv = useOps<MedResp>(`/api/admin/pharmacy?q=${encodeURIComponent(term)}`);
  const { send, busy } = useWrite();
  const [editing, setEditing] = useState<Med | "new" | null>(null);
  const [f, setF] = useState<typeof BLANK>(BLANK);
  const [restock, setRestock] = useState<{ id: number; value: string } | null>(null);
  const set = (k: keyof typeof BLANK) => (v: any) => setF((s) => ({ ...s, [k]: v }));

  const openNew = () => { setF(BLANK); setEditing("new"); };
  const openEdit = (m: Med) => {
    setF({
      brand_name: m.brand_name, generic_name: m.generic_name, strength: m.strength || "",
      pack: m.pack || "", schedule_class: m.schedule_class || "OTC",
      unit_price_inr: String(m.unit_price_inr ?? 0), stock_qty: String(m.stock_qty ?? 0),
      chronic: !!m.chronic, cold_chain: !!m.cold_chain, alternative_code: m.alternative_code || "",
    });
    setEditing(m);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = {
      brand_name: f.brand_name.trim(), generic_name: f.generic_name.trim(), strength: f.strength,
      pack: f.pack, schedule_class: f.schedule_class, unit_price_inr: Number(f.unit_price_inr) || 0,
      stock_qty: Number(f.stock_qty) || 0, chronic: f.chronic, cold_chain: f.cold_chain,
      alternative_code: f.alternative_code,
    };
    const r = editing === "new"
      ? await send("/api/admin/pharmacy", { method: "POST", body })
      : await send(`/api/admin/pharmacy/${(editing as Med).id}`, { method: "PATCH", body });
    if (r) { setEditing(null); inv.reload(); }
  };

  const remove = async (m: Med) => {
    const r = await send(`/api/admin/pharmacy/${m.id}`, { method: "DELETE" });
    if (r) { setEditing(null); inv.reload(); }
  };

  const doRestock = async (m: Med, value: string) => {
    const n = parseInt(value, 10);
    if (!Number.isFinite(n) || n < 0) return;
    const r = await send(`/api/admin/pharmacy/${m.id}`, { method: "PATCH", body: { stock_qty: n } });
    if (r) { setRestock(null); inv.reload(); }
  };

  const cols: Col<Med>[] = [
    {
      key: "m", head: "Medicine",
      cell: (m) => (
        <>
          {m.brand_name}
          <span className="ad-sub">{m.generic_name}{m.strength ? ` · ${m.strength}` : ""} · {m.medicine_code}</span>
        </>
      ),
    },
    { key: "pack", head: "Pack", cell: (m) => m.pack || "—" },
    {
      key: "cls", head: "Schedule",
      cell: (m) => <Chip kind={m.schedule_class === "OTC" ? "ok" : m.schedule_class === "X" ? "urgent" : "work"}>{m.schedule_class}</Chip>,
    },
    { key: "price", head: "Price", num: true, cell: (m) => <span className="ad-num">{rupees(m.unit_price_inr)}</span> },
    {
      key: "stock", head: "In stock", num: true,
      cell: (m) => (
        restock?.id === m.id ? (
          <span className="ad-inline-edit">
            <label className="sr-only" htmlFor={`rs-${m.id}`}>New stock count for {m.brand_name}</label>
            <input id={`rs-${m.id}`} className="input" type="number" min={0} value={restock.value} autoFocus
                   onChange={(e) => setRestock({ id: m.id, value: e.target.value })}
                   onKeyDown={(e) => { if (e.key === "Enter") doRestock(m, restock.value); if (e.key === "Escape") setRestock(null); }} />
            <Mini tone="accent" disabled={busy} onClick={() => doRestock(m, restock.value)}>Set</Mini>
            <Mini onClick={() => setRestock(null)}>Cancel</Mini>
          </span>
        ) : (
          <span className={m.stock_qty <= 0 ? "ad-num ad-bad" : m.stock_qty < 20 ? "ad-num ad-warnnum" : "ad-num"}>
            {m.stock_qty}
            {m.stock_qty <= 0 && <span className="ad-sub">out of stock</span>}
            {m.stock_qty > 0 && m.stock_qty < 20 && <span className="ad-sub">running low</span>}
          </span>
        )
      ),
    },
    {
      key: "flags", head: "Notes",
      cell: (m) => (
        <>
          {m.chronic && <Chip kind="plain">chronic</Chip>}
          {m.cold_chain && <Chip kind="live"><Snowflake size={11} aria-hidden="true" /> cold chain</Chip>}
          {!m.chronic && !m.cold_chain && <span className="ad-dim">—</span>}
        </>
      ),
    },
    {
      key: "do", head: "Manage", width: "1%",
      cell: (m) => (
        <RowActions>
          <Mini tone="accent" onClick={() => setRestock({ id: m.id, value: String(m.stock_qty) })}>Restock</Mini>
          <Mini onClick={() => openEdit(m)}>Edit</Mini>
          <Confirm label="Remove" busy={busy} question={`Remove ${m.brand_name} from the pharmacy?`} onYes={() => remove(m)} />
        </RowActions>
      ),
    },
  ];

  return (
    <div className="ad-stack">
      {editing && (
        <Sheet
          title={editing === "new" ? "Add a medicine" : `Edit ${editing.brand_name}`}
          sub="The refill agent quotes this price and this stock, so both must be right before a patient hears them."
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn btn-primary btn-sm" type="submit" form="med-form" disabled={busy}>
                {busy ? "Saving…" : editing === "new" ? "Add this medicine" : "Save changes"}
              </button>
              <button className="btn btn-quiet btn-sm" type="button" onClick={() => setEditing(null)}>Cancel</button>
            </>
          }
        >
          <form id="med-form" onSubmit={save} className="ad-form-grid">
            <F label="Brand name" value={f.brand_name} onChange={set("brand_name")} required placeholder="Amlong 5" />
            <F label="Generic name" value={f.generic_name} onChange={set("generic_name")} required placeholder="Amlodipine" />
            <F label="Strength" value={f.strength} onChange={set("strength")} placeholder="5 mg" />
            <F label="Pack" value={f.pack} onChange={set("pack")} placeholder="strip of 15 tablets" />
            <FSelect label="Schedule class" value={f.schedule_class} onChange={set("schedule_class")} options={CLASSES} />
            <F label="Price per pack (₹)" type="number" min={0} value={f.unit_price_inr} onChange={set("unit_price_inr")} />
            <F label="Stock on hand" type="number" min={0} value={f.stock_qty} onChange={set("stock_qty")} />
            <F label="In-stock alternative code" value={f.alternative_code} onChange={set("alternative_code")}
               hint="Offered when this one runs out." />
            <div className="ad-field-span ad-checks">
              <FCheck label="Chronic medicine — send 30-day refill reminders" checked={f.chronic} onChange={set("chronic")} />
              <FCheck label="Cold chain — 2–8 °C, insulated pouch, OTP handover" checked={f.cold_chain} onChange={set("cold_chain")} />
            </div>
          </form>
        </Sheet>
      )}

      <Panel
        title="Pharmacy inventory"
        count={inv.data ? inv.data.total : undefined}
        action={
          <div className="ad-head-tools">
            <SearchBox value={q} onChange={setQ} onSubmit={() => setTerm(q.trim())}
                       placeholder="Brand or generic name" label="Search the pharmacy" />
            <button type="button" className="btn btn-primary btn-sm" onClick={openNew}>
              <Plus size={15} aria-hidden="true" /> Add a medicine
            </button>
          </div>
        }
      >
        {inv.loading && !inv.data ? <Loading rows={10} />
          : inv.error ? <Empty title="Could not load the pharmacy" hint={inv.error} />
          : !inv.data?.medicines.length ? (
            <Empty title="Nothing matches that name"
                   hint="Clear the search, or add the medicine so the refill agent can quote it." />
          ) : <Table cols={cols} rows={inv.data.medicines} rowKey={(m) => String(m.id)}
                     isOn={(m) => editing !== "new" && editing?.id === m.id} />}
      </Panel>

      <Orders />
    </div>
  );
}

/* ------------------------------------------------------------------ order queue */

function Orders() {
  const [status, setStatus] = useState("");
  const { data, loading, error, reload } = useOps<OrderResp>(`/api/admin/orders?limit=100${status ? `&status=${status}` : ""}`, 20000);
  const { send, busy } = useWrite();

  const move = async (o: Order, to: string) => {
    const r = await send(`/api/admin/orders/${o.id}/status`, { method: "POST", body: { status: to } });
    if (r) reload();
  };

  const cols: Col<Order>[] = [
    { key: "c", head: "Order", cell: (o) => <code className="ad-code">{o.order_code}</code> },
    { key: "p", head: "Patient", cell: (o) => <>{o.full_name}<span className="ad-sub ad-num">{o.phone}</span></> },
    { key: "a", head: "Deliver to", wide: true, cell: (o) => <>{o.delivery_address}{o.zone && <span className="ad-sub">zone {o.zone}</span>}</> },
    {
      key: "t", head: "Total", num: true,
      cell: (o) => (
        <>
          <span className="ad-num">{rupees(o.total_inr)}</span>
          {o.credits_used ? <span className="ad-sub">{o.credits_used} credits used</span> : null}
          {o.amount_due_inr ? <span className="ad-sub">{rupees(o.amount_due_inr)} still due</span> : null}
        </>
      ),
    },
    { key: "w", head: "Placed", cell: (o) => when(o.created_at) },
    { key: "s", head: "Status", cell: (o) => <Status value={o.status} /> },
    {
      key: "do", head: "Move to", width: "1%",
      cell: (o) => (
        <RowActions>
          {ORDER_STATES.filter((s) => s !== o.status && s !== "cancelled").map((s) => (
            <Mini key={s} disabled={busy} onClick={() => move(o, s)}>{s.replace(/_/g, " ")}</Mini>
          ))}
          {o.status !== "cancelled" && (
            <Confirm label="Cancel" busy={busy} question={`Cancel order ${o.order_code}?`} onYes={() => move(o, "cancelled")} />
          )}
        </RowActions>
      ),
    },
  ];

  return (
    <Panel
      title="Delivery orders"
      count={data ? data.total : undefined}
      action={
        <Filters label="Status" value={status} onChange={setStatus}
                 options={[["", "All"], ["awaiting_payment", "Awaiting payment"], ["awaiting_stock", "Awaiting stock"],
                           ["confirmed", "Confirmed"], ["dispatched", "Dispatched"], ["delivered", "Delivered"]]} />
      }
    >
      {loading && !data ? <Loading rows={6} />
        : error ? <Empty title="Could not load the order queue" hint={error} />
        : !data?.orders.length ? (
          <Empty title="No orders in this state"
                 hint="When a patient orders a refill in chat or on a call, the order lands here for the pharmacy to pick and dispatch." />
        ) : <Table cols={cols} rows={data.orders} rowKey={(o) => String(o.id)} />}
    </Panel>
  );
}
