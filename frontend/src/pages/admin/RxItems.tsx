import { Plus, Trash2 } from "lucide-react";
import { F, FCheck, FSelect, useOps } from "../adminKit";

/**
 * The medicine lines of a prescription, used by the doctor's Prescribe screen and by the pharmacist when an
 * uploaded prescription is approved. The server checks every number again (dose ceiling, ranges); this form only
 * shows the daily dose so the prescriber sees it before saving.
 */

export type Med = {
  code: string; brand: string; generic: string; strength: string; strength_mg: number | null; pack: string;
  schedule: string; ingredient: string; max_daily_mg: number | null;
};
export type Line = {
  medicine_code: string; dose_units: string; times_per_day: string; duration_days: string; refills_allowed: string;
  substitution_allowed: boolean; instructions: string; override_reason: string;
};

export const BLANK_LINE: Line = {
  medicine_code: "", dose_units: "1", times_per_day: "1", duration_days: "5", refills_allowed: "0",
  substitution_allowed: true, instructions: "", override_reason: "",
};

const TIMES: [string, string][] = [
  ["1", "Once a day"], ["2", "Twice a day"], ["3", "Three times a day"], ["4", "Four times a day"],
  ["0.142857", "Once a week"],
];

export function useFormulary() {
  return useOps<{ medicines: Med[] }>("/api/staff/formulary");
}

export function toItems(lines: Line[]) {
  return lines.filter((l) => l.medicine_code).map((l) => ({
    medicine_code: l.medicine_code, dose_units: Number(l.dose_units), times_per_day: Number(l.times_per_day),
    duration_days: Number(l.duration_days), refills_allowed: Number(l.refills_allowed),
    substitution_allowed: l.substitution_allowed, instructions: l.instructions, override_reason: l.override_reason,
  }));
}

export function RxItems({ lines, onChange, meds }: { lines: Line[]; onChange: (l: Line[]) => void; meds: Med[] }) {
  const set = (i: number, k: keyof Line) => (v: any) => onChange(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const byCode = Object.fromEntries(meds.map((m) => [m.code, m]));
  const options: [string, string][] = [["", "Choose a medicine…"],
    ...meds.map((m) => [m.code, `${m.brand} · ${m.generic} ${m.strength} (${m.schedule})`] as [string, string])];

  return (
    <div className="ad-stack">
      {lines.map((l, i) => {
        const m = byCode[l.medicine_code];
        const daily = m?.strength_mg ? Number(l.dose_units) * Number(l.times_per_day) * m.strength_mg : null;
        const over = daily != null && m?.max_daily_mg != null && daily > m.max_daily_mg + 1e-9;
        return (
          <fieldset key={i} className="ad-rx-line">
            <legend>Medicine {i + 1}</legend>
            <div className="ad-form-grid">
              <FSelect label="Medicine" value={l.medicine_code} onChange={set(i, "medicine_code")} options={options} span />
              <F label="Dose per intake" type="number" min={0.25} step={0.25} value={l.dose_units} onChange={set(i, "dose_units")}
                 hint={m ? `tablets, capsules, puffs or ml · ${m.pack}` : undefined} />
              <FSelect label="How often" value={l.times_per_day} onChange={set(i, "times_per_day")} options={TIMES} />
              <F label="For how many days" type="number" min={1} value={l.duration_days} onChange={set(i, "duration_days")} />
              <F label="Refills" type="number" min={0} value={l.refills_allowed} onChange={set(i, "refills_allowed")}
                 hint="0 for a course (antibiotics); 5 covers 6 months of a 30-day medicine" />
              <F label="Instructions" value={l.instructions} onChange={set(i, "instructions")} placeholder="After food" span />
              {daily != null && (
                <p className={over ? "ad-rx-dose is-over" : "ad-rx-dose"} role={over ? "alert" : undefined}>
                  {daily.toLocaleString("en-IN")} mg a day
                  {m?.max_daily_mg != null && <> · usual adult maximum {m.max_daily_mg.toLocaleString("en-IN")} mg</>}
                </p>
              )}
              {over && (
                <F label="Reason to go above the maximum" value={l.override_reason} onChange={set(i, "override_reason")} required span />
              )}
              <div className="ad-field-span ad-checks">
                <FCheck label="Pharmacy may send an equivalent generic" checked={l.substitution_allowed}
                        onChange={set(i, "substitution_allowed")} />
              </div>
            </div>
            {lines.length > 1 && (
              <button type="button" className="ad-mini ad-mini-danger" onClick={() => onChange(lines.filter((_, j) => j !== i))}>
                <Trash2 size={14} aria-hidden="true" /> Remove
              </button>
            )}
          </fieldset>
        );
      })}
      <button type="button" className="ad-mini" onClick={() => onChange([...lines, { ...BLANK_LINE }])}>
        <Plus size={14} aria-hidden="true" /> Add another medicine
      </button>
    </div>
  );
}
