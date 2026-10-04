import { describe, expect, it } from "vitest";
import { viewportShowsAllNodes } from "./viewport-visibility";

const size = { width: 800, height: 600 };
const card = { x: 100, y: 100, w: 270, h: 90 };

describe("viewportShowsAllNodes", () => {
  it("karta uvnitř plochy je vidět", () => expect(viewportShowsAllNodes({ x: 0, y: 0, zoom: 1 }, size, [card])).toBe(true));
  it("pohled mimo všechny karty je prázdný", () => {
    expect(viewportShowsAllNodes({ x: -5000, y: 0, zoom: 1 }, size, [card])).toBe(false);
    expect(viewportShowsAllNodes({ x: 0, y: 3000, zoom: 1 }, size, [card])).toBe(false);
  });
  it("jedna schovaná karta stačí k přiblížení všeho a počítá se zoom", () => {
    expect(viewportShowsAllNodes({ x: 0, y: 0, zoom: 1 }, size, [card, { ...card, x: 9000 }])).toBe(false);
    expect(viewportShowsAllNodes({ x: 0, y: 0, zoom: 0.05 }, size, [card, { ...card, x: 9000 }])).toBe(true);
  });
  it("prázdná mapa nevyžaduje přiblížení", () => expect(viewportShowsAllNodes({ x: -9999, y: 0, zoom: 1 }, size, [])).toBe(true));
});
