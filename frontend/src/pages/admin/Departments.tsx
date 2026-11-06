import { useState } from "react";
import { Plus } from "lucide-react";
import {
  Confirm, Empty, F, FArea, Loading, Mini, Panel, RowActions, Sheet, Table, useOps, useWrite, type Col,
} from "../adminKit";

/** Departments — the specialities the AI offers, and the floor it sends people to. */

type Dept = { id: number; code: string; name: string; floor: string; description: string; doctors: number };
type Resp = { total: number; departments: Dept[] };

const BLANK = { code: "", name: "", floor: "", description: "" };

export function Departments() {
  const { data, loading, error, reload } = useOps<Resp>("/api/admin/departments");
  const { send, busy } = useWrite();
  const [editing, setEditing] = useState<Dept | "new" | null>(null);
  const [f, setF] = useState(BLANK);
  const set = (k: keyof typeof f) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const openNew = () => { setF(BLANK); setEditing("new"); };
  const openEdit = (d: Dept) => {
    setF({ code: d.code, name: d.name, floor: d.floor || "", description: d.description || "" });
    setEditing(d);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = { code: f.code.trim().toUpperCase(), name: f.name.trim(), floor: f.floor, description: f.description };
    const r = editing === "new"
      ? await send("/api/admin/departments", { method: "POST", body })
      : await send(`/api/admin/departments/${(editing as Dept).id}`, { method: "PATCH", body });
    if (r) { setEditing(null); reload(); }
  };

  const remove = async (d: Dept) => {
    const r = await send(`/api/admin/departments/${d.id}`, { method: "DELETE" });
    if (r) { setEditing(null); reload(); }
  };

  const cols: Col<Dept>[] = [
    { key: "n", head: "Department", cell: (d) => <>{d.name}<span className="ad-sub">{d.code}</span></> },
    { key: "f", head: "Floor", cell: (d) => d.floor || <span className="ad-dim">not set</span> },
    { key: "docs", head: "Doctors", num: true, cell: (d) => <span className="ad-num">{d.doctors}</span> },
    { key: "d", head: "What it covers", wide: true, cell: (d) => d.description || <span className="ad-dim">no description</span> },
    {
      key: "do", head: "Manage", width: "1%",
      cell: (d) => (
        <RowActions>
          <Mini tone="accent" onClick={() => openEdit(d)}>Edit</Mini>
          <Confirm label="Remove" busy={busy} question={`Remove ${d.name}?`} onYes={() => remove(d)} />
        </RowActions>
      ),
    },
  ];

  return (
    <div className="ad-stack">
      {editing && (
        <Sheet
          title={editing === "new" ? "Add a department" : `Edit ${editing.name}`}
          sub="The description is read out when a patient asks what a department does, so write it the way you would say it."
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn btn-primary btn-sm" type="submit" form="dept-form" disabled={busy}>
                {busy ? "Saving…" : editing === "new" ? "Add this department" : "Save changes"}
              </button>
              <button className="btn btn-quiet btn-sm" type="button" onClick={() => setEditing(null)}>Cancel</button>
            </>
          }
        >
          <form id="dept-form" onSubmit={save} className="ad-form-grid">
            <F label="Short code" value={f.code} onChange={set("code")} required placeholder="CARD"
               hint="Four or five letters. Used in booking references." />
            <F label="Name" value={f.name} onChange={set("name")} required placeholder="Cardiology" />
            <F label="Floor" value={f.floor} onChange={set("floor")} placeholder="3rd floor" />
            <FArea label="What it covers" value={f.description} onChange={set("description")}
                   hint="Plain words. “Heart and blood vessel care: chest pain review, BP, ECG, echo.”" />
          </form>
        </Sheet>
      )}

      <Panel
        title="Departments"
        count={data ? data.total : undefined}
        action={
          <button type="button" className="btn btn-primary btn-sm" onClick={openNew}>
            <Plus size={15} aria-hidden="true" /> Add a department
          </button>
        }
      >
        {loading && !data ? <Loading rows={8} />
          : error ? <Empty title="Could not load departments" hint={error} />
          : !data?.departments.length ? (
            <Empty title="No departments yet" hint="Add the first one; doctors are then assigned to it." />
          ) : <Table cols={cols} rows={data.departments} rowKey={(d) => String(d.id)}
                     isOn={(d) => editing !== "new" && editing?.id === d.id} />}
      </Panel>
    </div>
  );
}
