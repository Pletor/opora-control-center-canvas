import { describe, expect, it } from "vitest";
import { clampNames, FULL_KEY, LAYERS_KEY, NAMES_DEFAULT, NAMES_KEY, readFull, readLayers, readNames } from "./linie-prefs";

describe("předvolby pro aplikaci", () => {
  const store = (values: Record<string, string>) => ({ getItem: (key: string) => values[key] ?? null });
  it("šířka názvů 160–420 px, jinak výchozí", () => {
    expect(readNames(store({ [NAMES_KEY]: "300" }))).toBe(300);
    expect(readNames(store({ [NAMES_KEY]: "999" }))).toBe(420);
    expect(readNames(store({}))).toBe(NAMES_DEFAULT);
    expect(clampNames(10)).toBe(160);
  });
  it("vrstvy: jen známé, jen boolean, chybějící má výchozí (PR a tagy zapnuté); rozbitý zápis = výchozí", () => {
    expect(readLayers(store({ [LAYERS_KEY]: '{"plans":true,"x":true,"tags":"ano","prs":false}' }))).toEqual({ commits: false, plans: true, tags: true, worktree: false, prs: false, merged: false });
    expect(readLayers(store({ [LAYERS_KEY]: "{" }))).toEqual({ commits: false, plans: false, tags: true, worktree: false, prs: true, merged: false });
  });
  it("kostky commitů: čisté úložiště je nemá, uložená volba zůstává", () => {
    expect(readLayers(store({})).commits).toBe(false);
    expect(readLayers(store({ [LAYERS_KEY]: '{"commits":true}' })).commits).toBe(true);
  });
  it("celá obrazovka jen při uloženém true", () => {
    expect(readFull(store({ [FULL_KEY]: "true" }))).toBe(true);
    expect(readFull(store({ [FULL_KEY]: "1" }))).toBe(false);
    expect(readFull(store({}))).toBe(false);
    expect(readFull(undefined)).toBe(false);
  });
});
