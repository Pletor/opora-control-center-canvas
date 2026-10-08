import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { effectiveRules } from "./effective-rules";
import { emptyDesktopState, emptyNodeWorkflow } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";
import InheritedRules from "../components/InheritedRules";

it("shows project, path, ancestor and local rules without sibling leakage", () => {
  const graph: Graph = { nodes: [
    { id: "s", parentId: null, kind: "sector", name: "Sektor", purpose: "", x: 0, y: 0 },
    { id: "n", parentId: "s", kind: "node", name: "Karta", purpose: "", x: 0, y: 0,
      sourceRef: { origin: "planned", path: "backend/api.py", kind: "file" } },
  ], edges: [] };
  const state = emptyDesktopState();
  state.rules = [
    { id: "p", text: "Project rule", kind: "must", scope: "project", target: "" },
    { id: "path", text: "Path rule", kind: "must", scope: "path", target: "backend" },
    { id: "wrong-path", text: "Wrong path", kind: "must", scope: "path", target: "back" },
    { id: "sibling", text: "Sibling", kind: "must", scope: "node", target: "other" },
  ];
  state.nodes.s = { ...emptyNodeWorkflow(), rules: [{ id: "r", kind: "must_not", text: "Sector prohibition" }] };
  state.nodes.n = { ...emptyNodeWorkflow(), rules: [{ id: "r", kind: "must", text: "Own rule" }] };
  const rows = effectiveRules(graph, state, "n");
  expect(rows.map((row) => row.origin.scope)).toEqual(["project", "path", "sector", "card"]);
  expect(rows.map((row) => row.inherited)).toEqual([true, true, true, false]);
  const html = renderToStaticMarkup(createElement(InheritedRules, { rules: rows }));
  expect(html).toContain("Sektor: Sektor");
  expect(html).toContain("Cesta: backend");
  expect(html).toContain("zděděné");
  expect(html).not.toContain("Sibling");
});
