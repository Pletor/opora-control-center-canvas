import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { buildStudioTree } from "../../logic/studio-tree";
import { levelOf } from "../../logic/studio-level";
import { cardStatus, type StudioFacts } from "../../logic/studio-status";
import { detailHoles, detailLinks, detailView } from "./detail-model";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id.toUpperCase(), purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = {
  nodes: [
    node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
    node("a", "web", { purpose: "Vstup", site: { kind: "page", path: "/a" } }), node("b", "web", { site: { kind: "page", path: "/b" } }), node("a1", "a"),
  ],
  edges: [{ id: "e1", source: "a1", target: "b", carries: "navigation" }, { id: "e2", source: "a", target: "b", carries: "navigation" }],
};
const tree = buildStudioTree(graph);
const facts: StudioFacts = { done: new Set(["a"]), building: new Set(), holes: new Map([["a", ["bez cíle"]], ["a1", ["bez stavu"]]]), journeys: [
  { id: "j", name: "Kampaň", domainId: "web", pages: new Set(["a"]), derived: { applicationId: "web", id: "j", missing: [], segments: [], lastRun: { at: "2026-10-27T10:00:00Z", passed: true, stale: false, command: "npm run journey", failed: 0 } } },
] };

describe("detail model", () => {
  const level = levelOf(tree, graph, "web");

  it("lists links of the card, or all links of the open level", () => {
    expect(detailLinks(tree, level.links, "a", false)).toEqual([{ id: "a->b", from: "A", to: "B", count: 2, carries: "navigation", flow: "Navigace" }]);
    expect(detailLinks(tree, level.links, "web", true)).toHaveLength(1);
    expect(detailLinks(tree, level.links, "zzz", false)).toEqual([]);
  });

  it("collects holes of the card and everything below with the place name", () => {
    expect(detailHoles(tree, tree.items.get("a")!, facts)).toEqual([{ place: "A", message: "bez cíle" }, { place: "A1", message: "bez stavu" }]);
  });

  it("builds the read-only detail with state, journeys badge and editor link", () => {
    const item = tree.items.get("a")!;
    const view = detailView({ tree, item, status: cardStatus(tree, item, facts), facts, links: level.links, focus: false, project: "p", workspace: "w" });
    expect(view).toMatchObject({ name: "A", kindLabel: "Stránka", subtitle: "/a", purpose: "Vstup", state: "hole", stateLabel: "díra", summary: "0/1 stojí" });
    expect(view.journeys).toEqual([{ id: "j", name: "Kampaň", badge: expect.objectContaining({ tone: "ok", text: "Ověřeno" }), title: expect.stringContaining("Ověřeno") }]);
    expect(view.editor).toEqual({ label: "Otevřít v Editoru stránky", params: expect.objectContaining({ domainId: "web", pageId: "a" }) });
  });
});
