import { describe, expect, it } from "vitest";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import { arrangeLayer, footprintOf, resolveOverlap, type Footprint } from "./layout-model";

/** Skutečně se protínají jako obdélníky, bez ohledu na mezeru — pro ověření výsledku po srovnání. */
function rectsOverlap(a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/** Karta o výchozím půdorysu na daném místě — vstup pro srovnání vrstvy. */
const card = (id: string, x: number, y: number, w = 272, h = 240): Footprint => ({ id, x, y, w, h });
/** Vazba „odtud se pokračuje tam“; port neovlivňuje směr, jen kudy čára z karty vychází. */
const link = (source: string, target: string, port: GraphEdge["port"] = "next"): GraphEdge => ({
  id: `${source}->${target}`,
  source,
  target,
  port,
});
const frame = (id: string, x: number, y: number, w: number, h: number): CanvasNode => ({
  id,
  parentId: null,
  kind: "area",
  name: "",
  purpose: "",
  x,
  y,
  size: { w, h },
});
/** Umístěné otisky jako obdélníky (velikost si berou ze vstupu) — pro kontrolu překryvů. */
function rectsOf(input: Footprint[], placed: { id: string; x: number; y: number }[]) {
  return placed.map((p) => ({ ...input.find((f) => f.id === p.id)!, x: p.x, y: p.y }));
}
function noneOverlap(rects: { x: number; y: number; w: number; h: number }[]): boolean {
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) if (rectsOverlap(rects[i], rects[j])) return false;
  }
  return true;
}

describe("layout-model", () => {
  it("bez překryvu vrátí resolveOverlap původní místo beze změny", () => {
    const moved: Footprint = { id: "a", x: 0, y: 0, w: 272, h: 240 };
    const other: Footprint = { id: "b", x: 1000, y: 1000, w: 272, h: 240 };
    expect(resolveOverlap(moved, [other])).toEqual({ x: 0, y: 0 });
  });

  it("vodorovný posun: menší průnik na ose x vytlačí kartu doleva/doprava, y se nezmění", () => {
    const moved: Footprint = { id: "a", x: 0, y: 0, w: 100, h: 100 };
    const other: Footprint = { id: "b", x: 70, y: 0, w: 100, h: 100 };
    const result = resolveOverlap(moved, [other]);
    expect(result).toEqual({ x: -56, y: 0 });
    expect(rectsOverlap({ ...moved, x: result.x, y: result.y }, other)).toBe(false);
  });

  it("svislý posun je přednější, když je průnik na ose y menší", () => {
    const moved: Footprint = { id: "a", x: 0, y: 0, w: 100, h: 100 };
    const other: Footprint = { id: "b", x: 0, y: 70, w: 100, h: 100 };
    const result = resolveOverlap(moved, [other]);
    expect(result).toEqual({ x: 0, y: -56 });
    expect(rectsOverlap({ ...moved, x: result.x, y: result.y }, other)).toBe(false);
  });

  it("otisk karty s otevřeným blokem Akce se rozšíří doprava a nahoru o blok", () => {
    const withAction = footprintOf(
      { id: "a", kind: "node", x: 0, y: 0 },
      { measuredHeight: 240, openPorts: [], hasActions: true, hasRules: false, hasMaterials: false },
    );
    expect(withAction).toEqual({ id: "a", x: 0, y: -21, w: 327 + 260, h: 240 + 21 });

    const withoutBlocks = footprintOf(
      { id: "a", kind: "node", x: 0, y: 0 },
      { measuredHeight: 240, openPorts: [], hasActions: false, hasRules: false, hasMaterials: false },
    );
    expect(withoutBlocks).toEqual({ id: "a", x: 0, y: 0, w: 272, h: 240 });
  });

  it("boční blok se počítá do kolize, i když se samotné karty nepřekrývají", () => {
    const b: Footprint = { id: "b", x: 400, y: 0, w: 272, h: 240 };
    const plainA = footprintOf(
      { id: "a", kind: "node", x: 0, y: 0 },
      { measuredHeight: 240, openPorts: [], hasActions: false, hasRules: false, hasMaterials: false },
    )!;
    // Bez bloku karty samy o sobě nekolidují (272 < 400): resolveOverlap nic nemění.
    expect(resolveOverlap(plainA, [b])).toEqual({ x: 0, y: 0 });

    const actionA = footprintOf(
      { id: "a", kind: "node", x: 0, y: 0 },
      { measuredHeight: 240, openPorts: [], hasActions: true, hasRules: false, hasMaterials: false },
    )!;
    // S otevřeným blokem Akce (zasahuje do x=587) už se s kartou B překrývá — otisk se musí posunout.
    const result = resolveOverlap(actionA, [b]);
    expect(result).not.toEqual({ x: actionA.x, y: actionA.y });
    expect(rectsOverlap({ ...actionA, x: result.x, y: result.y }, b)).toBe(false);
  });

  it("odtažený blok se počítá tam, kam ho uživatel dal, ne na výchozí místo", () => {
    const opts = { measuredHeight: 240, openPorts: [], hasActions: true, hasRules: false, hasMaterials: false };
    // Blok Akce odtažený nalevo a dolů: otisk se rozšíří tím směrem a vpravo končí už na hraně karty.
    const movedLeft = footprintOf({ id: "a", kind: "node", x: 0, y: 0, blockOffsets: { action: { dx: -300, dy: 100 } } }, opts);
    expect(movedLeft).toEqual({ id: "a", x: -300, y: 0, w: 300 + 272, h: 300 });

    // Karta B stála v cestě výchozímu místu bloku; po odtažení bloku už ji otisk netlačí pryč.
    const b: Footprint = { id: "b", x: 400, y: 0, w: 272, h: 240 };
    const parked = footprintOf({ id: "a", kind: "node", x: 0, y: 0, blockOffsets: { action: { dx: 0, dy: -260 } } }, opts)!;
    expect(resolveOverlap(parked, [b])).toEqual({ x: parked.x, y: parked.y });
  });

  it("kind: area otisk nemá a do magnetismu nevstupuje", () => {
    expect(footprintOf({ id: "area1", kind: "area", x: 10, y: 10 }, { openPorts: [], hasActions: false, hasRules: false, hasMaterials: false })).toBeNull();
  });
});

