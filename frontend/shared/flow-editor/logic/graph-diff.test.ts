import { describe, expect, it } from "vitest";
import { heartGraph } from "./flow-fixtures";
import { diffSummary, graphDiff } from "./graph-diff";
import { moveNode, removeNode, setParam } from "./graph-edit";

describe("diff of two versions", () => {
  it("finds added, removed and changed nodes and edges, ignoring moves", () => {
    const base = heartGraph();
    let next = setParam(moveNode(removeNode(base, "udalost"), "jev", { x: 999, y: 0 }), "srdce", "per_hour", 3);
    next = { nodes: [...next.nodes, { id: "rozvrh", type: "trigger.manual" }], edges: [...next.edges,
      { id: "x", source_node: "rozvrh", source_port: "main", target_node: "jev", target_port: "main", kind: "main" }] };
    const diff = graphDiff(base, next);
    expect([...diff.nodes]).toEqual([["srdce", "changed"], ["rozvrh", "added"], ["udalost", "removed"]]);
    expect(diff.ghosts.map((n) => n.id)).toEqual(["udalost"]);
    expect(diff.addedEdges.map((e) => e.id)).toEqual(["x"]);
    expect(diff.removedEdges.map((e) => e.id)).toEqual(["udalost-jev"]);
    expect(diffSummary(diff)).toBe("+1 uzlů · −1 · ~1 změněno · vazby +1/−1");
  });
  it("sees no change when only the key order of params differs", () => {
    const a = setParam(setParam(heartGraph(), "srdce", "b", 1), "srdce", "c", 2);
    const b = { ...a, nodes: a.nodes.map((n) => n.id === "srdce" ? { ...n, params: { c: 2, b: 1, per_hour: 6 } } : n) };
    expect(graphDiff(a, b).nodes.size).toBe(0);
  });
});
