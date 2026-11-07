import { useState } from "react";
import { FoodResult, Meal, MealItem, MealType, Summary, api } from "../lib/api";
import { FoodSearch } from "../components";
import { needsCheck, roundKcal } from "../lib/format";

const TYPES: MealType[] = ["breakfast", "lunch", "snack", "dinner"];

function ItemRow({ item, onSummary, onError }: { item: MealItem; onSummary: (s: Summary) => void; onError: (m: string) => void }) {
  const [grams, setGrams] = useState(item.grams ? String(Math.round(item.grams)) : "");
  const [servings, setServings] = useState(item.servings ? String(+item.servings.toFixed(2)) : "");
  const [swapping, setSwapping] = useState(false);

  async function call(method: string, body?: object) {
    try {
      const r = await api<{ summary: Summary }>(`/api/meal-items/${item.id}`, { method, body: body && JSON.stringify(body) });
      onSummary(r.summary); setSwapping(false);
    } catch (e) { onError((e as Error).message); }
  }
  const num = (s: string) => (s.trim() === "" ? undefined : Number(s));
  const changed = {
    grams: num(grams) !== undefined && Math.round(item.grams ?? -1) !== Math.round(num(grams)!),
    servings: num(servings) !== undefined && +(item.servings ?? -1).toFixed(2) !== num(servings),
  };

  return (
    <li className="space-y-2 py-3">
      <div className="flex justify-between gap-2 text-sm">
        <span>{needsCheck(item) && <span title="Please check this item">⚠ </span>}{item.name}{item.user_edited && <span className="ml-1 text-xs text-gray-500">(edited)</span>}</span>
        <span className="shrink-0 font-medium">{roundKcal(item.kcal)} kcal</span>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-1">g <input inputMode="decimal" className="w-20 rounded border p-1" value={grams} onChange={(e) => setGrams(e.target.value)} /></label>
        <label className="flex items-center gap-1">servings <input inputMode="decimal" className="w-16 rounded border p-1" value={servings} onChange={(e) => setServings(e.target.value)} /></label>
        {(changed.grams || changed.servings) && (
          <button className="rounded bg-green-600 px-2 py-1 text-white"
            onClick={() => call("PATCH", changed.grams ? { grams: num(grams) } : { servings: num(servings) })}>Update</button>
        )}
        <button className="underline" onClick={() => setSwapping(!swapping)}>Swap food</button>
        <button className="text-red-600 underline" onClick={() => call("DELETE")}>Remove</button>
      </div>
      {swapping && <FoodSearch onCancel={() => setSwapping(false)} onPick={(f: FoodResult) => call("PATCH", { food_ref_id: f.id, ...(item.grams ? { grams: item.grams } : {}) })} />}
    </li>
  );
}

export default function EditMeal({ meal, onSummary, onClose }: { meal: Meal; onSummary: (s: Summary) => void; onClose: () => void }) {
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState("");

  async function meta(method: string, path: string, body?: object) {
    try {
      const r = await api<{ summary: Summary }>(path, { method, body: body && JSON.stringify(body) });
      onSummary(r.summary); setErr("");
      return true;
    } catch (e) { setErr((e as Error).message); return false; }
  }

  return (
    <main className="mx-auto max-w-md space-y-4 p-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-xl font-bold">Edit meal</h1>
        <button className="text-sm underline" onClick={onClose}>Done</button>
      </header>
      <select value={meal.meal_type} className="rounded border p-2"
        onChange={(e) => meta("PATCH", `/api/meals/${meal.id}`, { meal_type: e.target.value })}>
        {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <ul className="divide-y">
        {meal.items.map((i) => <ItemRow key={i.id + i.kcal} item={i} onSummary={onSummary} onError={setErr} />)}
      </ul>
      {adding ? (
        <FoodSearch onCancel={() => setAdding(false)}
          onPick={async (f) => { if (await meta("POST", `/api/meals/${meal.id}/items`, { food_ref_id: f.id })) setAdding(false); }} />
      ) : (
        <button className="text-sm underline" onClick={() => setAdding(true)}>+ Add food to this meal</button>
      )}
      {err && <p className="text-sm text-red-600">{err}</p>}
      <button className="w-full rounded border border-red-300 p-2 text-red-600"
        onClick={async () => { if (confirm("Delete this whole meal?") && (await meta("DELETE", `/api/meals/${meal.id}`))) onClose(); }}>
        Delete meal
      </button>
    </main>
  );
}
