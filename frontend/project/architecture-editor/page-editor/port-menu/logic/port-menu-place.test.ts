import { describe, expect, it } from "vitest";
import { CLICK_SLOP, MENU_SIZE, PLAN_CARD, PLAN_GAP, isPortClick, menuPosition, newCardPosition, planBox, type Box } from "./port-menu-place";

const card: Box = { x: 100, y: 200, w: 270, h: 120 };
const port: Box = { x: 364, y: 247, w: 26, h: 26 };
/** Vstupní port karty: vlevo uprostřed výšky, zásahová plocha 26 px. */
const input: Box = { x: card.x - 33, y: card.y + card.h / 2 - 13, w: 26, h: 26 };
const hit = (a: Box, b: Box) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const menuBox = (at: { x: number; y: number }): Box => ({ ...at, ...MENU_SIZE });

describe("umístění nabídky", () => {
  it("má-li místo, stojí vpravo od výstupního portu a nepřekryje kartu ani její vstup", () => {
    const at = menuPosition(port, card, { w: 1200, h: 800 });
    expect(at.x).toBeGreaterThan(port.x + port.w);
    expect(hit(menuBox(at), card)).toBe(false);
    expect(hit(menuBox(at), input)).toBe(false);
  });
  it("u pravého okraje sedne pod kartu, uvnitř plochy a mimo vstup", () => {
    const at = menuPosition(port, card, { w: 600, h: 800 });
    expect(at.y).toBeGreaterThanOrEqual(card.y + card.h);
    expect(at.x + MENU_SIZE.w).toBeLessThanOrEqual(600);
    expect(hit(menuBox(at), input)).toBe(false);
  });
  it("u spodního okraje sedne nad kartu", () => {
    const low = { ...card, y: 560 }; const lowPort = { ...port, y: 607 };
    const at = menuPosition(lowPort, low, { w: 600, h: 720 });
    expect(at.y + MENU_SIZE.h).toBeLessThanOrEqual(low.y);
  });
  it("nikdy nevyjede z plochy", () => {
    const at = menuPosition({ ...port, y: -50 }, card, { w: 1200, h: 300 });
    expect(at.y).toBeGreaterThanOrEqual(8);
  });
});

describe("poloha nové karty", () => {
  const source = planBox({ kind: "node", x: 0, y: 300 });
  it("vpravo od zdroje ve stejné výšce, mimo jeho těleso podle serveru", () => {
    expect(newCardPosition(source, [source])).toEqual({ x: PLAN_CARD.w + PLAN_GAP, y: 300 });
  });
  it("obsazené místo vpravo přeskočí o řádek níž", () => {
    const blocker = planBox({ kind: "node", x: PLAN_CARD.w + PLAN_GAP, y: 300 });
    expect(newCardPosition(source, [source, blocker])).toEqual({ x: blocker.x, y: 300 + PLAN_CARD.h + PLAN_GAP });
  });
  it("oblast blokuje svým rozměrem", () => {
    const area = planBox({ kind: "area", x: 500, y: 0, size: { w: 720, h: 900 } });
    expect(newCardPosition(source, [source, area]).y).toBeGreaterThanOrEqual(900 + PLAN_GAP);
  });
});

describe("klik vs. tah z portu", () => {
  it("pohyb pod práh je klik, delší je tah, bez stisku nic", () => {
    expect(isPortClick({ x: 10, y: 10 }, { x: 12, y: 11 })).toBe(true);
    expect(isPortClick({ x: 10, y: 10 }, { x: 10 + CLICK_SLOP, y: 10 })).toBe(false);
    expect(isPortClick(null, { x: 0, y: 0 })).toBe(false);
  });
});
