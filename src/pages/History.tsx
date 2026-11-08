import { useEffect, useState } from "react";
import { History as Hist, Profile, api, downloadCsv } from "../lib/api";
import { barLayout, niceMax, roundedTopBar, xLabel, yTicks } from "../lib/chart";
import { addDays, formatDay, roundKcal, todayInTz } from "../lib/format";
import { vsTarget } from "../lib/profile";
import { LimitRow, MacroRow } from "../components";
import { PageHeader } from "../shell";
import { Button, Card, Segmented, Skeleton } from "../ui";

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
              {d.logged && <path d={roundedTopBar(x, top, barW, PT + plotH - top)} fill="var(--series-1)" opacity={hover === null || hover === i ? 1 : 0.5} />}
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
            <line x1={PL} x2={W - PR} y1={y(target)} y2={y(target)} stroke="var(--text-primary)" strokeWidth="1.5" strokeDasharray="0" />
            <text x={W - PR + 4} y={y(target) - 1} fontSize="9" fontWeight="600" fill="var(--text-primary)">Target</text>
            <text x={W - PR + 4} y={y(target) + 9} fontSize="9" fill="var(--text-secondary)">{target}</text>
          </g>
        ) : null}
        {labelValues && data.map((d, i) => d.logged && (
          <g key={d.date} textAnchor="middle" fontSize="9">
            <text x={PL + i * band + band / 2} y={y(d.kcal) - 4} fill="none" {...HALO}>{roundKcal(d.kcal)}</text>
            <text x={PL + i * band + band / 2} y={y(d.kcal) - 4} fill="var(--text-secondary)">{roundKcal(d.kcal)}</text>
          </g>
        ))}
      </svg>
      {h && hover !== null && (
        <div className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-xl border border-line bg-card px-2.5 py-1.5 text-xs shadow-float"
          style={{ left: `clamp(15%, ${((PL + hover * band + band / 2) / W) * 100}%, 85%)` }}>
          <div className="font-bold">{formatDay(h.date)}</div>
          {h.logged ? <div className="num text-ink2">{roundKcal(h.kcal)} kcal · P {Math.round(h.protein_g)} C {Math.round(h.carbs_g)} F {Math.round(h.fat_g)}</div> : <div className="text-muted">Nothing logged</div>}
        </div>
      )}
    </div>
  );
}

export default function History({ profile, onProfile }: { profile: Profile; onProfile: () => void }) {
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
  const cmp = vsTarget(a.kcal ?? 0, t.kcal);

  return (
    <>
      <PageHeader eyebrow={`${formatDay(from)} – ${formatDay(to)}`} title="History" name={profile.display_name} onProfile={onProfile} />
      <div className="space-y-4 px-5">
        <Segmented label="Range" value={n} onChange={setN} options={[{ value: 7, label: "7 days" }, { value: 30, label: "30 days" }]} />
        {err && <p role="alert" className="rounded-2xl bg-danger-soft p-3.5 text-sm font-medium text-danger">{err}</p>}

        {!hist && !err && <div className="space-y-4"><Skeleton className="h-64" /><Skeleton className="h-28" /></div>}

        {hist && (
          <>
            <Card>
              <div className="mb-2 flex items-baseline justify-between">
                <h2 className="text-sm font-bold text-ink2">Calories per day</h2>
                <button className="-mr-2 -mt-2 min-h-[44px] px-2 text-xs font-semibold text-brand" onClick={() => setTable(!table)}>{table ? "Show chart" : "View as table"}</button>
              </div>
              {table ? (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-muted"><tr><th className="pb-1 font-medium">Date</th><th className="font-medium">kcal</th><th className="font-medium">P</th><th className="font-medium">C</th><th className="font-medium">F</th></tr></thead>
                  <tbody className="num">
                    {hist.days.map((d) => (
                      <tr key={d.date} className="border-t border-line">
                        <td className="py-1.5">{formatDay(d.date)}</td><td className="font-semibold">{d.logged ? roundKcal(d.kcal) : "–"}</td>
                        <td>{d.logged ? Math.round(d.protein_g) : "–"}</td><td>{d.logged ? Math.round(d.carbs_g) : "–"}</td><td>{d.logged ? Math.round(d.fat_g) : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <Chart data={hist.days} target={t.kcal ?? null} />}
            </Card>

            {hist.days_logged === 0 ? (
              <Card className="py-8 text-center"><p className="font-semibold">Nothing logged in this range yet</p><p className="mt-1 text-sm text-muted">Log a meal and your trends will appear here.</p></Card>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <Card>
                    <p className="text-xs font-medium text-muted">Daily average</p>
                    <p className="num mt-1 text-2xl font-bold">{roundKcal(a.kcal)}<span className="ml-1 text-sm font-medium text-muted">kcal</span></p>
                    {cmp.text && <p className={`mt-0.5 text-xs font-semibold ${cmp.tone === "ok" ? "text-brand" : "text-warn"}`}>{cmp.text}</p>}
                  </Card>
                  <Card>
                    <p className="text-xs font-medium text-muted">Days logged</p>
                    <p className="num mt-1 text-2xl font-bold">{hist.days_logged}<span className="ml-1 text-sm font-medium text-muted">of {n}</span></p>
                    <p className="mt-0.5 text-xs font-semibold text-ink2">{Math.round((hist.days_logged / n) * 100)}% consistency</p>
                  </Card>
                </div>
                <Card className="space-y-4">
                  <h2 className="text-sm font-bold text-ink2">Average per logged day</h2>
                  <MacroRow label="Protein" value={a.protein_g} target={t.protein_g ?? null} color="bg-protein" />
                  <MacroRow label="Carbs" value={a.carbs_g} target={t.carbs_g ?? null} color="bg-carbs" />
                  <MacroRow label="Fat" value={a.fat_g} target={t.fat_g ?? null} color="bg-fat" />
                  <LimitRow label="Sugar" value={a.sugar_g} cap={t.sugar_g ?? null} unit="g" />
                  <LimitRow label="Sodium" value={a.sodium_mg} cap={t.sodium_mg ?? null} unit="mg" />
                </Card>
              </>
            )}
            <Button variant="secondary" icon="download" className="w-full" loading={exporting} onClick={exportCsv}>Export CSV</Button>
            <p className="pb-2 text-center text-xs text-muted">The target line uses your current target for every day.</p>
          </>
        )}
      </div>
    </>
  );
}
