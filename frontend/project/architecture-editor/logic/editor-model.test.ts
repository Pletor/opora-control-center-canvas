import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph, PageSite } from "@/shared/types/logic/types";
import { architectureEditorId, canRemoveEditorEdge, createEditorElementPlan, scanLogicPlan, editorScopeNode, isEditorScopeClosed, setEditorEdgeCarries, setEditorNodeSection, setEditorPageLayout, setEditorPageSite, validateEditorRoute } from "./editor-model";

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
  it("prvek z palety je uzel s druhem pod stránkou a českým názvem", () => {
    expect(createEditorElementPlan("page", "service")).toEqual({ nodes: [{ ref: "element", kind: "node", parent: "@page", name: "Služba", purpose: "", element: { kind: "service" } }] });
    expect(() => createEditorElementPlan("@page", "form")).toThrow();
  });
  it("prvek logiky do boxu nese card.section, celá stránka ho nemá", () => {
    expect(createEditorElementPlan("page", "actor", "vyzva").nodes[0]).toMatchObject({ name: "Uživatel", element: { kind: "actor" }, card: { section: "vyzva" } });
    expect(createEditorElementPlan("page", "action").nodes[0]).not.toHaveProperty("card");
    expect(() => createEditorElementPlan("page", "action", "bad id")).toThrow();
  });
});

describe("edge carries", () => {
  const linked = (): Graph => ({ ...graph(), edges: [...graph().edges, { id: "n1", source: "page", target: "child", port: "next" }] });
  it("sets, replaces and clears carries only on next edges", () => {
    const set = setEditorEdgeCarries(linked(), "n1", "navigation");
    expect(set.edges[1]).toEqual({ id: "n1", source: "page", target: "child", port: "next", carries: "navigation" });
    expect(setEditorEdgeCarries(set, "n1", "navigation")).toBe(set);
    expect(setEditorEdgeCarries(set, "n1", "data").edges[1].carries).toBe("data");
    expect(setEditorEdgeCarries(set, "n1", null).edges[1]).toEqual({ id: "n1", source: "page", target: "child", port: "next" });
  });
  it("refuses other ports and missing edges", () => {
    expect(() => setEditorEdgeCarries(linked(), "existing", "data")).toThrow("jen vazba next");
    expect(() => setEditorEdgeCarries(linked(), "gone", "data")).toThrow();
  });
  it("odebrat jde jen nakreslenou vazbu next nebo flow", () => {
    expect(canRemoveEditorEdge({ port: "next" })).toBe(true);
    expect(canRemoveEditorEdge({ port: "flow" })).toBe(true);
    expect(canRemoveEditorEdge({})).toBe(true);
    expect(canRemoveEditorEdge({ port: "rule" })).toBe(false);
  });
});

describe("sekce stránky u komponenty", () => {
  it("zapíše a zruší card.section, ostatní pole karty zachová", () => {
    const set = setEditorNodeSection(graph(), "page", "form");
    expect(set.nodes[1].card).toEqual({ layer: "frontend", status: "draft", section: "form" });
    expect(setEditorNodeSection(set, "page", "form")).toBe(set);
    expect(setEditorNodeSection(set, "page", null).nodes[1].card).toEqual({ layer: "frontend", status: "draft" });
    const child = setEditorNodeSection(graph(), "child", "hero");
    expect(child.nodes[2].card).toEqual({ section: "hero" });
    expect("card" in setEditorNodeSection(child, "child", null).nodes[2]).toBe(false);
  });
  it("odmítne chybějící prvek, ne-uzel a neplatné id", () => {
    expect(() => setEditorNodeSection(graph(), "nic", "form")).toThrow("neexistuje");
    expect(() => setEditorNodeSection(graph(), "app", "form")).toThrow("jen uzel");
    expect(() => setEditorNodeSection(graph(), "child", "s/1")).toThrow("Neplatné id");
  });
});

