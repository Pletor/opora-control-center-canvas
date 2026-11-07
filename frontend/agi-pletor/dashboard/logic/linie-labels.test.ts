import { describe, expect, it } from "vitest";
import { GAP, labelAnchor, labelOffsets, labelWidth, placeLabels, type LabelBall } from "./linie-labels";

const b = (ticketId: string, x: number, rowId = "r"): LabelBall => ({ ticketId, rowId, x, label: "Linie L6: barvy", stateLabel: "čeká na přijetí" });
const w = labelWidth(b("a", 0));

describe("kolize popisků", () => {
  it("volné popisky jsou všechny pod osou; jiný řádek nekoliduje", () => {
    const { slots, clusters, tier2 } = placeLabels([b("a", 0), b("b", GAP), b("c", 0, "jiny")], "");
    expect(Object.values(slots)).toEqual([{ side: 1, tier: 1 }, { side: 1, tier: 1 }, { side: 1, tier: 1 }]);
    expect(clusters).toEqual([]);
    expect(tier2.size).toBe(0);
  });
  it("střídá pod · nad · druhé patro, nejvýš dvě patra, zbytek po jednom „+1“; mezera ve slotu je 200 px", () => {
    const { slots, clusters, tier2 } = placeLabels([b("a", 0), b("b", 10), b("c", 20), b("d", 30), b("e", 40), b("f", 50), b("g", GAP)], "");
    expect([slots.a, slots.b, slots.c, slots.d]).toEqual([{ side: 1, tier: 1 }, { side: -1, tier: 1 }, { side: 1, tier: 2 }, { side: -1, tier: 2 }]);
    expect(slots.e).toBeUndefined();
    expect(clusters).toEqual([{ rowId: "r", x: 40, ids: ["e"] }, { rowId: "r", x: 50, ids: ["f"] }]);
    expect(slots.g).toEqual({ side: 1, tier: 1 }); // 200 px od „a“: první patro je zase volné
    expect([...tier2]).toEqual(["r"]);
  });
  it("vybraná má přednost: dostane místo pod osou, i když leží až za ostatními; vzdálené sousedy nevytlačí", () => {
    const { slots, clusters } = placeLabels([b("a", 0), b("b", 10), b("c", 20), b("d", 30), b("e", 40), b("far", 1000)], "e");
    expect(slots.e).toEqual({ side: 1, tier: 1 });
    expect(slots.a).toEqual({ side: -1, tier: 1 });
    expect(clusters[0].ids).toEqual(["d"]);
    expect(slots.far).toEqual({ side: 1, tier: 1 });
  });
  it("řádek s pruhy worktree má popisky jen nad osou (up, u2)", () => {
    const { slots, clusters, tier2 } = placeLabels([b("a", 0), b("b", 10), b("c", 20), b("d", 0, "bez")], "", new Set(["r"]));
    expect([slots.a, slots.b]).toEqual([{ side: -1, tier: 1 }, { side: -1, tier: 2 }]);
    expect(clusters[0].ids).toEqual(["c"]);
    expect(slots.d).toEqual({ side: 1, tier: 1 });
    expect([...tier2]).toEqual(["r"]);
  });
  it("obě patra nesou název i stav, druhé o 28 px dál od osy", () => {
    expect(labelOffsets({ side: 1, tier: 1 })).toEqual({ name: 23, state: 36 });
    expect(labelOffsets({ side: 1, tier: 2 })).toEqual({ name: 51, state: 64 });
    expect(labelOffsets({ side: -1, tier: 2 })).toEqual({ name: -55, state: -42 });
  });
});

describe("popisek u okraje plátna", () => {
  const ball = b("a", 0), width = 1000, half = w / 2;
  const left = (x: number) => ({ start: x, middle: x - half, end: x - w }[labelAnchor(x, ball, width)]);
  const right = (x: number) => ({ start: x + w, middle: x + half, end: x }[labelAnchor(x, ball, width)]);
  it("u x=0 má levý okraj ≥ 0, u pravého okraje pravý ≤ šířka, uprostřed je střed", () => {
    expect(left(0)).toBeGreaterThanOrEqual(0);
    expect(right(width)).toBeLessThanOrEqual(width);
    expect(labelAnchor(500, ball, width)).toBe("middle");
  });
});
