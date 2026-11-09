import { describe, expect, it } from "vitest";
import { buildCreated, canCreate, emptyCreateForm } from "./create-form";
import { ELEMENT_GROUPS, withElementKind } from "./element-palette";
import type { CanvasNode } from "@/shared/types/logic/types";

const ctx = { ancestorSector: null, targetSector: null, legacyFree: false };

describe("application element palette", () => {
  it("creates every offered role as a persistent element without making it a task", () => {
    for (const group of ELEMENT_GROUPS) for (const elementKind of group.kinds) {
      const form = { ...emptyCreateForm("node"), name: "Identity", elementKind, origin: "concept" as const, purpose: "Isolate organizations" };
      expect(canCreate(form, ctx)).toBe(true);
      const { node } = buildCreated(form, ctx, { parent: null, nodes: [], id: "identity" });
      expect(node.element).toEqual({ kind: elementKind });
      expect(node.id).toBe("identity");
      expect(node).not.toHaveProperty("card.type");
      expect(node).not.toHaveProperty("sourceRef");
    }
  });

  it("keeps identity, hierarchy, source and card when changing a role", () => {
    const node: CanvasNode = { id: "stable", parentId: "parent", kind: "node", name: "Identity", purpose: "", x: 0, y: 0,
      element: { kind: "service" }, card: { layer: "backend" }, sourceRef: { kind: "file", origin: "planned", path: "identity.py" } };
    const changed = withElementKind(node, "entity");
    expect(changed).toEqual({ ...node, element: { kind: "entity" } });
    expect(node.element).toEqual({ kind: "service" });
    const cleared = withElementKind(changed, "");
    expect(cleared).not.toHaveProperty("element");
    expect(cleared.id).toBe(node.id);
    expect(cleared.sourceRef).toEqual(node.sourceRef);
    expect(cleared.card).toEqual(node.card);
  });
});