describe("záměr a sekce stránky z Detailu prvku", () => {
  const page = (g: Graph) => g.nodes[1];
  it("uloží cíl a sekce s moves oříznuté, cestu stránky nechá a ostatní pole uzlu zachová", () => {
    const base = graph();
    const next = setEditorPageSite(base, page(base), { kind: "page", path: "/jinam", goal: "  Poptávka ", feel: "  ",
      sections: [{ id: "form", role: "form", name: " Formulář ", intent: "", moves: "  Rozptýlí obavu ze spamu. " }] });
    expect(page(next).site).toEqual({ kind: "page", path: "/", goal: "Poptávka",
      sections: [{ id: "form", role: "form", name: "Formulář", intent: "", moves: "Rozptýlí obavu ze spamu." }] });
    expect(page(next).card).toEqual(page(base).card);
    expect(next.nodes.filter((item) => item.id !== "page")).toEqual(base.nodes.filter((item) => item.id !== "page"));
    expect(setEditorPageSite(next, page(next), structuredClone(page(next).site) as PageSite)).toBe(next);
    const cleared = setEditorPageSite(next, page(next), { kind: "page", path: "/", goal: "Poptávka", sections: [{ id: "form", role: "form", name: "Formulář", intent: "", moves: " " }] });
    expect(page(cleared).site).toEqual({ kind: "page", path: "/", goal: "Poptávka", sections: [{ id: "form", role: "form", name: "Formulář", intent: "" }] });
  });
  it("odmítne souběžnou změnu stránky, chybějící stránku a prvek, který stránkou není", () => {
    const base = graph();
    const stale = page(base);
    const changed = { ...base, nodes: base.nodes.map((item) => item.id === "page" ? { ...item, site: { kind: "page" as const, path: "/", feel: "klidně" } } : item) };
    expect(() => setEditorPageSite(changed, stale, { kind: "page", path: "/", goal: "Cíl" })).toThrow("mezitím změnila");
    expect(() => setEditorPageSite(base, { ...stale, id: "nic" }, { kind: "page", path: "/" })).toThrow("neexistuje");
    expect(() => setEditorPageSite(base, base.nodes[2], { kind: "page", path: "/" })).toThrow("jen stránka");
  });
});

describe("layout stránky", () => {
  const withSections = (): Graph => {
    const original = graph();
    original.nodes[1] = { ...original.nodes[1], site: { kind: "page", path: "/", sections: [
      { id: "head", role: "header", name: "Hlavička", intent: "", box: { x: 0, y: 0, w: 12, h: 2 } },
      { id: "cta", role: "cta", name: "Výzva", intent: "", box: { x: 0, y: 0, w: 6, h: 2 }, parent: "head" },
    ] } };
    original.nodes[2] = { ...original.nodes[2], element: { kind: "action" }, card: { section: "cta", layer: "frontend" } };
    return original;
  };
  it("uloží box a parent a prvkům odebraného boxu smaže sekci jednou změnou", () => {
    const { graph: next, touched } = setEditorPageLayout(withSections(), "page", [{ id: "head", role: "header", name: "Hlavička", intent: "", box: { x: 0, y: 0, w: 12, h: 3 } }]);
    expect(next.nodes[1].site).toEqual({ kind: "page", path: "/", sections: [{ id: "head", role: "header", name: "Hlavička", intent: "", box: { x: 0, y: 0, w: 12, h: 3 } }] });
    expect(touched).toEqual(["child"]);
    expect(next.nodes[2].card).toEqual({ layer: "frontend" });
  });
  it("prázdný layout vynechá klíč sections a stránku bez site odmítne", () => {
    expect(setEditorPageLayout(withSections(), "page", []).graph.nodes[1].site).toEqual({ kind: "page", path: "/" });
    expect(() => setEditorPageLayout(withSections(), "child", [])).toThrow();
  });
});

describe("prvky logiky ze skenu", () => {
  it("jeden plán s druhem, názvem, účelem a boxem; bez boxu celá stránka", () => {
    expect(scanLogicPlan("page", [{ kind: "action", name: "Koupit", purpose: "Platba", section: "cta" }, { kind: "actor", name: "Člen", purpose: "", section: null }])).toEqual({ nodes: [
      { ref: "logic-0", kind: "node", parent: "@page", name: "Koupit", purpose: "Platba", element: { kind: "action" }, card: { section: "cta" } },
      { ref: "logic-1", kind: "node", parent: "@page", name: "Člen", purpose: "", element: { kind: "actor" } },
    ] });
    expect(() => scanLogicPlan("bad id", [])).toThrow();
    expect(() => scanLogicPlan("page", [{ kind: "action", name: "x", purpose: "", section: "bad id" }])).toThrow("sekce");
  });
});
