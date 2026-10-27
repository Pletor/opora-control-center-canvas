// Převedeno z prototypu `test/routing.test.mjs`.
import { describe, expect, it } from "vitest";
import { cubicPoint, routeConnection } from "./routing";

describe("routeConnection", () => {
  it("Bézier respektuje normály pravého/levého i horního portu", () => {
    const route = routeConnection({ x: 270, y: 120, side: "right" }, { x: 385, y: 120, side: "left" }, [{ x: 0, y: 0, w: 270, h: 240 }, { x: 385, y: 0, w: 270, h: 240 }]);
    expect(route.kind).toBe("bezier");
    expect(route.points[1].x).toBeGreaterThan(270);
    expect(route.points[2].x).toBeLessThan(385);
    const top = routeConnection({ x: 90, y: 0, side: "top" }, { x: 500, y: 0, side: "top" });
    expect(top.points[1].y).toBeLessThan(0);
    expect(top.points[2].y).toBeLessThan(0);
    const [p, a, b, q] = route.points;
    expect(cubicPoint(p, a, b, q, 0)).toEqual({ x: 270, y: 120 });
    expect(cubicPoint(p, a, b, q, 1)).toEqual({ x: 385, y: 120 });
  });

  it("překážka mezi kartami způsobí zaoblenou obchozí trasu bez průchodu kartou", () => {
    const route = routeConnection({ x: 270, y: 120, side: "right" }, { x: 900, y: 120, side: "left" },
      [{ x: 0, y: 0, w: 270, h: 240 }, { x: 400, y: 0, w: 270, h: 240 }, { x: 900, y: 0, w: 270, h: 240 }]);
    expect(route.kind).toBe("rounded");
    if (route.kind !== "rounded") return;
    expect(route.obstacleCrossings).toBe(0);
    expect(route.d).toContain(" Q ");
    expect(route.points.some((pt) => pt.y < 0 || pt.y > 240)).toBe(true);
  });
});
