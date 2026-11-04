import { describe, expect, it } from "vitest";
import { loopProgress, onceProgress } from "./progress";

describe("progress", () => {
  it("spreads two dots evenly along the route and moves them linearly", () => {
    expect(loopProgress(0, 1000, 0, 2)).toBe(0);
    expect(loopProgress(0, 1000, 1, 2)).toBe(0.5);
    expect(loopProgress(250, 1000, 0, 2)).toBe(0.25);
    expect(loopProgress(750, 1000, 1, 2)).toBe(0.25);
    expect(loopProgress(2250, 1000, 0, 2)).toBe(0.25);
  });

  it("shows a one-shot dot only between its start and end", () => {
    expect(onceProgress(100, 100, 500, 1000)).toBeNull();
    expect(onceProgress(1100, 100, 500, 1000)).toBe(0.5);
    expect(onceProgress(1700, 100, 500, 1000)).toBeNull();
  });
});
