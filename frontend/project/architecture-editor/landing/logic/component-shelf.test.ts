import { describe, expect, it } from "vitest";
import { brainOf, BRAIN_SHELF, parseBrainArtifacts, parseHarness, shelfCount, shelfId, shortVersion, type ShelfData } from "./component-shelf";

const entry = (id: string) => BRAIN_SHELF.find((item) => item.id === id)!;
const loading: ShelfData = { brain: { data: null, error: "" }, harness: { data: null, error: "" } };

describe("BRAIN_SHELF", () => {
  it("má karty Skills, Tools a Harness z image6.png, každou s jedinečným ID", () => {
    expect(BRAIN_SHELF.map((item) => item.label)).toEqual(["Skills", "Tools", "Harness"]);
    expect(BRAIN_SHELF.map(shelfId)).toEqual(["opora:library:skills", "opora:library:tools", "opora:library:harness"]);
  });
});

describe("zdroje Brainu a Harness", () => {
  const brain = parseBrainArtifacts({ artifacts: [
    { id: "opora:brain:skill:heart", kind: "skill", plugin: "opora-heart", name: "heart", active: { version: "41a4755c3277dee6", status: "active" } },
    { id: "opora:brain:skill:x", kind: "skill", plugin: "p", name: "x", active: null },
    { id: "", kind: "tool" }, "nesmysl",
  ] });
  it("seznam artefaktů vynechá nepoužitelné řádky a zachová aktivní verzi", () => {
    expect(brain).toHaveLength(2);
    expect(brain[0].active).toEqual({ version: "41a4755c3277dee6", status: "active" });
    expect(brainOf(brain, "tool")).toEqual([]);
    expect(shortVersion("41a4755c3277dee6")).toBe("41a4755c3277");
    expect(parseBrainArtifacts(null)).toEqual([]);
  });
  it("přehled Harness přečte počty a čtení", () => {
    const overview = parseHarness({ scannedReceipts: 3, invalidReceipts: 1, conflictingReads: 0, limited: false,
      observations: [{ observation: { resource: { id: "react-docs" }, library: "/facebook/react", fetchedAt: "2026-11-03T10:00:00Z", durationMs: 120 } }] });
    expect(overview).toEqual({ scanned: 3, invalid: 1, conflicts: 0, limited: false,
      reads: [{ resource: "react-docs", library: "/facebook/react", fetchedAt: "2026-11-03T10:00:00Z", durationMs: 120 }] });
    expect(parseHarness(undefined).reads).toEqual([]);
  });
  it("karta ukáže počet artefaktů s aktivní verzí nebo čtení; při načítání nic", () => {
    expect(shelfCount(entry("skills"), loading)).toBeNull();
    expect(shelfCount(entry("skills"), { ...loading, brain: { data: brain, error: "" } })).toBe("2 · 1 aktivních");
    expect(shelfCount(entry("tools"), { ...loading, brain: { data: null, error: "HTTP 500" } })).toBe("nenačteno");
    expect(shelfCount(entry("harness"), { ...loading, harness: { data: parseHarness({}), error: "" } })).toBe("0 čtení");
  });
});
