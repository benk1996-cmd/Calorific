import type { MealItem } from "./api";

export const roundKcal = (k: number) => 5 * Math.round(k / 5);
export const needsCheck = (i: Pick<MealItem, "confidence" | "source">) =>
  i.source === "estimated" || (i.confidence ?? 1) < 0.5;
