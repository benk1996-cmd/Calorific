import { ReactNode, useMemo, useState } from "react";
import { ActivityLevel, Goal, Profile, api } from "../lib/api";
import { validateProfile } from "../lib/profile";
import { previewKcal, previewMacros } from "../lib/targets";
import { Button, Card, Field, Icon, Segmented, inputClass } from "../ui";

const ACTIVITY: { value: ActivityLevel; title: string; sub: string }[] = [
  { value: "sedentary", title: "Sedentary", sub: "Mostly seated, little exercise" },
  { value: "light", title: "Lightly active", sub: "Exercise 1–3 days a week" },
  { value: "moderate", title: "Moderately active", sub: "Exercise 3–5 days a week" },
  { value: "active", title: "Very active", sub: "Hard exercise 6–7 days a week" },
  { value: "very_active", title: "Athlete", sub: "Physical job plus training" },
];
const GOALS: { value: Goal; label: string }[] = [
  { value: "lose", label: "Lose" }, { value: "maintain", label: "Maintain" }, { value: "gain", label: "Gain" },
];
const GOAL_NOTE: Record<Goal, string> = {
  lose: "A gentle deficit of 500 kcal a day.", maintain: "Eat what you burn.", gain: "A modest surplus of 300 kcal a day.",
};
const ZONES = ["Asia/Singapore", "Asia/Kuala_Lumpur", "Asia/Jakarta", "Asia/Bangkok", "Asia/Hong_Kong", "Asia/Tokyo", "Australia/Sydney", "Europe/London", "America/New_York", "America/Los_Angeles"];

interface Form {
  display_name: string; sex: "male" | "female"; birth_year: string; height_cm: string; weight_kg: string;
  activity_level: ActivityLevel; goal: Goal; timezone: string; target_override: boolean; target_kcal: string;
}

