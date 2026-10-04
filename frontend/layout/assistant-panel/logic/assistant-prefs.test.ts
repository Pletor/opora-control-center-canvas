import { describe, expect, it } from "vitest";
import { DEFAULT_PREFS, parsePrefs, reopenSize, smallerSize } from "./assistant-prefs";

describe("preference asistenta", () => {
  it("čte model, velikost i rozsah", () => {
    expect(parsePrefs('{"model":"sonnet","size":"full","scope":"selection"}')).toEqual({ model: "sonnet", size: "full", scope: "selection" });
  });

  it("starý záznam jen s modelem dostane výchozí velikost a Celý obraz", () => {
    expect(parsePrefs('{"model":"fable"}')).toEqual({ model: "fable", size: "side", scope: "board" });
  });

  it("neznámé hodnoty a poškozený JSON vrátí výchozí", () => {
    expect(DEFAULT_PREFS.scope).toBe("board");
    expect(parsePrefs('{"model":"gpt","size":"huge","scope":"all"}')).toEqual(DEFAULT_PREFS);
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
