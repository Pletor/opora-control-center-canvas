import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import { layerEdges, simpleEdges, SIMPLE_EDGES_FROM } from "./board-edges";

function chain(count: number): Graph {
  const graph: Graph = { nodes: [], edges: [] };
  for (let i = 0; i <= count; i++) graph.nodes.push({ id: "n" + i, parentId: null, kind: "node", name: "K" + i, purpose: "", x: 0, y: 0 });
  for (let i = 0; i < count; i++) graph.edges.push({ id: "e" + i, source: "n" + i, target: "n" + (i + 1) });
  return graph;
}

const input = (graph: Graph, simple?: boolean) => ({ graph, state: emptyDesktopState(), ids: new Set(graph.nodes.map((n) => n.id)),
  kinds: new Map(), added: new Set<string>(), selectedEdge: null, blockEdges: [], simple });

describe("zjednodušené vazby velké vrstvy", () => {
  it("bez `simple` kreslí pravoúhle, se `simple` rovně", () => {
    const graph = chain(3);
    expect(layerEdges(input(graph)).map((e) => e.type)).toEqual(["smoothstep", "smoothstep", "smoothstep"]);
    const straight = layerEdges(input(graph, true));
    expect(straight.map((e) => e.type)).toEqual(["straight", "straight", "straight"]);
    expect((straight[0] as { pathOptions?: unknown }).pathOptions).toBeUndefined();
  });

  it("rovně až nad prahem vazeb mezi vykreslenými uzly", () => {
    const graph = chain(SIMPLE_EDGES_FROM);
    const ids = new Set(graph.nodes.map((n) => n.id));
    expect(simpleEdges(graph, ids)).toBe(false);
    const bigger = chain(SIMPLE_EDGES_FROM + 1);
    expect(simpleEdges(bigger, new Set(bigger.nodes.map((n) => n.id)))).toBe(true);
    // Vazby do nevykreslených uzlů (jiná vrstva) se nepočítají.
    expect(simpleEdges(bigger, new Set(bigger.nodes.map((n) => n.id).filter((id) => id !== "n0")))).toBe(false);
  });
});
