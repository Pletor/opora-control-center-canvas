import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { areaOf, membershipPoint } from "./area-model";
import { dropCard, growArea, startGrowth, stepGrowth, withGrownArea, type Rect } from "./area-growth";

function area(id: string, x: number, y: number, w: number, h: number): CanvasNode {
  return { id, parentId: null, kind: "area", name: id, purpose: "", x, y, size: { w, h } };
}
function card(id: string, x: number, y: number): CanvasNode {
  return { id, parentId: null, kind: "node", name: id, purpose: "", x, y };
}
const body = (n: CanvasNode): Rect & { id: string } => ({ id: n.id, x: n.x, y: n.y, w: 360, h: 240 });
const none = { rects: [], points: [] };
const home: Rect = { x: 0, y: 0, w: 800, h: 600 };

/** Rámeček po růstu musí kartu pojmout i s okrajem 16 px. */
function holds(frame: Rect, r: Rect): boolean {
  return frame.x <= r.x - 16 && frame.y <= r.y - 16 && frame.x + frame.w >= r.x + r.w + 16 && frame.y + frame.h >= r.y + r.h + 16;
}

describe("growArea", () => {
  it("roste doprava, dolů, doleva i nahoru tak, aby pojal kartu s okrajem", () => {
    const cases: Rect[] = [
      { x: 600, y: 100, w: 360, h: 240 },
      { x: 100, y: 500, w: 360, h: 240 },
      { x: -200, y: 100, w: 360, h: 240 },
      { x: 100, y: -150, w: 360, h: 240 },
    ];
    for (const c of cases) {
      const grown = growArea(home, c, { x: c.x + 180, y: c.y + 120 }, none)!;
      expect(grown).not.toBeNull();
      expect(holds(grown, c)).toBe(true);
    }
    expect(growArea(home, cases[0], { x: 780, y: 220 }, none)).toEqual({ x: 0, y: 0, w: 976, h: 600 });
    expect(growArea(home, cases[2], { x: -20, y: 220 }, none)).toEqual({ x: -216, y: 0, w: 1016, h: 600 });
  });

  it("nikdy se nezmenší: karta uvnitř vrátí stejný rámeček", () => {
    expect(growArea(home, { x: 100, y: 100, w: 360, h: 240 }, { x: 280, y: 220 }, none)).toEqual(home);
  });

  it("pojme i bod členství s rezervou, když leží mimo obdélník karty", () => {
    const grown = growArea(home, { x: 600, y: 400, w: 270, h: 90 }, { x: 780, y: 520 }, none)!;
    expect(grown.x + grown.w).toBeGreaterThanOrEqual(796);
    expect(grown.y + grown.h).toBeGreaterThanOrEqual(536);
  });

  it("zastaví se o cizí kartu, oblast i bod členství cizí karty", () => {
    const c = { x: 600, y: 100, w: 360, h: 240 };
    const p = { x: 780, y: 220 };
    expect(growArea(home, c, p, { rects: [{ x: 990, y: 0, w: 360, h: 240 }], points: [] })).toBeNull();
    expect(growArea(home, c, p, { rects: [{ x: 960, y: 300, w: 400, h: 400 }], points: [] })).toBeNull();
    expect(growArea(home, c, p, { rects: [], points: [{ x: 900, y: 50 }] })).toBeNull();
    expect(growArea(home, c, p, { rects: [{ x: 2000, y: 0, w: 360, h: 240 }], points: [] })).not.toBeNull();
  });

  it("karta mimo oblast → null", () => {
    expect(growArea(home, { x: 900, y: 100, w: 360, h: 240 }, { x: 1080, y: 220 }, none)).toBeNull();
  });
});

describe("session růstu", () => {
  const a = area("a", 0, 0, 800, 600);
  const b = area("b", 1400, 0, 600, 600);
  const member = card("m", 40, 40);
  const foreign = card("f", 0, 672);

  it("domovská oblast ze začátku tahu; areaOf po růstu vrací domovskou oblast", () => {
    const nodes = [a, b, member, foreign];
    const session = startGrowth(member, nodes, nodes.filter((n) => n.kind !== "area").map(body))!;
    expect(session.homeId).toBe("a");
    const moved = { ...member, x: 640, y: 40 };
    const grown = stepGrowth(session, moved, body(moved), nodes)!;
    expect(grown.w).toBeGreaterThan(800);
    expect(areaOf(moved, withGrownArea(nodes, "a", grown))?.id).toBe("a");
  });

  it("karta bez oblasti tah bez růstu", () => {
    const loose = card("l", 2400, 1200);
    expect(startGrowth(loose, [a, loose], [body(loose)])).toBeNull();
  });

  it("puštění: růst prošel → karta i nový rámeček; blokováno → dnešní settleCard", () => {
    const nodes = [a, b, member, foreign];
    const session = startGrowth(member, nodes, nodes.filter((n) => n.kind !== "area").map(body))!;
    const moved = { ...member, x: 640, y: 40 };
    const ok = dropCard(session, moved, body(moved), [body(foreign)], [a, b]);
    expect(ok.area?.id).toBe("a");
    expect(ok).toMatchObject({ x: 640, y: 40 });
    // Dolů by narazil na cizí kartu f (y 672): vrací se dnešní usazení dovnitř oblasti, bez rámečku.
    const down = { ...member, x: 40, y: 400 };
    const blocked = dropCard(session, down, body(down), [body(foreign)], [a, b]);
    expect(blocked.area).toBeUndefined();
    expect(areaOf({ ...down, ...blocked }, [a, b])?.id).toBe("a");
    expect(blocked.y + 240).toBeLessThanOrEqual(600 - 16);
  });

  it("membershipPoint drží CENTRE_OFFSET", () => {
    expect(membershipPoint(card("x", 10, 20))).toEqual({ x: 190, y: 140 });
  });
});
