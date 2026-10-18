import { describe, expect, it } from "vitest";
import { canvasIndexUrl, indexMatches, shortText } from "./canvas-index";

describe("canvas-index", () => {
  it("rozdělí shody na id karet a vazby", () => {
    const matches = indexMatches({
      total: 3,
      entries: [
        { id: "s1", kind: "sector", name: "Editor" },
        { id: "n1", kind: "node", name: "Pop-up" },
        { id: "e1", kind: "edge", from: "n1", to: "n2", fromName: "Pop-up", toName: "", handoff: "Pokračuj\n v routeru" },
      ],
    });
    expect(matches && [...matches.ids]).toEqual(["s1", "n1"]);
    expect(matches?.edges).toEqual([{ id: "e1", from: "n1", fromName: "Pop-up", toName: "n2", handoff: "Pokračuj v routeru" }]);
  });

  it("neznámý tvar odpovědi vrací null, aby panel spadl na lokální filtr", () => {
    expect(indexMatches(null)).toBeNull();
    expect(indexMatches({ error: "x" })).toBeNull();
    expect(indexMatches({ entries: [], total: 0 })).toEqual({ ids: new Set(), edges: [] });
  });

  it("předání se zkrátí na jeden řádek", () => {
    expect(shortText("a\n b")).toBe("a b");
    expect(shortText("x".repeat(100), 10)).toBe("x".repeat(9) + "…");
  });

  it("adresa nese projekt, prostor, oříznutý dotaz a limit", () => {
    expect(canvasIndexUrl("p 1", "draft", " typ:task ")).toBe("/api/canvas-index?project=p+1&workspace=draft&q=typ%3Atask&limit=2000");
  });
});
