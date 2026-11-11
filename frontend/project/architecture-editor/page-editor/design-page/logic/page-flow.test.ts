import { describe, expect, it } from "vitest";
import type { LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { pageFlow } from "./page-flow";

const box = (id: string, x: number, y: number, w: number, h: number): LayoutSection => ({ id, name: id, role: "content", box: { x, y, w, h } } as LayoutSection);
const ids = (rows: ReturnType<typeof pageFlow>) => rows.map((row) => row.columns.map((column) => column.items.map((item) => item.id)));

describe("tok stránky v pohledu Design", () => {
  it("boxy na celou šířku jdou shora dolů podle y, ne podle pořadí v datech", () => {
    const rows = pageFlow([box("pata", 0, 6, 12, 2), box("hlava", 0, 0, 12, 2), box("hero", 0, 2, 12, 4)]);
    expect(ids(rows)).toEqual([[["hlava"]], [["hero"]], [["pata"]]]);
    expect(rows[0]).toMatchObject({ gaps: [0], rest: 0 });
  });
  it("boxy se překrývajícím rozsahem y stojí vedle sebe zleva doprava", () => {
    const rows = pageFlow([box("vpravo", 8, 1, 4, 2), box("vlevo", 0, 0, 8, 3)]);
    expect(ids(rows)).toEqual([[["vlevo"], ["vpravo"]]]);
    expect(rows[0].columns.map((column) => column.span)).toEqual([8, 4]);
  });
  it("vysoký box vlevo a dva nad sebou vpravo: dva sloupce, ne tři boxy vedle sebe", () => {
    const rows = pageFlow([box("dole", 6, 2, 6, 2), box("vysoky", 0, 0, 6, 4), box("nahore", 6, 0, 6, 2)]);
    expect(ids(rows)).toEqual([[["vysoky"], ["nahore", "dole"]]]);
  });
  it("mezery ve sloupcích zůstanou: box uprostřed má prázdno vlevo i vpravo", () => {
    expect(pageFlow([box("stred", 3, 0, 6, 2)])[0]).toMatchObject({ gaps: [3], rest: 3 });
  });
  it("prázdný rodič = žádný řádek", () => {
    expect(pageFlow([])).toEqual([]);
  });
});
