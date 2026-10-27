import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { buildStudioTree } from "./studio-tree";
import { dominantFlow, levelOf } from "./studio-level";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id, purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = {
  nodes: [
    node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
    node("a", "web", { site: { kind: "page", path: "/a" } }),
    node("b", "web", { site: { kind: "page", path: "/b" } }),
    node("a1", "a"), node("a2", "a"), node("b1", "b"), node("note", "a", { kind: "comment" }),
  ],
  edges: [
    { id: "e1", source: "a1", target: "b1", carries: "data" },
    { id: "e2", source: "a2", target: "b1", carries: "data" },
    { id: "e3", source: "a", target: "b", carries: "navigation" },
    { id: "e4", source: "a1", target: "a2", carries: "command" },
    { id: "e5", source: "a1", target: "b", port: "rule" },
    { id: "e6", source: "note", target: "b1" },
  ],
};

describe("studio level", () => {
  const tree = buildStudioTree(graph);

  it("sums deeper edges into one link between ancestors with count and dominant carries", () => {
    const level = levelOf(tree, graph, "web");
    expect(level.cards.map((card) => card.id)).toEqual(["a", "b"]);
    expect(level.links).toEqual([{ id: "a->b", source: "a", target: "b", count: 4, carries: "data", kinds: { data: 2, navigation: 1, unspecified: 1 }, edgeIds: ["e1", "e2", "e3", "e6"] }]);
  });

  it("keeps edges between cards of the open page and drops edges leaving the level", () => {
    const level = levelOf(tree, graph, "a");
    expect(level.focus?.id).toBe("a");
    expect(level.cards.map((card) => card.id)).toEqual(["a1", "a2"]);
    expect(level.links.map((link) => [link.id, link.count, link.carries])).toEqual([["a1->a2", 1, "command"]]);
  });

  it("opens the project level for an unknown focus", () => {
    expect(levelOf(tree, graph, "missing").cards.map((card) => card.id)).toEqual(["web"]);
  });

  it("prefers specified flows and the earlier kind on a tie", () => {
    expect(dominantFlow({ unspecified: 5, event: 1 })).toBe("event");
    expect(dominantFlow({ data: 2, navigation: 2 })).toBe("navigation");
    expect(dominantFlow({})).toBe("unspecified");
  });
});
