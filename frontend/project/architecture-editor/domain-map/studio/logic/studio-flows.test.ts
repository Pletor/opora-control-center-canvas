import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { domainFlows, FLOW_KINDS } from "./studio-flows";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, parentId, name: id.toUpperCase(), purpose: "", kind: "node", x: 0, y: 0, ...extra });
const graph: Graph = {
  nodes: [
    node("web", null, { kind: "sector", site: { kind: "application", environments: [] } }),
    node("home", "web", { site: { kind: "page", path: "/" } }),
    node("form", "home"),
    node("contact", "web", { site: { kind: "page", path: "/kontakt" } }),
    node("api", "web"),
    node("other", null, { kind: "sector", site: { kind: "application", environments: [] } }),
    node("foreign", "other"),
  ],
  edges: [
    { id: "e1", source: "home", target: "contact", carries: "navigation" },
    { id: "e2", source: "form", target: "api", carries: "command" },
    { id: "e3", source: "api", target: "contact", carries: "data" },
    { id: "e4", source: "contact", target: "form" },
    { id: "e5", source: "form", target: "foreign", carries: "data" },
    { id: "e6", source: "home", target: "form", port: "flow" },
  ],
};

describe("domainFlows", () => {
  const flows = domainFlows(graph, "web");
  const of = (kind: string) => flows.find((item) => item.kind === kind)!;

  it("lists every kind in fixed order, counting only edges inside the domain that may carry a flow", () => {
    expect(flows.map((item) => item.kind)).toEqual(FLOW_KINDS);
    expect(flows.map((item) => item.count)).toEqual([1, 1, 1, 0, 1]);
    expect(of("event").groups).toEqual([]);
  });

  it("groups by the source page and targets the source node (page itself, component, or none)", () => {
    expect(of("navigation").groups).toEqual([{ pageId: "home", pageName: "HOME", items: [
      { edgeId: "e1", sourceId: "home", sourceName: "HOME", targetName: "CONTACT", target: { kind: "page", id: "home" } }] }]);
    expect(of("command").groups[0].items[0].target).toEqual({ kind: "node", id: "form", pageId: "home" });
    expect(of("data").groups).toEqual([{ pageId: null, pageName: "Mimo stránky", items: [
      { edgeId: "e3", sourceId: "api", sourceName: "API", targetName: "CONTACT", target: null }] }]);
    expect(of("unspecified").label).toBe("Neurčeno");
    expect(of("unspecified").groups[0].pageId).toBe("contact");
  });

  it("puts sources outside pages last and sorts pages by name", () => {
    const g: Graph = { ...graph, edges: [
      { id: "a", source: "api", target: "home" }, { id: "b", source: "form", target: "home" }, { id: "c", source: "contact", target: "home" }] };
    expect(domainFlows(g, "web").find((item) => item.kind === "unspecified")!.groups.map((group) => group.pageName)).toEqual(["CONTACT", "HOME", "Mimo stránky"]);
  });
});
