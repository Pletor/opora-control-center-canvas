import { describe, expect, it } from "vitest";
import { ICON_PATHS, iconPath, type IconName } from "./icon-paths";

const NAMES = Object.keys(ICON_PATHS) as IconName[];

describe("icon-paths – sada ikon", () => {
  it("každá ikona v tabulce má neprázdnou cestu", () => {
    expect(NAMES.length).toBeGreaterThan(0);
    for (const name of NAMES) {
      expect(ICON_PATHS[name].trim().length, name).toBeGreaterThan(0);
    }
  });

  it("cesta vždy začíná přesunem pera, aby ji prohlížeč uměl nakreslit", () => {
    for (const name of NAMES) {
      expect(ICON_PATHS[name].trim().startsWith("M"), name).toBe(true);
    }
  });

  it("iconPath vrací tutéž cestu jako tabulka", () => {
    for (const name of NAMES) {
      expect(iconPath(name), name).toBe(ICON_PATHS[name]);
    }
  });

  it("neznámé jméno nic nenakreslí a nic neshodí", () => {
    expect(iconPath("neexistuje")).toBe("");
    expect(iconPath("")).toBe("");
  });

  it("ikony, na kterých stojí lišta módů a police postupů, v sadě jsou", () => {
    for (const name of [
      "layout-grid",
      "type",
      "pencil",
      "map",
      "bot",
      "library",
      "workflow",
      "link",
      "scale",
      "terminal",
      "sparkles",
      "users",
      "search",
      "grip-vertical",
      "panel-right-close",
      "panel-right-open",
    ]) {
      expect(iconPath(name), name).not.toBe("");
    }
  });

  it("ikony, na kterých stojí Knihovna (kategorie, strom vrstev, ovládání), v sadě jsou", () => {
    for (const name of [
      "component",
      "function-square",
      "palette",
      "server",
      "database",
      "refresh-cw",
      "shield",
      "cloud",
      "check-circle",
      "layout-grid",
      "map",
      "home",
      "chevron-left",
      "chevron-right",
      "panel-left-close",
      "panel-left-open",
    ]) {
      expect(iconPath(name), name).not.toBe("");
    }
  });

  it("horní lišta se zavěšenými panely a souhrn práce agentů mají své ikony", () => {
    for (const name of ["x", "chevron-down", "user", "lock", "hourglass", "circle-help", "mail", "play", "filter", "arrow-up-down"]) {
      expect(iconPath(name), name).not.toBe("");
    }
  });

  it("stav a směr v zadání karty (odškrtnutí, předávky) mají vlastní ikonu", () => {
    for (const name of ["circle", "check", "arrow-up", "arrow-left", "arrow-right"]) {
      expect(iconPath(name), name).not.toBe("");
    }
  });
});
