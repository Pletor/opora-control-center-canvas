import { describe, expect, it } from "vitest";
import {
  CATALOG_CATEGORIES,
  CATALOG_ITEMS,
  catalogLint,
  decompositionSummary,
  foldDiacritics,
  itemById,
  itemsOf,
  searchItems,
  type CatalogItem,
} from "./library-catalog";

/** Zkušební položka: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<CatalogItem>): CatalogItem => ({
  id: "fixture",
  category: "fe-css",
  label: "Zkušební položka",
  hint: "Jen pro test",
  icon: "×",
  kind: "block",
  rules: { must: ["Musí"], mustNot: [] },
  decomposition: [{ title: "Dílek", text: "Popis" }],
  template: ".zkouska { padding: 0.5rem; }",
  ...patch,
});

describe("library-catalog – katalog jako data", () => {
  it("žádná kategorie z bloků 2–10 není prázdná", () => {
    for (const category of CATALOG_CATEGORIES) {
      expect(itemsOf(category.id).length, category.label).toBeGreaterThan(0);
    }
    expect(CATALOG_CATEGORIES.map((c) => c.id)).toEqual([
      "fe-components", "fe-css", "fe-logic", "backend", "database", "cloud", "cache", "security", "tests",
    ]);
  });

  it("id položek jsou jedinečná a každá položka patří do známé kategorie", () => {
    const ids = CATALOG_ITEMS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    const known = new Set(CATALOG_CATEGORIES.map((c) => c.id));
    expect(CATALOG_ITEMS.filter((item) => !known.has(item.category))).toEqual([]);
  });

  it("každá položka nese aspoň jedno pravidlo musí, jeden krok rozpadu a šablonu", () => {
    for (const item of CATALOG_ITEMS) {
      expect(item.rules.must.length, item.id).toBeGreaterThan(0);
      expect(item.decomposition.length, item.id).toBeGreaterThan(0);
      expect(item.template.trim().length, item.id).toBeGreaterThan(0);
      expect(item.label.trim().length, item.id).toBeGreaterThan(0);
      expect(item.hint.trim().length, item.id).toBeGreaterThan(0);
      expect(item.icon.trim().length, item.id).toBeGreaterThan(0);
    }
  });

  it("itemsOf vrací jen svou kategorii a itemById najde položku z tažení", () => {
    expect(itemsOf("cache").every((item) => item.category === "cache")).toBe(true);
    expect(itemById("css-grid-responsive")?.label).toBe("Responzivní mřížka Grid");
    expect(itemById("neexistuje")).toBeNull();
  });
});

describe("library-catalog – hledání bez diakritiky", () => {
  it("najde „Formulář“ i na dotaz „formular“", () => {
    const found = searchItems(CATALOG_ITEMS, "formular");
    expect(found.map((item) => item.id)).toContain("fe-form-validated");
  });

  it("hledá i v nápovědě, prázdný dotaz nechává katalog beze změny", () => {
    expect(searchItems(CATALOG_ITEMS, "  ")).toBe(CATALOG_ITEMS);
    expect(searchItems(CATALOG_ITEMS, "DIAKRITIKA").length).toBe(0);
    expect(foldDiacritics("Řádek Flex")).toBe("radek flex");
    const byHint = searchItems(CATALOG_ITEMS, "expectedRevision");
    expect(byHint.map((item) => item.id)).toContain("be-cas-revision");
  });

  it("řádek rozpadu počítá dílky i pravidla česky", () => {
    expect(decompositionSummary(fixture({}))).toBe("1 dílek · 1 pravidlo");
    expect(decompositionSummary(fixture({
      decomposition: [{ title: "a", text: "" }, { title: "b", text: "" }, { title: "c", text: "" }],
      rules: { must: ["a", "b", "c"], mustNot: ["d", "e"] },
    }))).toBe("3 dílky · 5 pravidel");
  });
});

describe("library-catalog – lint pravidel z bloku 3", () => {
  it("vydaný katalog je čistý", () => {
    expect(catalogLint()).toEqual([]);
  });

  it("chytí px mimo povolený seznam", () => {
    const bad = fixture({ id: "spatne-px", template: ".zkouska { padding: 12px; font-size: 14px; }" });
    const violations = catalogLint([bad]);
    expect(violations.length).toBe(2);
    expect(violations.every((v) => v.rule === "px" && v.itemId === "spatne-px")).toBe(true);
  });

  it("povolí 1px linku, rám, obrys, stín a ikonu do 24", () => {
    const ok = fixture({
      template: [
        ".zkouska {",
        "  border: 1px solid var(--line);",
        "  border-top-width: 2px;",
        "  outline-width: 2px;",
        "  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);",
        "}",
        ".zkouska__icon { width: 20px; height: 20px; }",
      ].join("\n"),
    });
    expect(catalogLint([ok])).toEqual([]);
  });

  it("nepovolí ikonu přes 24 ani rádius v px", () => {
    const bad = fixture({
      template: [".zkouska__icon { width: 32px; }", ".zkouska { border-radius: 8px; }"].join("\n"),
    });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["px", "px"]);
  });

  it("chytí selektory vnořené přes tři úrovně", () => {
    const bad = fixture({
      id: "spatne-vnoreni",
      template: [".a {", "  .b {", "    .c {", "      .d { color: red; }", "    }", "  }", "}"].join("\n"),
    });
    const violations = catalogLint([bad]);
    expect(violations.map((v) => v.rule)).toEqual(["nesting"]);
    expect(violations[0].detail).toContain("4");
  });
});
