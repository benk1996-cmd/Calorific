import { describe, expect, it } from "vitest";
import { addDays, calorieStatus, formatDay, greeting, isOver, limitState, mealTime, needsCheck, pct, ringDash, roundKcal, todayInTz } from "./format";

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

describe("day + progress helpers", () => {
  it("uses the user's timezone for the date (SGT midnight boundary)", () => {
    expect(todayInTz("Asia/Singapore", new Date("2026-11-07T15:59:00Z"))).toBe("2026-11-07");
    expect(todayInTz("Asia/Singapore", new Date("2026-11-07T16:01:00Z"))).toBe("2026-11-08");
    expect(todayInTz("America/New_York", new Date("2026-11-07T16:01:00Z"))).toBe("2026-11-07");
  });
  it("clamps percentages and handles missing targets", () => {
    expect(pct(50, 200)).toBe(25);
    expect(pct(500, 200)).toBe(100);
    expect(pct(-5, 200)).toBe(0);
    expect(pct(5, null)).toBe(0);
    expect(pct(5, 0)).toBe(0);
  });
  it("detects over target", () => {
    expect(isOver(2100, 2000)).toBe(true);
    expect(isOver(2000, 2000)).toBe(false);
    expect(isOver(5, null)).toBe(false);
  });
  it("computes ring dash length", () => {
    expect(ringDash(1000, 2000, 100)).toBe(50);
    expect(ringDash(4000, 2000, 100)).toBe(100);
  });
});

describe("addDays", () => {
  it("crosses month and year boundaries", () => {
    expect(addDays("2026-11-07", -6)).toBe("2026-11-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });
});

describe("greeting / dates", () => {
  it("greets by the hour in the user's timezone", () => {
    expect(greeting("Asia/Singapore", new Date("2026-11-07T23:00:00Z"))).toBe("Good morning"); // 07:00 SGT
    expect(greeting("Asia/Singapore", new Date("2026-11-07T06:00:00Z"))).toBe("Good afternoon"); // 14:00
    expect(greeting("Asia/Singapore", new Date("2026-11-07T12:00:00Z"))).toBe("Good evening"); // 20:00
    expect(greeting("Asia/Singapore", new Date("2026-11-07T16:30:00Z"))).toBe("Good morning"); // 00:30 next day
  });
  it("formats a day and a meal time", () => {
    expect(formatDay("2026-11-08")).toMatch(/Sun.*8.*Nov/);
    expect(mealTime("2026-11-07T04:35:00Z", "Asia/Singapore")).toBe("12:35 pm");
    expect(mealTime(undefined, "Asia/Singapore")).toBe("");
    expect(mealTime("garbage", "Asia/Singapore")).toBe("");
  });
});

describe("calorieStatus", () => {
  it("handles every state", () => {
    expect(calorieStatus(0, null).tone).toBe("none");
    expect(calorieStatus(0, 2000)).toEqual({ tone: "empty", text: "Nothing logged yet" });
    expect(calorieStatus(600, 2000)).toEqual({ tone: "ok", text: "Plenty of room left" });
    expect(calorieStatus(1200, 2000)).toEqual({ tone: "ok", text: "On track" });
    expect(calorieStatus(1850, 2000)).toEqual({ tone: "near", text: "Almost at your target" });
    expect(calorieStatus(2150, 2000)).toEqual({ tone: "over", text: "150 kcal over target" });
  });
});

describe("limitState", () => {
  it("is fine, near, then over", () => {
    expect(limitState(30, 50)).toBe("ok");
    expect(limitState(40, 50)).toBe("near");
    expect(limitState(50, 50)).toBe("near");
    expect(limitState(51, 50)).toBe("over");
    expect(limitState(5, null)).toBe("ok");
  });
});
