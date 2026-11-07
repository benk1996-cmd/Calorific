import { useEffect, useState } from "react";
import { History as Hist, Profile, api, downloadCsv } from "../lib/api";
import { barLayout, niceMax, roundedTopBar, xLabel, yTicks } from "../lib/chart";
import { addDays, roundKcal, todayInTz } from "../lib/format";

const W = 340, H = 200, PL = 38, PR = 40, PT = 14, PB = 24;
const HALO = { stroke: "var(--surface-1)", strokeWidth: 3, strokeLinejoin: "round" } as const;

export function Chart({ data, target }: { data: Hist["days"]; target: number | null }) {
  const [hover, setHover] = useState<number | null>(null);
  const plotW = W - PL - PR, plotH = H - PT - PB;
  const max = niceMax(Math.max(target ?? 0, ...data.map((d) => d.kcal)) * 1.05);
  const y = (v: number) => PT + plotH - (v / max) * plotH;
  const { band, barW, offset } = barLayout(data.length, plotW);
  const labelValues = data.length <= 7;
  const h = hover === null ? null : data[hover];

  return (
    <div className="viz relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Daily calories for the last ${data.length} days${target ? `, target ${target}` : ""}`}>
        {yTicks(max).map((t) => (
          <g key={t}>
            <line x1={PL} x2={W - PR} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
            <text x={PL - 6} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--text-muted)">{Math.round(t)}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = PL + i * band + offset;
          const top = y(d.kcal);
          return (
            <g key={d.date}>
              {d.logged && <path d={roundedTopBar(x, top, barW, PT + plotH - top)} fill="var(--series-1)" opacity={hover === null || hover === i ? 1 : 0.55} />}
              <text x={PL + i * band + band / 2} y={H - 8} textAnchor="middle" fontSize="9" fill="var(--text-muted)">{xLabel(d.date, i, data.length)}</text>
              <rect x={PL + i * band} y={PT} width={band} height={plotH} fill="transparent" tabIndex={0}
                aria-label={`${d.date}: ${d.logged ? `${roundKcal(d.kcal)} kcal` : "nothing logged"}`}
                onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)} onBlur={() => setHover(null)} onTouchStart={() => setHover(i)} />
            </g>
          );
        })}
        <line x1={PL} x2={W - PR} y1={PT + plotH} y2={PT + plotH} stroke="var(--text-muted)" strokeWidth="1" />
        {target ? (
          <g>
            <line x1={PL} x2={W - PR} y1={y(target)} y2={y(target)} stroke="var(--text-primary)" strokeWidth="1.5" />
            <text x={W - PR + 4} y={y(target) - 1} fontSize="9" fontWeight="600" fill="var(--text-primary)">Target</text>
            <text x={W - PR + 4} y={y(target) + 9} fontSize="9" fill="var(--text-secondary)">{target}</text>
          </g>
        ) : null}
        {labelValues && data.map((d, i) => d.logged && (
          <g key={d.date} textAnchor="middle" fontSize="9">
            {/* surface-coloured halo under the text keeps it readable where it crosses the target line */}
            <text x={PL + i * band + band / 2} y={y(d.kcal) - 4} fill="none" {...HALO}>{roundKcal(d.kcal)}</text>
            <text x={PL + i * band + band / 2} y={y(d.kcal) - 4} fill="var(--text-secondary)">{roundKcal(d.kcal)}</text>
          </g>
        ))}
      </svg>
      {h && hover !== null && (
        <div className="pointer-events-none absolute top-0 -translate-x-1/2 rounded border bg-white px-2 py-1 text-xs shadow"
          style={{ left: `${((PL + hover * band + band / 2) / W) * 100}%` }}>
          <div className="font-semibold">{h.date}</div>
          {h.logged ? <div>{roundKcal(h.kcal)} kcal · P {Math.round(h.protein_g)} C {Math.round(h.carbs_g)} F {Math.round(h.fat_g)}</div> : <div>Nothing logged</div>}
        </div>
      )}
    </div>
  );
}

