import { describe, expect, it } from "vitest";
import { PLAN_STATS } from "./plan-lens-fixture";
import { czechPlural, graphifyText, planLensTitle, statItems } from "./plan-lens-stats";

describe("plan lens stats", () => {
  it("lists the six numbers in order with Czech plurals", () => {
    expect(statItems(PLAN_STATS).map(item => item.text)).toEqual(
      ["2 oblasti", "3 karty", "2 s kódem", "1 v plánu", "0 samostatných", "1 nezařazená"]);
    expect(statItems({ areas: 5, cards: 12, withCode: 1, planned: 0, standalone: 3, unassigned: 7 }).map(item => item.text)).toEqual(
      ["5 oblastí", "12 karet", "1 s kódem", "0 v plánu", "3 samostatné", "7 nezařazených"]);
  });
  it("declines like Czech: 1, 2–4, the rest", () => {
    expect([0, 1, 2, 4, 5, 22].map(value => czechPlural(value, "a", "b", "c"))).toEqual(["c", "a", "b", "b", "c", "c"]);
  });
  it("says whether Graphify could draw the code links", () => {
    expect(graphifyText({ available: true, sourceRevision: "a6a28b0c42394e0a" })).toBe("Graphify ✓ · revize a6a28b0");
    expect(graphifyText({ available: true, sourceRevision: null })).toBe("Graphify ✓");
    expect(graphifyText({ available: false, sourceRevision: null })).toMatch(/nedostupný/);
  });
  it("titles the window for the project or one area", () => {
    expect(planLensTitle(null)).toBe("Lens plánu · celý projekt");
    expect(planLensTitle("area-1", "Přihlášení")).toBe("Lens oblasti · Přihlášení");
    expect(planLensTitle("area-1")).toBe("Lens oblasti · area-1");
  });
});
