import { describe, expect, it } from "vitest";
import { CATALOG_ITEMS } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { CATEGORY_ICON, LIBRARY_FAMILIES, libraryFamilies } from "./library-families";

describe("LIBRARY_FAMILIES", () => {
  it("má rodiny z kontraktu v jeho pořadí", () => {
    expect(LIBRARY_FAMILIES.map((family) => family.label)).toEqual(["Frontend", "Backend", "Databáze", "Security", "Testy", "Cache", "Cloud a infrastruktura"]);
  });
  it("každá kategorie katalogu patří právě jedné rodině a má ikonu", () => {
    const categories = LIBRARY_FAMILIES.flatMap((family) => family.categories);
    expect(new Set(categories).size).toBe(categories.length);
    for (const item of CATALOG_ITEMS) {
      expect(categories).toContain(item.category);
      expect(CATEGORY_ICON[item.category]).toBeTruthy();
    }
  });
});

describe("libraryFamilies", () => {
  it("bez hledání ukáže všechny prvky katalogu", () => {
    expect(libraryFamilies(CATALOG_ITEMS, "").reduce((sum, group) => sum + group.items.length, 0)).toBe(CATALOG_ITEMS.length);
  });
  it("vynechá rodiny bez shody", () => {
    expect(libraryFamilies(CATALOG_ITEMS, "zzzz-nic-takoveho")).toEqual([]);
  });
});
