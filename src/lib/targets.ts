// Client-side preview of the server's target calculation (server remains authoritative).
export const ACTIVITY_FACTORS = {
  sedentary: 1.2, light: 1.375, moderate: 1.55, active: 1.725, very_active: 1.9,
} as const;
export const GOAL_ADJUSTMENTS = { lose: -500, maintain: 0, gain: 300 } as const;
export const MIN_KCAL = 1200;

export interface TargetInput {
  sex: "male" | "female";
  birthYear: number;
  heightCm: number;
  weightKg: number;
  activity: keyof typeof ACTIVITY_FACTORS;
  goal: keyof typeof GOAL_ADJUSTMENTS;
  year?: number;
}

export function previewKcal(i: TargetInput): number {
  const age = (i.year ?? new Date().getFullYear()) - i.birthYear;
  const bmr = 10 * i.weightKg + 6.25 * i.heightCm - 5 * age + (i.sex === "male" ? 5 : -161);
  return Math.round(Math.max(MIN_KCAL, bmr * ACTIVITY_FACTORS[i.activity] + GOAL_ADJUSTMENTS[i.goal]));
}

/** Macro gram targets for a calorie target (30% protein / 40% carbs / 30% fat), matching the server. */
export function previewMacros(kcal: number): { protein: number; carbs: number; fat: number } {
  return { protein: Math.round((kcal * 0.3) / 4), carbs: Math.round((kcal * 0.4) / 4), fat: Math.round((kcal * 0.3) / 9) };
}
