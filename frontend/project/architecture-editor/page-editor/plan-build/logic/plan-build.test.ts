import { describe, expect, it } from "vitest";
import { parsePlanBuild, planBuildLines } from "./plan-build";

const RAW = {
  pages: [{ pageId: "home", name: "Domů", frameId: null }],
  counts: { areas: 3, cards: 2, edges: 7 }, existing: { frames: 0, areas: 0, cards: 0 },
  skipped: { pages: [{ pageId: "p", name: "Prázdná" }], boxes: [{ pageId: "home", id: "pata", name: "Pata" }] },
  unmatched: [{ elementId: "el", name: "Formulář", dataTo: "E-mail" }], orphans: [],
  proposal: { id: "gp1", reused: false },
};

describe("stavba plátna 3", () => {
  it("převede odpověď a řekne, co návrh přidá a co vynechal", () => {
    const build = parsePlanBuild(RAW);
    expect(build.proposal).toEqual({ id: "gp1", reused: false });
    expect(build.frameId).toBeNull();
    expect(planBuildLines(build)).toEqual([
      "Návrh srdce: 3 oblastí, 2 karet, 7 vazeb. Přijímá se v OporaHubu.",
      "Boxy bez prvku logiky (bez karty): Pata.",
      "Stránky bez logiky: Prázdná.",
      "Data mimo prvky stránky: Formulář → E-mail.",
    ]);
  });

  it("bez rozdílu návrh nevznikne a existující proces dá cíl odkazu", () => {
    const build = parsePlanBuild({ ...RAW, pages: [{ frameId: "f1" }], proposal: null, counts: {},
      existing: { frames: 1, areas: 3, cards: 2 }, skipped: {}, unmatched: [], orphans: [{ name: "Stará" }] });
    expect(build.frameId).toBe("f1");
    expect(planBuildLines(build)).toEqual(["Plátno 3 už má všechno z plánu stránky, návrh nevznikl.",
      "Už existuje: 2 karet, 3 oblastí.", "Karty bez prvku (nemažou se): Stará."]);
  });

  it("bez logiky i bez existujících karet řekne, že není z čeho stavět", () => {
    const build = parsePlanBuild({ ...RAW, proposal: null, counts: {}, existing: {}, skipped: { pages: ["prehled"] },
      unmatched: [], orphans: [] });
    expect(planBuildLines(build)[0]).toBe("Stránka zatím nemá prvky logiky, srdce nemá z čeho stavět. Přidejte logiku boxům na plátně 2.");
  });

  it("nesmyslná odpověď je prázdný výsledek", () => {
    expect(parsePlanBuild(null)).toMatchObject({ proposal: null, frameId: null, counts: { areas: 0, cards: 0, edges: 0 } });
  });
});
