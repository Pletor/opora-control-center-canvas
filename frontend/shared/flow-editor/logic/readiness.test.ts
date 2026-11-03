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
