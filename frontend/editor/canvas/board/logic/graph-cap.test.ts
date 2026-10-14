import { describe, expect, it } from "vitest";
import { capWarning, groupThousands, MAX_GRAPH_EDGES, MAX_GRAPH_NODES } from "./graph-cap";

const graph = (nodes: number, edges = 0) => ({
  nodes: Array.from({ length: nodes }, (_, i) => ({ id: "n" + i, parentId: null, kind: "node" as const, name: "", purpose: "", x: 0, y: 0 })),
  edges: Array.from({ length: edges }, (_, i) => ({ id: "e" + i, source: "n0", target: "n1" })),
});

describe("varování u stropu grafu", () => {
  it("pod 80 % stropu mlčí", () => {
    expect(capWarning(graph(1599, 3199))).toBeNull();
  });

  it("od 80 % uzlů ukáže počet uzlů a vysvětlí strop", () => {
    const warning = capWarning(graph(1640, 10));
    expect(warning?.text).toBe("Uzlů 1 640 / 2 000");
    expect(warning?.title).toContain("odmítne");
    expect(warning?.title).toContain("rozdělit");
  });

  it("u vazeb blíž stropu ukáže vazby", () => {
    expect(capWarning(graph(100, 3500))?.text).toBe("Vazeb 3 500 / 4 000");
  });

  it("počítá i uzly stavu", () => {
    expect(capWarning(graph(10), 1700)?.text).toBe("Uzlů 1 700 / 2 000");
  });

  it("stropy sedí se serverem a tisíce mají mezeru", () => {
    expect([MAX_GRAPH_NODES, MAX_GRAPH_EDGES]).toEqual([2000, 4000]);
    expect(groupThousands(1234567)).toBe("1 234 567");
    expect(groupThousands(999)).toBe("999");
  });
});
