import { describe, expect, it } from "vitest";
import { needsCheck, roundKcal } from "./format";

describe("format", () => {
  it("rounds kcal to nearest 5", () => {
    expect(roundKcal(612)).toBe(610);
    expect(roundKcal(613)).toBe(615);
  });
  it("flags low confidence or estimated items", () => {
    expect(needsCheck({ confidence: 0.4, source: "sgfoodid" })).toBe(true);
    expect(needsCheck({ confidence: 0.9, source: "estimated" })).toBe(true);
    expect(needsCheck({ confidence: 0.9, source: "usda" })).toBe(false);
    expect(needsCheck({ confidence: null, source: "usda" })).toBe(false);
  });
});
