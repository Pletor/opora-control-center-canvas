import { describe, expect, it } from "vitest";
import { DEFAULT_PREFS, parsePrefs, reopenSize, smallerSize } from "./assistant-prefs";

describe("preference panelu", () => {
  it("čte velikost", () => {
    expect(parsePrefs('{"size":"full"}')).toEqual({ size: "full" });
  });

  it("starý záznam s modelem, rozsahem a kanálem si nechá jen velikost", () => {
    expect(parsePrefs('{"model":"sonnet","size":"minimized","scope":"selection","channel":"heart"}')).toEqual({ size: "minimized" });
    expect(parsePrefs('{"model":"fable"}')).toEqual(DEFAULT_PREFS);
  });

  it("neznámé hodnoty a poškozený JSON vrátí výchozí", () => {
    expect(parsePrefs('{"size":"huge"}')).toEqual(DEFAULT_PREFS);
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