export default function History({ profile }: { profile: Profile }) {
  const [n, setN] = useState<7 | 30>(7);
  const [hist, setHist] = useState<Hist | null>(null);
  const [table, setTable] = useState(false);
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);
  const to = todayInTz(profile.timezone);
  const from = addDays(to, -(n - 1));

  useEffect(() => {
    setHist(null); setErr("");
    api<Hist>(`/api/history?from=${from}&to=${to}`).then(setHist).catch((e) => setErr((e as Error).message));
  }, [from, to]);

  async function exportCsv() {
    setExporting(true); setErr("");
    try { await downloadCsv(from, to); } catch (e) { setErr((e as Error).message); } finally { setExporting(false); }
  }

  const a = hist?.averages ?? {};
  const t = hist?.targets ?? {};
  const tile = "rounded-lg border p-2 text-center";
  return (
    <main className="mx-auto max-w-md space-y-4 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-bold">History</h1>
        <div className="flex overflow-hidden rounded border text-sm" role="group" aria-label="Range">
          {([7, 30] as const).map((d) => (
            <button key={d} onClick={() => setN(d)} aria-pressed={n === d}
              className={`px-3 py-1 ${n === d ? "bg-green-600 text-white" : ""}`}>{d} days</button>
          ))}
        </div>
      </header>

      {err && <p className="text-sm text-red-600">{err}</p>}
      {!hist && !err && <p className="animate-pulse text-sm text-gray-600">Loading…</p>}

      {hist && (
        <>
          <section>
            <h2 className="text-sm font-semibold text-gray-700">Calories per day</h2>
            {table ? (
              <table className="mt-1 w-full text-left text-sm">
                <thead className="text-gray-500"><tr><th>Date</th><th>kcal</th><th>P</th><th>C</th><th>F</th></tr></thead>
                <tbody>
                  {hist.days.map((d) => (
                    <tr key={d.date} className="border-t">
                      <td>{d.date}</td><td>{d.logged ? roundKcal(d.kcal) : "–"}</td>
                      <td>{d.logged ? Math.round(d.protein_g) : "–"}</td><td>{d.logged ? Math.round(d.carbs_g) : "–"}</td><td>{d.logged ? Math.round(d.fat_g) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Chart data={hist.days} target={t.kcal ?? null} />}
            <button className="mt-1 text-xs underline" onClick={() => setTable(!table)}>{table ? "Show chart" : "Show as table"}</button>
          </section>

          <section>
            <h2 className="mb-1 text-sm font-semibold text-gray-700">
              Daily average <span className="font-normal text-gray-500">({hist.days_logged} of {n} days logged)</span>
            </h2>
            {hist.days_logged === 0 ? <p className="text-sm text-gray-500">Nothing logged in this range yet.</p> : (
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div className={tile}><div className="text-xs text-gray-500">Calories</div><b>{roundKcal(a.kcal)}</b></div>
                <div className={tile}><div className="text-xs text-gray-500">Protein</div><b>{Math.round(a.protein_g)} g</b></div>
                <div className={tile}><div className="text-xs text-gray-500">Carbs</div><b>{Math.round(a.carbs_g)} g</b></div>
                <div className={tile}><div className="text-xs text-gray-500">Fat</div><b>{Math.round(a.fat_g)} g</b></div>
                <div className={tile}><div className="text-xs text-gray-500">Sugar</div><b>{Math.round(a.sugar_g)} g</b></div>
                <div className={tile}><div className="text-xs text-gray-500">Sodium</div><b>{Math.round(a.sodium_mg)} mg</b></div>
              </div>
            )}
          </section>
          <button onClick={exportCsv} disabled={exporting} className="w-full rounded-lg border p-3 text-sm font-medium disabled:opacity-50">
            {exporting ? "Preparing…" : `Export CSV (${from} to ${to})`}
          </button>
        </>
      )}
    </main>
  );
}
