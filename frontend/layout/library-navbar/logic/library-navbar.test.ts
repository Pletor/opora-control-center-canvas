import { describe, expect, it } from "vitest";
import { CATALOG_CATEGORIES } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  categoryIcon,
  emptyLibraryNavbar,
  isLibraryCollapseShortcut,
  layerKindIcon,
  LIBRARY_NAVBAR_KEY,
  openCategory,
  parseLibraryNavbar,
  readLibraryNavbar,
  setMode,
  setPageFilter,
  setPageQuery,
  setQuery,
  setTab,
  startCatalogDrag,
  toggleGroup,
} from "./library-navbar";

describe("library-navbar – stav panelu", () => {
  it("začíná na záložce OBSAH v režimu Elementy a se seznamem vrstev na Vše", () => {
    expect(emptyLibraryNavbar()).toEqual({
      tab: "content",
      mode: "elements",
      query: "",
      category: null,
      pageFilter: "all",
      pageQuery: "",
      collapsed: [],
    });
  });

  it("stav nenese viditelnost: jestli je Knihovna otevřená, drží zavěšený panel, ne preference", () => {
    expect(emptyLibraryNavbar()).not.toHaveProperty("expanded");
    expect(emptyLibraryNavbar()).not.toHaveProperty("open");
  });

  it("záložka, režim a hledání se navzájem nemažou", () => {
    const state = setQuery(setMode(emptyLibraryNavbar(), "blocks"), "grid");
    const onPage = setTab(state, "page");
    expect(onPage).toEqual({ ...state, tab: "page" });
    expect(setTab(onPage, "content").query).toBe("grid");
  });

  it("klik na kategorii ji rozbalí, druhý klik zavře, a vždy přepne na Bloky", () => {
    const opened = openCategory(emptyLibraryNavbar(), "backend");
    expect(opened).toMatchObject({ mode: "blocks", category: "backend" });
    expect(openCategory(opened, "backend").category).toBeNull();
    expect(openCategory(opened, "cache").category).toBe("cache");
  });
});

describe("library-navbar – stav záložky STRÁNKA", () => {
  it("filtr a hledání vrstev nesahají na katalog", () => {
    const catalog = setQuery(setMode(emptyLibraryNavbar(), "blocks"), "grid");
    const page = setPageQuery(setPageFilter(catalog, "sector"), "platby");
    expect(page).toMatchObject({ mode: "blocks", query: "grid", pageFilter: "sector", pageQuery: "platby" });
  });

  it("klik na hlavičku skupinu sbalí a druhý ji zase rozbalí", () => {
    const collapsed = toggleGroup(emptyLibraryNavbar(), "areas");
    expect(collapsed.collapsed).toEqual(["areas"]);
    expect(toggleGroup(collapsed, "sectors").collapsed).toEqual(["areas", "sectors"]);
    expect(toggleGroup(collapsed, "areas").collapsed).toEqual([]);
  });
});

describe("library-navbar – jeden klíč pro celou aplikaci", () => {
  it("klíč nenese projekt ani pracovní prostor", () => {
    expect(LIBRARY_NAVBAR_KEY).toBe("opora:library-navbar:v1");
  });

  it("poškozená nebo cizí preference spadne na výchozí stav", () => {
    expect(parseLibraryNavbar(null)).toEqual(emptyLibraryNavbar());
    expect(parseLibraryNavbar("{nevalidní")).toEqual(emptyLibraryNavbar());
    expect(parseLibraryNavbar(JSON.stringify({ tab: "cizi", mode: 7, category: "neznama" }))).toEqual(emptyLibraryNavbar());
  });

  it("starší preference s `expanded` nebo `open` se ignoruje: po načtení je Knihovna vždy zavřená", () => {
    expect(parseLibraryNavbar(JSON.stringify({ expanded: false }))).toEqual(emptyLibraryNavbar());
    expect(parseLibraryNavbar(JSON.stringify({ open: false }))).toEqual(emptyLibraryNavbar());
    const parsed = parseLibraryNavbar(JSON.stringify({ open: true, expanded: true, tab: "page" }));
    expect(parsed).toEqual({ ...emptyLibraryNavbar(), tab: "page" });
    expect(parsed).not.toHaveProperty("expanded");
    expect(parsed).not.toHaveProperty("open");
  });

  it("uložený stav se vrátí i s rozbalenou kategorií", () => {
    const stored = JSON.stringify({ open: true, tab: "page", mode: "blocks", query: "css", category: "fe-css" });
    expect(parseLibraryNavbar(stored)).toEqual({
      ...emptyLibraryNavbar(),
      tab: "page",
      mode: "blocks",
      query: "css",
      category: "fe-css",
    });
  });

  it("stav STRÁNKY bydlí v tomtéž klíči a cizí hodnoty se zahodí", () => {
    const stored = JSON.stringify({ pageFilter: "area", pageQuery: "platby", collapsed: ["areas", "cizi", 7] });
    expect(parseLibraryNavbar(stored)).toEqual({ ...emptyLibraryNavbar(), pageFilter: "area", pageQuery: "platby", collapsed: ["areas"] });
    expect(parseLibraryNavbar(JSON.stringify({ pageFilter: "nic", collapsed: "ne" }))).toEqual(emptyLibraryNavbar());
  });

  it("prostředí bez localStorage (test, soukromé okno) dostane výchozí stav místo výjimky", () => {
    expect(readLibraryNavbar()).toEqual(emptyLibraryNavbar());
  });
});

