import { useEffect, useRef, useState } from "react";
import { FoodResult, MealItem, MealType, Summary, api } from "../lib/api";
import { FoodSearch, SourceChip } from "../components";
import { needsCheck, roundKcal } from "../lib/format";
import { useLogging } from "../logging";
import { Button, Chip, Icon, IconButton, Segmented, Sheet } from "../ui";

const TYPES: { value: MealType; label: string }[] = [
  { value: "breakfast", label: "Breakfast" }, { value: "lunch", label: "Lunch" },
  { value: "snack", label: "Snack" }, { value: "dinner", label: "Dinner" },
];

/** Two-tap destructive action: first tap arms it, second confirms (no native dialog). */
function ConfirmButton({ label, confirmLabel, onConfirm, className = "" }: { label: string; confirmLabel: string; onConfirm: () => void; className?: string }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => { if (!armed) return; const t = setTimeout(() => setArmed(false), 3500); return () => clearTimeout(t); }, [armed]);
  return (
    <button onClick={() => (armed ? onConfirm() : setArmed(true))}
      className={`inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-xl px-3 text-sm font-semibold transition ${armed ? "bg-danger text-brand-ink" : "text-danger hover:bg-danger-soft"} ${className}`}>
      <Icon name="trash" className="h-4 w-4" />{armed ? confirmLabel : label}
    </button>
  );
}

type Mode = "servings" | "grams";
const modeFor = (i: MealItem): Mode => ((i.servings && i.servings > 0 && (i.source === "sgfoodid" || !i.grams)) ? "servings" : "grams");

