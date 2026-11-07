import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Empty, F, FSelect, Mini, Panel, Shown, Status, Table, when, useOps, useWrite, type Col } from "../adminKit";

/**
 * Staff accounts (admin only). Doctors sign in to prescribe as themselves; pharmacists to check orders.
 * Passwords are set here once and stored hashed; deactivating an account ends its access at once.
 */

type Account = { id: number; username: string; full_name: string; role: string; doctor: string | null; active: boolean; last_login_at: string | null };
type Doctor = { id: number; name: string; department?: string };

const BLANK = { username: "", full_name: "", role: "doctor", doctor_id: "", password: "" };

export function Staff() {
  const list = useOps<{ accounts: Account[] }>("/api/staff/accounts");
  const docs = useOps<{ doctors: Doctor[] }>("/api/admin/doctors");
  const { send, busy } = useWrite();
  const [f, setF] = useState(BLANK);
  const set = (k: keyof typeof BLANK) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await send("/api/staff/accounts", { method: "POST", body: {
      ...f, doctor_id: f.role === "doctor" && f.doctor_id ? Number(f.doctor_id) : null } });
    if (r) { setF(BLANK); list.reload(); }
  };
  const toggle = async (a: Account) => {
    const r = await send(`/api/staff/accounts/${a.id}/active`, { method: "POST", body: { active: !a.active } });
    if (r) list.reload();
  };

  const cols: Col<Account>[] = [
    { key: "u", head: "Account", cell: (a) => <><strong>{a.full_name}</strong><span className="ad-sub">{a.username}</span></> },
    { key: "r", head: "Role", cell: (a) => <>{a.role}{a.doctor && <span className="ad-sub">{a.doctor}</span>}</> },
    { key: "l", head: "Last sign-in", cell: (a) => when(a.last_login_at) },
    { key: "s", head: "Status", cell: (a) => <Status value={a.active ? "active" : "cancelled"} /> },
    { key: "a", head: "", cell: (a) => <Mini tone={a.active ? "danger" : "accent"} disabled={busy} onClick={() => toggle(a)}>
      {a.active ? "Deactivate" : "Reactivate"}</Mini> },
  ];
  const doctorOptions: [string, string][] = [["", "Choose the doctor…"],
    ...((docs.data?.doctors || []).map((d) => [String(d.id), d.name] as [string, string]))];

  return (
    <div className="ad-stack">
      <header className="ad-page-head">
        <h1>Staff accounts</h1>
        <p>Doctors prescribe and pharmacists check orders with their own sign-in. Each sees only their own desk.</p>
      </header>
      <Shown state={list} empty={{ title: "No staff accounts", hint: "Create the first one below." }}>
        {(d) => (
          <Panel title="Accounts" count={d.accounts.length}>
            {d.accounts.length ? <Table cols={cols} rows={d.accounts} rowKey={(a) => String(a.id)} />
              : <Empty title="No staff accounts" hint="Create the first one below." />}
          </Panel>
        )}
      </Shown>
      <Panel title="New account">
        <form className="ad-form-grid" onSubmit={create}>
          <F label="Full name" value={f.full_name} onChange={set("full_name")} required />
          <F label="Username" value={f.username} onChange={set("username")} required hint="Letters, numbers, dots" />
          <FSelect label="Role" value={f.role} onChange={set("role")} options={[["doctor", "Doctor"], ["pharmacist", "Pharmacist"], ["admin", "Administrator"]]} />
          {f.role === "doctor" && <FSelect label="Doctor" value={f.doctor_id} onChange={set("doctor_id")} options={doctorOptions} />}
          <F label="Password" type="password" value={f.password} onChange={set("password")} required hint="At least 10 characters; share it privately" />
          <div className="ad-field-span">
            <button className="btn btn-primary" disabled={busy}><UserPlus size={16} aria-hidden="true" /> Create account</button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
