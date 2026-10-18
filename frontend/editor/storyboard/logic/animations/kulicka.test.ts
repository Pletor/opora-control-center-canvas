import { describe, expect, it } from "vitest";
import { stateAt } from "../storyboard-model";
import { kulicka, squashAt, velocityAt } from "./kulicka";
import { fakeContext } from "./fake-canvas";

describe("kulička", () => {
  const board = kulicka.defaults();
  const ALL = new Set(kulicka.layers.map((l) => l.id));
  it("defaults má 11 momentů a stav v state, tři doteky", () => {
    expect(board.moments).toHaveLength(11);
    expect(board.moments.filter((m) => m.state.contact === true).map((m) => m.t)).toEqual([2.3, 3.7, 4.7]);
    expect(board.moments[3].state).toMatchObject({ x: 0.5, y: 0.745, r: 0.055, color: "#f4b942", opacity: 1 });
  });
  it("squash je nejsilnější v momentu doteku a mimo okno nulový", () => {
    expect(squashAt(board, 2.3)).toBeCloseTo(0.42, 10);
    expect(squashAt(board, 2.3 + 0.065)).toBeCloseTo(0.42 * 0.25, 10);
    expect(squashAt(board, 1.0)).toBe(0);
  });
  it("rychlost při pádu míří dolů a při visení je nulová", () => {
    expect(velocityAt(board, 2.0, 1920, 1080).vy).toBeGreaterThan(0);
    expect(velocityAt(board, 1.0, 1920, 1080)).toEqual({ vx: 0, vy: 0 });
  });
  it("paint nespadne v žádném čase a v dotyku kreslí kuličku", () => {
    for (const t of [0, 1, 2.3, 5, 12]) {
      const { ctx, calls } = fakeContext();
      kulicka.paint(ctx, 192, 108, stateAt(board, kulicka, t), t, board, ALL);
      expect(calls).toContain("fillRect");
    }
    const { ctx, calls } = fakeContext();
    kulicka.paint(ctx, 192, 108, stateAt(board, kulicka, 2.3), 2.3, board, ALL);
    expect(calls).toContain("arc");
  });
  it("kreslí jen viditelné vrstvy", () => {
    const paint = (ids: string[]) => {
      const { ctx, calls } = fakeContext();
      kulicka.paint(ctx, 192, 108, stateAt(board, kulicka, 2.3), 2.3, board, new Set(ids));
      return calls;
    };
    expect(paint(["pozadi", "stin"])).not.toContain("arc");
    expect(paint(["kulicka"])).not.toContain("fillRect");
    expect(paint(["kulicka"])).toContain("arc");
    expect(paint(["pozadi", "kulicka"])).not.toContain("ellipse");
    expect(paint(["stin"])).toContain("ellipse");
  });
});
