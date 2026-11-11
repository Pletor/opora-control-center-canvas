import { describe, expect, it } from "vitest";
import type { LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { besideScene, focusPath, inspirationSkeletons, notInScene, withBoxParam } from "./box-focus";

const sec = (id: string, parent?: string): LayoutSection => ({ id, role: "content", name: id, intent: "", box: { x: 0, y: 0, w: 12, h: 2 }, ...(parent ? { parent } : {}) });

describe("zanořený pohled boxu", () => {
  it("drobečky vedou od kořenového boxu k otevřenému; neznámý box = žádná cesta", () => {
    const sections = [sec("main"), sec("article", "main"), sec("quote", "article")];
    expect(focusPath(sections, "quote").map((item) => item.id)).toEqual(["main", "article", "quote"]);
    expect(focusPath(sections, "main").map((item) => item.id)).toEqual(["main"]);
    expect(focusPath(sections, "nic")).toEqual([]);
    expect(focusPath(sections, null)).toEqual([]);
  });
  it("cyklus rodičů neuvízne", () => {
    expect(focusPath([sec("a", "b"), sec("b", "a")], "a").map((item) => item.id)).toEqual(["b", "a"]);
  });
  it("adresa nese otevřený box a návrat ho smaže, ostatní parametry zůstanou", () => {
    expect(withBoxParam("?project=p&pageId=k", "hero")).toBe("project=p&pageId=k&boxId=hero");
    expect(withBoxParam("?project=p&boxId=hero", null)).toBe("project=p");
  });
  it("vloží jen obrázky, které v kresbě nejsou", () => {
    expect(notInScene(["a", "b", "c"], [{ type: "image", fileId: "a" }, { type: "image", fileId: "b", isDeleted: true }, { type: "rectangle" }])).toEqual(["b", "c"]);
  });
  it("obrázky jdou vpravo vedle kresby, zmenšené s poměrem stran", () => {
    expect(besideScene([])).toEqual({ x: 0, y: 0 });
    expect(besideScene([{ x: 10, y: 50, width: 100, height: 20 }, { x: 0, y: 30, width: 50, height: 5 }, { x: 900, y: 0, width: 9, height: 9, isDeleted: true }])).toEqual({ x: 150, y: 30 });
    expect(inspirationSkeletons([{ fileId: "a", width: 1280, height: 640 }, { fileId: "b", width: 200, height: 100 }], { x: 0, y: 5 })).toEqual([
      { type: "image", fileId: "a", x: 0, y: 5, width: 640, height: 320, status: "saved" },
      { type: "image", fileId: "b", x: 680, y: 5, width: 200, height: 100, status: "saved" },
    ]);
  });
});
