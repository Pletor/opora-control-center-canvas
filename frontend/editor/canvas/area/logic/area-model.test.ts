import { describe, expect, it } from "vitest";
import {
  AREA_COLORS,
  AREA_SIZE_MAX,
  AREA_SIZE_MIN,
  areaColorOf,
  areaHost,
  areaLabel,
  areaOf,
  areaRollup,
  EMPTY_AREA_ROLLUP,
  isArea,
  isFreeSpot,
  membersOf,
  moveWithMembers,
  newArea,
  nextAreaSpot,
  resizeArea,
  setAreaColor,
} from "./area-model";
import type { CanvasNode } from "@/shared/types/logic/types";

function area(id: string, x: number, y: number, w: number, h: number, parentId: string | null = null): CanvasNode {
  return { id, parentId, kind: "area", name: id, purpose: "", x, y, size: { w, h } };
}

function node(id: string, x: number, y: number, parentId: string | null = null, kind: CanvasNode["kind"] = "node"): CanvasNode {
  return { id, parentId, kind, name: id, purpose: "", x, y };
}

describe("area-model", () => {
  it("isArea rozpozná druh uzlu", () => {
    expect(isArea({ kind: "area" })).toBe(true);
    expect(isArea({ kind: "node" })).toBe(false);
    expect(isArea({ kind: "comment" })).toBe(false);
  });

  it("newArea vytvoří nepojmenovanou oblast s výchozí velikostí na daném místě", () => {
    const created = newArea("sector-1", 100, 200);
    expect(created.kind).toBe("area");
    expect(created.parentId).toBe("sector-1");
    expect(created.name).toBe("");
    expect(created.purpose).toBe("");
    expect(created.x).toBe(100);
    expect(created.y).toBe(200);
    expect(created.size).toEqual({ w: 720, h: 480 });
    expect(created.sourceRef).toBeUndefined();
    expect(typeof created.id).toBe("string");
  });

  it("areaLabel vrátí jméno, nebo když je prázdné (i jen bílé), „Nepojmenovaná oblast“", () => {
    expect(areaLabel({ name: "Platby" })).toBe("Platby");
    expect(areaLabel({ name: "" })).toBe("Nepojmenovaná oblast");
    expect(areaLabel({ name: "   " })).toBe("Nepojmenovaná oblast");
  });

  it("uzel uvnitř obdélníku oblasti do ní patří", () => {
    const big = area("big", 0, 0, 1000, 1000);
    const n = node("n1", 100, 100); // střed (236, 220), uvnitř [0,1000]×[0,1000]
    expect(areaOf(n, [big, n])?.id).toBe("big");
  });

  it("uzel mimo obdélník oblasti do ní nepatří", () => {
    const small = area("small", 0, 0, 200, 200);
    const n = node("n1", 100, 100); // střed (236, 220), těsně mimo
    expect(areaOf(n, [small, n])).toBeNull();
  });

  it("oblast na jiné vrstvě člena nemá", () => {
    const other = area("layer-area", 0, 0, 1000, 1000, "jinde");
    const n = node("n1", 100, 100, null);
    expect(areaOf(n, [other, n])).toBeNull();
  });

  it("při souběhu vyhrává nejmenší oblast", () => {
    const outer = area("outer", 0, 0, 2000, 2000);
    const inner = area("inner", 0, 0, 500, 500);
    const n = node("n1", 100, 100); // střed uvnitř obou
    expect(areaOf(n, [outer, inner, n])?.id).toBe("inner");
  });

  it("komentář používá svůj vlastní střed (x+120, y+80)", () => {
    const a = area("a", 0, 0, 150, 100);
    const c = node("c1", 10, 10, null, "comment"); // střed (130, 90), uvnitř [0,150]×[0,100]
    const n = node("n1", 10, 10); // střed (146, 130), mimo
    expect(areaOf(c, [a, c, n])?.id).toBe("a");
    expect(areaOf(n, [a, c, n])).toBeNull();
  });

  it("oblast sama nikdy nepatří do jiné oblasti", () => {
    const outer = area("outer", 0, 0, 2000, 2000);
    const inner = area("inner", 100, 100, 200, 200);
    expect(areaOf(inner, [outer, inner])).toBeNull();
  });

  it("oblast bez size ji nikdy neudělá kontejnerem", () => {
    const broken = { id: "broken", parentId: null, kind: "area" as const, name: "", purpose: "", x: 0, y: 0 };
    const n = node("n1", 0, 0);
    expect(areaOf(n, [broken, n])).toBeNull();
  });

  it("membersOf vrátí jen uzly té dané oblasti, ne jinou oblast ani cizí vrstvu", () => {
    const a = area("a", 0, 0, 1000, 1000);
    const other = area("other", 0, 0, 1000, 1000, "jinde");
    const inside = node("n1", 100, 100);
    const outside = node("n2", 5000, 5000);
    const nodes = [a, other, inside, outside];
    expect(membersOf(a, nodes).map((n) => n.id)).toEqual(["n1"]);
  });

  it("moveWithMembers posune oblast i její členy o stejný vektor, ostatní nechá být", () => {
    const a = area("a", 0, 0, 1000, 1000);
    const inside = node("n1", 100, 100);
    const outside = node("n2", 5000, 5000);
    const moved = moveWithMembers([a, inside, outside], "a", 50, -20);
    const byId = new Map(moved.map((n) => [n.id, n]));
    expect(byId.get("a")).toMatchObject({ x: 50, y: -20 });
    expect(byId.get("n1")).toMatchObject({ x: 150, y: 80 });
    expect(byId.get("n2")).toMatchObject({ x: 5000, y: 5000 });
  });

  it("moveWithMembers na neexistující oblast vrátí seznam beze změny", () => {
    const nodes = [node("n1", 1, 2)];
    expect(moveWithMembers(nodes, "chybi", 10, 10)).toEqual(nodes);
  });

  it("nextAreaSpot na prázdné vrstvě vrátí (80, 80)", () => {
    expect(nextAreaSpot([], null)).toEqual({ x: 80, y: 80 });
    expect(nextAreaSpot([], "layer-1")).toEqual({ x: 80, y: 80 });
  });

  it("nextAreaSpot obejde existující oblast a zůstane na stejném řádku, když je místo", () => {
    const existing = area("a", 80, 80, 720, 480);
    const spot = nextAreaSpot([existing], null);
    expect(isFreeSpot({ x: spot.x, y: spot.y, w: 720, h: 480 }, [existing], null)).toBe(true);
    expect(spot.y).toBe(80);
    expect(spot.x).toBeGreaterThan(80);
  });

  it("nextAreaSpot přeskočí první řádek plný karet a sestoupí na volný řádek níž", () => {
    const cards: CanvasNode[] = [];
    for (let x = -400; x <= 3400; x += 200) {
      cards.push(node(`c${x}`, x, 80));
    }
    const spot = nextAreaSpot(cards, null);
    expect(spot.y).toBeGreaterThan(80);
    expect(isFreeSpot({ x: spot.x, y: spot.y, w: 720, h: 480 }, cards, null)).toBe(true);
  });

  it("nextAreaSpot ignoruje uzly z jiné vrstvy", () => {
    const other = area("a", 80, 80, 720, 480, "jina-vrstva");
    expect(nextAreaSpot([other], null)).toEqual({ x: 80, y: 80 });
  });

  it("isFreeSpot vrací false, když obdélník protíná oblast i s rezervou", () => {
    const existing = area("a", 80, 80, 720, 480);
    expect(isFreeSpot({ x: 100, y: 100, w: 720, h: 480 }, [existing], null)).toBe(false);
    // těsně mimo i s 40px rezervou
    expect(isFreeSpot({ x: 840, y: 80, w: 720, h: 480 }, [existing], null)).toBe(true);
  });

  it("resizeArea ohraničí rozměr na 120..20000 v obou osách", () => {
    const a = area("a", 0, 0, 720, 480);
    expect(resizeArea(a, 50, 50).size).toEqual({ w: AREA_SIZE_MIN, h: AREA_SIZE_MIN });
    expect(resizeArea(a, 50000, 50000).size).toEqual({ w: AREA_SIZE_MAX, h: AREA_SIZE_MAX });
    expect(resizeArea(a, 800, 300).size).toEqual({ w: 800, h: 300 });
  });

  it("AREA_COLORS nabízí šest barev s českými popisky", () => {
    expect(AREA_COLORS.map((c) => c.value)).toEqual(["indigo", "teal", "amber", "rose", "violet", "slate"]);
    expect(AREA_COLORS.map((c) => c.label)).toEqual(["Indigová", "Tyrkysová", "Jantarová", "Růžová", "Fialová", "Šedá"]);
  });

  it("areaColorOf vrátí indigo, když oblast barvu nemá", () => {
    const a = area("a", 0, 0, 720, 480);
    expect(areaColorOf(a)).toBe("indigo");
  });

  it("areaColorOf vrátí nastavenou barvu", () => {
    const a = setAreaColor(area("a", 0, 0, 720, 480), "teal");
    expect(areaColorOf(a)).toBe("teal");
  });

  it("areaColorOf spadne na indigo u neznámé (starší nebo cizí) hodnoty", () => {
    const a = { ...area("a", 0, 0, 720, 480), color: "mystery" as unknown as CanvasNode["color"] };
    expect(areaColorOf(a)).toBe("indigo");
  });

  it("setAreaColor vrátí novou kopii uzlu s nastavenou barvou, originál nezmění", () => {
    const a = area("a", 0, 0, 720, 480);
    const updated = setAreaColor(a, "rose");
    expect(updated).not.toBe(a);
    expect(updated.color).toBe("rose");
    expect(a.color).toBeUndefined();
  });

  it("areaRollup ukáže jen nenulové části se skloňováním", () => {
    expect(areaRollup({ sectors: 3, cards: 14, closed: 5 })).toBe("3 sektory · 14 karet · 5 hotovo");
    expect(areaRollup({ sectors: 1, cards: 1, closed: 0 })).toBe("1 sektor · 1 karta");
    expect(areaRollup({ sectors: 2, cards: 2, closed: 0 })).toBe("2 sektory · 2 karty");
    expect(areaRollup({ sectors: 5, cards: 5, closed: 1 })).toBe("5 sektorů · 5 karet · 1 hotovo");
    expect(areaRollup({ sectors: 0, cards: 4, closed: 0 })).toBe("4 karty");
    expect(areaRollup({ sectors: 2, cards: 0, closed: 0 })).toBe("2 sektory");
  });

  it("areaRollup prázdné oblasti vyzve k záměru", () => {
    expect(areaRollup({ sectors: 0, cards: 0, closed: 0 })).toBe(EMPTY_AREA_ROLLUP);
  });

  it("areaHost najde sektor, v jehož vrstvě oblast leží; na kořeni nebo pod uzlem je null", () => {
    const nodes = [
      { id: "s4", kind: "sector", name: "4. VRSTVA" },
      { id: "n1", kind: "node", name: "Karta" },
    ];
    expect(areaHost({ parentId: "s4" }, nodes)).toEqual({ id: "s4", name: "4. VRSTVA", kind: "sector" });
    expect(areaHost({ parentId: null }, nodes)).toBeNull();
    expect(areaHost({ parentId: "n1" }, nodes)).toEqual({ id: "n1", name: "Karta", kind: "node" });
    expect(areaHost({ parentId: "chybí" }, nodes)).toEqual({ id: "chybí", name: "", kind: "missing" });
  });
});
