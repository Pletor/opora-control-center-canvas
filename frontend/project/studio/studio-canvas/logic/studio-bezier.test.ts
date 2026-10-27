import { describe, expect, it } from "vitest";
import { bendOf, studioBezier } from "./studio-bezier";

describe("studio bezier", () => {
  it("bends by a third of the distance, clamped to 20–140 px like the prototype", () => {
    expect(bendOf({ x: 0, y: 0 }, { x: 10, y: 0 })).toBe(20);
    expect(bendOf({ x: 0, y: 0 }, { x: 200, y: 0 })).toBe(70);
    expect(bendOf({ x: 0, y: 0 }, { x: 1000, y: 0 })).toBe(140);
  });

  it("leaves along the port normal and puts the label in the middle", () => {
    const { d, label } = studioBezier({ x: 0, y: 0, side: "right" }, { x: 200, y: 100, side: "left" });
    const bend = bendOf({ x: 0, y: 0 }, { x: 200, y: 100 });
    expect(d).toBe(`M 0 0 C ${Math.round(bend * 100) / 100} 0 ${Math.round((200 - bend) * 100) / 100} 100 200 100`);
    expect(label).toEqual({ x: 100, y: 50 });
  });
});
