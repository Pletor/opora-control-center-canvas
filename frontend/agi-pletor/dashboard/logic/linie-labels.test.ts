import { describe, expect, it } from "vitest";
import { labelOffsets, labelWidth, placeLabels, type LabelBall } from "./linie-labels";

const b = (ticketId: string, x: number, rowId = "r"): LabelBall => ({ ticketId, rowId, x, label: "Linie L6: barvy", stateLabel: "čeká na přijetí" });
const w = labelWidth(b("a", 0));

describe("kolize popisků", () => {
  it("volné popisky jsou všechny pod osou; jiný řádek nekoliduje", () => {
    const { slots, clusters } = placeLabels([b("a", 0), b("b", 2 * w), b("c", 0, "jiny")], "");
    expect(Object.values(slots)).toEqual([{ side: 1, tier: 1 }, { side: 1, tier: 1 }, { side: 1, tier: 1 }]);
    expect(clusters).toEqual([]);
  });
  it("střídá pod · nad · druhé patro, nejvýš dvě patra, zbytek do shluku +N", () => {
    const { slots, clusters } = placeLabels([b("a", 0), b("b", 10), b("c", 20), b("d", 30), b("e", 40), b("f", 50)], "");
    expect([slots.a, slots.b, slots.c, slots.d]).toEqual([{ side: 1, tier: 1 }, { side: -1, tier: 1 }, { side: 1, tier: 2 }, { side: -1, tier: 2 }]);
    expect(slots.e).toBeUndefined();
    expect(clusters).toEqual([{ rowId: "r", x: 40, ids: ["e", "f"] }]);
  });
  it("vybraná má přednost: dostane místo pod osou, i když leží až za ostatními", () => {
    const { slots, clusters } = placeLabels([b("a", 0), b("b", 10), b("c", 20), b("d", 30), b("e", 40)], "e");
    expect(slots.e).toEqual({ side: 1, tier: 1 });
    expect(slots.a).toEqual({ side: -1, tier: 1 });
    expect(clusters[0].ids).toEqual(["d"]);
  });
  it("řádek s pruhy worktree má popisky jen nad osou", () => {
    const { slots, clusters } = placeLabels([b("a", 0), b("b", 10), b("c", 20)], "", new Set(["r"]));
    expect([slots.a, slots.b]).toEqual([{ side: -1, tier: 1 }, { side: -1, tier: 2 }]);
    expect(clusters[0].ids).toEqual(["c"]);
  });
  it("druhé patro nese jen název, první název i stav", () => {
    expect(labelOffsets({ side: 1, tier: 1 })).toEqual({ name: 23, state: 36 });
    expect(labelOffsets({ side: -1, tier: 2 }).state).toBeNull();
  });
});
