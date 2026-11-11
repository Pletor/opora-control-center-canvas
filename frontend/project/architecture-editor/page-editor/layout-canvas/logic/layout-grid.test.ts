import { describe, expect, it } from "vitest";
import type { PageSection } from "@/shared/types/logic/types";
import { canNest, cellAt, clampBox, depthOf, endBox, layoutSections, settle, subtreeIds, ROW_PITCH, type LayoutSection } from "./layout-grid";

const sec = (id: string, box?: LayoutSection["box"], parent?: string): PageSection => ({ id, role: "content", name: id, intent: "", ...(box ? { box } : {}), ...(parent ? { parent } : {}) });

describe("mřížka", () => {
  it("přichytí box na celá čísla v mezích 12 sloupců", () => {
    expect(clampBox({ x: 10.6, y: -2, w: 4.2, h: 0 })).toEqual({ x: 8, y: 0, w: 4, h: 1 });
    expect(clampBox({ x: 0, y: 500, w: 30, h: 99 })).toEqual({ x: 0, y: 199, w: 12, h: 40 });
  });
  it("buňka pod ukazatelem podle kroku sloupce a řádku včetně mezery", () => {
    expect(cellAt({ left: 100, top: 50, width: 1192 }, { x: 100 + 200 + 1, y: 50 + ROW_PITCH * 3 + 1 })).toEqual({ x: 2, y: 3 });
    expect(cellAt({ left: 0, top: 0, width: 1192 }, { x: 199, y: ROW_PITCH - 1 })).toEqual({ x: 1, y: 0 });
    expect(cellAt({ left: 0, top: 0, width: 1200 }, { x: -40, y: -9 })).toEqual({ x: 0, y: 0 });
    expect(cellAt({ left: 0, top: 0, width: 1200 }, { x: 5000, y: 0 }).x).toBe(11);
  });
  it("nový box jde na konec pod nejnižšího sourozence", () => {
    expect(endBox([{ x: 0, y: 0, w: 12, h: 2 }, { x: 0, y: 2, w: 6, h: 4 }], 12, 3)).toEqual({ x: 0, y: 6, w: 12, h: 3 });
    expect(endBox([], 6, 2)).toEqual({ x: 0, y: 0, w: 6, h: 2 });
  });
  it("kolize posune box pod souseda, volný box nechá", () => {
    const siblings = [{ x: 0, y: 0, w: 12, h: 2 }, { x: 0, y: 2, w: 6, h: 3 }];
    expect(settle({ x: 3, y: 1, w: 4, h: 2 }, siblings)).toEqual({ x: 3, y: 5, w: 4, h: 2 });
    expect(settle({ x: 6, y: 2, w: 6, h: 2 }, siblings)).toEqual({ x: 6, y: 2, w: 6, h: 2 });
  });
});

describe("starší sekce a vnoření", () => {
  it("sekce bez boxu se skládají pod boxy na celou šířku, uložené boxy zůstanou", () => {
    const sections = layoutSections([sec("a"), sec("b", { x: 0, y: 0, w: 12, h: 3 }), sec("c")]);
    expect(sections.map((section) => section.box)).toEqual([{ x: 0, y: 3, w: 12, h: 2 }, { x: 0, y: 0, w: 12, h: 3 }, { x: 0, y: 5, w: 12, h: 2 }]);
  });
  it("neznámý, vlastní i zacyklený rodič se zahodí", () => {
    const sections = layoutSections([sec("a", undefined, "missing"), sec("b", undefined, "b"), sec("c", undefined, "d"), sec("d", undefined, "c"), sec("e", undefined, "a")]);
    expect(sections.map((section) => section.parent ?? null)).toEqual([null, null, null, null, "a"]);
  });
  const tree = layoutSections([sec("a", { x: 0, y: 0, w: 12, h: 4 }), sec("b", { x: 0, y: 0, w: 6, h: 2 }, "a"), sec("c", { x: 0, y: 0, w: 6, h: 1 }, "b"), sec("d", { x: 0, y: 4, w: 12, h: 2 })]);
  it("hloubka, potomci a dovolené vnoření (bez cyklu, nejvýš 3 úrovně)", () => {
    expect(depthOf(tree, null)).toBe(0);
    expect(depthOf(tree, "c")).toBe(3);
    expect([...subtreeIds(tree, "a")]).toEqual(["a", "b", "c"]);
    expect(canNest(tree, "a", "c")).toBe(false);
    expect(canNest(tree, null, "c")).toBe(false);
    expect(canNest(tree, null, "b")).toBe(true);
    expect(canNest(tree, "d", "b")).toBe(true);
    expect(canNest(tree, "b", "d")).toBe(true);
    expect(canNest(tree, "a", "d")).toBe(false);
    expect(canNest(tree, "a", null)).toBe(true);
  });
});
