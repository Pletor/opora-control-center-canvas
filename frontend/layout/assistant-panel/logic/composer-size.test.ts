import { describe, expect, it } from "vitest";
import { MESSAGE_LIMIT, canExpand, fieldHeight, lengthNote } from "./composer-size";

describe("výška pole pro zprávu", () => {
  it("prázdné pole má tři řádky, ne dva", () => {
    expect(fieldHeight(24, 800, false)).toEqual({ height: 84, scroll: false });
  });

  it("sbalené roste s textem do 40 % panelu a pak se posouvá", () => {
    expect(fieldHeight(200, 800, false)).toEqual({ height: 202, scroll: false });
    expect(fieldHeight(5000, 800, false)).toEqual({ height: 320, scroll: true });
  });

  it("rozbalené má tři čtvrtiny panelu bez ohledu na text", () => {
    expect(fieldHeight(5000, 800, true)).toEqual({ height: 600, scroll: true });
    expect(fieldHeight(24, 800, true)).toEqual({ height: 600, scroll: false });
  });

  it("rozbalit nabídne až dlouhý text, sbalit vždy", () => {
    expect(canExpand(100, 800, false)).toBe(false);
    expect(canExpand(5000, 800, false)).toBe(true);
    expect(canExpand(24, 800, true)).toBe(true);
  });
});

describe("počítadlo znaků", () => {
  it("krátká zpráva počítadlo nemá", () => {
    expect(lengthNote(1999)).toBeNull();
  });

  it("dlouhá ukáže stav a přes limit varuje", () => {
    expect(lengthNote(35000)?.over).toBe(false);
    expect(lengthNote(35000)?.text).toContain("znaků");
    expect(lengthNote(MESSAGE_LIMIT + 1)?.over).toBe(true);
  });
});
