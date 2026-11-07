import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AnalyzeResponse, Meal, Profile, Summary, Usage, api } from "../lib/api";
import { needsCheck, roundKcal } from "../lib/format";
import { resizeToJpeg } from "../lib/image";

const UNDO_SECONDS = 10;

export default function Today({ profile, onProfile }: { profile: Profile; onProfile: () => void }) {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [result, setResult] = useState<Meal | null>(null);
  const [undoLeft, setUndoLeft] = useState(0);
  const [mode, setMode] = useState<"home" | "text">("home");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const camera = useRef<HTMLInputElement>(null);
  const upload = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<Usage>("/api/usage").then(setUsage).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (undoLeft <= 0) return;
    const t = setTimeout(() => setUndoLeft((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [undoLeft]);

  const handle = useCallback((r: AnalyzeResponse) => {
    setUsage(r.usage);
    setSummary(r.summary);
    if (r.not_food || !r.meal) {
      setResult(null);
      setMsg("That doesn't look like food. Try another photo or describe it.");
    } else {
      setResult(r.meal);
      setUndoLeft(UNDO_SECONDS);
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
      const blob = await resizeToJpeg(file);
      const fd = new FormData();
      fd.append("image", blob, "meal.jpg");
      return api<AnalyzeResponse>("/api/analyze/photo", { method: "POST", body: fd });
    });
  };

  const onText = (e: FormEvent) => {
    e.preventDefault();
    run("Analysing…", () => api<AnalyzeResponse>("/api/analyze/text", { method: "POST", body: JSON.stringify({ text }) }));
  };

  async function undo() {
    if (!result) return;
    try {
      const r = await api<{ summary: Summary }>(`/api/meals/${result.id}`, { method: "DELETE" });
      setSummary(r.summary); setResult(null); setUndoLeft(0); setMsg("Meal removed.");
    } catch (e) { setMsg((e as Error).message); }
  }

  const eaten = summary?.totals.kcal ?? 0;
  const limitReached = usage !== null && usage.remaining <= 0;
  const total = result?.items.reduce((s, i) => s + i.kcal, 0) ?? 0;
  const btn = "rounded-lg bg-green-600 p-4 font-medium text-white disabled:opacity-50";

  return (
    <main className="mx-auto max-w-md space-y-4 p-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-green-700">Calorific</h1>
        <button className="text-sm underline" onClick={onProfile}>Profile</button>
      </header>
      <p className="text-sm text-gray-600">
        Target <b>{profile.target_kcal} kcal</b>
        {summary && <> · eaten <b>{roundKcal(eaten)}</b></>}
        {usage && <> · AI logs left today: <b>{usage.remaining}</b></>}
      </p>

      <input ref={camera} type="file" accept="image/*" capture="environment" hidden
        onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      <input ref={upload} type="file" accept="image/*" hidden
        onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />

      {mode === "home" ? (
        <div className="grid grid-cols-3 gap-2">
          <button className={btn} disabled={!!busy || limitReached} onClick={() => camera.current?.click()}>Take photo</button>
          <button className={btn} disabled={!!busy || limitReached} onClick={() => upload.current?.click()}>Upload</button>
          <button className={btn} disabled={!!busy || limitReached} onClick={() => setMode("text")}>Type it</button>
        </div>
      ) : (
        <form onSubmit={onText} className="space-y-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={300} rows={3} required
            placeholder="e.g. 1 plate chicken rice less rice, kopi siew dai" className="w-full rounded border p-2" />
          <div className="flex gap-2">
            <button className={btn} disabled={!!busy || text.trim().length < 2}>Log it</button>
            <button type="button" className="px-3 underline" onClick={() => setMode("home")}>Cancel</button>
          </div>
        </form>
      )}

      {limitReached && <p className="rounded bg-amber-50 p-3 text-sm text-amber-800">Daily AI limit reached. Use search to add food manually.</p>}
      {busy && <p className="animate-pulse text-sm text-gray-600">{busy}</p>}
      {msg && <p className="rounded bg-gray-100 p-3 text-sm">{msg}</p>}

      {result && (
        <section className="space-y-2 rounded-lg border p-4">
          <p className="font-semibold">Logged {roundKcal(total)} kcal · {result.meal_type}</p>
          <ul className="space-y-1 text-sm">
            {result.items.map((i) => (
              <li key={i.id} className="flex justify-between">
                <span>{needsCheck(i) && <span title="Please check this item">⚠ </span>}{i.name}</span>
                <span>{roundKcal(i.kcal)} kcal</span>
              </li>
            ))}
          </ul>
          {undoLeft > 0 && <button onClick={undo} className="text-sm underline">Undo ({undoLeft}s)</button>}
        </section>
      )}
    </main>
  );
}
