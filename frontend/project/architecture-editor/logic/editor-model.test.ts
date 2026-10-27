import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { architectureEditorId, connectEditorNodes, createEditorAreaPlan, editorScopeNode, isEditorScopeClosed, growEditorArea, moveEditorNode, resizeEditorNode, validateEditorRoute } from "./editor-model";

const node = (id: string, parentId: string | null = null, kind: CanvasNode["kind"] = "node"): CanvasNode => ({ id, parentId, kind, name: id, purpose: "Účel", x: 20, y: 40 });
const graph = (): Graph => ({ nodes: [
  { ...node("app", null, "sector"), site: { kind: "application", environments: [] } },
  { ...node("page", "app"), site: { kind: "page", path: "/" }, sourceRef: { origin: "planned", path: "home.tsx", kind: "file" }, card: { layer: "frontend", status: "draft" }, blockOffsets: { action: { dx: 40, dy: 50 } } },
  node("child", "page"), node("other"), node("note", null, "comment"),
  { ...node("area", null, "area"), size: { w: 720, h: 480 }, color: "teal" },
], edges: [{ id: "existing", source: "other", target: "page", port: "rule" }] });

describe("standalone architecture editor identity", () => {
  it("is stable and encodes scope segments without delimiter collisions", () => {
    expect(architectureEditorId("project", "draft")).toBe("opora:architecture:v1:project:draft");
    expect(architectureEditorId("a:b", "c")).not.toBe(architectureEditorId("a", "b:c"));
    expect(architectureEditorId("a%3Ab", "c")).not.toBe(architectureEditorId("a:b", "c"));
    expect(architectureEditorId("Projekt Ž", "main/one")).toBe("opora:architecture:v1:Projekt%20%C5%BD:main%2Fone");
    expect(() => architectureEditorId("", "draft")).toThrow();
  });
  it("accepts an omitted identity or exact identity and rejects another editor scope", () => {
    const id = architectureEditorId("one", "main");
    expect(validateEditorRoute(null, "one", "main")).toBe(id);
    expect(validateEditorRoute(id, "one", "main")).toBe(id);
    for (const supplied of ["", architectureEditorId("two", "main"), architectureEditorId("one", "draft"), "opora:architecture:v0:one:main"]) {
      expect(() => validateEditorRoute(supplied, "one", "main")).toThrow();
    }
  });
  it("gives domains separate durable identities while retaining legacy project editor links", () => {
    const legacy = architectureEditorId("project", "draft");
    const first = architectureEditorId("project", "draft", "prod");
    const second = architectureEditorId("project", "draft", "dev");
    expect(first).toBe(`${legacy}:domain:prod`);
    expect(first).not.toBe(second);
    expect(validateEditorRoute(null, "project", "draft", "prod")).toBe(first);
    expect(validateEditorRoute(first, "project", "draft", "prod")).toBe(first);
    expect(() => validateEditorRoute(second, "project", "draft", "prod")).toThrow();
    expect(() => validateEditorRoute(legacy, "project", "draft", "prod")).toThrow();
    expect(() => architectureEditorId("project", "draft", "")).toThrow();
    expect(architectureEditorId("p", "w", "a:b")).toBe("opora:architecture:v1:p:w:domain:a%3Ab");
  });
});

