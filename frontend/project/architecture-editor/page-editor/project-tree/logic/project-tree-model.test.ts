import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { domainPageTree } from "../../../logic/domain-model";
import { activePageId, isSharedDomain, structureRows } from "./project-tree-model";

const app = (id: string, envs: { name: string; host: string }[], purpose = ""): CanvasNode =>
  ({ id, parentId: null, kind: "sector", name: id, purpose, x: 0, y: 0, site: { kind: "application", environments: envs } });
const page = (id: string, parentId: string, path = "/" + id): CanvasNode =>
  ({ id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, site: { kind: "page", path } });
const plain = (id: string, parentId: string): CanvasNode => ({ id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0 });

const graph: Graph = {
  nodes: [
    app("prod-app", [{ name: "Produkce", host: "app.example.cz" }], "Hlavní aplikace"),
    app("legacy", [{ name: "Produkce", host: "a.cz" }, { name: "Vývoj", host: "a.dev" }]),
    page("dashboard", "prod-app"), plain("box", "dashboard"), page("detail", "box"), page("login", "prod-app"), page("cizi", "legacy"),
  ],
  edges: [],
};

describe("structureRows", () => {
  const rows = structureRows(domainPageTree(graph, "prod-app"), "detail");
  it("jen stránky otevřené domény, podstránky s hloubkou a aktivní stránka", () => {
    expect(rows.map((row) => [row.node.id, row.depth, row.active])).toEqual([["dashboard", 0, false], ["detail", 1, true], ["login", 0, false]]);
  });
  it("ví, kdo je první a poslední mezi sourozenci", () => {
    expect(rows.map((row) => [row.first, row.last])).toEqual([[true, false], [true, true], [false, true]]);
  });
  it("prázdná doména nemá řádky", () => {
    expect(structureRows([], null)).toEqual([]);
  });
});

describe("isSharedDomain", () => {
  it("vícehostová aplikace je sdílená struktura, jednohostová ne", () => {
    expect(isSharedDomain(graph.nodes[1])).toBe(true);
    expect(isSharedDomain(graph.nodes[0])).toBe(false);
    expect(isSharedDomain(page("p", "x"))).toBe(false);
  });
});

describe("activePageId", () => {
  it("najde nejbližší stránku nad rozsahem přes běžné kontejnery", () => {
    expect(activePageId(graph, "detail")).toBe("detail");
    expect(activePageId(graph, "box")).toBe("dashboard");
  });
  it("bez stránky nebo rozsahu vrátí null", () => {
    expect(activePageId(graph, "prod-app")).toBeNull();
    expect(activePageId(graph, null)).toBeNull();
    expect(activePageId(graph, "missing")).toBeNull();
  });
});
