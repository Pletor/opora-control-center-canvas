import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { sectorViews } from "./sector-status";
import SectorProgress from "../components/SectorProgress";
import SectorGateEditor from "../components/SectorGateEditor";
import type { Graph } from "@/shared/types/logic/types";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import { setDone } from "@/editor/node-detail/tree/logic/tree-model";

it("matches API blockers for sectors without explicit gates and card-to-sector links", () => {
  const graph: Graph = { nodes: [
    { id: "a", kind: "sector", parentId: null, name: "First", purpose: "", x: 0, y: 0 },
    { id: "b", kind: "sector", parentId: null, name: "Second", purpose: "", x: 0, y: 0 },
    { id: "card", kind: "node", parentId: "a", name: "Review", purpose: "", x: 0, y: 0 },
  ], edges: [{ id: "e", source: "a", target: "b" }, { id: "f", source: "card", target: "b" }] };
  let state = emptyDesktopState();
  expect(sectorViews(graph, state).b.blockedBy).toEqual(["First", "Review"]);
  state = setDone("card", { confirmed: true, by: "human" })(state);
  expect(sectorViews(graph, state).a.verified).toBe(true);
  expect(sectorViews(graph, state).b.blockedBy).toEqual([]);
});

it("unlocks the next sector only after its predecessor's human gate and all cards close", () => {
  const graph: Graph = { nodes: [
    { id: "a", kind: "sector", parentId: null, name: "First", purpose: "", x: 0, y: 0, gateNodeId: "gate" },
    { id: "b", kind: "sector", parentId: null, name: "Second", purpose: "", x: 0, y: 0 },
    { id: "gate", kind: "node", parentId: "a", name: "Verify", purpose: "", x: 0, y: 0 },
  ], edges: [{ id: "e", source: "a", target: "b" }] };
  let state = emptyDesktopState();
  expect(sectorViews(graph, state).b.blockedBy).toEqual(["First"]);
  state = setDone("gate", { confirmed: true, by: "human" })(state);
  const views = sectorViews(graph, state);
  expect(views.a.verified).toBe(true);
  expect(views.b.blockedBy).toEqual([]);
  expect(renderToStaticMarkup(createElement(SectorProgress, { value: views.a }))).toContain("Ověřeno");
  const html = renderToStaticMarkup(createElement(SectorGateEditor, { sector: graph.nodes[0], graph, disabled: false, save: () => {} }));
  expect(html).toContain('value="gate"');
  expect(html).not.toContain('value="b"');
});
