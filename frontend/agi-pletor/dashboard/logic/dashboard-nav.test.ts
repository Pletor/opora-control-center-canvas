import { describe, expect, it } from "vitest";
import { NAV_KEY, readNarrow, writeNarrow } from "./dashboard-nav";

const memory = () => {
  const map = new Map<string, string>();
  return { map, getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v), removeItem: (k: string) => void map.delete(k) };
};

describe("dashboard-nav", () => {
  it("chybějící klíč je roztažené menu", () => expect(readNarrow(memory())).toBe(false));
  it("zasunutí se zapíše a přečte, roztažení klíč smaže", () => {
    const s = memory();
    writeNarrow(s, true);
    expect(s.map.get(NAV_KEY)).toBe("narrow");
    expect(readNarrow(s)).toBe(true);
    writeNarrow(s, false);
    expect(s.map.has(NAV_KEY)).toBe(false);
  });
  it("úložiště, které vyhazuje, nerozbije velín", () => {
    const boom = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); }, removeItem: () => { throw new Error("x"); } };
    expect(readNarrow(boom)).toBe(false);
    expect(() => writeNarrow(boom, true)).not.toThrow();
  });
});
