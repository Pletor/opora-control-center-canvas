import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { clampAreaResize, settleArea, settleCard, type Body } from "./solid-bodies";

/** Karta na plátně: uzel tam, kam ji uživatel pustil. Střed (136, 120) rozhoduje o členství v oblasti. */
const node = (id: string, x: number, y: number): CanvasNode => ({
  id,
  parentId: null,
  kind: "node",
  name: "",
  purpose: "",
  x,
  y,
});
/** Otisk karty: výchozí půdorys 272 × 240 na jejím levém horním rohu. */
const print = (id: string, x: number, y: number, w = 272, h = 240): Body => ({ id, x, y, w, h });
/** Oblast jako uzel grafu — s rozměrem, jinak by ji `areaOf` ani magnetismus nevzaly v potaz. */
const area = (id: string, x: number, y: number, w: number, h: number): CanvasNode => ({
  id,
  parentId: null,
  kind: "area",
  name: "",
  purpose: "",
  x,
  y,
  size: { w, h },
});
/** Rámeček oblasti jako pevné těleso — vstup pro settleArea a clampAreaResize. */
const frame = (id: string, x: number, y: number, w: number, h: number): Body => ({ id, x, y, w, h });

function rectsOverlap(a: Body, b: Body): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}
const onGrid = (value: number) => value % 8 === 0;

describe("settleCard", () => {
  it("karta puštěná napůl přes hranu oblasti skončí celá venku, s mezerou od rámečku", () => {
    const zone = area("zone", 0, 0, 400, 400);
    // Střed karty (436, 224) je za pravou hranou oblasti, karta tedy patří ven — a ven celá.
    const dropped = node("c", 300, 104);
    const at = settleCard(dropped, print("c", 300, 104), [], [zone]);
    expect(at).toEqual({ x: 424, y: 104 });
    expect(rectsOverlap({ ...print("c", at.x, at.y) }, frame("zone", 0, 0, 400, 400))).toBe(false);
    expect(at.x).toBeGreaterThanOrEqual(400 + 24);
  });

  it("karta se středem uvnitř oblasti se do ní vejde celá, s odsazením od hrany", () => {
    const zone = area("zone", 0, 0, 400, 400);
    // Střed (392, 224) padl dovnitř, ale pravý okraj karty by trčel ven — rámeček si ji zarovná k sobě.
    const dropped = node("c", 256, 104);
    const at = settleCard(dropped, print("c", 256, 104), [], [zone]);
    expect(at).toEqual({ x: 112, y: 104 });
    expect(at.x).toBeGreaterThanOrEqual(16);
    expect(at.x + 272).toBeLessThanOrEqual(400 - 16);
    expect(at.y + 240).toBeLessThanOrEqual(400 - 16);
  });

  it("karta uvnitř oblasti se uhne členovi, a přesto z oblasti nevypadne", () => {
    const zone = area("zone", 0, 0, 800, 600);
    const member = print("m", 16, 16);
    const at = settleCard(node("c", 100, 100), print("c", 100, 100), [member], [zone]);
    const placed = print("c", at.x, at.y);
    expect(rectsOverlap(placed, member)).toBe(false);
    expect(placed.x).toBeGreaterThanOrEqual(16);
    expect(placed.y).toBeGreaterThanOrEqual(16);
    expect(placed.x + placed.w).toBeLessThanOrEqual(800 - 16);
    expect(placed.y + placed.h).toBeLessThanOrEqual(600 - 16);
  });

  it("karta, která nikomu nepřekáží, zůstane přesně tam, kde ji uživatel pustil", () => {
    const zone = area("zone", 0, 0, 400, 400);
    const dropped = node("c", 903, 501);
    expect(settleCard(dropped, print("c", 903, 501), [], [zone])).toEqual({ x: 903, y: 501 });
  });

  it("posunutá karta dosedne na mřížku a stejný vstup dá dvakrát stejné místo", () => {
    const zone = area("zone", 0, 0, 400, 400);
    const dropped = node("c", 301, 101);
    const at = settleCard(dropped, print("c", 301, 101), [], [zone]);
    expect(onGrid(at.x)).toBe(true);
    expect(onGrid(at.y)).toBe(true);
    expect(settleCard(dropped, print("c", 301, 101), [], [zone])).toEqual(at);
  });
});

