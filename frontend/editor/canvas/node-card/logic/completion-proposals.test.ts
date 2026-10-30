import { expect, it } from "vitest";
import { closeCardAfterMerge, confirmProposal, proposalCount } from "./completion-proposals";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import { setDone } from "@/editor/node-detail/tree/logic/tree-model";
import type { Graph } from "@/shared/types/logic/types";

it("counts nested proposals and decreases after explicit human confirmation", () => {
  const graph: Graph = { nodes: [
    { id: "s", parentId: null, kind: "sector", name: "Sector", purpose: "", x: 0, y: 0 },
    { id: "n", parentId: "s", kind: "node", name: "Card", purpose: "", x: 0, y: 0 },
    { id: "child", parentId: "n", kind: "node", name: "Nested", purpose: "", x: 0, y: 0 },
  ], edges: [] };
  let state = setDone("n", { by: "agent", confirmed: false, note: "Tests reported" })(emptyDesktopState());
  state = setDone("child", { by: "agent", confirmed: false })(state);
  expect(proposalCount(graph, state, "s")).toBe(2);
  state = confirmProposal("n")(state);
  expect(state.nodes.n.done).toMatchObject({ by: "human", confirmed: true, note: "Tests reported" });
  expect(proposalCount(graph, state, "s")).toBe(1);
  expect(() => confirmProposal("n")(state)).toThrow();
  expect(() => confirmProposal("missing")(state)).toThrow();
});

it("closes a merged card as the human with the merge note, never twice", () => {
  const state = closeCardAfterMerge("n", "Uzavřeno po sloučení PR (0123456)")(emptyDesktopState());
  expect(state.nodes.n.done).toMatchObject({ by: "human", confirmed: true, note: "Uzavřeno po sloučení PR (0123456)" });
  expect(() => closeCardAfterMerge("n", "znovu")(state)).toThrow();
});
