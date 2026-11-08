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

/** Add days to a YYYY-MM-DD string (calendar arithmetic, timezone-free). */
export function addDays(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + delta)).toISOString().slice(0, 10);
}

/** "Good morning" etc. from the hour in the user's timezone. */
export function greeting(tz: string, now: Date = new Date()): string {
  const hour = Number(new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", hourCycle: "h23" }).format(now));
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

/** "Sat, 8 Nov" for a YYYY-MM-DD date. */
export function formatDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d)));
}

/** "12:35 pm" for a UTC timestamp, shown in the user's timezone. */
export function mealTime(utcIso: string | undefined, tz: string): string {
  if (!utcIso) return "";
  const d = new Date(utcIso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit", hour12: true }).format(d).toLowerCase();
}

export type Tone = "ok" | "near" | "over";

/** Wording + tone for the calorie headline. Over target is "near/amber", never alarming. */
export function calorieStatus(eaten: number, target: number | null | undefined): { tone: Tone | "empty" | "none"; text: string } {
  if (!target) return { tone: "none", text: "Set a target in your profile" };
  if (eaten <= 0) return { tone: "empty", text: "Nothing logged yet" };
  const left = Math.round(target - eaten);
  if (left < 0) return { tone: "over", text: `${Math.abs(left)} kcal over target` };
  if (left <= target * 0.1) return { tone: "near", text: "Almost at your target" };
  return { tone: "ok", text: eaten < target * 0.5 ? "Plenty of room left" : "On track" };
}

/** Level for a daily cap (sugar, sodium): <80% fine, 80-100% near, >100% over. */
export function limitState(value: number, cap: number | null | undefined): Tone {
  if (!cap || cap <= 0) return "ok";
  const r = value / cap;
  return r > 1 ? "over" : r >= 0.8 ? "near" : "ok";
}
