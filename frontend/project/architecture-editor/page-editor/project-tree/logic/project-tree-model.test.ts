import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { activePageId, projectTree, SHARED_GROUP } from "./project-tree-model";

const app = (id: string, envs: { name: string; host: string }[], purpose = ""): CanvasNode =>
  ({ id, parentId: null, kind: "sector", name: id, purpose, x: 0, y: 0, site: { kind: "application", environments: envs } });
const page = (id: string, parentId: string, path = "/" + id): CanvasNode =>
  ({ id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, site: { kind: "page", path } });
const plain = (id: string, parentId: string): CanvasNode => ({ id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0 });

const graph: Graph = {
  nodes: [
    app("prod-app", [{ name: "Produkce", host: "app.example.cz" }], "Hlavní aplikace"),
    app("dev-web", [{ name: "Vývoj", host: "example.dev" }]),
    app("legacy", [{ name: "Produkce", host: "a.cz" }, { name: "Vývoj", host: "a.dev" }]),
    app("stage", [{ name: "Staging", host: "admin.stage.cz" }]),
    page("dashboard", "prod-app"), plain("box", "dashboard"), page("detail", "box"), page("login", "prod-app"),
  ],
  edges: [],
};

describe("projectTree", () => {
  const groups = projectTree(graph, "prod-app", "detail");
  it("řadí Produkce, Vývoj, další prostředí a sdílenou strukturu", () => {
    expect(groups.map((group) => [group.label, group.badge, group.tone])).toEqual([
      ["Produkce", "LIVE", "live"], ["Vývoj", "DEV", "dev"], ["Staging", null, "other"], [SHARED_GROUP, null, "shared"]]);
  });
  it("zachová prázdné Produkce/Vývoj a označí aktivní skupinu", () => {
    const empty = projectTree({ nodes: [], edges: [] }, null, null);
    expect(empty.map((group) => group.label)).toEqual(["Produkce", "Vývoj"]);
    expect(groups[0].active).toBe(true);
    expect(groups[1].active).toBe(false);
  });
  it("dává doméně host, druh a stránky s hloubkou podstránek", () => {
    const domain = groups[0].domains[0];
    expect(domain).toMatchObject({ id: "prod-app", host: "app.example.cz", kind: "app", kindLabel: "Aplikace", purpose: "Hlavní aplikace", active: true });
    expect(domain.pages.map((item) => [item.id, item.depth, item.active])).toEqual([["dashboard", 0, false], ["detail", 1, true], ["login", 0, false]]);
  });
  it("vícehostová aplikace ukáže všechny hosty a druh podle prvního", () => {
    expect(groups[3].domains[0]).toMatchObject({ id: "legacy", host: "a.cz, a.dev", kind: "web" });
    expect(groups[2].domains[0].kind).toBe("admin");
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
