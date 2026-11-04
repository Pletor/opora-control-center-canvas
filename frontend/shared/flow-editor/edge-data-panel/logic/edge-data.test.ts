import { describe, expect, it } from "vitest";
import { dataLabel, edgeData, edgeKindError, inheritedExample, kindError, sampleFromSchema } from "./edge-data";
import { nodeTypeMap, type FlowGraph, type NodeTypeSpec } from "../../logic/flow-types";

const ports = [{ name: "main", direction: "in" as const, kind: "main" as const, cardinality: "many" as const }, { name: "main", direction: "out" as const, kind: "main" as const, cardinality: "many" as const }];
const types = nodeTypeMap([{ type: "a", version: 1, trigger: false, ports, emits: "json" }, { type: "b", version: 1, trigger: false, ports, accepts: ["number", "text"] },
  { type: "c", version: 1, trigger: false, ports }] as NodeTypeSpec[]);
const edge = { id: "e", source_node: "x", source_port: "main", target_node: "y", target_port: "main", kind: "main" as const };

describe("edge data", () => {
  it("builds the label from via and kind", () => {
    expect(dataLabel({ via: "http", data: { kind: "json" } })).toBe("http · json");
    expect(dataLabel({ data: { kind: "text" } })).toBe("text");
    expect(dataLabel({ via: "sql" })).toBe("sql");
    expect(edgeData({ data: { kind: "nic" } as never })).toBeUndefined();
  });
  it("samples a value from a schema", () => {
    expect(sampleFromSchema({ type: "object", properties: { vyska: { type: "number", example: 180 }, jmeno: { type: "string" }, tagy: { type: "array", items: { enum: ["a"] } } } }))
      .toEqual({ vyska: 180, jmeno: "", tagy: ["a"] });
    expect(sampleFromSchema(undefined)).toBeUndefined();
  });
  it("inherits the example from the source node, then from its output schema", () => {
    const graph: FlowGraph = { nodes: [{ id: "x", type: "a", example: { bmi: 24.7 } }, { id: "y", type: "b", outputSchema: { type: "object", properties: { n: { type: "number" } } } }], edges: [] };
    expect(inheritedExample(graph, edge)).toEqual({ value: { bmi: 24.7 }, from: "x" });
    expect(inheritedExample(graph, { source_node: "y" })).toEqual({ value: { n: 0 }, from: "y" });
    expect(inheritedExample({ nodes: [{ id: "x", type: "a" }], edges: [] }, edge)).toBeNull();
  });
  it("rejects a kind the target does not accept; empty accepts means anything", () => {
    expect(kindError("json", ["number"], "y")).toMatch(/nepřijímá data druhu JSON/);
    expect(kindError("json", [], "y")).toBeNull();
    const graph: FlowGraph = { nodes: [{ id: "x", type: "a" }, { id: "y", type: "b" }, { id: "z", type: "c" }], edges: [] };
    expect(edgeKindError(graph, types, { ...edge })).toMatch(/přijímá: číslo, text/);
    expect(edgeKindError(graph, types, { ...edge, data: { kind: "number" } })).toBeNull();
    expect(edgeKindError(graph, types, { ...edge, target_node: "z" })).toBeNull();
  });
});
