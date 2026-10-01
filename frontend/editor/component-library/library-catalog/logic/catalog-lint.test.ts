// Trvalá brána nad katalogem (blok 3 sektoru „Drag&drop-knihovna-levý navbar“): žádná šablona
// v CATALOG_ITEMS nesmí lintu utéct. Pod bránou jsou fixtury pravidlo po pravidle, aby bylo hned
// vidět, které přesně z pěti pravidel (px, vnoření, !important, #id, dvojité __) šablona porušila.
import { describe, expect, it } from "vitest";
import { CATALOG_ITEMS, catalogLint, type CatalogItem } from "./library-catalog";

/** Zkušební položka: stylová šablona, ke které se v testu dopisuje jen to, co se zkouší. */
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

describe("catalog-lint – trvalá brána nad vydaným katalogem", () => {
  it("žádná šablona v CATALOG_ITEMS neporušuje pravidla bloku 3", () => {
    const violations = catalogLint(CATALOG_ITEMS);
    const readable = violations.map((v) => `${v.itemId}: [${v.rule}] ${v.detail}`).join("\n");
    expect(violations, readable ? `Nalezená porušení lintu:\n${readable}` : undefined).toEqual([]);
  });
});

describe("catalog-lint – pravidlo po pravidle", () => {
  it("px na šířce je porušení", () => {
    const bad = fixture({ template: [".zkouska {", "  width: 200px;", "}"].join("\n") });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["px"]);
  });

  it("border: 1px solid je v pořádku", () => {
    const ok = fixture({ template: [".zkouska {", "  border: 1px solid var(--line);", "}"].join("\n") });
    expect(catalogLint([ok])).toEqual([]);
  });

  it("box-shadow: 0 2px 8px je v pořádku", () => {
    const ok = fixture({
      template: [".zkouska {", "  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);", "}"].join("\n"),
    });
    expect(catalogLint([ok])).toEqual([]);
  });

  it("font-size v px je porušení", () => {
    const bad = fixture({ template: [".zkouska {", "  font-size: 14px;", "}"].join("\n") });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["px"]);
  });

  it("čtyři selektory za sebou (.a .b .c .d) jsou vnoření přes tři úrovně", () => {
    const bad = fixture({ id: "hluboky-selektor", template: [".a .b .c .d {", "  color: red;", "}"].join("\n") });
    const violations = catalogLint([bad]);
    expect(violations.map((v) => v.rule)).toEqual(["nesting"]);
    expect(violations[0].detail).toContain("4");
  });

  it("tři selektory za sebou (.a .b .c) jsou v pořádku", () => {
    const ok = fixture({ template: [".a .b .c {", "  color: red;", "}"].join("\n") });
    expect(catalogLint([ok])).toEqual([]);
  });

  it("rem, em i % jsou v pořádku", () => {
    const ok = fixture({
      template: [
        ".zkouska {",
        "  padding: 0.5rem;",
        "  margin-block-end: 0.25em;",
        "  width: 100%;",
        "}",
      ].join("\n"),
    });
    expect(catalogLint([ok])).toEqual([]);
  });

  it("!important je porušení", () => {
    const bad = fixture({
      id: "spatny-important",
      template: [".zkouska {", "  color: red !important;", "}"].join("\n"),
    });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["important"]);
  });

  it("#id selektor je porušení", () => {
    const bad = fixture({ id: "spatne-id", template: ["#zkouska {", "  color: red;", "}"].join("\n") });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["id"]);
  });

  it("třída s víc než jedním __ (mimo BEM) je porušení", () => {
    const bad = fixture({
      id: "spatny-bem",
      template: [".a__b__c {", "  color: red;", "}"].join("\n"),
    });
    expect(catalogLint([bad]).map((v) => v.rule)).toEqual(["bem"]);
  });

  it("jedna úroveň __ (blok__prvek) je v pořádku", () => {
    const ok = fixture({ template: [".dlazdice__popis {", "  color: var(--ink-muted);", "}"].join("\n") });
    expect(catalogLint([ok])).toEqual([]);
  });
});

describe("catalog-lint – fe-css položky vysvětlují relativní jednotky", () => {
  /** "rem"/"em" jen jako samostatný token (mezera/číslice/interpunkce kolem), ne konec českého
   * slova jako „komentářem“ — proto kontrola sousedů přes Unicode písmeno, ne \b. */
  const mentionsRelativeUnit = (text: string): boolean => {
    if (text.includes("%")) return true;
    if (/relativ/i.test(text)) return true;
    return /(?:^|[^\p{L}])(rem|em)(?:$|[^\p{L}])/iu.test(text);
  };

  it("každá položka kategorie fe-css zmiňuje v pravidlech „musí“ rem, em, % nebo slovo „relativní“", () => {
    const offenders = CATALOG_ITEMS.filter(
      (item) => item.category === "fe-css" && !item.rules.must.some(mentionsRelativeUnit),
    ).map((item) => item.id);
    expect(offenders).toEqual([]);
  });
});
