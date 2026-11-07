import { useEffect, useState } from "react";
import { FoodResult, api } from "./lib/api";
import { isOver, pct, ringDash, roundKcal } from "./lib/format";

const SRC: Record<string, string> = { sgfoodid: "HPB", usda: "USDA", estimated: "est." };

export function FoodSearch({ onPick, onCancel }: { onPick: (f: FoodResult) => void; onCancel: () => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FoodResult[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api<{ results: FoodResult[] }>(`/api/foods/search?q=${encodeURIComponent(q.trim())}`)
        .then((r) => { setResults(r.results); setErr(""); })
        .catch((e) => setErr((e as Error).message));
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="space-y-2 rounded-lg border p-3">
      <div className="flex gap-2">
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search foods…" className="w-full rounded border p-2" />
        <button type="button" className="px-2 text-sm underline" onClick={onCancel}>Cancel</button>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {q.trim().length >= 2 && !err && results.length === 0 && <p className="text-sm text-gray-500">No matches.</p>}
      <ul className="max-h-64 divide-y overflow-y-auto text-sm">
        {results.map((f) => (
          <li key={f.id}>
            <button type="button" onClick={() => onPick(f)} className="flex w-full items-start justify-between gap-2 py-2 text-left">
              <span>{f.name}<span className="ml-1 rounded bg-gray-100 px-1 text-xs text-gray-600">{SRC[f.source]}</span></span>
              <span className="shrink-0 text-gray-600">
                {f.per_serving ? `${roundKcal(f.per_serving.kcal)} kcal${f.serving_desc ? ` / ${f.serving_desc}` : "/serving"}`
                  : f.per_100g ? `${roundKcal(f.per_100g.kcal)} kcal/100g` : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CalorieRing({ eaten, target }: { eaten: number; target: number | null }) {
  const r = 52, c = 2 * Math.PI * r;
  const over = isOver(eaten, target);
  const left = target ? Math.round(target - eaten) : null;
  return (
    <div className="flex justify-center">
      <svg viewBox="0 0 120 120" className="h-40 w-40" role="img" aria-label="Calories eaten versus target">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#e5e7eb" strokeWidth="10" />
        <circle cx="60" cy="60" r={r} fill="none" stroke={over ? "#dc2626" : "#16a34a"} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${ringDash(eaten, target, c)} ${c}`} transform="rotate(-90 60 60)" />
        <text x="60" y="58" textAnchor="middle" className="fill-current text-[20px] font-bold">{left === null ? "–" : Math.abs(left)}</text>
        <text x="60" y="74" textAnchor="middle" className="fill-gray-500 text-[9px]">{left !== null && left < 0 ? "kcal over" : "kcal left"}</text>
      </svg>
    </div>
  );
}

export function Bar({ label, value, target, unit, cap }: { label: string; value: number; target: number | null; unit: string; cap?: boolean }) {
  const over = isOver(value, target);
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-600">
        <span>{label}</span>
        <span className={over && cap ? "font-semibold text-red-600" : ""}>
          {Math.round(value)} / {target ?? "–"} {unit}{cap ? " max" : ""}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-gray-200">
        <div className={`h-full ${over ? (cap ? "bg-red-500" : "bg-amber-500") : "bg-green-500"}`} style={{ width: `${pct(value, target)}%` }} />
      </div>
    </div>
  );
}
