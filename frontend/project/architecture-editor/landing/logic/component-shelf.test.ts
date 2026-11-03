import { describe, expect, it } from "vitest";
import { CATALOG_CATEGORIES } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { brainOf, COMPONENT_SHELF, parseBrainArtifacts, parseHarness, shelfCount, shelfId, shelfItems, shortVersion, type ShelfData } from "./component-shelf";

const entry = (id: string) => COMPONENT_SHELF.find((item) => item.id === id)!;
const loading: ShelfData = { brain: { data: null, error: "" }, harness: { data: null, error: "" } };

describe("COMPONENT_SHELF", () => {
  it("má karty z image6.png a doplňky, každá s jedinečným ID", () => {
    const labels = COMPONENT_SHELF.map((item) => item.label);
    for (const label of ["Databáze", "Backend", "DevOps", "Cache", "Docker", "Funkce a metody", "Infrastruktura", "Security", "Monitoring", "Skills", "Tools", "Harness"])
      expect(labels).toContain(label);
    expect(new Set(COMPONENT_SHELF.map(shelfId)).size).toBe(COMPONENT_SHELF.length);
  });
  it("každá katalogová karta míří na známou kategorii a má aspoň jednu předlohu", () => {
    const known = new Set(CATALOG_CATEGORIES.map((category) => category.id));
    for (const item of COMPONENT_SHELF.filter((shelf) => shelf.source.kind === "catalog")) {
      if (item.source.kind === "catalog") item.source.categories.forEach((category) => expect(known.has(category), category).toBe(true));
      expect(shelfItems(item).length, item.id).toBeGreaterThan(0);
    }
    expect(shelfItems(entry("skills"))).toEqual([]);
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
  it("karta ukáže počet předloh, artefaktů s aktivní verzí nebo čtení; při načítání nic", () => {
    expect(shelfCount(entry("docker"), loading)).toMatch(/^\d+ předlo/);
    expect(shelfCount(entry("skills"), loading)).toBeNull();
    expect(shelfCount(entry("skills"), { ...loading, brain: { data: brain, error: "" } })).toBe("2 · 1 aktivních");
    expect(shelfCount(entry("tools"), { ...loading, brain: { data: null, error: "HTTP 500" } })).toBe("nenačteno");
    expect(shelfCount(entry("harness"), { ...loading, harness: { data: parseHarness({}), error: "" } })).toBe("0 čtení");
  });
});
