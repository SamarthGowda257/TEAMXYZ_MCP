import { useMemo, useState } from "react";
import { BookOpen } from "lucide-react";
import {
  Chip, Confirm, Empty, F, FArea, FSelect, Filters, Loading, Mini, Panel, RowActions, SearchBox,
  Sheet, Table, rupees, useOps, useWrite, type Col,
} from "./adminKit";

/**
 * Knowledge and insurance: what the AI knows, in the same words it says it.
 *
 * Insurers are editable here, because a TPA change or a new document requirement has to reach the
 * phone line the same hour it is decided. The knowledge passages are read-only on purpose — they come
 * from `app/kb.py` and `data/hospital/`, which are version-controlled, and the page says where.
 */

/* ------------------------------------------------------------------ insurers */

type Insurer = { id: number; code: string; name: string; mode: string; tpa_name: string; documents: string; notes: string };
type InsResp = { total: number; insurers: Insurer[] };

const MODES: [string, string][] = [["cashless", "Cashless"], ["reimbursement", "Reimbursement"], ["both", "Both"]];

export function AdminInsurance() {
  const { data, loading, error, reload } = useOps<InsResp>("/api/admin/insurers");
  const { send, busy } = useWrite();
  const [editing, setEditing] = useState<Insurer | null>(null);
  const [f, setF] = useState({ name: "", mode: "both", tpa_name: "", documents: "", notes: "" });
  const set = (k: keyof typeof f) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const open = (i: Insurer) => {
    setF({ name: i.name, mode: i.mode || "both", tpa_name: i.tpa_name || "", documents: i.documents || "", notes: i.notes || "" });
    setEditing(i);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    const r = await send(`/api/admin/insurers/${editing.id}`, { method: "PATCH", body: f });
    if (r) { setEditing(null); reload(); }
  };

  const cols: Col<Insurer>[] = [
    { key: "n", head: "Insurer", cell: (i) => <>{i.name}<span className="ad-sub">{i.code}</span></> },
    { key: "m", head: "Settlement", cell: (i) => <Chip kind={i.mode === "cashless" ? "ok" : i.mode === "both" ? "live" : "plain"}>{i.mode}</Chip> },
    { key: "t", head: "TPA", cell: (i) => i.tpa_name || <span className="ad-dim">in-house</span> },
    { key: "d", head: "Documents to bring", wide: true, cell: (i) => i.documents || <span className="ad-dim">none listed</span> },
    { key: "no", head: "Notes", wide: true, cell: (i) => i.notes || <span className="ad-dim">—</span> },
    { key: "do", head: "Manage", width: "1%", cell: (i) => <RowActions><Mini tone="accent" onClick={() => open(i)}>Edit</Mini></RowActions> },
  ];

  return (
    <div className="ad-stack">
      {editing && (
        <Sheet
          title={`Edit ${editing.name}`}
          sub="These exact words are read out when a patient asks what to bring for a cashless claim."
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn btn-primary btn-sm" type="submit" form="ins-form" disabled={busy}>
                {busy ? "Saving…" : "Save changes"}
              </button>
              <button className="btn btn-quiet btn-sm" type="button" onClick={() => setEditing(null)}>Cancel</button>
            </>
          }
        >
          <form id="ins-form" onSubmit={save} className="ad-form-grid">
            <F label="Name" value={f.name} onChange={set("name")} required />
            <FSelect label="Settlement mode" value={f.mode} onChange={set("mode")} options={MODES} />
            <F label="TPA" value={f.tpa_name} onChange={set("tpa_name")} placeholder="Star Health in-house TPA" span />
            <FArea label="Documents to bring" value={f.documents} onChange={set("documents")}
                   hint="Comma separated, in the order you would say them." />
            <FArea label="Notes" value={f.notes} onChange={set("notes")}
                   hint="Pre-authorisation rules, exclusions, anything the desk repeats daily." />
          </form>
        </Sheet>
      )}

      <Panel title="Insurers and TPAs" count={data ? data.total : undefined}>
        {loading && !data ? <Loading rows={8} />
          : error ? <Empty title="Could not load insurers" hint={error} />
          : !data?.insurers.length ? (
            <Empty title="No insurers on file" hint="Insurers are seeded with the hospital data and can be edited here." />
          ) : <Table cols={cols} rows={data.insurers} rowKey={(i) => String(i.id)} isOn={(i) => editing?.id === i.id} />}
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ tests and scans */

type Proc = { code: string; name: string; category: string; price_inr: number; preauth_required: boolean; fasting_hours: number; instructions: string };

export function AdminTests() {
  const { data, loading, error } = useOps<Proc[]>("/api/procedures");
  const [cat, setCat] = useState("");
  const cats = useMemo(() => Array.from(new Set((data || []).map((p) => p.category))).sort(), [data]);
  const rows = (data || []).filter((p) => !cat || p.category === cat);

  const cols: Col<Proc>[] = [
    { key: "n", head: "Test", cell: (p) => <>{p.name}<span className="ad-sub">{p.code}</span></> },
    { key: "c", head: "Category", cell: (p) => p.category },
    { key: "p", head: "Price", num: true, cell: (p) => <span className="ad-num">{rupees(p.price_inr)}</span> },
    { key: "f", head: "Fasting", cell: (p) => (p.fasting_hours ? <span className="ad-num">{p.fasting_hours} h</span> : <span className="ad-dim">none</span>) },
    { key: "pa", head: "Pre-auth", cell: (p) => (p.preauth_required ? <Chip kind="work">needed</Chip> : <Chip kind="ok">no</Chip>) },
    { key: "i", head: "How to prepare", wide: true, cell: (p) => p.instructions },
  ];

  return (
    <Panel
      title="Tests and scans"
      count={data ? data.length : undefined}
      action={
        <Filters label="Category" value={cat} onChange={setCat}
                 options={[["", "All"], ...cats.map((c) => [c, c] as [string, string])]} />
      }
    >
      {loading && !data ? <Loading rows={10} />
        : error ? <Empty title="Could not load tests" hint={error} />
        : !rows.length ? <Empty title="Nothing in this category" hint="Pick another category." />
        : <Table cols={cols} rows={rows} rowKey={(p) => p.code} />}
    </Panel>
  );
}

/* ------------------------------------------------------------------ knowledge base */

type KbItem = { ref: string; title: string; embedded: boolean; text: string };
type KbResp = { passages: number; by_kind: Record<string, { passages: number; embedded: number }>; items: KbItem[] };

const KIND_LABEL: Record<string, string> = {
  info: "Hospital information", dept: "Departments", proc: "Tests and scans",
  ins: "Insurers", faq: "FAQs", policy: "Policies", doc: "Uploaded documents",
};

export function AdminKnowledge() {
  const { data, loading, error } = useOps<KbResp>("/api/ops/kb?full=true");
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");

  const rows = (data?.items || []).filter((it) => {
    if (kind && it.ref.split(":")[1] !== kind) return false;
    if (!q.trim()) return true;
    return `${it.title} ${it.text}`.toLowerCase().includes(q.trim().toLowerCase());
  });
  const kinds = Object.keys(data?.by_kind || {});

  return (
    <Panel
      title="Knowledge base"
      count={data ? `${data.passages} passages` : undefined}
      action={<SearchBox value={q} onChange={setQ} placeholder="Search everything the AI knows" label="Search the knowledge base" />}
    >
      {loading && !data ? <Loading rows={10} />
        : error ? <Empty title="Could not load the knowledge base" hint={error} />
        : (
          <>
            <div className="ad-filters ad-filters-wrap">
              <button type="button" aria-pressed={kind === ""} className={kind === "" ? "is-on" : ""} onClick={() => setKind("")}>
                All {data?.passages}
              </button>
              {kinds.map((k) => (
                <button key={k} type="button" aria-pressed={kind === k} className={kind === k ? "is-on" : ""} onClick={() => setKind(k)}>
                  {KIND_LABEL[k] || k} {data?.by_kind[k].passages}
                </button>
              ))}
            </div>
            {!rows.length ? (
              <Empty title="Nothing matches that word" hint="This searches the passage titles and their full text. Try a shorter word." />
            ) : (
              <ul className="ad-kb">
                {rows.map((it) => (
                  <li key={it.ref}>
                    <div className="ad-kb-top">
                      <strong>{it.title}</strong>
                      <code className="ad-code">{it.ref}</code>
                      {it.embedded ? <Chip kind="ok">embedded</Chip> : <Chip kind="plain">keyword only</Chip>}
                    </div>
                    <p>{it.text}</p>
                  </li>
                ))}
              </ul>
            )}
            <p className="ad-note">
              <BookOpen size={14} aria-hidden="true" /> These are the exact sentences the Info agent reads out on
              chat and on the phone. They are version-controlled, so they are edited in
              <code className="ad-code"> app/kb.py </code> or by dropping a Markdown file into
              <code className="ad-code"> data/hospital/</code> — not from this screen.
            </p>
          </>
        )}
    </Panel>
  );
}

/* Kept so nothing that imported the old names breaks. Doctors and departments are now full CRUD
   screens of their own, under pages/admin/. */
export { Doctors as AdminDoctors } from "./admin/Doctors";
export { Departments as AdminDepartments } from "./admin/Departments";
export { Confirm as _Confirm };
