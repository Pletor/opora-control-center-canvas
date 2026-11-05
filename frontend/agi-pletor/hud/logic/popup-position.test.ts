import { describe, expect, it } from "vitest";
import { clampPosition, defaultPosition } from "./popup-position";
import { parseListenPrefs } from "./listen-prefs";

const popup = { w: 300, h: 200 };
const viewport = { w: 1000, h: 800 };

describe("popup-position", () => {
  it("výchozí roh je vpravo dole s okrajem", () => {
    expect(defaultPosition(popup, viewport)).toEqual({ x: 688, y: 588 });
  });
  it("poloha uvnitř okna zůstane, mimo okno se ořízne", () => {
    expect(clampPosition({ x: 100, y: 50 }, popup, viewport)).toEqual({ x: 100, y: 50 });
    expect(clampPosition({ x: -40, y: 5000 }, popup, viewport)).toEqual({ x: 12, y: 588 });
    expect(clampPosition({ x: 2000, y: -3 }, popup, viewport)).toEqual({ x: 688, y: 12 });
  });
  it("po zmenšení okna se popup vrátí do viewportu; větší než okno drží levý horní roh", () => {
    expect(clampPosition({ x: 688, y: 588 }, popup, { w: 500, h: 400 })).toEqual({ x: 188, y: 188 });
    expect(clampPosition({ x: 50, y: 50 }, popup, { w: 200, h: 100 })).toEqual({ x: 12, y: 12 });
  });
});

describe("parseListenPrefs", () => {
  it("čte oslovení a polohu, vadná data dají výchozí", () => {
    expect(parseListenPrefs('{"wakeOnly":true,"position":{"x":5,"y":6}}')).toEqual({ wakeOnly: true, position: { x: 5, y: 6 } });
    expect(parseListenPrefs('{"position":{"x":"a"}}')).toEqual({ wakeOnly: false, position: null });
    expect(parseListenPrefs("{rozbité")).toEqual({ wakeOnly: false, position: null });
  });
});
