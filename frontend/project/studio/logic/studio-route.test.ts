import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { architectureEditorId } from "@/project/architecture-editor/logic/editor-model";
import { buildStudioTree, sectionItemId } from "./studio-tree";
import { editorLabel, editorParams, focusUp, readStudioFocus, withStudioFocus } from "./studio-route";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({ id, parentId, name: id, purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = { nodes: [
  node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
  node("home", "web", { site: { kind: "page", path: "/", sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "" }] } }),
  node("c1", "home", { card: { section: "hero" } }), node("api", "web"),
], edges: [] };
const tree = buildStudioTree(graph);
const item = (id: string) => tree.items.get(id)!;

describe("studio route", () => {
  it("reads only known focus ids and writes the focus without touching other parameters", () => {
    expect(readStudioFocus(new URLSearchParams("studioFocus=home"), tree)).toBe("home");
    expect(readStudioFocus(new URLSearchParams("studioFocus=gone"), tree)).toBeNull();
    expect(withStudioFocus(new URLSearchParams("project=p&studioFocus=x"), "home").toString()).toBe("project=p&studioFocus=home");
    expect(withStudioFocus(new URLSearchParams("project=p&studioFocus=x"), null).toString()).toBe("project=p");
  });

  it("links a card to the architecture editor: domain map, page editor or page with the selected component", () => {
    const domainEditor = architectureEditorId("p", "w", "web");
    expect(editorParams(item("web"), "p", "w")).toEqual({ editorId: domainEditor, domainId: "web" });
    expect(editorParams(item("home"), "p", "w")).toEqual({ editorId: domainEditor, domainId: "web", pageId: "home" });
    expect(editorParams(item(sectionItemId("home", "hero")), "p", "w")).toEqual({ editorId: domainEditor, domainId: "web", pageId: "home" });
    expect(editorParams(item("c1"), "p", "w")).toEqual({ editorId: domainEditor, domainId: "web", pageId: "home", architectureNode: "c1" });
    expect(editorParams(item("api"), "p", "w")).toEqual({ editorId: domainEditor, domainId: "web" });
    expect(editorLabel(item("web"))).toBe("Otevřít mapu domény");
    expect(editorLabel(item("c1"))).toBe("Otevřít v Editoru stránky");
  });

  it("goes up one level and stays on the project level", () => {
    expect(focusUp(tree, "c1")).toBe(sectionItemId("home", "hero"));
    expect(focusUp(tree, "web")).toBeNull();
    expect(focusUp(tree, null)).toBeNull();
  });
});
