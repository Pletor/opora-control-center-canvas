import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { CATALOG_ITEMS, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { catalogEdges } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { firstInPort, hasPortMenu, libraryForCarries, linkTargets, searchTargets, stepIndex } from "./port-menu";

const node = (id: string, name: string, kind: CanvasNode["kind"] = "node", parentId: string | null = "page"): CanvasNode =>
  ({ id, parentId, kind, name, purpose: "", x: 0, y: 0 });
const graph = (): Graph => ({
  nodes: [node("page", "Stránka", "node", null), node("form", "Formulář"), node("api", "Odeslání"), node("note", "Pozn.", "comment"),
    node("zone", "Oblast", "area"), node("far", "Jinde", "node", "other"), node("section", "Hlavička", "sector")],
  edges: [{ id: "e1", source: "form", target: "api", port: "next" }],
});
const item = (id: string, ports: CatalogItem["ports"], label = id): CatalogItem =>
  ({ id, category: "backend", label, purpose: "Účel " + id, relates: [], done: ["x"], invariants: [], ports });

describe("nabídka vazby: existující karty", () => {
  it("nabídne jen karty rozsahu, kam jde vazba tahem: bez sebe, komentáře, oblasti, už propojené a cyklu", () => {
    expect(linkTargets(graph(), "page", "form").map((n) => n.id)).toEqual(["section"]);
    expect(linkTargets(graph(), "page", "api").map((n) => n.id)).toEqual(["section"]);
    expect(linkTargets(graph(), "page", "section").map((n) => n.id)).toEqual(["form", "api"]);
  });
  it("hledá podle názvu bez háčků a velikosti písmen", () => {
    const nodes = graph().nodes;
    expect(searchTargets(nodes, "FORMULAR").map((n) => n.id)).toEqual(["form"]);
    expect(searchTargets(nodes, "  ")).toBe(nodes);
  });
  it("nabídku mají jen uzly a sektory", () => {
    expect(["node", "sector", "area", "comment"].map((kind) => hasPortMenu({ kind: kind as CanvasNode["kind"] }))).toEqual([true, true, false, false]);
  });
});

describe("nabídka vazby: vytvořit z Knihovny", () => {
  const items = [item("a", [{ id: "in", direction: "in", carries: "data" }]), item("b", [{ id: "out", direction: "out", carries: "data" }]),
    item("c", [{ id: "in", direction: "in", carries: "command" }], "Příkazový modul"), item("d", undefined)];
  it("bez druhu toku stačí jakýkoli vstupní port, s druhem jen shodný první vstup", () => {
    expect(libraryForCarries(items, null).map((i) => i.id)).toEqual(["a", "c"]);
    expect(libraryForCarries(items, "command").map((i) => i.id)).toEqual(["c"]);
    expect(libraryForCarries(items, "event")).toEqual([]);
  });
  it("hledá jako panel Knihovny", () => {
    expect(libraryForCarries(items, null, "prikazovy").map((i) => i.id)).toEqual(["c"]);
  });
  it("druh toku nabídnuté položky je ten, který vložení dá vazbě (catalogEdges)", () => {
    for (const entry of libraryForCarries(CATALOG_ITEMS, null)) {
      expect(catalogEdges(entry, "component", { nodeId: "src", side: "source" })[0].carries).toBe(firstInPort(entry)!.carries);
    }
    expect(libraryForCarries(CATALOG_ITEMS, null).length).toBeGreaterThan(0);
  });
});

describe("šipky po položkách", () => {
  it("přetočí se přes okraje a prázdný seznam nemá výběr", () => {
    expect(stepIndex(-1, 1, 3)).toBe(0);
    expect(stepIndex(-1, -1, 3)).toBe(2);
    expect(stepIndex(2, 1, 3)).toBe(0);
    expect(stepIndex(0, -1, 3)).toBe(2);
    expect(stepIndex(0, 1, 0)).toBe(-1);
  });
});
