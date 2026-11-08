import { describe, expect, it } from "vitest";
import { validateProfile, vsTarget } from "./profile";

const ok = { birth_year: "1996", height_cm: "175", weight_kg: "70", target_override: false, target_kcal: "" };

describe("validateProfile", () => {
  it("accepts valid input", () => expect(validateProfile(ok, 2026)).toEqual({}));
  it("flags each out-of-range or empty field", () => {
    const e = validateProfile({ ...ok, birth_year: "2026", height_cm: "5", weight_kg: "" }, 2026);
    expect(Object.keys(e).sort()).toEqual(["birth_year", "height_cm", "weight_kg"]);
    expect(validateProfile({ ...ok, birth_year: "1990.5" }, 2026).birth_year).toBeDefined();
    expect(validateProfile({ ...ok, weight_kg: "abc" }, 2026).weight_kg).toBeDefined();
  });
  it("only checks the manual target when overriding", () => {
    expect(validateProfile({ ...ok, target_kcal: "10" }, 2026)).toEqual({});
    expect(validateProfile({ ...ok, target_override: true, target_kcal: "10" }, 2026).target_kcal).toBeDefined();
    expect(validateProfile({ ...ok, target_override: true, target_kcal: "1800" }, 2026)).toEqual({});
  });
});

describe("vsTarget", () => {
  it("describes under, on and over target", () => {
    expect(vsTarget(1840, 2000)).toEqual({ tone: "ok", text: "8% under target" });
    expect(vsTarget(2000, 2000)).toEqual({ tone: "ok", text: "On target" });
    expect(vsTarget(2100, 2000)).toEqual({ tone: "near", text: "5% over target" });
    expect(vsTarget(2400, 2000)).toEqual({ tone: "over", text: "20% over target" });
    expect(vsTarget(0, 2000).tone).toBe("none");
    expect(vsTarget(1500, null).tone).toBe("none");
  });
});
