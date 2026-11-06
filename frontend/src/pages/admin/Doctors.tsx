import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import {
  Confirm, DayPicker, Days, Empty, F, FArea, FSelect, Loading, Mini, Panel, RowActions, SearchBox,
  Sheet, Table, rupees, useOps, useWrite, type Col,
} from "../adminKit";

/** Doctors — the roster the booking engine reads. Adding one here opens real slots within seconds. */

type Doctor = {
  id: number; code: string; name: string; gender: string; department_id: number;
  qualification: string; experience_years: number; languages: string; fee_inr: number;
  room: string; consult_days: string; start_time: string; end_time: string; slot_minutes: number;
  bio: string; department: string;
};
type Resp = { total: number; doctors: Doctor[] };
type Dept = { id: number; name: string };

const BLANK = {
  name: "", department_id: "", qualification: "", experience_years: "0", languages: "English",
  fee_inr: "500", room: "OPD-000", consult_days: "1,2,3,4,5", start_time: "09:00", end_time: "13:00",
  slot_minutes: "15", gender: "", bio: "",
};

export function Doctors() {
  const { data, loading, error, reload } = useOps<Resp>("/api/admin/doctors");
  const depts = useOps<{ departments: Dept[] }>("/api/admin/departments");
  const { send, busy } = useWrite();
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [editing, setEditing] = useState<Doctor | "new" | null>(null);
  const [f, setF] = useState<Record<string, string>>(BLANK);

  const deptOptions = useMemo<[string, string][]>(
    () => (depts.data?.departments || []).map((d) => [String(d.id), d.name]),
    [depts.data],
  );

  const term = q.trim().toLowerCase();
  const rows = (data?.doctors || []).filter((d) => {
    if (dept && String(d.department_id) !== dept) return false;
    if (!term) return true;
    return `${d.name} ${d.department} ${d.languages} ${d.qualification} ${d.room} ${d.code}`.toLowerCase().includes(term);
  });

  const openNew = () => {
    setF({ ...BLANK, department_id: deptOptions[0]?.[0] || "" });
    setEditing("new");
  };
  const openEdit = (d: Doctor) => {
    setF({
      name: d.name, department_id: String(d.department_id), qualification: d.qualification || "",
      experience_years: String(d.experience_years ?? 0), languages: d.languages || "English",
      fee_inr: String(d.fee_inr ?? 0), room: d.room || "", consult_days: d.consult_days || "",
      start_time: d.start_time || "09:00", end_time: d.end_time || "13:00",
      slot_minutes: String(d.slot_minutes ?? 15), gender: d.gender || "", bio: d.bio || "",
    });
    setEditing(d);
  };
  const set = (k: string) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = {
      name: f.name.trim(), department_id: Number(f.department_id),
      qualification: f.qualification, experience_years: Number(f.experience_years) || 0,
      languages: f.languages, fee_inr: Number(f.fee_inr) || 0, room: f.room,
      consult_days: f.consult_days || "1,2,3,4,5", start_time: f.start_time, end_time: f.end_time,
      slot_minutes: Number(f.slot_minutes) || 15, gender: f.gender, bio: f.bio,
    };
    const r = editing === "new"
      ? await send("/api/admin/doctors", { method: "POST", body })
      : await send(`/api/admin/doctors/${(editing as Doctor).id}`, { method: "PATCH", body });
    if (r) { setEditing(null); reload(); }
  };

  const remove = async (d: Doctor) => {
    const r = await send(`/api/admin/doctors/${d.id}`, { method: "DELETE" });
    if (r) { if (editing !== "new" && editing?.id === d.id) setEditing(null); reload(); }
  };

  const cols: Col<Doctor>[] = [
    { key: "who", head: "Doctor", cell: (d) => <>{d.name}<span className="ad-sub">{d.code} · {d.qualification || "—"}{d.experience_years ? ` · ${d.experience_years} yrs` : ""}</span></> },
    { key: "dept", head: "Department", cell: (d) => d.department },
    { key: "days", head: "Consults", cell: (d) => <Days codes={d.consult_days || ""} /> },
    {
      key: "hours", head: "Hours",
      cell: (d) => (
        <>
          <span className="ad-num">{d.start_time}–{d.end_time}</span>
          <span className="ad-sub">{d.slot_minutes} min slots</span>
        </>
      ),
    },
    { key: "fee", head: "Fee", num: true, cell: (d) => <span className="ad-num">{rupees(d.fee_inr)}</span> },
    { key: "room", head: "Room", cell: (d) => <span className="ad-num">{d.room}</span> },
    { key: "lang", head: "Speaks", wide: true, cell: (d) => d.languages },
    {
      key: "do", head: "Manage", width: "1%",
      cell: (d) => (
        <RowActions>
          <Mini tone="accent" onClick={() => openEdit(d)}>Edit</Mini>
          <Confirm label="Remove" busy={busy}
                   question={`Remove ${d.name} from the roster?`}
                   onYes={() => remove(d)} />
        </RowActions>
      ),
    },
  ];

  return (
    <div className="ad-stack">
      {editing && (
        <Sheet
          title={editing === "new" ? "Add a doctor" : `Edit ${editing.name}`}
          sub="Consulting days and hours decide the slots patients are offered in chat and on the phone."
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn btn-primary btn-sm" type="submit" form="doc-form" disabled={busy}>
                {busy ? "Saving…" : editing === "new" ? "Add this doctor" : "Save changes"}
              </button>
              <button className="btn btn-quiet btn-sm" type="button" onClick={() => setEditing(null)}>Cancel</button>
            </>
          }
        >
          <form id="doc-form" onSubmit={save} className="ad-form-grid">
            <F label="Name" value={f.name} onChange={set("name")} required placeholder="Dr. Meera Iyer" />
            <FSelect label="Department" value={f.department_id} onChange={set("department_id")}
                     options={deptOptions.length ? deptOptions : [["", "Loading departments…"]]} />
            <F label="Qualification" value={f.qualification} onChange={set("qualification")} placeholder="MBBS, MD (Medicine)" />
            <F label="Years of experience" type="number" min={0} value={f.experience_years} onChange={set("experience_years")} />
            <F label="Languages" value={f.languages} onChange={set("languages")}
               hint="Comma separated. The AI matches a patient's language against this." />
            <FSelect label="Gender" value={f.gender} onChange={set("gender")}
                     options={[["", "Not stated"], ["female", "Female"], ["male", "Male"]]} />
            <F label="Consultation fee (₹)" type="number" min={0} value={f.fee_inr} onChange={set("fee_inr")} />
            <F label="Room" value={f.room} onChange={set("room")} placeholder="OPD-204" />
            <DayPicker value={f.consult_days} onChange={set("consult_days")} />
            <F label="Clinic starts" type="time" value={f.start_time} onChange={set("start_time")} />
            <F label="Clinic ends" type="time" value={f.end_time} onChange={set("end_time")} />
            <F label="Slot length (minutes)" type="number" min={5} step={5} value={f.slot_minutes} onChange={set("slot_minutes")} />
            <FArea label="Bio" value={f.bio} onChange={set("bio")}
                   hint="One or two sentences. The AI may read this out when a patient asks who they will see." />
          </form>
        </Sheet>
      )}

      <Panel
        title="Doctors"
        count={data ? rows.length : undefined}
        action={
          <div className="ad-head-tools">
            <FSelect bare label="Filter by department" value={dept} onChange={setDept}
                     options={[["", "All departments"], ...deptOptions]} />
            <SearchBox value={q} onChange={setQ} placeholder="Name, language, room" label="Search doctors" />
            <button type="button" className="btn btn-primary btn-sm" onClick={openNew}>
              <Plus size={15} aria-hidden="true" /> Add a doctor
            </button>
          </div>
        }
      >
        {loading && !data ? <Loading rows={10} />
          : error ? <Empty title="Could not load the roster" hint={error} />
          : !rows.length ? (
            <Empty title="No doctors match"
                   hint="Clear the search or pick another department. Use “Add a doctor” to create one." />
          ) : <Table cols={cols} rows={rows} rowKey={(d) => String(d.id)} isOn={(d) => editing !== "new" && editing?.id === d.id} />}
      </Panel>
    </div>
  );
}