function initial(p: Profile | null): Form {
  return {
    display_name: p?.display_name ?? "", sex: p?.sex ?? "female", birth_year: String(p?.birth_year ?? 1995),
    height_cm: String(p?.height_cm ?? 165), weight_kg: String(p?.weight_kg ?? 60),
    activity_level: p?.activity_level ?? "light", goal: p?.goal ?? "maintain",
    timezone: p?.timezone ?? (Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Singapore"),
    target_override: p?.target_override ?? false, target_kcal: String(p?.target_kcal ?? 2000),
  };
}

function TargetCard({ kcal, manual }: { kcal: number; manual: boolean }) {
  const m = previewMacros(kcal);
  return (
    <div className="rounded-2xl bg-brand-soft p-5 text-center">
      <p className="text-xs font-semibold uppercase tracking-wide text-brand">{manual ? "Your target" : "Your daily target"}</p>
      <p className="num mt-1 text-5xl font-extrabold text-ink">{kcal.toLocaleString()}</p>
      <p className="text-sm font-medium text-ink2">kcal per day</p>
      <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
        {[["Protein", m.protein, "bg-protein"], ["Carbs", m.carbs, "bg-carbs"], ["Fat", m.fat, "bg-fat"]].map(([l, g, c]) => (
          <div key={l as string} className="rounded-xl bg-card p-2.5"><span className={`mx-auto mb-1 block h-1.5 w-8 rounded-full ${c}`} /><b className="num block">{g} g</b><span className="text-xs text-muted">{l}</span></div>
        ))}
      </div>
    </div>
  );
}

export default function ProfileForm({ initial: init, onSaved, onboarding, onSignOut, dataSection }: {
  initial: Profile | null; onSaved: (p: Profile) => void; onboarding?: boolean; onSignOut?: () => void; dataSection?: ReactNode;
}) {
  const start = useMemo(() => initial(init), [init]);
  const [f, setF] = useState<Form>(start);
  const [step, setStep] = useState(0);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((p) => ({ ...p, [k]: v }));
  const errors = validateProfile(f);
  const show = (k: keyof typeof errors) => (touched ? errors[k] : undefined);
  const calc = previewKcal({ sex: f.sex, birthYear: Number(f.birth_year), heightCm: Number(f.height_cm), weightKg: Number(f.weight_kg), activity: f.activity_level, goal: f.goal });
  const shown = f.target_override && !errors.target_kcal ? Number(f.target_kcal) : calc;
  const dirty = JSON.stringify(f) !== JSON.stringify(start);
  const bodyOk = !errors.birth_year && !errors.height_cm && !errors.weight_kg;

  async function save() {
    setTouched(true);
    if (Object.keys(errors).length) { if (onboarding && !bodyOk) setStep(0); return; }
    setBusy(true); setErr("");
    try {
      const res = await api<{ profile: Profile }>("/api/profile", {
        method: "PUT",
        body: JSON.stringify({
          display_name: f.display_name.trim() || null, sex: f.sex, birth_year: Number(f.birth_year), height_cm: Number(f.height_cm),
          weight_kg: Number(f.weight_kg), activity_level: f.activity_level, goal: f.goal, timezone: f.timezone,
          target_override: f.target_override, target_kcal: f.target_override ? Number(f.target_kcal) : null,
        }),
      });
      onSaved(res.profile);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  const about: ReactNode = (
    <div className="space-y-4">
      <Field label="First name (optional)"><input className={inputClass} value={f.display_name} autoComplete="given-name" onChange={(e) => set("display_name", e.target.value)} /></Field>
      <div><span className="mb-1.5 block text-sm font-semibold text-ink2">Sex <span className="font-normal text-muted">(used for the calorie formula)</span></span>
        <Segmented label="Sex" value={f.sex} onChange={(v) => set("sex", v)} options={[{ value: "female", label: "Female" }, { value: "male", label: "Male" }]} /></div>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Birth year" error={show("birth_year")}><input className={inputClass} inputMode="numeric" value={f.birth_year} onChange={(e) => set("birth_year", e.target.value)} /></Field>
        <Field label="Height" suffix="cm" error={show("height_cm")}><input className={`${inputClass} pr-10`} inputMode="decimal" value={f.height_cm} onChange={(e) => set("height_cm", e.target.value)} /></Field>
        <Field label="Weight" suffix="kg" error={show("weight_kg")}><input className={`${inputClass} pr-10`} inputMode="decimal" value={f.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} /></Field>
      </div>
    </div>
  );

  const lifestyle: ReactNode = (
    <div className="space-y-4">
      <div role="radiogroup" aria-label="Activity level" className="space-y-2">
        {ACTIVITY.map((a) => {
          const on = f.activity_level === a.value;
          return (
            <button key={a.value} type="button" role="radio" aria-checked={on} onClick={() => set("activity_level", a.value)}
              className={`flex min-h-[56px] w-full items-center gap-3 rounded-xl border p-3 text-left transition ${on ? "border-brand bg-brand-soft" : "border-line bg-card"}`}>
              <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${on ? "border-brand bg-brand text-brand-ink" : "border-line"}`}>{on && <Icon name="check" className="h-3 w-3" />}</span>
              <span><span className="block font-semibold">{a.title}</span><span className="block text-sm text-muted">{a.sub}</span></span>
            </button>
          );
        })}
      </div>
      <div><span className="mb-1.5 block text-sm font-semibold text-ink2">Goal</span>
        <Segmented label="Goal" value={f.goal} onChange={(v) => set("goal", v)} options={GOALS} />
        <p className="mt-1.5 text-xs text-muted">{GOAL_NOTE[f.goal]}</p></div>
    </div>
  );

  const target: ReactNode = (
    <div className="space-y-4">
      <TargetCard kcal={shown} manual={f.target_override && !errors.target_kcal} />
      <label className="flex min-h-[44px] items-center gap-3 text-sm font-medium">
        <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--brand))]" checked={f.target_override} onChange={(e) => set("target_override", e.target.checked)} />
        Set my own calorie target
      </label>
      {f.target_override && <Field label="Daily target" suffix="kcal" error={show("target_kcal")}><input className={`${inputClass} pr-14`} inputMode="numeric" value={f.target_kcal} onChange={(e) => set("target_kcal", e.target.value)} /></Field>}
      <Field label="Timezone" hint="Your day resets at midnight here.">
        <input className={inputClass} list="zones" value={f.timezone} onChange={(e) => set("timezone", e.target.value)} />
        <datalist id="zones">{[...new Set([f.timezone, ...ZONES])].map((z) => <option key={z} value={z} />)}</datalist>
      </Field>
    </div>
  );

  if (onboarding) {
    const titles = ["About you", "Activity & goal", "Your target"];
    const next = () => { setTouched(true); if (step === 0 && !bodyOk) return; setStep(step + 1); setTouched(false); };
    return (
      <main className="mx-auto min-h-screen max-w-md px-5 pb-32 pt-8">
        <div className="mb-6 flex items-center gap-2" aria-label={`Step ${step + 1} of 3`}>
          {titles.map((t, i) => <span key={t} className={`h-1.5 flex-1 rounded-full transition-colors ${i <= step ? "bg-brand" : "bg-line"}`} />)}
        </div>
        <p className="text-sm font-semibold text-brand">Step {step + 1} of 3</p>
        <h1 className="mb-1 text-2xl font-bold tracking-tight">{step === 0 ? "Let's set up your target" : titles[step]}</h1>
        <p className="mb-5 text-sm text-muted">{["We use this to calculate how much you should eat each day.", "How active are you, and what are you aiming for?", "Here's your personalised plan. You can change it any time."][step]}</p>
        {[about, lifestyle, target][step]}
        {err && <p role="alert" className="mt-4 rounded-xl bg-danger-soft p-3 text-sm font-medium text-danger">{err}</p>}
        <div className="pb-safe fixed inset-x-0 bottom-0 border-t border-line/80 bg-card/90 p-4 backdrop-blur-md">
          <div className="mx-auto flex max-w-md gap-3">
            {step > 0 && <Button variant="secondary" onClick={() => setStep(step - 1)} className="px-6">Back</Button>}
            {step < 2 ? <Button className="flex-1" onClick={next}>Continue</Button> : <Button className="flex-1" loading={busy} onClick={save}>Start tracking</Button>}
          </div>
        </div>
      </main>
    );
  }

  return (
    <div className="px-5 pb-6 pt-5">
      <h1 className="mb-4 text-2xl font-bold tracking-tight">Profile</h1>
      <div className="space-y-4">
        <Card><h2 className="mb-3 text-sm font-bold text-ink2">About you</h2>{about}</Card>
        <Card><h2 className="mb-3 text-sm font-bold text-ink2">Activity & goal</h2>{lifestyle}</Card>
        <Card><h2 className="mb-3 text-sm font-bold text-ink2">Daily target</h2>{target}</Card>
        {err && <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm font-medium text-danger">{err}</p>}
        <Button className="w-full" loading={busy} disabled={!dirty} onClick={save}>{dirty ? "Save changes" : "No changes"}</Button>
        {dataSection}
        {onSignOut && <Button variant="secondary" icon="logout" className="w-full" onClick={onSignOut}>Sign out</Button>}
      </div>
    </div>
  );
}
