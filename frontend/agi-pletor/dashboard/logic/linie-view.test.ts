import { describe, expect, it } from "vitest";
import { linieFixture } from "./linie-fixture";
import { graphView, shortSha } from "./linie-view";

describe("graphView", () => {
  it("mapuje linie, commity, přijetí a PR", () => {
    const view = graphView(linieFixture);
    expect(view.lanes.map((lane) => lane.name)).toEqual(["main", "develop", "feat/detail-karty"]);
    expect(view.lanes[0].parent).toBe("");
    expect(view.lanes[1].commits[1].parents).toEqual(["d1", "f2"]);
    expect(view.lanes[2].pr).toEqual({ number: 7, state: "open", url: "https://x/pr/7", base: "develop" });
    expect(view.active).toBe("feat/detail-karty");
    expect(view.lanes[2].acceptance?.valid).toBe(true);
    expect(shortSha("0123456789")).toBe("0123456");
  });
  it("prázdná nebo chybná odpověď nespadne", () => {
    expect(graphView(null).lanes).toEqual([]);
    const view = graphView({ lanes: { error: "git" }, deployed: { error: "chybí soubor" } });
    expect(view.lanes).toEqual([]);
    expect(view.deployed).toBeNull();
    expect(view.problem).toBe("nedostupné: git · nedostupné: chybí soubor");
  });
});
