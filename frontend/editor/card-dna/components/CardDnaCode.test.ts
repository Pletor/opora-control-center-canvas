import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import CardDnaCode from "./CardDnaCode";

it("never renders a success mark for a planned empty path, even with an old present response", () => {
  const node: CanvasNode = { id: "n1", parentId: null, kind: "node", name: "DNA", purpose: "", x: 0, y: 0,
    sourceRef: { origin: "planned", path: "", kind: "directory" } };
  const status = { status: "present", path: "", origin: "planned" };
  const data = { view: {}, sourceStatus: status, realization: { status, disabled: true, save: async () => {} } } as unknown as NodeCardData;
  const html = renderToStaticMarkup(createElement(CardDnaCode, {node, data,
    state: { settings: [], rules: [], decisions: [], tickets: [], nodes: {} }, graph: {nodes:[],edges:[]} }));
  expect(html).toContain("cesta neurčena");
  expect(html).toContain("Cesta neurčena");
  expect(html).not.toContain("✓");
  expect(html).not.toContain("Cesta existuje");
});

it("renders honest status evidence and only a derived GitHub commit link", () => {
  const node: CanvasNode = { id: "n1", parentId: null, kind: "node", name: "DNA", purpose: "", x: 0, y: 0,
    sourceRef: { origin: "existing", path: "frontend/dna.tsx", kind: "file" },
    realization: { commit: "abcdef012345", prUrl: "https://github.com/acme/repo/pull/7", verifiedAt: "2026-10-08" } };
  const data = { view: { design: undefined }, sourceStatus: { status: "unavailable", path: "frontend/dna.tsx", origin: "existing" }, assignmentStatus: { status: "current", resultId: "r1" } } as unknown as NodeCardData;
  const props = { node, data, state: { settings: [], rules: [], decisions: [], tickets: [], nodes: {} } as DesktopState, graph: { nodes: [], edges: [] } as Graph };
  const html = renderToStaticMarkup(createElement(CardDnaCode, props));
  expect(html).toContain("nedostupný");
  expect(html).toContain("current");
  expect(html).toContain('href="https://github.com/acme/repo/commit/abcdef012345"');
  expect(html).not.toContain('href="https://github.com/acme/repo/pull/7"');
});
