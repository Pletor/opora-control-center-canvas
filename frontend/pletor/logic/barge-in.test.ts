import { describe, expect, it } from "vitest";
import { BARGE_HOLD_MS, createBargeDetector } from "./barge-in";

describe("createBargeDetector", () => {
  it("odpoví až po souvislé hlasitosti nad prahem", () => {
    const hears = createBargeDetector();
    expect(hears(0.5, 0, 1000)).toBe(false);
    expect(hears(0.5, 0, 1000 + BARGE_HOLD_MS - 1)).toBe(false);
    expect(hears(0.5, 0, 1000 + BARGE_HOLD_MS)).toBe(true);
  });
  it("krátký šum odpočet zruší", () => {
    const hears = createBargeDetector();
    hears(0.5, 0, 0);
    expect(hears(0.1, 0, 200)).toBe(false);
    expect(hears(0.5, 0, 300)).toBe(false);
    expect(hears(0.5, 0, 300 + BARGE_HOLD_MS)).toBe(true);
  });
  it("vlastní hlas z reproduktorů za řeč nebere", () => {
    const hears = createBargeDetector();
    hears(0.4, 0.8, 0);
    expect(hears(0.4, 0.8, 5000)).toBe(false);
  });
});
