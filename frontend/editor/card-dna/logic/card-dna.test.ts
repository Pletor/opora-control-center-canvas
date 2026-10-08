import { describe, expect, it } from "vitest";
import { buildCardDna, timelineForGroup, timelineItems } from "./card-dna";

describe("Card DNA logic", () => {
  it("řadí proces chronologicky a filtruje jej podle skupiny", () => {
    const rows = timelineItems([
      { at: "2026-10-08T12:00:00Z", group: "Kód", label: "commit" },
      { at: "2026-10-08T10:00:00Z", group: "Zadání", label: "revize" },
      { at: "2026-10-08T11:00:00Z", group: "Ověření", label: "test" },
    ]);
    expect(rows.map((row) => row.label)).toEqual(["revize", "test", "commit"]);
    expect(rows.filter((row) => row.group === "Ověření").map((row) => row.label)).toEqual(["test"]);
    expect(timelineForGroup(rows, "Kód").map((row) => row.label)).toEqual(["commit"]);
  });

  it("balík DNA obsahuje zadání, pipeline s poznámkou, důkazy, commit i cestu", () => {
    const dna = buildCardDna({
      title: "GOAL", goal: "Dodat kartu", nonGoals: "Neměnit backend", acceptance: "Test zelený",
      pipeline: [{ name: "Ověření", note: "Spustit test" }], evidence: ["review: OK"],
      realization: { commit: "abcdef123", path: "frontend/editor/card-dna" },
    });
    expect(dna).toContain("Dodat kartu");
    expect(dna).toContain("Ověření — Spustit test");
    expect(dna).toContain("review: OK");
    expect(dna).toContain("abcdef123");
    expect(dna).toContain("frontend/editor/card-dna");
  });
});
