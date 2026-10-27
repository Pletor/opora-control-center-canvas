import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { editProductNode, productFingerprint, productTree, sitePlan, type ProductDraft } from "./product-tree";

const node = (id: string, parentId: string | null, site?: CanvasNode["site"]): CanvasNode => ({
  id, parentId, kind: site?.kind === "application" ? "sector" : "node", name: id, purpose: "Smysl části", x: 20, y: 40, ...(site ? { site } : {}),
});

describe("product tree shares the graph", () => {
  it("projects nested pages through ordinary containers without duplicating production and development", () => {
    const app = node("app", "container", { kind: "application", environments: [{ name: "Produkce", host: "example.cz" }, { name: "Vývoj", host: "localhost:3000" }] });
    const page = node("home", "layout", { kind: "page", path: "/" });
    const subpage = node("detail", "page-content", { kind: "page", path: "/detail" });
    const graph = [node("container", null), app, node("layout", "app"), page, node("page-content", "home"), subpage];
    const roots = productTree(graph);
    expect(roots).toHaveLength(1);
    expect(roots[0].node).toBe(app);
    expect(roots[0].children).toHaveLength(1);
    expect(roots[0].children[0].node).toBe(page);
    expect(roots[0].children[0].children[0].node).toBe(subpage);
    expect(graph).toHaveLength(6);
  });
  it("keeps nested applications separate and tolerates old graphs without site metadata", () => {
    const one = node("one", null, { kind: "application", environments: [] });
    const two = node("two", "one", { kind: "application", environments: [] });
    expect(productTree([one, two, node("page", "two", { kind: "page", path: "/" })]).map((branch) => [branch.node.id, branch.children.length])).toEqual([["one", 0], ["two", 1]]);
    expect(productTree([node("old", null)])).toEqual([]);
  });
  it("creates a structural page with one purpose and no invented assignment or domain", () => {
    const draft: ProductDraft = { parentId: "app", name: " Home ", purpose: " Úvod webu ", site: { kind: "page", path: "/" } };
    const planned = sitePlan(draft).nodes[0];
    expect(planned).toMatchObject({ ref: "component", kind: "node", parent: "@app", name: "Home", purpose: "Úvod webu", site: { kind: "page", path: "/" } });
    expect(planned).not.toHaveProperty("spec");
    expect(planned).not.toHaveProperty("sourceRef");
    expect(sitePlan({ ...draft, parentId: null, site: { kind: "application", environments: [] } }).nodes[0].site).toEqual({ kind: "application", environments: [] });
  });
  it("edits in place and preserves the parent, identity, source and card fields", () => {
    const original = { ...node("page", "app", { kind: "page", path: "/" }), sourceRef: { origin: "planned" as const, kind: "file" as const, path: "frontend/home.tsx" }, card: { status: "draft" as const } };
    const draft: ProductDraft = { id: "page", original: productFingerprint(original), parentId: "wrong-parent", name: "Nový název", purpose: "Nový účel", site: { kind: "page", path: "/new" } };
    expect(editProductNode(original, draft)).toEqual({ ...original, name: draft.name, purpose: draft.purpose, site: draft.site });
    expect(original.site).toEqual({ kind: "page", path: "/" });
    expect(() => editProductNode(original, { ...draft, id: "other" })).toThrow();
    expect(() => editProductNode({ ...original, purpose: "Cizí změna" }, draft)).toThrow("mezitím změnily");
    expect(editProductNode({ ...original, x: 800 }, draft).x).toBe(800);
  });
});

describe("page fingerprint notices concurrent changes to page intent and sections", () => {
  const page = node("page", "app", { kind: "page", path: "/kontakt", goal: "Poptávka do 2 minut", feel: "klidně", navLabel: "Kontakt",
    sections: [{ id: "form", role: "cta", name: "Formulář", intent: "" }] });
  it.each([
    ["goal", { goal: "Jiný cíl" }],
    ["feel", { feel: "rychle" }],
    ["navLabel", { navLabel: "Napište nám" }],
    ["missing goal", { goal: undefined }],
    ["section intent", { sections: [{ id: "form", role: "cta" as const, name: "Formulář", intent: "Jméno" }] }],
    ["section role", { sections: [{ id: "form", role: "form" as const, name: "Formulář", intent: "" }] }],
    ["no sections", { sections: undefined }],
  ])("%s changes the fingerprint", (_label, change) => {
    const changed = { ...page, site: { ...page.site, ...change } as CanvasNode["site"] };
    expect(productFingerprint(changed)).not.toBe(productFingerprint(page));
  });
  it("editing a page keeps the sections the form only shows", () => {
    const draft: ProductDraft = { id: "page", original: productFingerprint(page), parentId: "app", name: "page", purpose: "Smysl části", site: structuredClone(page.site!) };
    expect(editProductNode(page, draft).site).toEqual(page.site);
    const concurrent = { ...page, site: { ...page.site, sections: [] } as CanvasNode["site"] };
    expect(() => editProductNode(concurrent, draft)).toThrow("mezitím změnily");
  });
});
