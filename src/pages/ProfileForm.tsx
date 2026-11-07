import { FormEvent, useState } from "react";
import { ActivityLevel, Goal, Profile, api } from "../lib/api";
import { previewKcal } from "../lib/targets";

const ACTIVITY: [ActivityLevel, string][] = [
  ["sedentary", "Sedentary (desk job, little exercise)"],
  ["light", "Light (1–3 days/week)"],
  ["moderate", "Moderate (3–5 days/week)"],
  ["active", "Active (6–7 days/week)"],
  ["very_active", "Very active (physical job + training)"],
];
const GOALS: [Goal, string][] = [["lose", "Lose weight (−500 kcal)"], ["maintain", "Maintain"], ["gain", "Gain (+300 kcal)"]];

export default function ProfileForm({ initial, onSaved, onboarding }: {
  initial: Profile | null; onSaved: (p: Profile) => void; onboarding?: boolean;
}) {
  const [f, setF] = useState({
    display_name: initial?.display_name ?? "",
    sex: initial?.sex ?? "male",
    birth_year: initial?.birth_year ?? 1995,
    height_cm: initial?.height_cm ?? 170,
    weight_kg: initial?.weight_kg ?? 65,
    activity_level: initial?.activity_level ?? "light",
    goal: initial?.goal ?? "maintain",
    timezone: initial?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "Asia/Singapore",
    target_override: initial?.target_override ?? false,
    target_kcal: initial?.target_kcal ?? 2000,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));
  const preview = previewKcal({ sex: f.sex, birthYear: f.birth_year, heightCm: f.height_cm,
    weightKg: f.weight_kg, activity: f.activity_level, goal: f.goal });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const res = await api<{ profile: Profile }>("/api/profile", {
        method: "PUT",
        body: JSON.stringify({ ...f, display_name: f.display_name || null,
          target_kcal: f.target_override ? f.target_kcal : null }),
      });
      onSaved(res.profile);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  const input = "w-full rounded border p-2";
  const label = "block text-sm font-medium text-gray-700";
  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-4 p-6">
      <h1 className="text-xl font-bold">{onboarding ? "Welcome — set up your profile" : "Profile & target"}</h1>
      <div><label className={label}>Name</label>
        <input className={input} value={f.display_name} onChange={(e) => set("display_name", e.target.value)} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className={label}>Sex</label>
          <select className={input} value={f.sex} onChange={(e) => set("sex", e.target.value as "male" | "female")}>
            <option value="male">Male</option><option value="female">Female</option></select></div>
        <div><label className={label}>Birth year</label>
          <input type="number" className={input} value={f.birth_year} onChange={(e) => set("birth_year", +e.target.value)} /></div>
        <div><label className={label}>Height (cm)</label>
          <input type="number" className={input} value={f.height_cm} onChange={(e) => set("height_cm", +e.target.value)} /></div>
        <div><label className={label}>Weight (kg)</label>
          <input type="number" step="0.1" className={input} value={f.weight_kg} onChange={(e) => set("weight_kg", +e.target.value)} /></div>
      </div>
      <div><label className={label}>Activity</label>
        <select className={input} value={f.activity_level} onChange={(e) => set("activity_level", e.target.value as ActivityLevel)}>
          {ACTIVITY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      <div><label className={label}>Goal</label>
        <select className={input} value={f.goal} onChange={(e) => set("goal", e.target.value as Goal)}>
          {GOALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      <div><label className={label}>Timezone</label>
        <input className={input} value={f.timezone} onChange={(e) => set("timezone", e.target.value)} /></div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={f.target_override} onChange={(e) => set("target_override", e.target.checked)} />
        Set target manually</label>
      {f.target_override ? (
        <div><label className={label}>Daily target (kcal)</label>
          <input type="number" className={input} value={f.target_kcal} onChange={(e) => set("target_kcal", +e.target.value)} /></div>
      ) : (
        <p className="rounded bg-green-50 p-3 text-sm text-green-800">Estimated daily target: <b>{preview} kcal</b></p>
      )}
      {err && <p className="text-sm text-red-600">{err}</p>}
      <button disabled={busy} className="w-full rounded bg-green-600 p-3 font-medium text-white disabled:opacity-60">
        {busy ? "Saving…" : "Save"}</button>
    </form>
  );
}