describe("whole graph patches", () => {
  it("moves a card without losing metadata, edges or unrelated branches and does not mutate input", () => {
    const original = graph();
    const before = structuredClone(original);
    const moved = moveEditorNode(original, "page", -10, 200);
    expect(moved.nodes[1]).toEqual({ ...original.nodes[1], x: -10, y: 200 });
    expect(moved.nodes[0]).toBe(original.nodes[0]);
    expect(moved.nodes[3]).toBe(original.nodes[3]);
    expect(moved.edges).toBe(original.edges);
    expect(original).toEqual(before);
    expect(moveEditorNode(original, "area", 0, 0).nodes[5]).toEqual({ ...original.nodes[5], x: 0, y: 0 });
  });
  it("rejects missing cards and invalid coordinates", () => {
    expect(() => moveEditorNode(graph(), "missing", 0, 0)).toThrow();
    for (const value of [NaN, Infinity, -Infinity, 1_000_001]) expect(() => moveEditorNode(graph(), "page", value, 0)).toThrow();
  });
  it("moves an area with its geometric members, preserving nested layer coordinates", () => {
    const original = graph();
    const moved = moveEditorNode(original, "area", 120, 140);
    expect(moved.nodes[0]).toEqual({ ...original.nodes[0], x: 120, y: 140 });
    expect(moved.nodes[3]).toEqual({ ...original.nodes[3], x: 120, y: 140 });
    expect(moved.nodes[1]).toBe(original.nodes[1]);
    expect(moved.nodes[2]).toBe(original.nodes[2]);
    expect(original.nodes[0].x).toBe(20);
  });
  it("resizes only an area, clamped to the canvas limits, and keeps other nodes by reference", () => {
    const original = graph();
    const resized = resizeEditorNode(original, "area", 1368.4, 900);
    expect(resized.nodes[5]).toEqual({ ...original.nodes[5], size: { w: 1368, h: 900 } });
    expect(resized.nodes[0]).toBe(original.nodes[0]);
    expect(resized.edges).toBe(original.edges);
    expect(original.nodes[5].size).toEqual({ w: 720, h: 480 });
    expect(resizeEditorNode(original, "area", 10, 50_000).nodes[5].size).toEqual({ w: 120, h: 20000 });
    expect(resizeEditorNode(original, "area", 720, 480)).toBe(original);
    expect(() => resizeEditorNode(original, "page", 500, 500)).toThrow("jen oblasti");
    expect(() => resizeEditorNode(original, "missing", 500, 500)).toThrow();
    for (const value of [NaN, Infinity, 0, -5]) expect(() => resizeEditorNode(original, "area", value, 400)).toThrow();
  });
  it("adds a next edge while preserving existing rules and the full node array", () => {
    const original = graph();
    const result = connectEditorNodes(original, "other", "page", "next");
    expect(result.nodes).toBe(original.nodes);
    expect(result.edges).toEqual([...original.edges, { id: "next", source: "other", target: "page", port: "next" }]);
    expect(original.edges).toHaveLength(1);
    expect(connectEditorNodes(result, "page", "other", "reverse").edges).toHaveLength(3);
    expect(connectEditorNodes(original, "app", "page", "sector-link").edges).toHaveLength(2);
  });
  it("refuses self, missing, comment/area endpoints and duplicate identities or next links", () => {
    for (const [from, to, id] of [["page", "page", "new"], ["missing", "page", "new"], ["note", "page", "new"], ["page", "area", "new"], ["area", "other", "new"], ["other", "page", "existing"], ["other", "page", "bad id"]]) {
      expect(() => connectEditorNodes(graph(), from, to, id)).toThrow();
    }
    for (const port of [undefined, "next"] as const) {
      const original = graph();
      original.edges.push({ id: "legacy", source: "page", target: "child", ...(port ? { port } : {}) });
      expect(() => connectEditorNodes(original, "page", "child", "duplicate")).toThrow();
    }
  });
  it("connects two areas through flow and refuses duplicate flow links", () => {
    const original = graph();
    original.nodes.push({ ...node("second-area", null, "area"), size: { w: 720, h: 480 } });
    const linked = connectEditorNodes(original, "area", "second-area", "flow");
    expect(linked.edges.at(-1)).toEqual({ id: "flow", source: "area", target: "second-area", port: "flow" });
    expect(() => connectEditorNodes(linked, "area", "second-area", "duplicate")).toThrow();
  });
});

describe("scope and creation", () => {
  it("accepts root, application, page and ordinary nested scopes but rejects non-parents", () => {
    const original = graph();
    expect(editorScopeNode(original, null)).toBeNull();
    for (const id of ["app", "page", "child"]) expect(editorScopeNode(original, id)?.id).toBe(id);
    for (const id of ["missing", "area", "note", ""]) expect(() => editorScopeNode(original, id)).toThrow();
  });
  it("honors own and ancestor closures without locking unrelated branches", () => {
    const original = graph();
    expect(isEditorScopeClosed(original, "child", new Set(["app"]))).toBe(true);
    expect(isEditorScopeClosed(original, "page", new Set(["page"]))).toBe(true);
    expect(isEditorScopeClosed(original, "other", new Set(["app"]))).toBe(false);
    expect(isEditorScopeClosed(original, null, new Set(["app"]))).toBe(false);
    expect(() => isEditorScopeClosed(original, "missing", new Set())).toThrow();
    original.nodes[0].parentId = "child";
    expect(() => isEditorScopeClosed(original, "page", new Set())).toThrow("cyklus");
  });
  it("builds an existing atomic canvas-plan request without inventing another graph root", () => {
    expect(createEditorAreaPlan(null)).toEqual({ nodes: [{ ref: "area", kind: "area", parent: null, name: "Nová oblast", purpose: "", size: { w: 720, h: 480 } }] });
    expect(createEditorAreaPlan("page", " Obsah ").nodes[0]).toMatchObject({ parent: "@page", name: "Obsah" });
    expect(() => createEditorAreaPlan("@page")).toThrow();
    expect(() => createEditorAreaPlan("page.with.dot")).toThrow();
    expect(() => createEditorAreaPlan(null, " ")).toThrow();
  });
});

describe("growEditorArea", () => {
  it("posune a natáhne jen oblast, členy nechá na místě", () => {
    const original = graph();
    const grown = growEditorArea(original, { id: "area", x: -16, y: 40, w: 1000, h: 480 });
    expect(grown.nodes[5]).toMatchObject({ x: -16, y: 40, size: { w: 1000, h: 480 }, color: "teal" });
    expect(grown.nodes.slice(0, 5)).toEqual(original.nodes.slice(0, 5));
    expect(() => growEditorArea(original, { id: "page", x: 0, y: 0, w: 200, h: 200 })).toThrow();
  });
});