describe("arrangeLayer", () => {
  const at = (placed: { id: string; x: number; y: number }[], id: string) => placed.find((p) => p.id === id)!;

  it("řetěz a → b → c stojí zleva doprava, sloupec vedle sloupce o gapX", () => {
    const input = [card("a", 500, 500), card("b", 0, 0), card("c", 900, 30)];
    const { nodes } = arrangeLayer(input, [link("a", "b"), link("b", "c")], []);
    expect(at(nodes, "a")).toEqual({ id: "a", x: 80, y: 80 });
    expect(at(nodes, "b").x).toBe(80 + 272 + 96);
    expect(at(nodes, "c").x).toBe(80 + (272 + 96) * 2);
    expect(at(nodes, "b").y).toBe(80);
    expect(at(nodes, "c").y).toBe(80);
  });

  it("dva předchůdci téhož uzlu stojí nad sebou v jednom sloupci", () => {
    const input = [card("a", 0, 0), card("b", 0, 600), card("c", 0, 300)];
    const { nodes } = arrangeLayer(input, [link("a", "c"), link("b", "c")], []);
    expect(at(nodes, "a").x).toBe(at(nodes, "b").x);
    expect(at(nodes, "b").y - at(nodes, "a").y).toBe(240 + 48);
    expect(at(nodes, "c").x).toBe(at(nodes, "a").x + 272 + 96);
  });

  it("kruh v procesu nespadne a každý uzel dostane místo", () => {
    const input = [card("a", 0, 0), card("b", 10, 10), card("c", 20, 20)];
    const { nodes } = arrangeLayer(input, [link("a", "b"), link("b", "c"), link("c", "a")], []);
    expect(nodes.map((n) => n.id).sort()).toEqual(["a", "b", "c"]);
    expect(noneOverlap(rectsOf(input, nodes))).toBe(true);
  });

  it("osamělé uzly spadnou do mřížky pod tok, po čtyřech ve sloupci", () => {
    const flow = [card("a", 0, 0), card("b", 0, 0)];
    const lonely = Array.from({ length: 5 }, (_, i) => card(`s${i}`, 0, 1000 + i * 10));
    const input = [...flow, ...lonely];
    const { nodes } = arrangeLayer(input, [link("a", "b")], []);
    const flowBottom = Math.max(at(nodes, "a").y + 240, at(nodes, "b").y + 240);
    for (const one of lonely) expect(at(nodes, one.id).y).toBeGreaterThanOrEqual(flowBottom);
    // Čtyři pod sebou v prvním sloupci, pátý začíná sloupec druhý.
    expect(at(nodes, "s3").x).toBe(at(nodes, "s0").x);
    expect(at(nodes, "s4").x).toBe(at(nodes, "s0").x + 272 + 96);
    expect(at(nodes, "s4").y).toBe(at(nodes, "s0").y);
    expect(noneOverlap(rectsOf(input, nodes))).toBe(true);
  });

  it("členové oblasti zůstanou uvnitř a rámeček se pod nimi zvětší", () => {
    const area = frame("area1", 100, 100, 400, 300);
    const input = [card("m1", 120, 120), card("m2", 150, 150), card("m3", 180, 180)];
    const { nodes, areas } = arrangeLayer(input, [link("m1", "m2"), link("m2", "m3")], [area]);
    expect(areas).toHaveLength(1);
    // Oblast neuhne z místa, ale vyroste: tři karty v řadě (1008) + 32 po stranách, výška 240 + 56 + 32.
    expect(areas[0].x).toBe(100);
    expect(areas[0].y).toBe(100);
    expect(areas[0].w).toBe(272 * 3 + 96 * 2 + 64);
    expect(areas[0].h).toBe(240 + 56 + 32);
    for (const rect of rectsOf(input, nodes)) {
      expect(rect.x).toBeGreaterThanOrEqual(areas[0].x);
      expect(rect.y).toBeGreaterThanOrEqual(areas[0].y);
      expect(rect.x + rect.w).toBeLessThanOrEqual(areas[0].x + areas[0].w);
      expect(rect.y + rect.h).toBeLessThanOrEqual(areas[0].y + areas[0].h);
    }
  });

  it("volné karty se odstěhují pod oblast a nikdy do ní nezasahují", () => {
    const area = frame("area1", 0, 0, 600, 400);
    const inside = [card("m1", 20, 20), card("m2", 200, 40)];
    const outside = [card("f1", 0, 900), card("f2", 400, 900), card("f3", 800, 900)];
    const input = [...inside, ...outside];
    const { nodes, areas } = arrangeLayer(input, [link("m1", "m2"), link("f1", "f2")], [area]);
    for (const free of outside) {
      const rect = rectsOf(input, nodes).find((r) => r.id === free.id)!;
      expect(rectsOverlap(rect, areas[0])).toBe(false);
      expect(rect.y).toBeGreaterThanOrEqual(areas[0].y + areas[0].h);
    }
    expect(noneOverlap(rectsOf(input, nodes))).toBe(true);
  });

  it("stejný vstup dá dvakrát stejné rozvržení", () => {
    const area = frame("area1", 0, 0, 600, 400);
    const input = [card("m1", 20, 20), card("m2", 200, 40), card("f1", 0, 900), card("f2", 400, 900)];
    const edges = [link("m1", "m2"), link("f1", "f2")];
    expect(arrangeLayer(input, edges, [area])).toEqual(arrangeLayer(input, edges, [area]));
  });

  it("dvanáct karet, vazby napříč a jedna oblast: po srovnání se nepřekrývá vůbec nic", () => {
    const area = frame("area1", 0, 0, 600, 400);
    const input = [
      card("n1", 20, 20),
      card("n2", 200, 40),
      card("n3", 60, 150),
      card("n4", 300, 200),
      card("n5", 40, 700),
      card("n6", 380, 720),
      card("n7", 720, 700),
      card("n8", 60, 1000, 240, 140),
      card("n9", 400, 1000),
      card("n10", 760, 1040),
      card("n11", 1100, 700, 240, 140),
      card("n12", 1100, 1000),
    ];
    const edges = [
      link("n1", "n2"),
      link("n2", "n3", "action"),
      link("n3", "n4", "rule"),
      link("n4", "n5"),
      link("n5", "n6", "block"),
      link("n6", "n7"),
      link("n5", "n8"),
      link("n9", "n10"),
      link("n10", "n9"),
      link("area1", "area2", "flow"),
    ];
    const { nodes, areas } = arrangeLayer(input, edges, [area]);
    expect(nodes).toHaveLength(12);
    const rects = rectsOf(input, nodes);
    expect(noneOverlap(rects)).toBe(true);
    const memberIds = ["n1", "n2", "n3", "n4"];
    for (const rect of rects) {
      if (memberIds.includes(rect.id)) {
        expect(rect.x + rect.w).toBeLessThanOrEqual(areas[0].x + areas[0].w);
        expect(rect.y + rect.h).toBeLessThanOrEqual(areas[0].y + areas[0].h);
      } else {
        expect(rectsOverlap(rect, areas[0])).toBe(false);
      }
    }
  });
});
