import { describe, expect, it } from "vitest";
import { overlaps, type LayoutSection } from "./layout-grid";
import { settleLayout } from "./settle-layout";

const box = (id: string, x: number, y: number, w: number, h: number, parent?: string): LayoutSection =>
  ({ id, role: "content", name: id, intent: "", box: { x, y, w, h }, ...(parent ? { parent } : {}) });
const noOverlap = (sections: LayoutSection[]) => {
  for (const a of sections) for (const b of sections) {
    if (a !== b && (a.parent ?? null) === (b.parent ?? null)) expect(overlaps(a.box, b.box), `${a.id} × ${b.id}`).toBe(false);
  }
};

describe("usazení layoutu", () => {
  const messy = [box("hero", 0, 0, 12, 4), box("cols", 0, 2, 6, 3), box("side", 6, 3, 6, 3), box("foot", 0, 4, 12, 2)];

  it("překryv zmizí a box sjede těsně pod umístěného sourozence", () => {
    const next = settleLayout(messy);
    noOverlap(next);
    expect(next.map((section) => section.box)).toEqual([
      { x: 0, y: 0, w: 12, h: 4 }, { x: 0, y: 4, w: 6, h: 3 }, { x: 6, y: 4, w: 6, h: 3 }, { x: 0, y: 7, w: 12, h: 2 }]);
  });
  it("pořadí shora dolů i pořadí v seznamu zůstane, id a ostatní pole se nemění", () => {
    const next = settleLayout(messy);
    expect(next.map((section) => section.id)).toEqual(["hero", "cols", "side", "foot"]);
    const tops = [...next].sort((a, b) => a.box.y - b.box.y || a.box.x - b.box.x).map((section) => section.id);
    expect(tops).toEqual(["hero", "cols", "side", "foot"]);
    expect(next[0]).toBe(messy[0]);
    expect({ ...next[3], box: messy[3].box }).toEqual(messy[3]);
  });
  it("děti se vejdou do rodiče pod jeho hlavičku, i ve dvou úrovních", () => {
    const next = settleLayout([box("a", 0, 0, 12, 2), box("b", 0, 0, 12, 2, "a"), box("c", 0, 1, 6, 3, "b"), box("d", 0, 0, 6, 1, "b"), box("e", 0, 2, 12, 2)]);
    noOverlap(next);
    const of = (id: string) => next.find((section) => section.id === id)!.box;
    expect(of("c")).toEqual({ x: 0, y: 1, w: 6, h: 3 });
    expect(of("b").h).toBe(5);
    expect(of("a").h).toBe(6);
    expect(of("e").y).toBe(6);
  });
  it("druhé volání nic nemění a layout bez překryvu zůstane tentýž", () => {
    const once = settleLayout(messy);
    expect(settleLayout(once)).toBe(once);
    const clean = [box("a", 0, 0, 12, 2), box("b", 0, 2, 4, 3), box("c", 4, 2, 8, 3), box("d", 0, 1, 12, 1, "c")];
    expect(settleLayout(clean)).toBe(clean);
  });
  it("box s předností zůstane, kam ho člověk dal, sourozenci uhnou dolů", () => {
    const next = settleLayout([box("a", 0, 0, 12, 2), box("b", 0, 2, 12, 2), box("drop", 0, 0, 6, 1)], "drop");
    expect(next.map((section) => section.box.y)).toEqual([1, 3, 0]);
  });
});
