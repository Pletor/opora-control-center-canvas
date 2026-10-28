import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph, NodeSpec } from "@/shared/types/logic/types";
import { buildStudioTree } from "../../logic/studio-tree";
import { elementView } from "./element-view";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id.toUpperCase(), purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = {
  nodes: [
    node("web", null, { kind: "sector", site: { kind: "application", environments: [{ name: "prod", host: "web.cz" }] } as never }),
    node("a", "web", { site: { kind: "page", path: "/a", sections: [{ id: "hero", role: "hero", name: "Hero" }] } as never }),
    node("b", "web", { site: { kind: "page", path: "/b" } }),
    node("a1", "a", { sourceRef: { origin: "planned", path: "src/a1.tsx", kind: "file" } }),
  ],
  edges: [{ id: "e1", source: "a1", target: "b", carries: "navigation" }],
};
const tree = buildStudioTree(graph);
const NOW = Date.parse("2026-10-28T10:00:00Z");
const spec = { status: "ready", spec: { fields: { goal: "Cíl", non_goals: "", acceptance: "", steps: [{ id: "s1", order: 1, title: "Model", acceptance: [], dependsOn: [] }] }, available: true } as unknown as NodeSpec } as const;
const base = { graph, spec, card: null, phase: "build" as const, done: false, now: NOW };

describe("elementView", () => {
  it("komponenta: kontext agenta, práce ze zadání a přímé vazby", () => {
    const view = elementView({ ...base, item: tree.items.get("a1")! })!;
    expect(view.nodeId).toBe("a1");
    expect(view.context).toMatchObject({ environment: "prod", host: "web.cz", page: { id: "a", name: "A" }, componentPath: ["A1"], repo: { kind: "planned", path: "src/a1.tsx" } });
    expect(view.work.connected).toBe(false);
    expect(view.work.steps?.map((row) => row.id)).toEqual(["s1"]);
    expect(view.links?.outgoing).toEqual([{ edgeId: "e1", otherId: "b", otherName: "B", port: "next", carries: "navigation" }]);
    expect(view.links?.incoming).toEqual([]);
    expect(view.phase).toBe("build");
  });

  it("stránka a doména nemají přímé vazby (Studio ukáže souhrnné vazby úrovně)", () => {
    expect(elementView({ ...base, item: tree.items.get("a")! })?.links).toBeNull();
    expect(elementView({ ...base, item: tree.items.get("web")! })?.context.host).toBe("web.cz");
  });

  it("sekce bez uzlu grafu žádný Detail prvku nemá", () => {
    const section = [...tree.items.values()].find((item) => item.kind === "section")!;
    expect(elementView({ ...base, item: section })).toBeNull();
  });

  it("nenačtené zadání: práce bez kroků", () => {
    expect(elementView({ ...base, spec: { status: "loading" }, item: tree.items.get("a1")! })?.work.steps).toBeNull();
  });
});
