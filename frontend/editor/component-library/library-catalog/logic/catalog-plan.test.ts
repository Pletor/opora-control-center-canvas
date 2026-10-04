import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { catalogPlacement, catalogPlan } from "./catalog-plan";
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
    expect(saved.card).toEqual({ status: "draft", layer: "frontend" });
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
});
