import { describe, expect, it } from "vitest";
import { canExpand, expandFunction } from "./detail-expand";
import { PROCESS, processGraph } from "../../logic/flow-fixtures";

describe("detail funkce", () => {
  it("replaces a function with a same-named group, a three-step chain and rewired outer edges", () => {
    const graph = processGraph();
    graph.nodes = graph.nodes.map((node) => node.id === "bmi" ? { ...node, inputSchema: { type: "object" }, outputSchema: { type: "number" }, params: { description: "Spočítá BMI" } } : node);
    const { graph: next, group } = expandFunction(graph, PROCESS, "bmi");
    expect(next.nodes.some((node) => node.id === "bmi")).toBe(false);
    expect(group).toMatchObject({ name: "bmi", description: "Spočítá BMI", nodeIds: ["bmi-vstup", "bmi-krok", "bmi-vystup"], inputSchema: { type: "object" }, outputSchema: { type: "number" } });
    expect(next.nodes.filter((node) => group.nodeIds.includes(node.id)).every((node) => node.type === "custom.step" && node.layer === "be")).toBe(true);
    expect(next.edges.find((edge) => edge.id === "e4")).toMatchObject({ source_node: "kontrola", target_node: "bmi-vstup" });
    expect(next.edges.find((edge) => edge.id === "e5")).toMatchObject({ source_node: "bmi-vystup", target_node: "zapis", via: "sql" });
    expect(next.edges.filter((edge) => group.nodeIds.includes(edge.source_node) && group.nodeIds.includes(edge.target_node))).toHaveLength(2);
  });
  it("refuses a node that is not a function, is already in a group, or leaves through a named port", () => {
    const graph = processGraph();
    expect(() => expandFunction(graph, PROCESS, "zapis")).toThrow(/Vnitřek/);
    expect(canExpand(graph, { id: "bmi", type: "be.function" })).toBe(true);
    const { graph: next } = expandFunction(graph, PROCESS, "bmi");
    expect(canExpand(next, { id: "bmi-krok", type: "custom.step" })).toBe(false);
    const branched = { ...graph, edges: graph.edges.map((edge) => edge.id === "e5" ? { ...edge, source_port: "true" } : edge) };
    expect(() => expandFunction(branched, PROCESS, "bmi")).toThrow(/jiného portu/);
  });
});
