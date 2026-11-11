import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { domainEntryPage, domainForNode, domainNode, domainPageTree, reorderDomainPage, splitDomainHost, worktreeDomainChoice } from "./domain-model";

const node = (id: string, parentId: string | null = null): CanvasNode => ({ id, parentId, name: id, purpose: "Účel", kind: "node", x: 10, y: 20 });
const app = (id: string, parentId: string | null = null): CanvasNode => ({ ...node(id, parentId), kind: "sector", site: { kind: "application", environments: [{ name: "Produkce", host: `${id}.example.cz` }] } });
const page = (id: string, parentId: string): CanvasNode => ({ ...node(id, parentId), site: { kind: "page", path: `/${id}/` }, card: { layer: "frontend" } });
const graph = (): Graph => ({ nodes: [app("app"), page("home", "app"), node("component", "home"), page("child", "component"), node("wrapper", "app"), page("about", "wrapper"), app("other"), page("foreign", "other"), app("nested", "home"), page("nested-page", "nested")], edges: [{ id: "edge", source: "home", target: "about" }] });

describe("domain boundary", () => {
  it("finds the exact nearest application, including nested application roots", () => {
    const original = graph();
    expect(domainNode(original, "app").id).toBe("app");
    expect(domainForNode(original, "component")?.id).toBe("app");
    expect(domainForNode(original, "nested-page")?.id).toBe("nested");
    expect(domainForNode(original, "nested")?.id).toBe("nested");
    expect(domainForNode({ nodes: [node("loose")], edges: [] }, "loose")).toBeNull();
    expect(() => domainNode(original, "home")).toThrow();
    expect(() => domainForNode(original, "missing")).toThrow();
  });
  it("projects only this domain's pages in saved order through ordinary containers", () => {
    const tree = domainPageTree(graph(), "app");
    expect(tree.map((branch) => branch.node.id)).toEqual(["home", "about"]);
    expect(tree[0].children.map((branch) => branch.node.id)).toEqual(["child"]);
    expect(domainPageTree(graph(), "nested").map((branch) => branch.node.id)).toEqual(["nested-page"]);
    expect(() => domainPageTree(graph(), "missing")).toThrow();
  });
});

describe("explicit legacy host split", () => {
  it("keeps every original child and attribute and creates one empty independent domain", () => {
    const original = graph();
    original.nodes[0] = { ...original.nodes[0], sourceRef: { origin: "planned", path: "site", kind: "directory" }, blockOffsets: { action: { dx: 30, dy: 40 } }, site: { kind: "application", environments: [{ name: "Produkce", host: "app.example.cz" }, { name: "Vývoj", host: "app.example.dev" }] } };
    const before = structuredClone(original);
    const split = splitDomainHost(original, "app", "app.example.dev", "dev");
    expect(split.nodes[0]).toEqual({ ...original.nodes[0], site: { kind: "application", environments: [{ name: "Produkce", host: "app.example.cz" }] } });
    expect(split.nodes.slice(1, -1)).toEqual(original.nodes.slice(1));
    expect(split.nodes.at(-1)).toMatchObject({ id: "dev", kind: "sector", parentId: null, name: "app.example.dev", purpose: "", site: { kind: "application", environments: [{ name: "Vývoj", host: "app.example.dev" }] } });
    expect(split.nodes.at(-1)).not.toHaveProperty("sourceRef");
    expect(domainPageTree(split, "dev")).toEqual([]);
    expect(domainPageTree(split, "app").map((branch) => branch.node.id)).toEqual(["home", "about"]);
    expect(split.edges).toBe(original.edges);
    expect(original).toEqual(before);
  });
  it("refuses automatic splitting of one host and invalid or reused IDs", () => {
    expect(() => splitDomainHost(graph(), "app", "app.example.cz", "new")).toThrow();
    const original = graph();
    original.nodes[0].site = { kind: "application", environments: [{ name: "Produkce", host: "one.cz" }, { name: "Vývoj", host: "two.cz" }] };
    for (const id of ["app", "bad.id", ""]) expect(() => splitDomainHost(original, "app", "two.cz", id)).toThrow();
    expect(() => splitDomainHost(original, "app", "not-stored.cz", "new")).toThrow();
  });
});

describe("page structure mutations", () => {
  it("otevře doménu na první stránce, prázdnou bez stránky", () => {
    expect(domainEntryPage(graph(), "app")).toBe("home");
    expect(domainEntryPage({ nodes: [app("empty")], edges: [] }, "empty")).toBeNull();
  });
  it("reorders only navigation sibling slots and preserves every object and other-domain position", () => {
    const original = graph();
    const reordered = reorderDomainPage(original, "app", "about", -1);
    expect(domainPageTree(reordered, "app").map((branch) => branch.node.id)).toEqual(["about", "home"]);
    expect(reordered.nodes[1]).toBe(original.nodes[5]);
    expect(reordered.nodes[5]).toBe(original.nodes[1]);
    for (const index of [0, 2, 3, 4, 6, 7, 8, 9]) expect(reordered.nodes[index]).toBe(original.nodes[index]);
    expect(reordered.edges).toBe(original.edges);
    expect(original.nodes[1].id).toBe("home");
    expect(reorderDomainPage(reordered, "app", "about", 1)).toEqual(original);
    expect(reorderDomainPage(original, "app", "child", 1)).toBe(original);
    expect(() => reorderDomainPage(original, "app", "foreign", -1)).toThrow();
  });
});

describe("doména nového worktree", () => {
  it("předvolba vyhrává, jinak doména vybraného uzlu, jinak nic", () => {
    expect(worktreeDomainChoice(graph(), "other", "component")).toBe("other");
    expect(worktreeDomainChoice(graph(), null, "component")).toBe("app");
    expect(worktreeDomainChoice(graph(), null, null)).toBe("");
    expect(worktreeDomainChoice(graph(), null, "chybí")).toBe("");
    expect(worktreeDomainChoice(graph(), "home", null)).toBe("");
  });
});
