import { expect, it } from "vitest";
import { heartGraph, TYPES } from "./flow-fixtures";
import { removeEdge, removeNode } from "./graph-edit";
import { readinessIssues } from "./readiness";

it("lists a missing trigger, a missing model and unknown types", () => {
  expect(readinessIssues(heartGraph(), TYPES)).toEqual([]);
  const broken = removeEdge(removeNode(heartGraph(), "udalost"), "model-srdce");
  expect(readinessIssues({ ...broken, nodes: [...broken.nodes, { id: "x", type: "nope" }] }, TYPES)).toEqual([
    { nodeId: null, text: "Workflow nemá spouštěč." }, { nodeId: "srdce", text: "srdce: chybí Model." }, { nodeId: "x", text: "x: neznámý typ nope." }]);
});

it("does not ask for a trigger when the catalog has none (page intent is never run)", () => {
  const intent = new Map([["intent.entry", { type: "intent.entry", version: 1, trigger: false, ports: [] }]]);
  expect(readinessIssues({ nodes: [{ id: "entry", type: "intent.entry" }], edges: [] }, intent)).toEqual([]);
});
