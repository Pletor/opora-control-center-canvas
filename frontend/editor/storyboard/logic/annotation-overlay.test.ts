import { describe, expect, it } from "vitest";
import { drawAnnotations, hitAnnotation } from "./annotation-overlay";
import { fakeContext } from "./animations/fake-canvas";
import type { Annotation } from "./storyboard-model";

const list: Annotation[] = [
  { kind: "arrow", from: { x: 0.1, y: 0.1 }, to: { x: 0.5, y: 0.1 }, text: "šipka" },
  { kind: "note", at: { x: 0.8, y: 0.8 }, text: "poznámka" },
];

describe("hitAnnotation", () => {
  it("najde šipku podél úsečky i poznámku u bodu", () => {
    expect(hitAnnotation(list, { x: 0.3, y: 0.11 })).toBe(0);
    expect(hitAnnotation(list, { x: 0.8, y: 0.81 })).toBe(1);
  });
  it("mimo dosah vrací -1", () => {
    expect(hitAnnotation(list, { x: 0.3, y: 0.5 })).toBe(-1);
  });
});

describe("drawAnnotations", () => {
  it("nakreslí šipku s hrotem, štítky i rozdělanou šipku", () => {
    const { ctx, calls } = fakeContext();
    drawAnnotations(ctx, 1920, 1080, list, 0, { from: { x: 0, y: 0 }, to: { x: 1, y: 1 } });
    expect(calls).toContain("closePath");
    expect(calls).toContain("strokeRect");
    expect(calls.filter((c) => c === "fillText")).toHaveLength(2);
  });
});
