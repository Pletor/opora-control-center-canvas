import { describe, expect, it } from "vitest";
import { capProblem, capsChanges, parseCaps } from "./heart-caps";

const raw = { per_hour: 6, per_project: 2, rate_sleep_seconds: 300, bounds: { per_hour: [1, 60], per_project: [1, 4], rate_sleep_seconds: [60, 3600] } };

describe("heart-caps", () => {
  it("přečte hodnoty a meze", () => {
    const caps = parseCaps(raw);
    expect(caps.values.per_hour).toBe(6);
    expect(caps.bounds.per_project).toEqual([1, 4]);
  });
  it("vadná odpověď je chyba", () => {
    expect(() => parseCaps({ error: "nelze" })).toThrow("nelze");
  });
  it("PUT nese jen změněné klíče", () => {
    const caps = parseCaps(raw);
    expect(capsChanges(caps, { ...caps.values, per_hour: 12 })).toEqual({ per_hour: 12 });
  });
  it("hlídá meze", () => {
    const caps = parseCaps(raw);
    expect(capProblem(caps, "per_hour", 61)).not.toBeNull();
    expect(capProblem(caps, "per_hour", 12)).toBeNull();
    expect(capProblem(caps, "per_hour", NaN)).not.toBeNull();
  });
});
