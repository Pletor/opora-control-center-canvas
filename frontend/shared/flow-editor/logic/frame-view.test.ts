import { describe, expect, it } from "vitest";
import type { FlowGraph } from "./flow-types";
import { LIBRARY } from "./flow-fixtures";
import { flowEdges, flowNodes } from "./flow-view";
import { foldEdges, groupBox, groupNodes, hiddenNodes, noteNodes } from "./frame-view";

const edge = (id: string, source: string, target: string) => ({ id, source_node: source, source_port: "main", target_node: target, target_port: "main", kind: "main" as const });
const graph: FlowGraph = {
  nodes: [{ id: "chat", type: "trigger.chat", position: { x: 0, y: 0 } }, { id: "set", type: "transform.set", position: { x: 260, y: 0 } },
    { id: "if", type: "flow.if", position: { x: 520, y: 40 } }, { id: "end", type: "transform.set", position: { x: 780, y: 0 } }],
  edges: [edge("a", "chat", "set"), edge("b", "set", "if"), { ...edge("c", "if", "end"), source_port: "true" }],
  notes: [{ id: "n1", content: "# Dotaz", x: -40, y: -200, width: 900, height: 400, color: 2 }],
  groups: [{ id: "g1", name: "Úprava", description: "Připraví dotaz", nodeIds: ["set", "if"] }],
};

describe("notes and frames on the canvas", () => {
  it("puts notes behind the cards with their size and colour", () => {
    expect(noteNodes(graph, false)[0]).toMatchObject({ id: "note:n1", type: "flow-note", position: { x: -40, y: -200 }, width: 900, height: 400, zIndex: -2, draggable: true });
    expect(noteNodes(graph, true)[0].draggable).toBe(false);
  });
  it("wraps a frame around its cards with room for the title", () => {
    const cards = flowNodes(graph, LIBRARY);
    expect(groupBox(graph.groups![0], cards)).toEqual({ x: 224, y: -92, width: 408, height: 284 });
    const [frame] = groupNodes(graph, cards, new Set(), new Map([["g1", ["vstup vede jen do prvního uzlu"]]]), "g1");
    expect(frame).toMatchObject({ id: "group:g1", type: "flow-group", zIndex: -1, data: { collapsed: false, selected: true, errors: ["vstup vede jen do prvního uzlu"] } });
  });
  it("collapses a frame into one node: members hidden, outer edges rewired, inner edges gone", () => {
    const collapsed = new Set(["g1"]);
    expect([...hiddenNodes(graph, collapsed)]).toEqual(["set", "if"]);
    const [frame] = groupNodes(graph, flowNodes(graph, LIBRARY), collapsed, new Map(), null);
    expect(frame).toMatchObject({ position: { x: 260, y: 0 }, data: { collapsed: true } });
    expect(frame.width).toBeUndefined();
    const edges = foldEdges(flowEdges(graph), graph, collapsed);
    expect(edges.map((e) => [e.id, e.source, e.target, e.sourceHandle, e.targetHandle])).toEqual([
      ["a", "chat", "group:g1", "out:main", "in:main"], ["c", "group:g1", "end", "out:main", "in:main"]]);
  });
});
