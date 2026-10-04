import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph, GraphEdge } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { breadcrumbs, buildStructure, nodeStatus, pipelineSteps, workflowChain } from "./structure-model";

const node = (id: string, parentId: string | null, kind: CanvasNode["kind"] = "node", x = 0, y = 0): CanvasNode => ({
  id, parentId, kind, name: id.toUpperCase(), purpose: `účel ${id}`, x, y,
});
const area = (id: string, parentId: string, x: number, y: number): CanvasNode => ({
  ...node(id, parentId, "area", x, y), size: { w: 1000, h: 1000 },
});
const edge = (source: string, target: string, port?: GraphEdge["port"]): GraphEdge => ({ id: `${source}-${target}`, source, target, port });
const phase = (id: string): NodePhase => (id === "n1" ? "build" : "discover");
const done = (id: string) => id === "n2";

describe("stav uzlu", () => {
  it("hotovo vyhrává, build/verify jsou v řešení, jinak čeká", () => {
    expect(nodeStatus("discover", true)).toBe("done");
    expect(nodeStatus("build", false)).toBe("active");
    expect(nodeStatus("verify", false)).toBe("active");
    expect(nodeStatus("define", false)).toBe("waiting");
    expect(nodeStatus("live", false)).toBe("waiting");
  });
});

describe("strom oblasti → sektory → uzly", () => {
  const graph: Graph = {
    nodes: [
      node("root", null, "sector"),
      area("a", "root", 0, 0),
      { ...node("s1", "root", "sector", 100, 100) },
      { ...node("n1", "s1"), card: { layer: "backend" } },
      { ...node("n2", "s1"), card: { layer: "backend" } },
      node("c1", "s1", "comment"),
      node("free", "root", "node", 5000, 5000),
      node("note", "root", "comment", 5000, 5000),
      node("elsewhere", null, "node", 100, 100),
    ],
    edges: [],
  };
  it("seskupí sourozence podle geometrie a přímé děti mimo oblast dá do implicitní skupiny", () => {
    const groups = buildStructure(graph, "root", phase, done);
    expect(groups.map((g) => g.id)).toEqual([null, "a"]);
    expect(groups[0].items.map((i) => i.id)).toEqual(["free"]);
    expect(groups[1].sectors).toHaveLength(1);
    const sector = groups[1].sectors[0];
    expect(sector.tone).toBe("backend");
    expect(sector.items.map((i) => [i.id, i.status])).toEqual([["n1", "active"], ["n2", "done"]]);
  });
  it("prázdný root nemá žádné skupiny", () => {
    expect(buildStructure({ nodes: [node("root", null, "sector")], edges: [] }, "root", phase, done)).toEqual([]);
  });
  it("prázdná oblast zůstane vidět", () => {
    const groups = buildStructure({ nodes: [node("root", null), area("a", "root", 0, 0)], edges: [] }, "root", phase, done);
    expect(groups).toEqual([{ id: "a", name: "A", purpose: "účel a", sectors: [], items: [] }]);
  });
});

describe("drobečky", () => {
  const graph: Graph = { nodes: [node("app", null, "sector"), node("page", "app"), node("root", "page"), node("leaf", "root"), node("other", null)], edges: [] };
  it("vedou od nejvyššího předka po vybraný pod rootem", () => {
    expect(breadcrumbs(graph, "root", "leaf").map((n) => n.id)).toEqual(["app", "page", "root", "leaf"]);
  });
  it("končí rootem, když výběr leží jinde nebo chybí", () => {
    expect(breadcrumbs(graph, "root", "other").map((n) => n.id)).toEqual(["app", "page", "root"]);
    expect(breadcrumbs(graph, "root", null).map((n) => n.id)).toEqual(["app", "page", "root"]);
  });
  it("přežije cyklus rodičů", () => {
    const loop: Graph = { nodes: [{ ...node("x", "y") }, { ...node("y", "x") }], edges: [] };
    expect(breadcrumbs(loop, "x", "x").map((n) => n.id)).toEqual(["y", "x"]);
  });
});

describe("workflow uživatele", () => {
  const base = [node("root", null, "sector"), node("a", "root"), node("b", "root"), node("c", "root"), node("d", "b"), node("out", null)];
  it("řadí potomky topologicky podle next a ignoruje jiné porty i uzly mimo root", () => {
    const graph: Graph = { nodes: base, edges: [edge("c", "d"), edge("a", "c", "next"), edge("b", "a"), edge("a", "out"), edge("a", "b", "rule")] };
    expect(workflowChain(graph, "root").map((n) => n.id)).toEqual(["b", "a", "c", "d"]);
  });
  it("cyklus nezacyklí řazení a jeho uzly skončí na konci", () => {
    const graph: Graph = { nodes: base, edges: [edge("a", "b"), edge("b", "c"), edge("c", "b")] };
    expect(workflowChain(graph, "root").map((n) => n.id)).toEqual(["a", "b", "c"]);
  });
  it("bez vazeb je prázdný", () => {
    expect(workflowChain({ nodes: base, edges: [] }, "root")).toEqual([]);
  });
});

describe("pipeline práce", () => {
  it("vyznačí fázi a české popisky", () => {
    expect(pipelineSteps("build").map((s) => `${s.label}:${s.state}`)).toEqual([
      "Průzkum:past", "Zadání:past", "Stavba:current", "Ověření:future", "Provoz:future",
    ]);
  });
});
