import { describe, expect, it } from "vitest";
import { groupInOrder, matchesWords, searchWords } from "./palette-search";

describe("palette search core", () => {
  it("splits a query into lowercase words and needs every word in the text", () => {
    expect(searchWords("  Load   Balancer ")).toEqual(["load", "balancer"]);
    expect(matchesWords("Load-Balancer http-request", searchWords("load http"))).toBe(true);
    expect(matchesWords("Load-Balancer", searchWords("load sql"))).toBe(false);
    expect(matchesWords("cokoli", [])).toBe(true);
  });
  it("groups in the given order, appends unknown groups alphabetically and drops empty ones", () => {
    const items = [{ group: "B", n: 1 }, { group: "Z", n: 2 }, { group: "A", n: 3 }, { group: "Y", n: 4 }, { group: "B", n: 5 }];
    expect(groupInOrder(items, ["A", "B", "C"]).map((g) => [g.id, g.items.map((i) => i.n)])).toEqual([["A", [3]], ["B", [1, 5]], ["Y", [4]], ["Z", [2]]]);
  });
});
