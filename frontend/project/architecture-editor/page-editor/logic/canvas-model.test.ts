import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { areaSectorLabel, CARRIES_COLORS, cardBodies, cardSummary, czechCount, edgeLook, NODE_FORMS, scopePath, TONE_COLORS, toneOf } from "./canvas-model";

const node = (id: string, parentId: string | null, kind: CanvasNode["kind"] = "node", extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, parentId, kind, name: id, purpose: "", x: 0, y: 0, ...extra });

describe("toneOf", () => {
  it("bere vrstvu karty", () => {
    expect(toneOf(node("a", null, "node", { card: { layer: "backend" } }))).toBe("backend");
    expect(toneOf(node("a", null, "node", { card: { layer: "library" } }))).toBe("infrastructure");
  });
  it("sektor bez vrstvy je frontend, uzel infrastruktura, oblast oblast", () => {
    expect(toneOf(node("s", null, "sector"))).toBe("frontend");
    expect(toneOf(node("n", null))).toBe("infrastructure");
    expect(toneOf(node("o", null, "area"))).toBe("area");
  });
});

describe("czechCount", () => {
  it("skloňuje podle počtu", () => {
    expect([0, 1, 2, 4, 5, 22].map((count) => czechCount(count, NODE_FORMS))).toEqual(["0 uzlů", "1 uzel", "2 uzly", "4 uzly", "5 uzlů", "22 uzlů"]);
  });
});

describe("cardSummary", () => {
  const graph: Graph = { nodes: [node("s", null, "sector"), node("a", "s"), node("b", "s"), node("c", "s", "sector"), node("d", "s"), node("x", "s", "comment")], edges: [] };
  it("počítá jen uzly a ukáže tři potomky", () => {
    const summary = cardSummary(graph.nodes[0], graph);
    expect(summary.countLabel).toBe("3 uzly");
    expect(summary.preview.map((child) => child.id)).toEqual(["a", "b", "c"]);
    expect(summary.more).toBe(1);
    expect(summary.tone).toBe("frontend");
    expect(summary.page).toBeNull();
  });
  it("podstránka je na plátně odkazem na svou stránku s cestou", () => {
    expect(cardSummary(node("p", "s", "node", { site: { kind: "page", path: "/novinky" } }), graph).page).toEqual({ path: "/novinky" });
    expect(cardSummary(node("q", "s", "node", { site: { kind: "page", path: "" } }), graph).page).toEqual({ path: null });
  });
});

describe("areaSectorLabel", () => {
  it("počítá sektory, jejichž střed leží v oblasti", () => {
    const area = node("o", "p", "area", { x: 0, y: 0, size: { w: 800, h: 500 } });
    const graph: Graph = { nodes: [area, node("s1", "p", "sector", { x: 10, y: 10 }), node("s2", "p", "sector", { x: 5000, y: 0 }), node("n", "p", "node", { x: 20, y: 20 })], edges: [] };
    expect(areaSectorLabel(area, graph)).toBe("1 sektor");
  });
});

describe("edgeLook", () => {
  const graph: Graph = { nodes: [node("a", null, "node", { card: { layer: "database" } }), node("o", null, "area")], edges: [] };
  it("barví podle zdroje a flow kreslí přerušovaně", () => {
    expect(edgeLook({ id: "e", source: "a", target: "b" }, graph)).toEqual({ color: TONE_COLORS.database, stroke: TONE_COLORS.database,
      dash: undefined, width: 2, label: undefined, className: "page-editor__edge", title: undefined });
    expect(edgeLook({ id: "f", source: "o", target: "o2", port: "flow" }, graph).dash).toBe("7 6");
    expect(edgeLook({ id: "r", source: "a", target: "b", port: "rule" }, graph).label).toBe("pravidlo");
  });
  it("vazba next s druhem toku má barvu druhu, háček a tooltip; jiný port carries nečte", () => {
    expect(edgeLook({ id: "c", source: "a", target: "b", carries: "command" }, graph)).toEqual({
      color: CARRIES_COLORS.command, stroke: "var(--edge-carries-command)", dash: undefined, width: 2.5, label: undefined,
      className: "page-editor__edge edge--carries-command", title: "Po vazbě teče: Příkaz" });
    expect(edgeLook({ id: "v", source: "a", target: "b", port: "next", carries: "event" }, graph).dash).toBe("6 4");
    expect(edgeLook({ id: "r", source: "a", target: "b", port: "rule", carries: "data" }, graph).className).toBe("page-editor__edge");
  });
});

describe("scopePath", () => {
  it("vede od stránky pod doménou po rozsah", () => {
    const graph: Graph = { nodes: [node("d", null, "sector"), node("p", "d"), node("c", "p")], edges: [] };
    expect(scopePath(graph, "c", "d").map((item) => item.id)).toEqual(["p", "c"]);
  });
});

describe("cardBodies", () => {
  it("bere změřený rozměr karty, nezměřená dostane 270 × odhad, oblasti vynechá", () => {
    const graph: Graph = { nodes: [node("a", "p", "node", { x: 10, y: 20 }), node("b", "p"), node("o", "p", "area"), node("c", "q")], edges: [] };
    const bodies = cardBodies(graph, "p", new Map([["a", { width: 270, height: 140 }]]));
    expect(bodies).toEqual([{ id: "a", x: 10, y: 20, w: 270, h: 140 }, { id: "b", x: 0, y: 0, w: 270, h: 90 }]);
  });
});
