export interface ProfileFields {
  birth_year: string; height_cm: string; weight_kg: string; target_override: boolean; target_kcal: string;
}
export type ProfileErrors = Partial<Record<"birth_year" | "height_cm" | "weight_kg" | "target_kcal", string>>;

const inRange = (raw: string, min: number, max: number) => {
  const n = Number(raw);
  return raw.trim() !== "" && Number.isFinite(n) && n >= min && n <= max;
};

/** Same ranges the API enforces, so errors appear next to the field instead of after saving. */
export function validateProfile(f: ProfileFields, year: number = new Date().getFullYear()): ProfileErrors {
  const e: ProfileErrors = {};
  if (!inRange(f.birth_year, 1900, year - 1) || !Number.isInteger(Number(f.birth_year))) e.birth_year = `Enter a year between 1900 and ${year - 1}`;
  if (!inRange(f.height_cm, 80, 250)) e.height_cm = "Enter a height between 80 and 250 cm";
  if (!inRange(f.weight_kg, 20, 400)) e.weight_kg = "Enter a weight between 20 and 400 kg";
  if (f.target_override && !inRange(f.target_kcal, 500, 10000)) e.target_kcal = "Enter a target between 500 and 10,000 kcal";
  return e;
}

/** Relative position against a target, as friendly text ("8% under target"). */
export function vsTarget(avg: number, target: number | null | undefined): { tone: "ok" | "near" | "over" | "none"; text: string } {
  if (!target || avg <= 0) return { tone: "none", text: "" };
  const p = Math.round(((avg - target) / target) * 100);
  if (Math.abs(p) < 1) return { tone: "ok", text: "On target" };
  return p < 0 ? { tone: "ok", text: `${-p}% under target` } : { tone: p > 10 ? "over" : "near", text: `${p}% over target` };
}
