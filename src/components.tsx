import { useEffect, useState } from "react";
import { FoodResult, api } from "./lib/api";
import { Tone, calorieStatus, limitState, pct, ringDash, roundKcal } from "./lib/format";
import { Chip, Icon, Skeleton, inputClass } from "./ui";

const SOURCE: Record<string, { label: string; tone: "brand" | "neutral" | "warn" }> = {
  sgfoodid: { label: "HPB", tone: "brand" }, usda: { label: "USDA", tone: "neutral" }, estimated: { label: "Estimate", tone: "warn" },
};
export const SourceChip = ({ source }: { source: string }) => <Chip tone={SOURCE[source]?.tone ?? "neutral"}>{SOURCE[source]?.label ?? source}</Chip>;

const TONE_TEXT: Record<Tone | "empty" | "none", string> = {
  ok: "text-brand", near: "text-warn", over: "text-warn", empty: "text-muted", none: "text-muted",
};

/** Hero calorie ring: remaining in the centre, eaten/target beside it. Over target is amber, not red. */
export function CalorieHero({ eaten, target }: { eaten: number; target: number | null }) {
  const r = 54, c = 2 * Math.PI * r;
  const status = calorieStatus(eaten, target);
  const over = status.tone === "over";
  const left = target ? Math.round(target - eaten) : null;
  return (
    <div className="flex items-center gap-5">
      <svg viewBox="0 0 132 132" className="h-[132px] w-[132px] shrink-0" role="img"
        aria-label={target ? `${roundKcal(eaten)} of ${target} calories eaten` : "No calorie target set"}>
        <circle cx="66" cy="66" r={r} fill="none" stroke="rgb(var(--line))" strokeWidth="12" />
        {ringDash(eaten, target, c) >= 1 && (
          <circle cx="66" cy="66" r={r} fill="none" stroke={over ? "rgb(var(--warn))" : "rgb(var(--brand))"} strokeWidth="12"
            strokeLinecap="round" strokeDasharray={`${ringDash(eaten, target, c)} ${c}`} transform="rotate(-90 66 66)"
            style={{ transition: "stroke-dasharray .7s cubic-bezier(.2,.8,.2,1)" }} />
        )}
        <text x="66" y="68" textAnchor="middle" className="num fill-ink text-[30px] font-bold">{left === null ? "–" : Math.abs(left)}</text>
        <text x="66" y="87" textAnchor="middle" className="fill-muted text-[11px] font-medium">{left !== null && left < 0 ? "kcal over" : "kcal left"}</text>
      </svg>
      <dl className="min-w-0 flex-1 space-y-2.5">
        <div><dt className="text-xs font-medium text-muted">Eaten</dt><dd className="num text-xl font-bold leading-tight">{roundKcal(eaten)}<span className="ml-1 text-sm font-medium text-muted">kcal</span></dd></div>
        <div><dt className="text-xs font-medium text-muted">Target</dt><dd className="num text-xl font-bold leading-tight">{target ?? "–"}<span className="ml-1 text-sm font-medium text-muted">kcal</span></dd></div>
        <p className={`text-[13px] font-semibold leading-snug ${TONE_TEXT[status.tone]}`}>{status.text}</p>
      </dl>
    </div>
  );
}

export function MacroRow({ label, value, target, color }: { label: string; value: number; target: number | null; color: string }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span className="flex items-center gap-2 font-semibold"><span className={`h-2.5 w-2.5 rounded-full ${color}`} aria-hidden />{label}</span>
        <span className="num text-ink2"><b className="text-ink">{Math.round(value)}</b> / {target ?? "–"} g</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-label={label}
        aria-valuenow={Math.round(value)} aria-valuemax={target ?? undefined}>
        <div className={`h-full rounded-full transition-[width] duration-700 ${color}`} style={{ width: `${pct(value, target)}%` }} />
      </div>
    </div>
  );
}

const LIMIT_STYLE: Record<Tone, { bar: string; chip: "brand" | "warn" | "danger"; text: string }> = {
  ok: { bar: "bg-brand", chip: "brand", text: "Within limit" },
  near: { bar: "bg-warn", chip: "warn", text: "Near limit" },
  over: { bar: "bg-danger", chip: "danger", text: "Over limit" },
};

export function LimitRow({ label, value, cap, unit }: { label: string; value: number; cap: number | null; unit: string }) {
  const s = LIMIT_STYLE[limitState(value, cap)];
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 font-semibold">{label}<Chip tone={s.chip}>{s.text}</Chip></span>
        <span className="num text-ink2"><b className="text-ink">{Math.round(value)}</b> / {cap ?? "–"} {unit}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-label={`${label} against daily limit`}
        aria-valuenow={Math.round(value)} aria-valuemax={cap ?? undefined}>
        <div className={`h-full rounded-full transition-[width] duration-700 ${s.bar}`} style={{ width: `${pct(value, cap)}%` }} />
      </div>
    </div>
  );
}

/** Search the food database (no AI call). Used for manual add and for swapping a food. */
export function FoodSearch({ onPick, autoFocus = true }: { onPick: (f: FoodResult) => void; autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FoodResult[] | null>(null);
  const [err, setErr] = useState("");
  const term = q.trim();

  useEffect(() => {
    if (term.length < 2) { setResults(null); setErr(""); return; }
    setResults(null);
    const t = setTimeout(() => {
      api<{ results: FoodResult[] }>(`/api/foods/search?q=${encodeURIComponent(term)}`)
        .then((r) => { setResults(r.results); setErr(""); })
        .catch((e) => { setErr((e as Error).message); setResults([]); });
    }, 300);
    return () => clearTimeout(t);
  }, [term]);

  return (
    <div>
      <div className="relative">
        <Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" />
        <input autoFocus={autoFocus} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search foods, e.g. chicken rice"
          className={`${inputClass} pl-11`} aria-label="Search foods" type="search" enterKeyHint="search" />
      </div>
      <div className="mt-3 min-h-[120px]" aria-live="polite">
        {err && <p className="text-sm text-danger">{err}</p>}
        {term.length < 2 && !err && <p className="px-1 text-sm text-muted">Type at least 2 letters. Searching never uses an AI call.</p>}
        {term.length >= 2 && results === null && !err && (
          <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
        )}
        {results && results.length === 0 && !err && <p className="px-1 text-sm text-muted">No matches for “{term}”. Try a simpler word.</p>}
        <ul className="divide-y divide-line">
          {results?.map((f) => (
            <li key={f.id}>
              <button type="button" onClick={() => onPick(f)}
                className="flex min-h-[56px] w-full items-center justify-between gap-3 py-2 text-left transition active:bg-line/50">
                <span className="min-w-0">
                  <span className="line-clamp-2 text-[15px] font-medium leading-snug">{f.name}</span>
                  <span className="mt-0.5 flex items-center gap-1.5"><SourceChip source={f.source} />
                    {f.serving_desc && <span className="truncate text-xs text-muted">{f.serving_desc}</span>}</span>
                </span>
                <span className="num shrink-0 text-sm font-semibold text-ink2">
                  {f.per_serving ? `${roundKcal(f.per_serving.kcal)} kcal` : f.per_100g ? `${roundKcal(f.per_100g.kcal)} /100g` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
