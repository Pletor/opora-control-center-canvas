import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { upstreamRows } from "./upstream";
import CardUpstream from "../components/CardUpstream";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import { addBlock, addBlockPort, decideBlockPort } from "@/editor/node-detail/tree/logic/tree-model";
import type { Graph } from "@/shared/types/logic/types";

it("shows a direct upstream branch and never reverses the dependency", () => {
  let state = addBlock("source")(emptyDesktopState());
  const block = state.nodes.source.blocks![0];
  state = addBlockPort("source", block.id, "Storage")(state);
  const port = state.nodes.source.blocks![0].ports![0];
  state = decideBlockPort("source", block.id, port.id, "rejected", "Too slow")(state);
  const graph: Graph = { nodes: ["source", "target"].map(id => ({ id, name: id, parentId: null, kind: "node", purpose: "", x: 0, y: 0 })),
    edges: [{ id: "e", source: "source", target: "target", port: "block", sourceBlockId: block.id, sourcePortId: port.id }] };
  const rows = upstreamRows(graph, state, "target");
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ nodeId: "source", label: "Storage", rejected: true, details: "Too slow" });
  expect(upstreamRows(graph, state, "source")).toEqual([]);
  const html = renderToStaticMarkup(createElement(CardUpstream, { rows, open: () => {} }));
  expect(html).toContain("Zamítnutá větev z:");
  expect(html).toContain("Otevřít source");
  expect(html).toContain("Too slow");
});
