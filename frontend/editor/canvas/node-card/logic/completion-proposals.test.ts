import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { confirmProposal, proposalCount } from "./completion-proposals";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import { setDone } from "@/editor/node-detail/tree/logic/tree-model";
import type { Graph } from "@/shared/types/logic/types";
import ConfirmProposal from "../components/ConfirmProposal";

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

it("shows one-click confirmation and respects read-only mode", () => {
  const html = renderToStaticMarkup(createElement(ConfirmProposal, { disabled: true, confirm: async () => true, note: "Review ready" }));
  expect(html).toContain("Potvrdit");
  expect(html).toContain("Review ready");
  expect(html).toContain('disabled=""');
});
