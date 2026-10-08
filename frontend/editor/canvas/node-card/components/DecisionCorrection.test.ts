import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { upstreamRows } from "../logic/upstream";
import CardUpstream from "./CardUpstream";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

it("warns downstream cards and distinguishes superseded assumptions", () => {
  const graph = { nodes: [{ id: "source", name: "Research" }, { id: "target", name: "Task" }],
    edges: [{ id: "e", source: "source", target: "target", port: "block" }] } as Graph;
  const state = { nodes: {}, decisions: [
    { id: "old", nodeId: "source", text: "Empty DB" },
    { id: "new", nodeId: "source", text: "RLS hides rows", supersedes: "old" },
  ] } as DesktopState;
  const rows = upstreamRows(graph, state, "target");
  expect(rows[0].assumptionChanged).toBe(true);
  expect(rows[0].details).toContain("Nahrazeno: Empty DB");
  expect(rows[0].details).toContain("Oprava: RLS hides rows");
  expect(renderToStaticMarkup(createElement(CardUpstream, { rows, open: () => {} }))).toContain("Předpoklad se změnil");
  expect(upstreamRows(graph, state, "source")).toEqual([]);
});
