import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { counted, unresolvedRows } from "./proposal-rows";

describe("proposal rows", () => {
  it("names both ends of each unresolved edge and keeps the reason", () => {
    const graph = { nodes: [{ id: "a", name: "Košík" }, { id: "b", name: "" }], edges: [{ id: "e", source: "a", target: "b" }] } as unknown as Graph;
    expect(unresolvedRows(graph, [{ edgeId: "e", reason: "Vazba neříká, co nese (carries)." }, { edgeId: "x", reason: "?" }])).toEqual([
      { edgeId: "e", from: "Košík", to: "b", reason: "Vazba neříká, co nese (carries)." },
      { edgeId: "x", from: "?", to: "?", reason: "?" },
    ]);
  });

  it("counts with the Czech word form", () => {
    const forms = ["vazba", "vazby", "vazeb"] as const;
    expect([0, 1, 3, 5].map((n) => counted(n, forms))).toEqual(["0 vazeb", "1 vazba", "3 vazby", "5 vazeb"]);
  });
});
