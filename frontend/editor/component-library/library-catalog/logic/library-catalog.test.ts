import { describe, expect, it } from "vitest";
import {
  CATALOG_CATEGORIES,
  CATALOG_ITEMS,
  catalogLint,
  relatesLines,
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
  purpose: "Jen pro test.",
  relates: [],
  done: ["Hotovo."],
  invariants: [],
  template: ".zkouska { padding: 0.5rem; }",
  ...patch,
});

describe("library-catalog – katalog jako data", () => {
  it("žádná kategorie z bloků 2–10 není prázdná", () => {
    for (const category of CATALOG_CATEGORIES) {
      expect(itemsOf(category.id).length, category.label).toBeGreaterThan(0);
    }
    expect(CATALOG_CATEGORIES.map((c) => c.id)).toEqual([
      "fe-components", "fe-css", "fe-logic", "backend", "database", "tenancy", "cloud", "cache", "security", "tests",
    ]);
  });

  it("id položek jsou jedinečná a každá položka patří do známé kategorie", () => {
    const ids = CATALOG_ITEMS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    const known = new Set(CATALOG_CATEGORIES.map((c) => c.id));
    expect(CATALOG_ITEMS.filter((item) => !known.has(item.category))).toEqual([]);
  });

  it("každý prvek nese popisek, účel, 1–3 kritéria hotovo a nejvýš 2 invarianty", () => {
    for (const item of CATALOG_ITEMS) {
      expect(item.label.trim().length, item.id).toBeGreaterThan(0);
      expect(item.purpose.trim().length, item.id).toBeGreaterThan(0);
      expect(item.done.length, item.id).toBeGreaterThanOrEqual(1);
      expect(item.done.length, item.id).toBeLessThanOrEqual(3);
      expect(item.invariants.length, item.id).toBeLessThanOrEqual(2);
    }
  });

  it("sloučené duplicity v katalogu nejsou a žádný popisek se neopakuje", () => {
    for (const gone of ["fe-form-state-split", "fe-member-area", "be-input-validation", "cloud-env-vars", "cloud-single-source-ports", "be-module-with-test", "cache-invalidate-on-source"]) {
      expect(itemById(gone), gone).toBeNull();
    }
    const labels = CATALOG_ITEMS.map((item) => item.label);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("tři brány hotovo vypisuje jen test-done-gates, ostatní na ně odkazují", () => {
    const gates = CATALOG_ITEMS.filter((item) => (item.template ?? "").includes("npm run build")).map((item) => item.id);
    expect(gates).toEqual(["test-done-gates"]);
    expect(itemById("cloud-repeatable-build")?.relates).toContain("@test-done-gates");
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

  it("hledá i v účelu, prázdný dotaz nechává katalog beze změny", () => {
    expect(searchItems(CATALOG_ITEMS, "  ")).toBe(CATALOG_ITEMS);
    expect(searchItems(CATALOG_ITEMS, "DIAKRITIKA").length).toBe(0);
    expect(foldDiacritics("Řádek Flex")).toBe("radek flex");
    const byPurpose = searchItems(CATALOG_ITEMS, "409");
    expect(byPurpose.map((item) => item.id)).toContain("be-cas-revision");
  });

  it("souvislosti: @id se přeloží na název a účel, věta zůstane", () => {
    const pure = itemById("fe-pure-model")!;
    expect(relatesLines(["@fe-pure-model", " Data přes rodiče. "])).toEqual([`${pure.label}: ${pure.purpose}`, "Data přes rodiče."]);
    expect(relatesLines(["@neexistuje"])).toEqual(["@neexistuje"]);
  });
});

describe("library-catalog – lint pravidel z bloku 3", () => {
  it("vydaný katalog je čistý", () => {
    expect(catalogLint()).toEqual([]);
  });

  it("chytí neznámý odkaz, chybějící hotovo a víc než dvě invarianty", () => {
    const bad = fixture({
      id: "spatny-tvar",
      relates: ["@neexistuje"],
      done: [],
      invariants: [
        { kind: "must", text: "a" },
        { kind: "must", text: "b" },
        { kind: "must_not", text: "c" },
      ],
    });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["done", "invariants", "relates"]);
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
