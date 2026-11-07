import { describe, expect, it } from "vitest";
import { attempts, fitDimensions } from "./image";

describe("fitDimensions", () => {
  it("scales a 12MP landscape photo to 1280 on the long side", () =>
    expect(fitDimensions(4032, 3024)).toEqual({ width: 1280, height: 960 }));
  it("scales portrait", () => expect(fitDimensions(3024, 4032)).toEqual({ width: 960, height: 1280 }));
  it("never upscales", () => expect(fitDimensions(800, 600)).toEqual({ width: 800, height: 600 }));
  it("keeps at least 1px", () => expect(fitDimensions(10000, 1).height).toBe(1));
});

describe("attempts", () => {
  it("starts at full quality and gets progressively smaller", () => {
    const a = attempts();
    expect(a[0]).toEqual({ quality: 0.85, scale: 1 });
    expect(a[a.length - 1]).toEqual({ quality: 0.55, scale: 0.6 });
    expect(a).toHaveLength(9);
  });
});
