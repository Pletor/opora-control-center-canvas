import { expect, it } from "vitest";
import { checkTargets } from "./check-strip";
import type { FlowGraph } from "./flow-types";

const graph: FlowGraph = { nodes: [{ id: "agent", type: "ai.agent" }, { id: "store", type: "ai.vectorStore" }], edges: [], groups: [{ id: "dotaz", name: "Dotaz", nodeIds: ["agent"] }] };

it("maps graph-check sentences to nodes and frames on the canvas", () => {
  const targets = checkTargets([
    "Uzel agent: povinný port model není připojený.",
    "Port store.tool (out) nese jen jednu hranu, má 2.",
    "Skupina dotaz: sub-uzel a jeho kořenový uzel musí být ve stejné skupině (model → agent).",
    "Hrana e1: uzel nikdo nemá in port 'main'.",
    "nodes a edges musí být seznamy.",
  ], graph);
  expect([...targets.nodes]).toEqual(["agent", "store"]);
  expect([...targets.groups]).toEqual([["dotaz", ["Uzel agent: povinný port model není připojený.", "sub-uzel a jeho kořenový uzel musí být ve stejné skupině (model → agent)."]]]);
});
