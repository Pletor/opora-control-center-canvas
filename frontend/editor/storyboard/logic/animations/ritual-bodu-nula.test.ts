import { describe, expect, it } from "vitest";
import { stateAt, validate } from "../storyboard-model";
import { orbPosition, ritualBoduNula } from "./ritual-bodu-nula";
import { fakeContext } from "./fake-canvas";

describe("rituál bodu nula", () => {
  const board = ritualBoduNula.defaults();
  const ALL = new Set(ritualBoduNula.layers.map((l) => l.id));
  it("defaults projde validací a má časovou osu z kontraktu", () => {
    expect(validate(board, ["ritual-bodu-nula"])).toEqual([]);
    expect(board.moments.map((m) => m.t)).toEqual([0, 0.3, 2, 3, 4, 6]);
    expect(board.moments.every((m) => m.shows && m.changes)).toBe(true);
  });
  it("koule se s gather 1 sjedou na kruh kolem středu", () => {
    const W = 1920, H = 1080;
    for (let i = 0; i < 8; i++) {
      const p = orbPosition(i, 3.3, 1, W, H);
      expect(Math.hypot((p.x - 0.5) * W, (p.y - 0.5) * H)).toBeCloseTo(0.22 * H, 5);
    }
  });
  it("stav ve 2,5 s je mezi kruhem a nálezem, text je pryč", () => {
    const s = stateAt(board, ritualBoduNula, 2.5);
    expect(s.gather).toBe(1);
    expect(s.overlay).toBe(0);
    expect(Number(s.found)).toBeGreaterThan(0);
  });
  it("kreslí jen viditelné vrstvy", () => {
    const paint = (ids: string[]) => {
      const { ctx, calls } = fakeContext();
      ritualBoduNula.paint(ctx, 192, 108, stateAt(board, ritualBoduNula, 0), 0, board, new Set(ids));
      return calls;
    };
    expect(paint(["pozadi"])).not.toContain("createRadialGradient");
    expect(paint(["koule"])).not.toContain("fillRect");
    expect(paint(["koule"])).toContain("createRadialGradient");
    expect(paint(["jadro"])).toContain("stroke");
    expect(paint(["koule"])).not.toContain("stroke");
    expect(paint(["prekryv"])).toContain("fillText");
    expect(paint(["pozadi", "koule", "jadro"])).not.toContain("fillText");
  });
  it("paint nespadne v žádném čase", () => {
    for (const t of [0, 0.15, 2, 3, 3.5, 6]) {
      const { ctx, calls } = fakeContext();
      ritualBoduNula.paint(ctx, 192, 108, stateAt(board, ritualBoduNula, t), t, board, ALL);
      expect(calls).toContain("createRadialGradient");
    }
  });
});
