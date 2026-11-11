import { describe, expect, it } from "vitest";
import { MAX_PAGE_SECTIONS } from "../../../domain-site/logic/page-site";
import { addBox, moveBox, newSectionId, removeBox, resizeBox } from "./layout-edit";
import type { LayoutSection } from "./layout-grid";
import { BOX_KINDS, TEMPLATES, templateSections } from "./layout-templates";
import { settleLayout } from "./settle-layout";

const box = (id: string, x: number, y: number, w: number, h: number, parent?: string): LayoutSection =>
  ({ id, role: "content", name: id, intent: "", box: { x, y, w, h }, ...(parent ? { parent } : {}) });
const header = BOX_KINDS[0];

describe("úpravy layoutu", () => {
  it("nové id je první volné sekce-N", () => {
    expect(newSectionId([{ id: "sekce-1" }, { id: "sekce-3" }])).toBe("sekce-2");
  });
  it("klik přidá box na konec stránky, tah ho nechá na buňce a sourozenec uhne dolů", () => {
    const start = [box("a", 0, 0, 12, 3)];
    expect(addBox(start, header, null).at(-1)).toEqual({ id: "sekce-1", role: "header", name: "Hlavička", intent: "", box: { x: 0, y: 3, w: 12, h: 2 } });
    expect(addBox(start, header, null, { x: 0, y: 1 }).map((section) => section.box)).toEqual([{ x: 0, y: 3, w: 12, h: 3 }, { x: 0, y: 1, w: 12, h: 2 }]);
  });
  it("box do boxu dostane rodiče a rodič povyroste; na limitu nebo ve 3. úrovni nic", () => {
    const next = addBox([box("a", 0, 0, 12, 2)], BOX_KINDS[1], "a");
    expect(next.at(-1)).toMatchObject({ parent: "a", box: { x: 0, y: 0, w: 12, h: 1 } });
    expect(next[0].box.h).toBe(2);
    const deep = [box("a", 0, 0, 12, 9), box("b", 0, 0, 12, 6, "a"), box("c", 0, 0, 12, 3, "b")];
    expect(addBox(deep, header, "c")).toBe(deep);
    const full = Array.from({ length: MAX_PAGE_SECTIONS }, (_, i) => box("s" + i, 0, i, 12, 1));
    expect(addBox(full, header, null)).toBe(full);
  });
  it("posun přichytí box na buňku, kolidující sourozenec uhne dolů a vnoření změní rodiče", () => {
    const start = [box("a", 0, 0, 12, 2), box("b", 0, 2, 12, 2)];
    expect(moveBox(start, "b", null, { x: 6.4, y: 0.2, w: 6, h: 2 }).map((section) => section.box)).toEqual([{ x: 0, y: 2, w: 12, h: 2 }, { x: 6, y: 0, w: 6, h: 2 }]);
    const nested = moveBox(start, "b", "a", { x: 0, y: 0, w: 12, h: 2 });
    expect(nested[1]).toMatchObject({ parent: "a", box: { x: 0, y: 0, w: 12, h: 2 } });
    expect(nested[0].box.h).toBe(3);
    expect(moveBox(nested, "b", null, { x: 0, y: 5, w: 12, h: 2 })[1]).not.toHaveProperty("parent");
    expect(moveBox(nested, "a", "b", { x: 0, y: 0, w: 1, h: 1 })).toBe(nested);
  });
  it("velikost drží box v mřížce a box pod ním odsune", () => {
    expect(resizeBox([box("a", 8, 0, 4, 2)], "a", 9, 50)[0].box).toEqual({ x: 8, y: 0, w: 4, h: 40 });
    expect(resizeBox([box("a", 0, 0, 6, 2), box("b", 0, 2, 12, 2)], "a", 6, 4)[1].box.y).toBe(4);
  });
  it("odebrání vezme i vnořené boxy", () => {
    expect(removeBox([box("a", 0, 0, 12, 3), box("b", 0, 0, 12, 1, "a"), box("c", 0, 3, 12, 1)], "a").map((s) => s.id)).toEqual(["c"]);
  });
});

describe("šablony", () => {
  it("tři šablony v mezích mřížky bez překryvu sourozenců", () => {
    expect(TEMPLATES.map((template) => template.name)).toEqual(["Klasický web", "Landing", "Aplikace"]);
    for (const template of TEMPLATES) for (const [, , x, , w] of template.boxes) expect(x + w).toBeLessThanOrEqual(12);
    for (const template of TEMPLATES) { const sections = templateSections(template.id, []); expect(settleLayout(sections)).toBe(sections); }
  });
  it("landing má hlavičku, úvod, tři sloupce, výzvu a patičku s id volnými vůči dosavadním sekcím", () => {
    const sections = templateSections("landing", [{ id: "sekce-1" }]);
    expect(sections.map((section) => section.role)).toEqual(["header", "hero", "content", "content", "content", "cta", "footer"]);
    expect(sections[0].id).toBe("sekce-2");
    expect(new Set(sections.map((section) => section.id)).size).toBe(7);
    expect(templateSections("unknown", [])).toEqual([]);
  });
});
