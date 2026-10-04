import { describe, expect, it } from "vitest";
import { revealNodeCenter } from "./reveal-node";

describe("explicit inserted-card reveal", () => {
  const board = { left: 0, top: 100, width: 1200, height: 700 };
  const card = { x: 0, y: 0, width: 360, height: 240 };
  it("centers within the exposed canvas to the right of the library at the current zoom", () => {
    const result = revealNodeCenter(board, { left: 435, right: 1200, top: 100, bottom: 800 }, card, 1)!;
    const screenX = board.width / 2 + (card.x + card.width / 2 - result.x) * result.zoom;
    expect(screenX).toBe((435 + 1200) / 2);
    expect(result.zoom).toBe(1);
    expect(screenX - card.width / 2).toBeGreaterThan(435);
  });
  it("reduces zoom only when the measured card needs it", () => {
    const result = revealNodeCenter(board, { left: 800, right: 1200, top: 100, bottom: 800 }, { ...card, width: 600 }, 1)!;
    expect(result.zoom).toBeCloseTo(352 / 600);
    expect(revealNodeCenter(board, { left: 435, right: 1200, top: 100, bottom: 800 }, card, 0.5)?.zoom).toBe(0.5);
  });
  it("does not collapse zoom for a drawer covering the full canvas", () => {
    expect(revealNodeCenter(board, { left: 1200, right: 1200, top: 100, bottom: 800 }, card, 1)).toBeNull();
  });
});
