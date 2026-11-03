import { expect, it } from "vitest";
import { contrastLevel, contrastRatio, parseColor, toHex } from "./color-contrast";

it("parses hex, rgb and hsl and gives up on colors it cannot convert", () => {
  expect(parseColor("#fff")).toEqual([255, 255, 255]);
  expect(parseColor("#2A1F1Aff")).toEqual([42, 31, 26]);
  expect(parseColor("rgb(214 88 42)")).toEqual([214, 88, 42]);
  expect(parseColor("rgba(0, 0, 0, 0.08)")).toEqual([0, 0, 0]);
  expect(parseColor("rgb(100% 0% 0%)")).toEqual([255, 0, 0]);
  expect(parseColor("hsl(0 100% 50%)")).toEqual([255, 0, 0]);
  expect(parseColor("hsl(120, 100%, 25%)")).toEqual([0, 128, 0]);
  expect(parseColor("oklch(0.7 0.1 200)")).toBeNull();
  expect(parseColor("{ink}")).toBeNull();
  expect(toHex([214, 88, 42])).toBe("#d6582a");
});

it("computes the WCAG ratio and level", () => {
  expect(contrastRatio("#000", "#fff")).toBeCloseTo(21, 5);
  expect(contrastRatio("#fff", "#fff")).toBeCloseTo(1, 5);
  expect(contrastRatio("#777", "#fff")!).toBeCloseTo(4.48, 2);
  expect(contrastRatio("oklch(0.5 0 0)", "#fff")).toBeNull();
  expect(contrastLevel(21)).toBe("AAA");
  expect(contrastLevel(5)).toBe("AA");
  expect(contrastLevel(4.48)).toBe("fail");
});
