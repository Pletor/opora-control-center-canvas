import { describe, expect, it } from "vitest";
import { boxStyle, fitCamera, panBy, unionBox, zoomAt } from "./overlay";

describe("atlas → overlay", () => {
  it("scales viewBox units to image pixels, with an optional rim pad", () => {
    expect(boxStyle({ x: 32, y: 92, width: 372, height: 62 }, 0.5)).toEqual({ left: 16, top: 46, width: 186, height: 31 });
    expect(boxStyle({ x: 10, y: 10, width: 10, height: 10 }, 2, 4)).toEqual({ left: 12, top: 12, width: 36, height: 36 });
  });
  it("unions focus boxes, keeping zero-width edges", () => {
    expect(unionBox([])).toBeNull();
    expect(unionBox([{ x: 218, y: 154, width: 0, height: 52 }, { x: 32, y: 92, width: 372, height: 62 }]))
      .toEqual({ x: 32, y: 92, width: 372, height: 114 });
  });
  it("fits a box into the viewport centre and zooms around a fixed point", () => {
    const camera = fitCamera({ x: 0, y: 0, width: 1000, height: 500 }, { width: 548, height: 300 }, 24);
    expect(camera.scale).toBeCloseTo(0.5);
    expect(camera.x).toBeCloseTo(24);
    expect(camera.y).toBeCloseTo(25);
    expect(fitCamera({ x: 0, y: 0, width: 10, height: 10 }, { width: 500, height: 500 }).scale).toBe(1.6);
    const zoomed = zoomAt({ scale: 1, x: 0, y: 0 }, 2, { x: 100, y: 50 });
    expect(zoomed).toEqual({ scale: 2, x: -100, y: -50 });
    expect(zoomAt({ scale: 4, x: 0, y: 0 }, 2, { x: 0, y: 0 }).scale).toBe(4);
    expect(panBy(zoomed, 10, -5)).toEqual({ scale: 2, x: -90, y: -55 });
  });
});
