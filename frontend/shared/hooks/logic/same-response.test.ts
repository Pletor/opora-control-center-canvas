import { describe, expect, it } from "vitest";
import { keepSame, sameJson } from "./same-response";

describe("keepSame", () => {
  it("vrací původní referenci pro stejný obsah", () => {
    const before = { key: "a", rows: { x: { id: "x", n: [1, 2] } } };
    const next = { key: "a", rows: { x: { id: "x", n: [1, 2] } } };
    expect(keepSame(before, next)).toBe(before);
  });
  it("vrací nový objekt, když se obsah změnil", () => {
    const before = { key: "a", rows: { x: 1 } };
    const next = { key: "a", rows: { x: 2 } };
    expect(keepSame(before, next)).toBe(next);
  });
  it("zvládne null a rozdílný klíč", () => {
    const next = { key: "b" };
    expect(keepSame<{ key: string } | null>(null, next)).toBe(next);
    expect(keepSame<{ key: string } | null>({ key: "a" }, next)).toBe(next);
    expect(keepSame(null, null)).toBeNull();
    expect(sameJson([], [])).toBe(true);
  });
});
