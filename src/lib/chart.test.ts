import { describe, expect, it } from "vitest";
import { barLayout, niceMax, roundedTopBar, xLabel, yTicks } from "./chart";

describe("chart geometry", () => {
  it("niceMax picks the tightest clean maximum", () => {
    expect(niceMax(1830)).toBe(2000);
    expect(niceMax(2000)).toBe(2000);
    expect(niceMax(2730)).toBe(3000);
    expect(niceMax(0)).toBe(25);
    expect(niceMax(26)).toBe(30);
  });
  it("yTicks spans 0..max at clean steps", () => {
    expect(yTicks(3000)).toEqual([0, 1000, 2000, 3000]);
    expect(yTicks(2000)).toEqual([0, 500, 1000, 1500, 2000]);
    expect(yTicks(100)).toEqual([0, 25, 50, 75, 100]);
  });
  it("roundedTopBar has rounded top, square base, and handles zero/tiny heights", () => {
    expect(roundedTopBar(0, 10, 20, 30)).toContain("Q0,10 4,10");
    expect(roundedTopBar(0, 10, 20, 0)).toBe("");
    expect(roundedTopBar(0, 10, 20, 2)).toContain("V12"); // radius clamped to height
  });
  it("barLayout caps bar width at 24px and centres", () => {
    const wide = barLayout(7, 700);
    expect(wide.barW).toBe(24);
    expect(wide.offset).toBe((100 - 24) / 2);
    expect(barLayout(30, 300).barW).toBeCloseTo(7);
  });
  it("xLabel: weekdays for a week, sparse d/m for a month", () => {
    expect(xLabel("2026-11-07", 6, 7)).toBe("Sat");
    expect(xLabel("2026-11-01", 0, 30)).toBe("1/11");
    expect(xLabel("2026-11-02", 1, 30)).toBe("");
    expect(xLabel("2026-11-30", 29, 30)).toBe("30/11");
  });
});
