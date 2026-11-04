import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Chip, Empty, Loading, Panel, rupees, useOps } from "./adminKit";

/**
 * The hospital reference: everything the AI knows, in the same words it says it.
 * Each page reads an endpoint that already existed, so what staff read here is exactly what a patient hears.
 */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Doctor = {
  code?: string; name: string; department: string; days: string; hours: string;
  fee_inr: number; room: string; languages: string; qualification?: string;
  experience_years?: number; day_codes?: number[];
};

export function AdminDoctors() {
  const { data, loading, error } = useOps<Doctor[]>("/api/doctors");
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");

  const depts = useMemo(() => Array.from(new Set((data || []).map((d) => d.department))).sort(), [data]);
  const rows = (data || []).filter((d) => {
    if (dept && d.department !== dept) return false;
    if (!q) return true;
    const hay = `${d.name} ${d.department} ${d.languages} ${d.qualification || ""} ${d.room}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  return (
    <Panel title={`Doctors${data ? ` · ${data.length}` : ""}`} action={
      <div className="ad-ref-controls">
        <select className="input" aria-label="Department" value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">All departments</option>
          {depts.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <div className="ad-search-inline">
          <Search size={15} aria-hidden="true" />
          <input className="input" placeholder="Name, language, room" aria-label="Search doctors"
                 value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
    }>
      {loading ? <Loading rows={8} /> : error ? <Empty title="Could not load doctors" hint={error} /> : !rows.length ? (
        <Empty title="No doctors match" hint="Try another department or clear the search." />
      ) : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Doctor</th><th>Department</th><th>Consults</th><th>Hours</th><th>Fee</th><th>Room</th><th>Speaks</th></tr></thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.code || d.name}>
                  <td>{d.name}<span className="ad-sub">{d.qualification}{d.experience_years ? ` · ${d.experience_years} yrs` : ""}</span></td>
                  <td>{d.department}</td>
                  <td>
                    <span className="ad-days">
                      {DAYS.map((lbl, i) => (
                        <i key={lbl} className={(d.day_codes || []).includes(i + 1) ? "on" : ""} title={lbl}>{lbl[0]}</i>
                      ))}
                    </span>
                  </td>
                  <td>{d.hours}</td>
                  <td>{rupees(d.fee_inr)}</td>
                  <td>{d.room}</td>
                  <td className="ad-wrap-cell">{d.languages}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

type Dept = { code: string; name: string; floor: string; description: string; doctors: number };

export function AdminDepartments() {
  const { data, loading, error } = useOps<Dept[]>("/api/departments");
  return (
    <Panel title={`Departments${data ? ` · ${data.length}` : ""}`}>
      {loading ? <Loading rows={6} /> : error ? <Empty title="Could not load departments" hint={error} /> : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Department</th><th>Floor</th><th>Doctors</th><th>What it covers</th></tr></thead>
            <tbody>
              {(data || []).map((d) => (
                <tr key={d.code}>
                  <td>{d.name}<span className="ad-sub">{d.code}</span></td>
                  <td>{d.floor}</td>
                  <td>{d.doctors}</td>
                  <td className="ad-wrap-cell">{d.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

type Proc = { code: string; name: string; category: string; price_inr: number; preauth_required: boolean; fasting_hours: number; instructions: string };

export function AdminTests() {
  const { data, loading, error } = useOps<Proc[]>("/api/procedures");
  const [cat, setCat] = useState("");
  const cats = useMemo(() => Array.from(new Set((data || []).map((p) => p.category))).sort(), [data]);
  const rows = (data || []).filter((p) => !cat || p.category === cat);

  return (
    <Panel title={`Tests and scans${data ? ` · ${data.length}` : ""}`} action={
      <div className="ad-filters">
        <button type="button" className={cat === "" ? "is-on" : ""} onClick={() => setCat("")}>All</button>
        {cats.map((c) => (
          <button key={c} type="button" className={cat === c ? "is-on" : ""} onClick={() => setCat(c)}>{c}</button>
        ))}
      </div>
    }>
      {loading ? <Loading rows={8} /> : error ? <Empty title="Could not load tests" hint={error} /> : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Test</th><th>Category</th><th>Price</th><th>Fasting</th><th>Pre-auth</th><th>How to prepare</th></tr></thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.code}>
                  <td>{p.name}<span className="ad-sub">{p.code}</span></td>
                  <td>{p.category}</td>
                  <td>{rupees(p.price_inr)}</td>
                  <td>{p.fasting_hours ? `${p.fasting_hours} h` : "none"}</td>
                  <td>{p.preauth_required ? <Chip kind="work">needed</Chip> : <Chip kind="ok">no</Chip>}</td>
                  <td className="ad-wrap-cell">{p.instructions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

type Insurer = { code: string; name: string; mode: string; tpa: string; documents: string };

export function AdminInsurance() {
  const { data, loading, error } = useOps<Insurer[]>("/api/insurers");
  return (
    <Panel title={`Insurers and TPAs${data ? ` · ${data.length}` : ""}`}>
      {loading ? <Loading rows={6} /> : error ? <Empty title="Could not load insurers" hint={error} /> : (
        <div className="ad-table-wrap">
          <table className="ad-table">
            <thead><tr><th>Insurer</th><th>Mode</th><th>TPA</th><th>Documents to bring</th></tr></thead>
            <tbody>
              {(data || []).map((i) => (
                <tr key={i.code}>
                  <td>{i.name}<span className="ad-sub">{i.code}</span></td>
                  <td><Chip kind={i.mode === "cashless" ? "ok" : "plain"}>{i.mode}</Chip></td>
                  <td>{i.tpa || "—"}</td>
                  <td className="ad-wrap-cell">{i.documents}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

type KbItem = { ref: string; title: string; embedded: boolean; text: string };
type KbResp = { passages: number; by_kind: Record<string, { passages: number; embedded: number }>; items: KbItem[]; search?: any };

const KIND_LABEL: Record<string, string> = {
  info: "Hospital information", dept: "Departments", proc: "Tests and scans",
  ins: "Insurers", faq: "FAQs", policy: "Policies", doc: "Uploaded documents",
};

/** Everything in the hospital knowledge base: the exact passages get_hospital_info reads out. */
export function AdminKnowledge() {
  const { data, loading, error } = useOps<KbResp>("/api/ops/kb?full=true");
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");

  const rows = (data?.items || []).filter((it) => {
    if (kind && it.ref.split(":")[1] !== kind) return false;
    if (!q) return true;
    return `${it.title} ${it.text}`.toLowerCase().includes(q.toLowerCase());
  });
  const kinds = Object.keys(data?.by_kind || {});

  return (
    <Panel title={`Knowledge base${data ? ` · ${data.passages} passages` : ""}`} action={
      <div className="ad-search-inline">
        <Search size={15} aria-hidden="true" />
        <input className="input" placeholder="Search everything the AI knows" aria-label="Search the knowledge base"
               value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
    }>
      {loading ? <Loading rows={10} /> : error ? <Empty title="Could not load the knowledge base" hint={error} /> : (
        <>
          <div className="ad-filters ad-filters-wrap">
            <button type="button" className={kind === "" ? "is-on" : ""} onClick={() => setKind("")}>
              All {data?.passages}
            </button>
            {kinds.map((k) => (
              <button key={k} type="button" className={kind === k ? "is-on" : ""} onClick={() => setKind(k)}>
                {KIND_LABEL[k] || k} {data?.by_kind[k].passages}
              </button>
            ))}
          </div>
          {!rows.length ? (
            <Empty title="Nothing matches" hint="Try a different word. This searches the passage titles and their full text." />
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
            These are the exact sentences the Info agent reads out on chat and on the phone. Change them in
            <code className="ad-code"> app/kb.py </code> or drop a Markdown file into <code className="ad-code">data/hospital/</code>.
          </p>
        </>
      )}
    </Panel>
  );
}
