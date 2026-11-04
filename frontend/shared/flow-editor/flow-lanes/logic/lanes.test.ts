import { describe, expect, it } from "vitest";
import { nodeTypeMap, type FlowGraph, type NodeTypeSpec } from "../../logic/flow-types";
import type { FlowCardNode } from "../../logic/flow-view";
import { arrangeLanes, laneNodes } from "./lanes";
import { effectiveLayer } from "./layers";

const step = [{ name: "main", direction: "in" as const, kind: "main" as const, cardinality: "many" as const }, { name: "main", direction: "out" as const, kind: "main" as const, cardinality: "many" as const }];
const types = nodeTypeMap([
  { type: "fe.click", version: 1, trigger: false, layer: "fe", ports: step }, { type: "be.function", version: 1, trigger: false, layer: "be", ports: step },
  { type: "db.write", version: 1, trigger: false, layer: "db", ports: step }, { type: "transform.set", version: 1, trigger: false, layer: "neutral", ports: step },
] satisfies NodeTypeSpec[]);
const node = (id: string, type: string, x: number, y: number, layer?: "fe") => ({ id, type, position: { x, y }, ...(layer ? { layer } : {}) });
const graph: FlowGraph = { nodes: [node("a", "db.write", 0, 500), node("b", "fe.click", 300, 10), node("c", "be.function", 600, 200), node("d", "be.function", 900, 0, "fe")], edges: [] };

describe("flow lanes", () => {
  it("uses the node layer over the type layer", () => {
    expect(effectiveLayer({ layer: "fe" }, { layer: "be" })).toBe("fe");
    expect(effectiveLayer({}, { layer: "be" })).toBe("be");
    expect(effectiveLayer({}, undefined)).toBeUndefined();
  });
  it("stacks layers FE, BE, DB top to bottom and only changes y", () => {
    const next = arrangeLanes(graph, types), at = (id: string) => next.nodes.find((n) => n.id === id)!.position!;
    expect(next.nodes.map((n) => n.position!.x)).toEqual(graph.nodes.map((n) => n.position!.x));
    expect(at("b").y).toBe(10);
    expect(at("d").y).toBe(0);
    expect(at("b").y).toBeLessThan(at("c").y);
    expect(at("c").y).toBeLessThan(at("a").y);
    expect(arrangeLanes(next, types)).toEqual(next);
  });
  it("leaves a graph without layers untouched", () => {
    const plain: FlowGraph = { nodes: [{ id: "x", type: "unknown.type", position: { x: 5, y: 7 } }], edges: [] };
    expect(arrangeLanes(plain, types)).toEqual(plain);
  });
  it("draws a lane only for a layer that has nodes", () => {
    const card = (id: string, layer: "fe" | "db", x: number, y: number) => ({ id, position: { x, y }, data: { layer, role: "main", ghost: false } }) as unknown as FlowCardNode;
    const lanes = laneNodes([card("a", "fe", 0, 0), card("b", "fe", 200, 50), card("c", "db", 0, 300)]);
    expect(lanes.map((l) => l.id)).toEqual(["lane:fe", "lane:db"]);
    expect(lanes[0].position.y).toBeLessThan(0);
    expect(laneNodes([])).toEqual([]);
  });
});
