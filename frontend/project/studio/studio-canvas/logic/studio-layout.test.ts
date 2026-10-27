import { describe, expect, it } from "vitest";
import { CARD_HEIGHT, CARD_WIDTH, layerRanks, layoutLevel } from "./studio-layout";

describe("studio layout", () => {
  it("ranks cards by the longest path along links and caps cycles", () => {
    expect(Object.fromEntries(layerRanks(["a", "b", "c", "d"], [{ source: "a", target: "b" }, { source: "b", target: "c" }, { source: "a", target: "c" }]))).toEqual({ a: 0, b: 1, c: 2, d: 0 });
    const cycle = layerRanks(["a", "b"], [{ source: "a", target: "b" }, { source: "b", target: "a" }]);
    expect(Math.max(...cycle.values())).toBe(1);
  });

  it("places layers left to right and rows in graph order, the same way every time", () => {
    const cards = [{ id: "a" }, { id: "b" }, { id: "c" }];
    const links = [{ source: "a", target: "c" }];
    const first = layoutLevel(cards, links);
    expect(Object.fromEntries(first.positions)).toEqual({ a: { x: 0, y: 0 }, b: { x: 0, y: CARD_HEIGHT + 64 }, c: { x: CARD_WIDTH + 120, y: 0 } });
    expect(layoutLevel(cards, links)).toEqual(first);
    expect(first.group).toBeNull();
  });

  it("puts grouped cards into a frame under the main block", () => {
    const layout = layoutLevel([{ id: "a" }, { id: "x", grouped: true }, { id: "y", grouped: true }], []);
    expect(layout.group).toEqual({ id: "studio-group-unsectioned", x: 0, y: CARD_HEIGHT + 70, width: 22 + (CARD_WIDTH + 120) + CARD_WIDTH + 22, height: 40 + CARD_HEIGHT + 22 });
    expect(layout.positions.get("x")).toEqual({ x: 22, y: CARD_HEIGHT + 70 + 40 });
    expect(layout.positions.get("y")).toEqual({ x: 22 + CARD_WIDTH + 120, y: CARD_HEIGHT + 70 + 40 });
  });
});
