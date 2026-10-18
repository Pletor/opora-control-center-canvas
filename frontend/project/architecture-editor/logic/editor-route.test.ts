import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { architectureEditorId } from "./editor-model";
import { resolveEditorRoute } from "./editor-route";

const node = (id: string, parentId: string | null = null): CanvasNode => ({ id, parentId, name: id, purpose: "", kind: "node", x: 0, y: 0 });
const graph: Graph = { nodes: [
  { ...node("app"), kind: "sector", site: { kind: "application", environments: [{ name: "Produkce", host: "app.example.cz" }] } },
  { ...node("home", "app"), site: { kind: "page", path: "/" } },
  node("card", "home"),
  { ...node("other"), kind: "sector", site: { kind: "application", environments: [{ name: "Vývoj", host: "app.example.dev" }] } },
], edges: [] };
const route = (values: Record<string, string>) => new URLSearchParams(values);

describe("editor route", () => {
  it("opens the landing without parameters", () => {
    expect(resolveEditorRoute(graph, route({}), "p", "main")).toEqual({ domainId: null, pageId: null, selectedId: null, structureId: null });
  });

  it("keeps domain, page, selection and structure from the link", () => {
    const editorId = architectureEditorId("p", "w1", "app");
    expect(resolveEditorRoute(graph, route({ editorId, domainId: "app", pageId: "home", architectureNode: "card", structureNode: "card" }), "p", "w1"))
      .toEqual({ domainId: "app", pageId: "home", selectedId: "card", structureId: "card" });
  });

  it("derives the domain from a page and rejects foreign or invalid links", () => {
    expect(resolveEditorRoute(graph, route({ pageId: "home" }), "p", "main").domainId).toBe("app");
    expect(() => resolveEditorRoute(graph, route({ domainId: "" }), "p", "main")).toThrow("platné ID domény");
    expect(() => resolveEditorRoute(graph, route({ domainId: "other", pageId: "home" }), "p", "main")).toThrow("nepatří k doméně");
    expect(() => resolveEditorRoute(graph, route({ domainId: "app", editorId: architectureEditorId("p", "main", "other") }), "p", "main")).toThrow();
  });
});
