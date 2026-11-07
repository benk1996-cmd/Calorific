// Pure chart geometry (unit-tested); the SVG itself lives in components/History.

/** Clean tick step (1/2/2.5/5 x 10^n) giving roughly four ticks across [0, v]. */
export function niceStep(v: number): number {
  if (v <= 0) return 25;
  const rough = v / 4;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * pow >= rough) return m * pow;
  return 10 * pow;
}

/** Axis maximum: the smallest multiple of the tick step that is >= v. */
export function niceMax(v: number): number {
  const step = niceStep(v);
  return Math.max(step, Math.ceil(v / step) * step);
}

/** Axis ticks from 0 to max (inclusive) at the clean step for max. */
export function yTicks(max: number): number[] {
  const step = niceStep(max);
  return Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
}

/** Column path: square at the baseline, 4px rounded data-end (top). */
export function roundedTopBar(x: number, y: number, w: number, h: number, r = 4): string {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  if (h <= 0) return "";
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

/** Column band geometry: bars capped at 24px, centred in their band. */
export function barLayout(n: number, plotW: number, cap = 24): { band: number; barW: number; offset: number } {
  const band = plotW / Math.max(1, n);
  const barW = Math.min(cap, band * 0.7);
  return { band, barW, offset: (band - barW) / 2 };
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** X label for a YYYY-MM-DD date: weekday for short ranges, d/m every few days for long ones. */
export function xLabel(iso: string, index: number, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (n <= 7) return WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return index % 5 === 0 || index === n - 1 ? `${d}/${m}` : "";
}
