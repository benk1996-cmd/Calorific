import type { MealItem } from "./api";

export const roundKcal = (k: number) => 5 * Math.round(k / 5);
export const needsCheck = (i: Pick<MealItem, "confidence" | "source">) =>
  i.source === "estimated" || (i.confidence ?? 1) < 0.5;

/** Today's date (YYYY-MM-DD) in the user's timezone; midnight there is the day boundary. */
export function todayInTz(tz: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

/** Percent of target, clamped 0..100 for bar widths. */
export function pct(value: number, target: number | null | undefined): number {
  if (!target || target <= 0) return 0;
  return Math.max(0, Math.min(100, (value / target) * 100));
}

export const isOver = (value: number, target: number | null | undefined) => !!target && value > target;

/** SVG ring: dash length for the eaten fraction of a circle with the given circumference. */
export function ringDash(eaten: number, target: number | null | undefined, circumference: number): number {
  return (pct(eaten, target) / 100) * circumference;
}
