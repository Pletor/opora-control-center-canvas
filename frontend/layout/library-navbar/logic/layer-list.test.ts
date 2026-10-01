import { describe, expect, it } from "vitest";
import { buildLayerTree, countLayers, LAYER_FILTERS, LAYER_GROUPS, UNNAMED_LAYER_LABEL } from "./layer-list";
import { UNNAMED_AREA_LABEL } from "@/editor/canvas/area/logic/area-model";
import type { CanvasNode } from "@/shared/types/logic/types";

const node = (id: string, kind: CanvasNode["kind"], name: string, parentId: string | null = null): CanvasNode => ({
  id,
  parentId,
  kind,
  name,
  purpose: "",
  x: 0,
  y: 0,
  ...(kind === "area" ? { size: { w: 720, h: 480 } } : {}),
});

// Malý projekt, na kterém je vidět všechno naráz: sektor s uzly i podsektorem, uzel mimo sektor,
// oblast na kořeni i oblast uvnitř sektoru a jeden komentář, který do seznamu vrstev nepatří.
const graph: CanvasNode[] = [
  node("s1", "sector", "Platby"),
  node("n1", "node", "Účtenka", "s1"),
  node("n2", "node", "Bránu vybrat", "s1"),
  node("s2", "sector", "Vrácení plateb", "s1"),
  node("n3", "node", "Storno", "s2"),
  node("n0", "node", "Zálohy", null),
  node("a1", "area", "Hotové základy", null),
  node("a2", "area", "Výstavba", "s1"),
  node("c1", "comment", "Poznámka na okraj", null),
];

describe("layer-list – tři skupiny nad grafem", () => {
  it("vrátí Sektory, Uzly mimo sektor a Oblasti ve stálém pořadí", () => {
    expect(buildLayerTree(graph).map((group) => group.id)).toEqual(["sectors", "nodes", "areas"]);
    expect(LAYER_GROUPS.map((group) => group.filter)).toEqual(["sector", "node", "area"]);
    expect(LAYER_FILTERS.map((filter) => filter.id)).toEqual(["all", "sector", "node", "area"]);
  });

  it("sektor nese své uzly i podsektor odsazené podle zanoření", () => {
    const [sectors] = buildLayerTree(graph);
    expect(sectors.rows.map((row) => [row.name, row.depth])).toEqual([
      ["Platby", 0],
      ["Bránu vybrat", 1],
      ["Účtenka", 1],
      ["Vrácení plateb", 1],
      ["Storno", 2],
    ]);
  });

  it("uzel mimo sektor má vlastní skupinu a nezdvojí se v sektorech", () => {
    const [sectors, nodes] = buildLayerTree(graph);
    expect(nodes.rows.map((row) => row.id)).toEqual(["n0"]);
    expect(sectors.rows.some((row) => row.id === "n0")).toBe(false);
  });

  it("oblasti se popisují přes areaLabel a odsazují podle vrstvy, na které leží", () => {
    const [, , areas] = buildLayerTree([...graph, node("a3", "area", "   ", null)]);
    expect(areas.rows.map((row) => [row.name, row.depth])).toEqual([
      ["Hotové základy", 0],
      [UNNAMED_AREA_LABEL, 0],
      ["Výstavba", 1],
    ]);
  });

  it("komentář není vrstva a v žádné skupině se neobjeví", () => {
    expect(buildLayerTree(graph).flatMap((group) => group.rows).some((row) => row.id === "c1")).toBe(false);
  });

  it("uzel bez jména dostane popisek místo prázdna", () => {
    const [, nodes] = buildLayerTree([node("x", "node", "   ")]);
    expect(nodes.rows[0].name).toBe(UNNAMED_LAYER_LABEL);
  });
});

describe("layer-list – kořen a skrytá karta", () => {
  it("domeček patří jen tomu, co leží rovnou v projektu", () => {
    const rows = buildLayerTree(graph).flatMap((group) => group.rows);
    expect(rows.filter((row) => row.isRoot).map((row) => row.id).sort()).toEqual(["a1", "n0", "s1"]);
  });

  it("uzavřená karta je v seznamu označená jako skrytá", () => {
    const rows = buildLayerTree(graph, "all", "", new Set(["n1", "s2"])).flatMap((group) => group.rows);
    expect(rows.filter((row) => row.hidden).map((row) => row.id).sort()).toEqual(["n1", "s2"]);
  });

  it("bez množiny uzavřených karet není skrytý nikdo", () => {
    expect(buildLayerTree(graph).flatMap((group) => group.rows).every((row) => !row.hidden)).toBe(true);
  });
});

describe("layer-list – filtr a hledání", () => {
  it("filtr nechá jen svou skupinu, i když je prázdná", () => {
    expect(buildLayerTree(graph, "sector").map((group) => group.id)).toEqual(["sectors"]);
    expect(buildLayerTree(graph, "area").map((group) => group.id)).toEqual(["areas"]);
    expect(buildLayerTree([], "node")).toEqual([{ id: "nodes", label: "Uzly mimo sektor", rows: [] }]);
  });

  it("hledání nezáleží na diakritice ani na velikosti písmen", () => {
    const found = buildLayerTree(graph, "all", "ucteNKA").flatMap((group) => group.rows);
    expect(found.map((row) => row.id)).toEqual(["s1", "n1"]);
  });

  it("nález si nese cestu stromem, aby bylo vidět, kde leží", () => {
    const [sectors] = buildLayerTree(graph, "sector", "storno");
    expect(sectors.rows.map((row) => [row.name, row.depth])).toEqual([
      ["Platby", 0],
      ["Vrácení plateb", 1],
      ["Storno", 2],
    ]);
  });

  it("nalezený sektor ukáže celý svůj obsah", () => {
    const [sectors] = buildLayerTree(graph, "sector", "vrácení");
    expect(sectors.rows.map((row) => row.id)).toEqual(["s1", "s2", "n3"]);
  });

  it("co dotazu neodpovídá, ze seznamu zmizí a počet to ukáže", () => {
    expect(countLayers(buildLayerTree(graph))).toBe(8);
    expect(countLayers(buildLayerTree(graph, "all", "nic takového tu není"))).toBe(0);
  });
});

describe("layer-list – cizí a poškozená data", () => {
  it("prázdný graf vrátí prázdné skupiny, ne výjimku", () => {
    expect(countLayers(buildLayerTree([]))).toBe(0);
  });

  it("uzel se smazanou vrstvou se v seznamu neztratí: vyjde nahoru, ale bez domečku", () => {
    const orphan = [node("s1", "sector", "Sektor"), node("n9", "node", "Sirotek", "pryc")];
    const [, nodes] = buildLayerTree(orphan);
    expect(nodes.rows.map((row) => [row.id, row.depth, row.isRoot])).toEqual([["n9", 0, false]]);
  });

  it("kruh v datech (uzel je svým vlastním předkem) strom usekne", () => {
    const loop = [node("a", "sector", "A", "b"), node("b", "sector", "B", "a")];
    expect(() => buildLayerTree(loop)).not.toThrow();
    expect(countLayers(buildLayerTree(loop))).toBe(0);
  });
});
