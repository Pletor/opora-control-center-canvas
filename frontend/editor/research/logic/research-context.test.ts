import { expect, it } from "vitest";
import { researchContext } from "./research-context";
import type { ResearchHeader, ResearchEdge } from "./research-types";
it("rejects deep links to cards and edges outside the entered problem", () => {
  const cards = [
    { id: "login", refs: { nodeIds: ["a"] } },
    { id: "tenant", refs: { nodeIds: ["b"] } },
    { id: "shared", refs: { nodeIds: ["a", "b"] } },
  ] as ResearchHeader[];
  const edges = [{ id: "foreign", fromId: "tenant", toId: "shared" }, { id: "local", fromId: "login", toId: "shared" }] as ResearchEdge[];
  const scope = { projectId: "ample", nodeId: "a" };
  expect(researchContext(cards, edges, scope, { kind: "card", id: "tenant" }).currentCard).toBeUndefined();
  expect(researchContext(cards, edges, scope, { kind: "edge", id: "foreign" }).currentEdge).toBeUndefined();
  expect(researchContext(cards, edges, scope, { kind: "card", id: "shared" }).currentCard).toBe(cards[2]);
  expect(researchContext(cards, edges, scope, { kind: "edge", id: "local" }).currentEdge).toBe(edges[1]);
  expect(researchContext(cards, edges, { ...scope, nodeId: null }, { kind: "card", id: "tenant" }).currentCard).toBe(cards[1]);
});
