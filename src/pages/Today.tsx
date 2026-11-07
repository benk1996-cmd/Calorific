import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AnalyzeResponse, FoodResult, Meal, Profile, Summary, Usage, api } from "../lib/api";
import { Bar, CalorieRing, FoodSearch } from "../components";
import { needsCheck, roundKcal, todayInTz } from "../lib/format";
import { resizeToJpeg } from "../lib/image";
import EditMeal from "./EditMeal";

const UNDO_SECONDS = 10;

export default function Today({ profile, onProfile }: { profile: Profile; onProfile: () => void }) {
  const day = todayInTz(profile.timezone);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [result, setResult] = useState<Meal | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [undoLeft, setUndoLeft] = useState(0);
  const [mode, setMode] = useState<"home" | "text" | "search">("home");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const camera = useRef<HTMLInputElement>(null);
  const upload = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, u] = await Promise.all([api<Summary>(`/api/days/${day}/summary`), api<Usage>("/api/usage")]);
      setSummary(s); setUsage(u);
    } catch (e) { setMsg((e as Error).message); }
  }, [day]);
  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (undoLeft <= 0) return;
    const t = setTimeout(() => setUndoLeft((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [undoLeft]);

  const handle = useCallback((r: AnalyzeResponse) => {
    setUsage(r.usage);
    if (r.meal) setSummary(r.summary);
    if (r.not_food || !r.meal) {
      setResult(null);
      setMsg("That doesn't look like food. Try another photo or describe it.");
    } else {
      setResult(r.meal); setUndoLeft(UNDO_SECONDS);
    }
  }, []);

  async function run(label: string, fn: () => Promise<AnalyzeResponse>) {
    setBusy(label); setMsg(""); setResult(null);
    try { handle(await fn()); setMode("home"); setText(""); }
    catch (e) { setMsg((e as Error).message); }
    finally { setBusy(""); }
  }

  const onFile = (file?: File) => {
    if (!file) return;
    run("Resizing and analysing photo…", async () => {
      const fd = new FormData();
      fd.append("image", await resizeToJpeg(file), "meal.jpg");
      return api<AnalyzeResponse>("/api/analyze/photo", { method: "POST", body: fd });
    });
  };

  const onText = (e: FormEvent) => {
    e.preventDefault();
    run("Analysing…", () => api<AnalyzeResponse>("/api/analyze/text", { method: "POST", body: JSON.stringify({ text }) }));
  };

  async function addManual(f: FoodResult) {
    setBusy("Adding…"); setMsg("");
    try {
      const r = await api<{ meal: Meal; summary: Summary }>("/api/meals/manual", { method: "POST", body: JSON.stringify({ food_ref_id: f.id }) });
      setSummary(r.summary); setMode("home"); setEditingId(r.meal.id); // opens the editor so the portion can be set
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(""); }
  }

  async function undo() {
    if (!result) return;
    try {
      const r = await api<{ summary: Summary }>(`/api/meals/${result.id}`, { method: "DELETE" });
      setSummary(r.summary); setResult(null); setUndoLeft(0); setMsg("Meal removed.");
    } catch (e) { setMsg((e as Error).message); }
  }

  const editing = summary?.meals.find((m) => m.id === editingId);
  if (editingId && editing) {
    return <EditMeal meal={editing} onSummary={(s) => { setSummary(s); setResult(null); }} onClose={() => { setEditingId(null); refresh(); }} />;
  }

  const t = summary?.totals ?? {};
  const tg = summary?.targets ?? {};
  const limitReached = usage !== null && usage.remaining <= 0;
  const total = result?.items.reduce((s, i) => s + i.kcal, 0) ?? 0;
  const btn = "rounded-lg bg-green-600 p-4 font-medium text-white disabled:opacity-50";

  return (
    <main className="mx-auto max-w-md space-y-4 p-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-green-700">Calorific</h1>
        <button className="text-sm underline" onClick={onProfile}>Profile</button>
      </header>

      <CalorieRing eaten={t.kcal ?? 0} target={tg.kcal ?? profile.target_kcal} />
      <p className="text-center text-sm text-gray-600">
        <b>{roundKcal(t.kcal ?? 0)}</b> of {tg.kcal ?? profile.target_kcal} kcal
        {usage && <> · AI logs left today: <b>{usage.remaining}</b></>}
      </p>
      <div className="space-y-2">
        <Bar label="Protein" value={t.protein_g ?? 0} target={tg.protein_g ?? null} unit="g" />
        <Bar label="Carbs" value={t.carbs_g ?? 0} target={tg.carbs_g ?? null} unit="g" />
        <Bar label="Fat" value={t.fat_g ?? 0} target={tg.fat_g ?? null} unit="g" />
        <Bar label="Sugar" value={t.sugar_g ?? 0} target={tg.sugar_g ?? null} unit="g" cap />
        <Bar label="Sodium" value={t.sodium_mg ?? 0} target={tg.sodium_mg ?? null} unit="mg" cap />
      </div>

      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      <input ref={upload} type="file" accept="image/*" hidden onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />

      {mode === "text" ? (
        <form onSubmit={onText} className="space-y-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={300} rows={3} required
            placeholder="e.g. 1 plate chicken rice less rice, kopi siew dai" className="w-full rounded border p-2" />
          <div className="flex gap-2">
            <button className={btn} disabled={!!busy || text.trim().length < 2}>Log it</button>
            <button type="button" className="px-3 underline" onClick={() => setMode("home")}>Cancel</button>
          </div>
        </form>
      ) : mode === "search" ? (
        <FoodSearch onCancel={() => setMode("home")} onPick={addManual} />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <button className={btn} disabled={!!busy || limitReached} onClick={() => camera.current?.click()}>Take photo</button>
            <button className={btn} disabled={!!busy || limitReached} onClick={() => upload.current?.click()}>Upload</button>
            <button className={btn} disabled={!!busy || limitReached} onClick={() => setMode("text")}>Type it</button>
          </div>
          <button className="w-full text-sm underline" onClick={() => setMode("search")}>Search &amp; add food manually</button>
        </>
      )}

      {limitReached && <p className="rounded bg-amber-50 p-3 text-sm text-amber-800">Daily AI limit reached. Use search to add food manually.</p>}
      {busy && <p className="animate-pulse text-sm text-gray-600">{busy}</p>}
      {msg && <p className="rounded bg-gray-100 p-3 text-sm">{msg}</p>}

      {result && (
        <section className="space-y-2 rounded-lg border border-green-300 bg-green-50 p-4">
          <p className="font-semibold">Logged {roundKcal(total)} kcal · {result.meal_type}</p>
          <ul className="space-y-1 text-sm">
            {result.items.map((i) => (
              <li key={i.id} className="flex justify-between">
                <span>{needsCheck(i) && <span title="Please check this item">⚠ </span>}{i.name}</span>
                <span>{roundKcal(i.kcal)} kcal</span>
              </li>
            ))}
          </ul>
          <div className="flex gap-4 text-sm">
            <button onClick={() => setEditingId(result.id)} className="underline">Edit</button>
            {undoLeft > 0 && <button onClick={undo} className="underline">Undo ({undoLeft}s)</button>}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-1 text-sm font-semibold text-gray-700">Today's meals</h2>
        {summary && summary.meals.length === 0 && <p className="text-sm text-gray-500">Nothing logged yet.</p>}
        <ul className="space-y-2">
          {summary?.meals.map((m) => (
            <li key={m.id} className="rounded-lg border p-3 text-sm">
              <div className="flex justify-between font-medium">
                <span className="capitalize">{m.meal_type}</span>
                <span>{roundKcal(m.items.reduce((s, i) => s + i.kcal, 0))} kcal</span>
              </div>
              <ul className="mt-1 text-gray-700">
                {m.items.map((i) => (
                  <li key={i.id} className="flex justify-between">
                    <span>{needsCheck(i) && "⚠ "}{i.name}</span><span>{roundKcal(i.kcal)}</span>
                  </li>
                ))}
              </ul>
              <button className="mt-2 text-xs underline" onClick={() => setEditingId(m.id)}>Edit</button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
