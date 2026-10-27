import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { buildStudioTree, cardInLevel, sectionItemId, studioDescendants, studioTrail } from "./studio-tree";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id.toUpperCase(), purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [{ name: "Vývoj", host: "web.dev" }] } }),
  node("folder", "web", { kind: "sector" }),
  node("home", "folder", { site: { kind: "page", path: "/", sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "" }, { id: "form", role: "form", name: "Formulář", intent: "" }] } }),
  node("sub", "home", { site: { kind: "page", path: "/sub" } }),
  node("area", "home", { kind: "area" }),
  node("form-card", "area", { card: { section: "form" } }),
  node("loose", "home", { card: { section: "gone" } }),
  node("child", "form-card"),
  node("subcomp", "sub"),
  node("api", "web"),
  node("orphan", null),
], edges: [] };

describe("studio tree", () => {
  const tree = buildStudioTree(graph);

  it("puts domains on the project level and skips page folders and nodes outside a domain", () => {
    expect(tree.children.get(null)).toEqual(["web"]);
    expect(tree.items.has("folder")).toBe(false);
    expect(tree.items.has("orphan")).toBe(false);
    expect(tree.children.get("web")).toEqual(["home", "api"]);
  });

  it("builds sections from site.sections first and assigns components by card.section through areas", () => {
    expect(tree.children.get("home")).toEqual([sectionItemId("home", "hero"), sectionItemId("home", "form"), "sub", "loose"]);
    expect(tree.parent.get("form-card")).toBe(sectionItemId("home", "form"));
    expect(tree.items.get(sectionItemId("home", "form"))).toMatchObject({ kind: "section", name: "Formulář", pageId: "home", domainId: "web", node: null });
    expect(tree.items.get("loose")).toMatchObject({ kind: "component", unsectioned: true, pageId: "home" });
    expect(tree.parent.get("child")).toBe("form-card");
  });

  it("keeps components of a page without sections directly on the page, not grouped", () => {
    expect(tree.parent.get("subcomp")).toBe("sub");
    expect(tree.items.get("subcomp")?.unsectioned).toBeUndefined();
    expect(tree.items.get("sub")).toMatchObject({ kind: "page", pageId: "sub", domainId: "web" });
  });

  it("walks the trail, descendants and the card of a level", () => {
    expect(studioTrail(tree, "child").map((item) => item.id)).toEqual(["web", "home", sectionItemId("home", "form"), "form-card", "child"]);
    expect(studioTrail(tree, "missing")).toEqual([]);
    expect(studioDescendants(tree, "sub").map((item) => item.id)).toEqual(["subcomp"]);
    expect(cardInLevel(tree, "web", "child")).toBe("home");
    expect(cardInLevel(tree, "home", "child")).toBe(sectionItemId("home", "form"));
    expect(cardInLevel(tree, "sub", "child")).toBeNull();
  });
});
