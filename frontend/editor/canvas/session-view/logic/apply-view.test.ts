import { expect, it } from "vitest";
import { sameSelection, visibleSelection } from "./apply-view";
import type { Graph } from "@/shared/types/logic/types";

const graph = { nodes: [{ id: "a", name: "Alpha", parentId: null }, { id: "b", name: "Beta", parentId: "a" }], edges: [] } as unknown as Graph;
it("refuses to acknowledge foreign-layer or filtered-out selections", () => {
  const view = { selection: ["a"], filter: "alp", viewport: null };
  expect(visibleSelection(view, graph, null)).toBe(true);
  expect(visibleSelection({ ...view, selection: ["b"] }, graph, null)).toBe(false);
  expect(visibleSelection({ ...view, filter: "beta" }, graph, null)).toBe(false);
  expect(visibleSelection({ ...view, selection: ["missing"] }, graph, null)).toBe(false);
});
it("checks the actual complete selected set without changing order in caller state", () => {
  const actual = ["b", "a"];
  expect(sameSelection(actual, ["a", "b"])).toBe(true);
  expect(sameSelection(actual, ["a"])).toBe(false);
  expect(actual).toEqual(["b", "a"]);
});
