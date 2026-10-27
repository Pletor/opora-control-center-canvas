import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { agentContext, ancestry, nodeLinks } from "./agent-context";

const node = (id: string, parentId: string | null, extra: Partial<CanvasNode> = {}): CanvasNode => ({
  id, parentId, kind: "node", name: id, purpose: "", x: 0, y: 0, ...extra,
});
const graph: Graph = {
  nodes: [
    node("app", null, { kind: "sector", site: { kind: "application", environments: [{ name: "Produkce", host: "app.example.cz" }] } }),
    node("page", "app", { name: "Dashboard", site: { kind: "page", path: "/dashboard" } }),
    node("form", "page", { name: "Formulář" }),
    node("field", "form", { name: "Pole e-mail", sourceRef: { origin: "existing", path: "src/Email.tsx", kind: "file" } }),
    node("plan", "form", { name: "", sourceRef: { origin: "planned", path: "app/pages/dashboard/", kind: "directory" } }),
  ],
  edges: [
    { id: "e1", source: "form", target: "field" },
    { id: "e2", source: "field", target: "plan", port: "rule" },
    { id: "e3", source: "ghost", target: "field", port: "next" },
  ],
};

describe("pracovní kontext agenta", () => {
  it("čte prostředí, host, stránku, cestu komponent a existující soubor", () => {
    expect(agentContext(graph, "field", "app")).toEqual({
      environment: "Produkce",
      host: "app.example.cz",
      page: { id: "page", name: "Dashboard" },
      componentPath: ["Formulář", "Pole e-mail"],
      repo: { kind: "existing", path: "src/Email.tsx" },
    });
  });
  it("navrženou cestu označí jako návrh a prázdné jméno jako Bez názvu", () => {
    const context = agentContext(graph, "plan", "app");
    expect(context.repo).toEqual({ kind: "planned", path: "app/pages/dashboard/" });
    expect(context.componentPath).toEqual(["Formulář", "Bez názvu"]);
  });
  it("bez stránky končí cesta pod doménou, stránka sama nemá cestu komponent", () => {
    const flat: Graph = { nodes: [...graph.nodes, node("loose", "app", { name: "Volný" })], edges: [] };
    expect(agentContext(flat, "loose", "app")).toMatchObject({ page: null, componentPath: ["Volný"], repo: null });
    expect(agentContext(graph, "page", "app")).toMatchObject({ page: { id: "page" }, componentPath: [] });
  });
  it("neznámá doména nebo prostředí je null, ne vymyšlená hodnota", () => {
    expect(agentContext(graph, "field", "missing")).toMatchObject({ environment: null, host: null });
    const bare: Graph = { nodes: [node("d", null, { kind: "sector", site: { kind: "application", environments: [] } }), node("x", "d")], edges: [] };
    expect(agentContext(bare, "x", "d")).toMatchObject({ environment: null, host: "d", page: null, componentPath: ["x"] });
  });
  it("stránka nese cíl a působení, jen když je člověk zadal", () => {
    const intent: Graph = { nodes: graph.nodes.map((item) => item.id === "page"
      ? { ...item, site: { kind: "page" as const, path: "/dashboard", goal: "Přehled do 5 s", feel: "klidně", navLabel: "Přehled" } } : item), edges: [] };
    expect(agentContext(intent, "field", "app").page).toEqual({ id: "page", name: "Dashboard", goal: "Přehled do 5 s", feel: "klidně" });
    expect(agentContext(graph, "field", "app").page).toEqual({ id: "page", name: "Dashboard" });
  });
  it("předci přežijí cyklus", () => {
    const loop: Graph = { nodes: [node("a", "b"), node("b", "a")], edges: [] };
    expect(ancestry(loop, "a").map((n) => n.id)).toEqual(["a", "b"]);
  });
});

describe("vazby prvku", () => {
  it("dělí vazby na příchozí a odchozí, port bez hodnoty je next a chybějící konec je nedostupný", () => {
    const links = nodeLinks(graph, "field");
    expect(links.incoming).toEqual([
      { edgeId: "e1", otherId: "form", otherName: "Formulář", port: "next" },
      { edgeId: "e3", otherId: "ghost", otherName: "nedostupné", port: "next" },
    ]);
    expect(links.outgoing).toEqual([{ edgeId: "e2", otherId: "plan", otherName: "Bez názvu", port: "rule" }]);
  });
  it("nese druh toku vazby jen když ho graf má", () => {
    const carried: Graph = { ...graph, edges: graph.edges.map((edge) => edge.id === "e1" ? { ...edge, carries: "data" as const } : edge) };
    const links = nodeLinks(carried, "field");
    expect(links.incoming[0]).toEqual({ edgeId: "e1", otherId: "form", otherName: "Formulář", port: "next", carries: "data" });
    expect("carries" in links.incoming[1]).toBe(false);
  });
});
