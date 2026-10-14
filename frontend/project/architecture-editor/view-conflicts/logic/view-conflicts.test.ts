import { describe, expect, it } from "vitest";
import { conflictLine, normalizeConflicts } from "./view-conflicts";

describe("view conflicts", () => {
  it("normalizes the view payload", () => {
    expect(normalizeConflicts(undefined)).toEqual([]);
    expect(normalizeConflicts([{ id: "a", name: "Kontakt" }, { id: "a" }, { name: "bez id" }, null, { id: "b", reason: "removed" }])).toEqual([
      { id: "a", name: "Kontakt", reason: "architecture" },
      { id: "b", name: "", reason: "removed" },
    ]);
  });

  it("names the node and the reason", () => {
    expect(conflictLine({ id: "a", name: "Kontakt", reason: "architecture" })).toBe("Uzel „Kontakt“ (a) má v tomto worktree jinou podobu než v architektuře projektu.");
    expect(conflictLine({ id: "b", name: "", reason: "removed" })).toContain("Uzel b byl z architektury projektu odstraněn");
  });
});