/** − / + stepper with a typed value; saves automatically after a short pause. */
function PortionStepper({ item, onSave }: { item: MealItem; onSave: (body: { servings?: number; grams?: number }) => Promise<void> }) {
  const mode = modeFor(item);
  const step = mode === "servings" ? 0.5 : 10;
  const min = mode === "servings" ? 0.5 : 5;
  const server = mode === "servings" ? item.servings ?? 1 : item.grams ?? 100;
  const [text, setText] = useState(String(+server.toFixed(2)));
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const dirty = useRef(false);

  useEffect(() => { if (!dirty.current) setText(String(+server.toFixed(2))); }, [server]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const schedule = (raw: string) => {
    dirty.current = true;
    setText(raw);
    clearTimeout(timer.current);
    const v = Number(raw);
    if (!raw.trim() || !Number.isFinite(v) || v < min) return;
    timer.current = setTimeout(async () => {
      setState("saving");
      try { await onSave(mode === "servings" ? { servings: v } : { grams: v }); setState("saved"); }
      catch { setState("idle"); }
      finally { dirty.current = false; }
    }, 700);
  };
  const bump = (d: number) => schedule(String(Math.max(min, +((Number(text) || server) + d).toFixed(2))));
  const circle = "flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line bg-card text-ink transition active:bg-line";

  return (
    <div className="flex items-center gap-3">
      <button type="button" className={circle} onClick={() => bump(-step)} aria-label={`Decrease ${mode}`}><Icon name="minus" /></button>
      <label className="flex items-baseline gap-1.5">
        <input value={text} onChange={(e) => schedule(e.target.value)} inputMode="decimal" aria-label={mode === "servings" ? "Servings" : "Grams"}
          className="num h-11 w-20 rounded-xl border border-line bg-card text-center text-lg font-bold focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30" />
        <span className="text-sm font-medium text-muted">{mode === "servings" ? "serving" + (Number(text) === 1 ? "" : "s") : "g"}</span>
      </label>
      <button type="button" className={circle} onClick={() => bump(step)} aria-label={`Increase ${mode}`}><Icon name="plus" /></button>
      <span className="ml-auto text-xs font-medium text-muted" aria-live="polite">{state === "saving" ? "Saving…" : state === "saved" ? "Saved ✓" : ""}</span>
    </div>
  );
}

function ItemCard({ item, onChange, onSummary }: { item: MealItem; onChange: (e: string) => void; onSummary: (s: Summary) => void }) {
  const [swap, setSwap] = useState(false);
  const patch = async (body: object) => {
    try { onSummary((await api<{ summary: Summary }>(`/api/meal-items/${item.id}`, { method: "PATCH", body: JSON.stringify(body) })).summary); }
    catch (e) { onChange((e as Error).message); throw e; }
  };
  const remove = async () => {
    try { onSummary((await api<{ summary: Summary }>(`/api/meal-items/${item.id}`, { method: "DELETE" })).summary); }
    catch (e) { onChange((e as Error).message); }
  };
  return (
    <div className="space-y-3 rounded-2xl border border-line/70 bg-card p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[15px] font-semibold leading-snug">{item.name}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <SourceChip source={item.source} />
            {needsCheck(item) && <Chip tone="warn"><Icon name="alert" className="h-3 w-3" />Check</Chip>}
            {item.user_edited && <Chip>Edited</Chip>}
          </div>
        </div>
        <p className="num shrink-0 text-xl font-bold">{roundKcal(item.kcal)}<span className="ml-1 text-xs font-medium text-muted">kcal</span></p>
      </div>
      <PortionStepper item={item} onSave={patch} />
      <p className="num text-xs text-muted">Protein {Math.round(item.protein_g)} g · Carbs {Math.round(item.carbs_g)} g · Fat {Math.round(item.fat_g)} g</p>
      <div className="flex items-center justify-between border-t border-line pt-2">
        <Button variant="ghost" icon="swap" className="min-h-[44px] px-3 text-sm" onClick={() => setSwap(true)}>Swap food</Button>
        <ConfirmButton label="Remove" confirmLabel="Tap to confirm" onConfirm={remove} />
      </div>
      <Sheet open={swap} onClose={() => setSwap(false)} title="Swap food">
        <FoodSearch onPick={async (f: FoodResult) => { setSwap(false); await patch({ food_ref_id: f.id, ...(item.grams ? { grams: item.grams } : {}) }).catch(() => undefined); }} />
      </Sheet>
    </div>
  );
}

export default function EditMeal() {
  const { summary, editingId, edit, setSummary, refresh } = useLogging();
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const meal = summary?.meals.find((m) => m.id === editingId);

  useEffect(() => { window.scrollTo(0, 0); }, []); // the editor is a new page: start at the top
  useEffect(() => { if (editingId && summary && !meal) edit(null); }, [editingId, summary, meal, edit]); // deleted -> leave
  if (!meal) return null;

  const call = async (method: string, path: string, body?: object) => {
    try { setSummary((await api<{ summary: Summary }>(path, { method, body: body && JSON.stringify(body) })).summary); setErr(""); return true; }
    catch (e) { setErr((e as Error).message); return false; }
  };
  const total = meal.items.reduce((s, i) => s + i.kcal, 0);
  const done = () => { edit(null); void refresh(); };

  return (
    <div className="mx-auto min-h-screen max-w-md pb-32">
      <header className="pt-safe sticky top-0 z-30 flex items-center gap-1 border-b border-line/70 bg-bg/90 px-2 py-2 backdrop-blur-md">
        <IconButton label="Back" icon="back" onClick={done} />
        <h1 className="flex-1 text-lg font-bold">Edit meal</h1>
        <span className="num pr-3 text-sm font-bold">{roundKcal(total)} <span className="font-medium text-muted">kcal</span></span>
      </header>
      <div className="space-y-4 px-5 pt-4">
        <Segmented label="Meal type" value={meal.meal_type} options={TYPES}
          onChange={(v) => void call("PATCH", `/api/meals/${meal.id}`, { meal_type: v })} />
        {err && <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm font-medium text-danger">{err}</p>}
        {meal.items.map((i) => <ItemCard key={i.id} item={i} onChange={setErr} onSummary={(s) => { setSummary(s); setErr(""); }} />)}
        <Button variant="secondary" icon="plus" className="w-full" onClick={() => setAdding(true)}>Add food to this meal</Button>
        <div className="flex justify-center pt-2">
          <ConfirmButton label="Delete whole meal" confirmLabel="Tap again to delete" onConfirm={() => void call("DELETE", `/api/meals/${meal.id}`)} />
        </div>
      </div>
      <div className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-line/80 bg-card/90 p-4 backdrop-blur-md">
        <Button className="mx-auto flex w-full max-w-md" onClick={done}>Done</Button>
      </div>
      <Sheet open={adding} onClose={() => setAdding(false)} title="Add food">
        <FoodSearch onPick={async (f) => { setAdding(false); await call("POST", `/api/meals/${meal.id}/items`, { food_ref_id: f.id }); }} />
      </Sheet>
    </div>
  );
}
