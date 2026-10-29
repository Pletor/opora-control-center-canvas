import { describe, expect, it } from "vitest";
import { DEFAULT_PREFS, parsePrefs, pickChannel, reopenSize, smallerSize } from "./assistant-prefs";

describe("preference asistenta", () => {
  it("čte model, velikost i rozsah", () => {
    expect(parsePrefs('{"model":"sonnet","size":"full","scope":"selection"}')).toEqual({ model: "sonnet", size: "full", scope: "selection", channel: null });
  });

  it("starý záznam jen s modelem dostane výchozí velikost a Celý obraz", () => {
    expect(parsePrefs('{"model":"fable"}')).toEqual({ model: "fable", size: "side", scope: "board", channel: null });
  });

  it("neznámé hodnoty a poškozený JSON vrátí výchozí", () => {
    expect(DEFAULT_PREFS.scope).toBe("board");
    expect(parsePrefs('{"model":"gpt","size":"huge","scope":"all","channel":"x"}')).toEqual(DEFAULT_PREFS);
    expect(parsePrefs("{nesmysl")).toEqual(DEFAULT_PREFS);
    expect(parsePrefs(null)).toEqual(DEFAULT_PREFS);
  });
});

describe("velikost panelu", () => {
  it("Esc zmenšuje o stupeň a na liště zůstane", () => {
    expect(smallerSize("full")).toBe("side");
    expect(smallerSize("side")).toBe("minimized");
    expect(smallerSize("minimized")).toBe("minimized");
  });

  it("znovuotevření z lišty jde vpravo, jinak do poslední velikosti", () => {
    expect(reopenSize("minimized")).toBe("side");
    expect(reopenSize("full")).toBe("full");
    expect(reopenSize("side")).toBe("side");
  });
});

describe("kanál panelu", () => {
  it("uložená volba platí pro všechny projekty", () => {
    expect(parsePrefs('{"channel":"heart"}').channel).toBe("heart");
    expect(pickChannel("assistant", true)).toBe("assistant");
    expect(pickChannel("heart", false)).toBe("heart");
  });

  it("bez volby rozhodne brána projektu", () => {
    expect(pickChannel(null, true)).toBe("heart");
    expect(pickChannel(null, false)).toBe("assistant");
  });
});
