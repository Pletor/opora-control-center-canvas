import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { domainForNode, domainNode, domainPageTree, reparentDomainPage, reorderDomainPage, splitDomainHost } from "./domain-model";

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
  it("moves a page in the same domain without rewriting paths, children, edges or unrelated data", () => {
    const original = graph();
    const moved = reparentDomainPage(original, "app", "about", "home");
    expect(moved.nodes[5]).toEqual({ ...original.nodes[5], parentId: "home" });
    expect(moved.nodes[7]).toBe(original.nodes[7]);
    expect(moved.nodes[2]).toBe(original.nodes[2]);
    expect(moved.edges).toBe(original.edges);
    expect(original.nodes[5].parentId).toBe("wrapper");
    expect(domainPageTree(moved, "app")[0].children.map((branch) => branch.node.id)).toEqual(["child", "about"]);
    expect(reparentDomainPage(moved, "app", "about", "app").nodes[5].parentId).toBe("app");
    expect(reparentDomainPage(original, "app", "home", "app")).toBe(original);
  });
  it("rejects self, descendants through containers, different domains and nonpage parents", () => {
    for (const [pageId, parent] of [["home", "home"], ["home", "child"], ["home", "other"], ["home", "foreign"], ["home", "nested-page"], ["foreign", "app"], ["about", "component"], ["missing", "home"]]) {
      expect(() => reparentDomainPage(graph(), "app", pageId, parent)).toThrow();
    }
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
