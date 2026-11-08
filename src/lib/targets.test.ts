import { describe, expect, it } from "vitest";
import { previewKcal, previewMacros } from "./targets";

const base = { sex: "male", birthYear: 1996, heightCm: 175, weightKg: 70, activity: "moderate", goal: "maintain", year: 2026 } as const;

describe("previewKcal", () => {
  it("matches Mifflin-St Jeor x activity", () => expect(previewKcal(base)).toBe(Math.round(1648.75 * 1.55)));
  it("applies goal adjustment", () => expect(previewKcal({ ...base, goal: "lose" })).toBe(Math.round(1648.75 * 1.55 - 500)));
  it("applies floor", () =>
    expect(previewKcal({ ...base, sex: "female", heightCm: 150, weightKg: 40, activity: "sedentary", goal: "lose" })).toBe(1200));
});

describe("previewMacros", () => {
  it("splits 30/40/30 like the server", () => expect(previewMacros(2000)).toEqual({ protein: 150, carbs: 200, fat: 67 }));
});