describe("library-navbar – zdroj tažení", () => {
  it("do schránky tažení jde jen id položky pod vlastním typem a s kopírováním", () => {
    const written: Record<string, string> = {};
    const transfer = {
      effectAllowed: "none",
      setData: (type: string, value: string) => { written[type] = value; },
    } as unknown as DataTransfer;
    startCatalogDrag(transfer, "css-grid-responsive");
    expect(written).toEqual({ "application/x-opora-catalog-item": "css-grid-responsive" });
    expect(transfer.effectAllowed).toBe("copy");
  });
});

describe("library-navbar – ikona kategorie", () => {
  it("každá z devíti kategorií katalogu má svou ikonu podle tabulky v docs/panely-editoru.md", () => {
    expect(categoryIcon("fe-components")).toBe("component");
    expect(categoryIcon("fe-logic")).toBe("function-square");
    expect(categoryIcon("fe-css")).toBe("palette");
    expect(categoryIcon("backend")).toBe("server");
    expect(categoryIcon("database")).toBe("database");
    expect(categoryIcon("cache")).toBe("refresh-cw");
    expect(categoryIcon("security")).toBe("shield");
    expect(categoryIcon("cloud")).toBe("cloud");
    expect(categoryIcon("tests")).toBe("check-circle");
  });

  it("každá ikona kategorie je jméno, které sada opravdu umí nakreslit", () => {
    for (const category of CATALOG_CATEGORIES) {
      expect(iconPath(categoryIcon(category.id)), category.id).not.toBe("");
    }
  });

  it("neznámá kategorie dostane dílek, aby lišta nikdy nezůstala bez ikony", () => {
    expect(categoryIcon("neznama-kategorie")).toBe("component");
    expect(categoryIcon("")).toBe("component");
  });
});

describe("library-navbar – ikona druhu vrstvy", () => {
  it("sektor, uzel a oblast mají ve stromu STRÁNKY vlastní značku", () => {
    expect(layerKindIcon("sector")).toBe("layout-grid");
    expect(layerKindIcon("node")).toBe("component");
    expect(layerKindIcon("area")).toBe("map");
  });

  it("komentář ani cizí druh řádek nerozbijí — dostanou ikonu uzlu", () => {
    expect(layerKindIcon("comment")).toBe("component");
    expect(layerKindIcon("")).toBe("component");
  });
});

describe("library-navbar – zkratka Ctrl+Shift+, (posluchač drží panel-dock)", () => {
  const key = (over: Partial<Parameters<typeof isLibraryCollapseShortcut>[0]>) =>
    ({ key: ",", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false, ...over });

  it("platí pro čárku i pro „<“ a na Macu pro ⌘ místo Ctrl", () => {
    expect(isLibraryCollapseShortcut(key({}))).toBe(true);
    expect(isLibraryCollapseShortcut(key({ key: "<" }))).toBe(true);
    expect(isLibraryCollapseShortcut(key({ ctrlKey: false, metaKey: true }))).toBe(true);
  });

  it("bez Ctrl/⌘, bez Shiftu, s Altem ani na tečce Agentů zkratka neplatí", () => {
    expect(isLibraryCollapseShortcut(key({ ctrlKey: false }))).toBe(false);
    expect(isLibraryCollapseShortcut(key({ shiftKey: false }))).toBe(false);
    expect(isLibraryCollapseShortcut(key({ altKey: true }))).toBe(false);
    expect(isLibraryCollapseShortcut(key({ key: "." }))).toBe(false);
    expect(isLibraryCollapseShortcut(key({ key: ">" }))).toBe(false);
  });
});
