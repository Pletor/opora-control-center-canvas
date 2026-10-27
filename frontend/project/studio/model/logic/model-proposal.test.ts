import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph, GraphEdge } from "@/shared/types/logic/types";
import { componentType } from "./catalog";
import { validateModel } from "./model-rules";
import { CARRIES_PORT_TYPE, pickComponentType, proposeModelFromArchitecture } from "./model-proposal";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, parentId, kind: "node", name: id.toUpperCase(), purpose: "", x: 0, y: 0, ...extra });
const graph: Graph = {
  nodes: [
    node("app", null, { kind: "sector", site: { kind: "application" } as CanvasNode["site"] }),
    node("p1", "app", { site: { kind: "page", path: "/" } as CanvasNode["site"] }),
    node("p2", "app", { site: { kind: "page", path: "/b" } as CanvasNode["site"] }),
    node("c1", "p1"), node("c2", "p2"), node("c3", "p2"), node("note", "p1", { kind: "comment" }),
    node("other", null, { kind: "sector" }), node("x", "other"),
  ],
  edges: [
    { id: "nav", source: "p1", target: "p2", carries: "navigation" },
    { id: "back", source: "p2", target: "p1", carries: "navigation" },
    { id: "read", source: "c1", target: "c2", carries: "data" },
    { id: "write", source: "c1", target: "c3", carries: "command" },
    { id: "bare", source: "c2", target: "c3" },
    { id: "outside", source: "c1", target: "x", carries: "event" },
  ] satisfies GraphEdge[],
};

describe("proposeModelFromArchitecture", () => {
  it("převod carries → typ portu podle kontraktu", () => {
    expect(CARRIES_PORT_TYPE).toEqual({ navigation: "http-request", data: "data", command: "record-command", event: "event" });
  });

  it("karty domény dostanou komponenty s binding a vazby s typem podle carries", () => {
    const before = structuredClone(graph), { model, unresolved } = proposeModelFromArchitecture(graph, "app");
    expect(graph).toEqual(before);
    expect(model.domainId).toBe("app");
    expect(model.revision).toBe(0);
    expect(model.nodes.map((n) => n.binding?.nodeId)).toEqual(["p1", "p2", "c1", "c2", "c3"]);
    expect(model.nodes.map((n) => n.name)).toEqual(["P1", "P2", "C1", "C2", "C3"]);
    expect(model.edges.map((e) => [e.id, e.type])).toEqual([["opora:read", "data"], ["opora:write", "record-command"]]);
    // Stránky s navigací tam i zpět dostanou Frontend App a role Studia vazbu Frontend → Frontend nedovolí.
    expect(unresolved.map((u) => u.edgeId)).toEqual(["nav", "back", "bare"]);
    expect(unresolved[0].reason).toMatch(/Role Studia/);
    expect(unresolved[2].reason).toMatch(/carries/);
    expect(validateModel(model)).toBe(model);
    const c1 = componentType(model.nodes[2].type)!;
    expect(c1.ports.some((p) => p.direction === "output" && p.type === "data")).toBe(true);
    expect(c1.ports.some((p) => p.direction === "output" && p.type === "record-command")).toBe(true);
  });

  it("neznámá nebo prázdná doména dá prázdný návrh", () => {
    expect(proposeModelFromArchitecture(graph, "nic")).toEqual({ model: expect.objectContaining({ nodes: [], edges: [] }), unresolved: [] });
  });

  it("výběr typu: nejméně chybějících portů, pak nejméně portů, bez cloudu a Podu", () => {
    const type = pickComponentType(new Set(["http-request"]), new Set(["http-request"]));
    expect(type.id).toBe("frontend-app");
    expect(pickComponentType(new Set(), new Set()).provider).toBeUndefined();
    expect(pickComponentType(new Set(["sql-query"]), new Set()).ports.some((p) => p.type === "sql-query" && p.direction === "input")).toBe(true);
  });
});
