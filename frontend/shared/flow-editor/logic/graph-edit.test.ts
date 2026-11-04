import { describe, expect, it } from "vitest";
import { heartGraph, LIBRARY, TYPES } from "./flow-fixtures";
import { addConnected, addNode, connect, moveNode, nextNodeId, removeEdge, removeNode, setEdgeVia, setParam } from "./graph-edit";

describe("graph edits return a new graph and leave the version untouched", () => {
  it("names new nodes after the type and keeps ids unique", () => {
    const graph = heartGraph();
    expect(nextNodeId(graph, "decision.jev")).toBe("jev-2");
    expect(nextNodeId(graph, "approval.human")).toBe("human");
    const { graph: next, node } = addNode(graph, TYPES, "approval.human", { x: 10, y: 20 });
    expect(node).toEqual({ id: "human", type: "approval.human", type_version: 1, params: {}, position: { x: 10, y: 20 } });
    expect(next.nodes).toHaveLength(5);
    expect(graph.nodes).toHaveLength(4);
    expect(() => addNode(graph, TYPES, "nope", { x: 0, y: 0 })).toThrow(/Neznámý typ/);
  });
  it("gives a new node the parameters its catalog type describes, empty", () => {
    const intent = new Map([["intent.view", { type: "intent.view", version: 1, trigger: false, ports: [], params: { section: "id sekce", shows: "co vidí" } }]]);
    expect(addNode({ nodes: [], edges: [] }, intent, "intent.view", { x: 0, y: 0 }).node.params).toEqual({ section: "", shows: "" });
  });
  it("adds a sub-node below the agent and wires it to the clicked port", () => {
    const next = addConnected(heartGraph(), TYPES, "tool.opora_heart", { nodeId: "srdce", port: "tool", direction: "in" });
    expect(next.nodes.at(-1)).toMatchObject({ id: "opora_heart", position: { x: 520, y: 200 } });
    expect(next.edges.at(-1)).toMatchObject({ source_node: "opora_heart", source_port: "tool", target_node: "srdce", target_port: "tool", kind: "tool" });
    expect(() => addConnected(heartGraph(), TYPES, "tool.opora_heart", { nodeId: "srdce", port: "model", direction: "in" })).toThrow(/nemá port/);
  });
  it("adds a main step to the right of an output", () => {
    const next = addConnected(heartGraph(), TYPES, "context.snapshot", { nodeId: "jev", port: "main", direction: "out" });
    expect(next.nodes.at(-1)?.position).toEqual({ x: 520, y: 0 });
  });
  it("connects, removes nodes with their edges, moves and sets params", () => {
    const graph = heartGraph();
    expect(connect(graph, TYPES, { nodeId: "udalost", port: "main", direction: "out" }, { nodeId: "srdce", port: "main", direction: "in" }).edges).toHaveLength(4);
    expect(removeNode(graph, "jev").edges.map((e) => e.id)).toEqual(["model-srdce"]);
    expect(removeEdge(graph, "jev-srdce").edges).toHaveLength(2);
    expect(moveNode(graph, "jev", { x: 1.6, y: 2.2 }).nodes[1].position).toEqual({ x: 2, y: 2 });
    expect(setParam(graph, "srdce", "per_hour", 3).nodes[2].params).toEqual({ per_hour: 3 });
    expect(setParam(graph, "srdce", "per_hour", undefined).nodes[2].params).toEqual({});
  });
  it("adds a type from the plus through its variant with the variant params", () => {
    const graph = { nodes: [{ id: "agent", type: "ai.agent", position: { x: 0, y: 0 } }], edges: [] };
    const next = addConnected(graph, LIBRARY, "ai.vectorStore", { nodeId: "agent", port: "tool", direction: "in" });
    expect(next.nodes[1]).toMatchObject({ id: "vectorstore", params: { mode: "retrieveAsTool" }, position: { x: 0, y: 200 } });
    expect(next.edges[0]).toMatchObject({ source_node: "vectorstore", source_port: "tool", target_node: "agent", target_port: "tool", kind: "tool" });
  });
  it("sets and clears the via of an edge", () => {
    const graph = heartGraph(), withVia = setEdgeVia(graph, "udalost-jev", "http");
    expect(withVia.edges[0].via).toBe("http");
    expect("via" in setEdgeVia(withVia, "udalost-jev", undefined).edges[0]).toBe(false);
    expect(graph.edges[0].via).toBeUndefined();
  });
});