describe("settleArea", () => {
  it("oblast puštěná na jinou oblast se odsune a rámečky se neprotnou", () => {
    const moved = frame("a", 100, 100, 400, 300);
    const other = frame("b", 300, 150, 400, 300);
    const at = settleArea(moved, [other], []);
    expect(at).not.toEqual({ x: 100, y: 100 });
    expect(rectsOverlap({ ...moved, ...at }, other)).toBe(false);
    expect(onGrid(at.x)).toBe(true);
    expect(onGrid(at.y)).toBe(true);
  });

  it("oblast puštěná napůl přes cizí kartu se odsune a kartu nepřekryje", () => {
    const moved = frame("a", 0, 0, 400, 300);
    const stranger = print("c", 300, 100);
    const at = settleArea(moved, [], [stranger]);
    expect(rectsOverlap({ ...moved, ...at }, stranger)).toBe(false);
  });

  it("vlastní členové nejsou překážka: oblast nad svými kartami se nehne", () => {
    const moved = frame("a", 0, 0, 400, 300);
    expect(settleArea(moved, [], [])).toEqual({ x: 0, y: 0 });
  });

  it("stejný vstup dá dvakrát stejné místo", () => {
    const moved = frame("a", 100, 100, 400, 300);
    const other = frame("b", 300, 150, 400, 300);
    expect(settleArea(moved, [other], [])).toEqual(settleArea(moved, [other], []));
  });
});

describe("clampAreaResize", () => {
  it("růst se zastaví o mezeru před sousední oblastí", () => {
    const zone = frame("a", 0, 0, 200, 200);
    const neighbour = frame("b", 400, 0, 200, 200);
    const fitted = clampAreaResize(zone, [], [neighbour], [], 1000, 200);
    expect(fitted.w).toBe(376);
    expect(fitted.w + 24).toBeLessThanOrEqual(neighbour.x);
    expect(onGrid(fitted.w)).toBe(true);
  });

  it("růst se zastaví i před cizí kartou, která do cesty leží", () => {
    const zone = frame("a", 0, 0, 200, 200);
    const stranger = print("c", 0, 504);
    const fitted = clampAreaResize(zone, [], [], [stranger], 200, 2000);
    expect(fitted.h).toBe(480);
    expect(fitted.h + 24).toBeLessThanOrEqual(stranger.y);
  });

  it("zmenšit pod obsah nejde: rámeček své členy pojme celé i s odsazením", () => {
    const zone = frame("a", 0, 0, 600, 500);
    const member = print("m", 100, 100);
    const fitted = clampAreaResize(zone, [member], [], [], 120, 120);
    expect(fitted).toEqual({ w: 392, h: 360 });
    expect(member.x + member.w).toBeLessThanOrEqual(fitted.w - 16);
    expect(member.y + member.h).toBeLessThanOrEqual(fitted.h - 16);
  });

  it("volnou oblast bez sousedů zmenší přesně na vyžádaný rozměr a stejný vstup dá dvakrát totéž", () => {
    const zone = frame("a", 0, 0, 600, 500);
    expect(clampAreaResize(zone, [], [], [], 320, 240)).toEqual({ w: 320, h: 240 });
    expect(clampAreaResize(zone, [], [], [], 1001, 801)).toEqual(clampAreaResize(zone, [], [], [], 1001, 801));
    const odd = clampAreaResize(zone, [], [], [], 1001, 801);
    expect(onGrid(odd.w)).toBe(true);
    expect(onGrid(odd.h)).toBe(true);
  });
});
