import { describe, expect, it } from "vitest";
import { PROCESS, processGraph, heartGraph, TYPES } from "./flow-fixtures";
import { flowEdges, flowNodes, handleId, parseHandle } from "./flow-view";
import { graphDiff } from "./graph-diff";
import { removeNode } from "./graph-edit";
import { runOverlay } from "./run-overlay";

describe("graph to React Flow", () => {
  it("builds cards with role, ports, run state and highlight", () => {
    const overlay = runOverlay([{ id: "n", run_id: "r", node_id: "srdce", attempt: 1, status: "running" }]);
    const nodes = flowNodes(heartGraph(), TYPES, { overlay, highlighted: "jev", issues: new Set(["srdce"]) });
    const agent = nodes.find((n) => n.id === "srdce")!;
    expect(agent.data).toMatchObject({ role: "agent", glyph: "✳", run: { status: "running" }, issue: true, highlighted: false });
    expect(agent.data.ports.find((p) => p.name === "model")).toMatchObject({ handleId: "in:model", connected: 1, required: true });
    expect(nodes.find((n) => n.id === "jev")!.data.highlighted).toBe(true);
    expect(flowEdges(heartGraph(), { overlay }).find((e) => e.id === "jev-srdce")).toMatchObject({ animated: true, sourceHandle: "out:main", targetHandle: "in:main" });
  });
  it("shows a custom step with its title and a custom flag", () => {
    const step = [{ name: "main", direction: "in" as const, kind: "main" as const, cardinality: "many" as const }];
    const types = new Map([["custom.step", { type: "custom.step", version: 1, trigger: false, ports: step }]]);
    const [card] = flowNodes({ nodes: [{ id: "bmi", type: "custom.step", layer: "be", params: { title: "Spočítej BMI" } }], edges: [] }, types);
    expect(card.data).toMatchObject({ name: "Spočítej BMI", custom: true, layer: "be" });
    expect(flowNodes({ nodes: [{ id: "x", type: "custom.step", params: {} }], edges: [] }, types)[0].data.name).toBe("step");
  });
  it("draws sub-port edges straight and dashed by class", () => {
    expect(flowEdges(heartGraph()).find((e) => e.id === "model-srdce")).toMatchObject({ type: "straight", className: "flow-edge flow-edge--sub" });
  });
  it("shows removed nodes and edges of the compared version as ghosts", () => {
    const base = heartGraph(), next = removeNode(base, "udalost"), diff = graphDiff(base, next);
    const ghost = flowNodes(next, TYPES, { diff }).find((n) => n.id === "ghost:udalost")!;
    expect(ghost.data).toMatchObject({ ghost: true, mark: "removed", readOnly: true });
    expect(ghost.draggable).toBe(false);
    expect(flowEdges(next, { diff }).at(-1)).toMatchObject({ id: "ghost:udalost-jev", source: "ghost:udalost", target: "jev" });
  });
  it("round-trips handle ids", () => {
    expect(parseHandle("a", handleId("in", "model"))).toEqual({ nodeId: "a", direction: "in", port: "model" });
    expect(parseHandle("a", null)).toBeNull();
  });
  it("puts the effective layer on the card and the via label on the edge", () => {
    const graph = processGraph();
    graph.nodes[2] = { ...graph.nodes[2], layer: "fe" };
    const cards = flowNodes(graph, PROCESS);
    expect(cards.map((c) => c.data.layer)).toEqual(["fe", "fe", "fe", "be", "be", "db", "fe"]);
    expect(flowNodes(heartGraph(), TYPES)[0].data.layer).toBeUndefined();
    expect(flowEdges(graph).map((e) => e.label)).toEqual([undefined, "http", undefined, undefined, "sql", "event"]);
  });
});
