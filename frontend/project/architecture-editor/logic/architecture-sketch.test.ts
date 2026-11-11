import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { architectureSketch } from "./architecture-sketch";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, ...extra });
const graph: Graph = {
  nodes: [node("web", null, { kind: "sector", site: { kind: "application", environments: [{ name: "Produkce", host: "a.cz" }] } }),
    node("home", "web", { site: { kind: "page", path: "/" } }), node("buy", "home"), node("other", null)],
  edges: [{ id: "e1", source: "home", target: "buy" }, { id: "e2", source: "buy", target: "other" }],
};

describe("export náčrtu", () => {
  it("vezme otevřenou stránku s potomky a vazby uvnitř", () => {
    const sketch = architectureSketch(graph, "web", "home");
    expect(sketch.nodes.map((item) => item.id)).toEqual(["home", "buy"]);
    expect(sketch.edges.map((edge) => edge.id)).toEqual(["e1"]);
  });
  it("bez domény vezme jen domény projektu", () => {
    expect(architectureSketch(graph, null, null).nodes.map((item) => item.id)).toEqual(["web"]);
  });
});
