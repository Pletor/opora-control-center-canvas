import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { catalogEdges, catalogPlacement, catalogPlan } from "./catalog-plan";
import { CATALOG_ITEMS, itemById } from "./library-catalog";
import { CATALOG_FAMILIES } from "./catalog-families";

const node = (id: string, kind: CanvasNode["kind"], parentId: string | null = null): CanvasNode => ({ id, kind, parentId, name: id, purpose: "", x: 0, y: 0 });

describe("catalog component insertion", () => {
  it("distinguishes nesting, geometric area membership and current-layer insertion", () => {
    const nodes = [node("sector", "sector"), node("child", "node", "sector"), node("area", "area", "sector"), node("note", "comment")];
    expect(catalogPlacement(nodes, "sector", "child", { x: 81, y: 95 })).toEqual({ parentId: "child" });
    expect(catalogPlacement(nodes, null, "sector", { x: 81, y: 95 })).toEqual({ parentId: "sector" });
    expect(catalogPlacement(nodes, "sector", "area", { x: 81.4, y: 95.9 })).toEqual({ parentId: "area", position: { x: 81, y: 96 } });
    expect(catalogPlacement(nodes, "sector", null)).toEqual({ parentId: "sector" });
    expect(() => catalogPlacement(nodes, null, "note")).toThrow();
    expect(() => catalogPlacement(nodes, null, "missing")).toThrow();
  });

  it("copies the canonical specification without a second checklist or expanded blocks", () => {
    const item = itemById("fe-button")!;
    const snapshot = JSON.stringify(item);
    const saved = catalogPlan(item, { parentId: "sector" }).nodes[0];
    expect(saved.parent).toBe("@sector");
    expect(saved.spec).toEqual({ goal: item.purpose, non_goals: "", acceptance: item.done.join("\n") });
    expect(saved.card).toEqual({ status: "draft", layer: "frontend", states: item.states, fill: item.fill });
    expect(saved).not.toHaveProperty("criteria");
    expect(saved.blocks).toEqual([]);
    expect(saved.text).toContain("## Souvisí s");
    expect(saved.rules).toEqual(item.invariants);
    expect(JSON.stringify(item)).toBe(snapshot);
  });

  it("retains full old template context and does not mislabel infrastructure as library", () => {
    const item = CATALOG_ITEMS.find((entry) => entry.template && entry.steps?.length)!;
    const saved = catalogPlan(item, { parentId: null, position: { x: 12, y: 34 } }).nodes[0];
    expect(saved.text).toContain(item.template);
    for (const step of item.steps!) expect(saved.text).toContain(step.text);
    expect(saved.position).toEqual({ x: 12, y: 34 });
    expect(catalogPlan(itemById("infra-deployment")!, { parentId: null }).nodes[0].card).not.toHaveProperty("layer");
    for (const item of CATALOG_ITEMS) expect(CATALOG_FAMILIES.filter((family) => family.categories.includes(item.category))).toHaveLength(1);
  });

  it("skládá kartu z kontextu pro agenta bez modelu: tech, stavy, fetch a fill; porty jsou v textu", () => {
    const item = itemById("fe-form-validated")!;
    const plan = catalogPlan(item, { parentId: "page" });
    const saved = plan.nodes[0];
    expect(saved.card).toEqual({
      status: "draft", layer: "frontend", tech: item.tech, states: item.states,
      fetch: { files: item.fetch!.files, docs: item.fetch!.docs }, fill: item.fill,
    });
    expect(saved.text).toContain(["## Porty", "- vstup `otevreni`: navigation", "- výstup `odeslani`: command"].join("\n"));
    expect(plan).not.toHaveProperty("edges");
    expect(catalogPlan(item, { parentId: "page" })).toEqual(plan);
  });

  it("prázdné seznamy fetch se vynechají, položka bez kontextu kartu nemění", () => {
    const item = { ...itemById("fe-button")!, fetch: { files: [], docs: ["docs/a.md"] } };
    expect(catalogPlan(item, { parentId: null }).nodes[0].card.fetch).toEqual({ docs: ["docs/a.md"] });
    const bare = itemById("infra-deployment")!;
    expect(catalogPlan(bare, { parentId: null }).nodes[0].card).toEqual({ status: "draft" });
  });

  it("cílené vložení navrhne jednu vazbu next s carries z portu, bez cíle žádnou", () => {
    const item = itemById("fe-form-validated")!;
    expect(catalogEdges(item, "component")).toEqual([]);
    expect(catalogEdges(item, "component", { nodeId: "nav", side: "source" })).toEqual([{ from: "@nav", to: "component", port: "next", carries: "navigation" }]);
    expect(catalogEdges(item, "component", { nodeId: "api", side: "target" })).toEqual([{ from: "component", to: "@api", port: "next", carries: "command" }]);
    expect(catalogEdges(itemById("db-query")!, "component", { nodeId: "x", side: "target" })).toEqual([{ from: "component", to: "@x", port: "next" }]);
    const plan = catalogPlan(item, { parentId: "page" }, { nodeId: "api", side: "target" });
    expect(plan.edges).toEqual([{ from: "component", to: "@api", port: "next", carries: "command" }]);
  });
});
