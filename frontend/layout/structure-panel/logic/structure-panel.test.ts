import { describe, expect, it } from "vitest";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  STRUCTURE_PANEL_KEY, emptyStructure, layerKindIcon, parseStructure, readStructure, setFilter, setQuery, setTab, toggleGroup,
} from "./structure-panel";

describe("structure-panel – stav", () => {
  it("začíná na záložce Struktura, na Vše, bez dotazu a se vším rozbaleným", () => {
    expect(emptyStructure()).toEqual({ tab: "tree", filter: "all", query: "", collapsed: [] });
  });

  it("záložka Vybraná karta se pamatuje a filtr ani hledání nemaže", () => {
    const state = setTab(setQuery(emptyStructure(), "auth"), "card");
    expect(state).toEqual({ tab: "card", filter: "all", query: "auth", collapsed: [] });
    expect(parseStructure(JSON.stringify(state)).tab).toBe("card");
    expect(parseStructure(JSON.stringify({ ...state, tab: "katalog" })).tab).toBe("tree");
  });

  it("filtr a hledání se nemažou, klik na hlavičku skupinu sbalí a druhý rozbalí", () => {
    const state = setQuery(setFilter(emptyStructure(), "sector"), "cache");
    expect(state).toEqual({ tab: "tree", filter: "sector", query: "cache", collapsed: [] });
    const folded = toggleGroup(state, "sectors");
    expect(folded.collapsed).toEqual(["sectors"]);
    expect(toggleGroup(folded, "sectors").collapsed).toEqual([]);
  });
});

describe("structure-panel – jeden klíč pro celou aplikaci", () => {
  it("klíč nenese projekt ani pracovní prostor", () => {
    expect(STRUCTURE_PANEL_KEY).toBe("opora:structure-panel:v1");
  });

  it("uložený stav se vrátí a cizí hodnoty se zahodí", () => {
    expect(parseStructure(JSON.stringify({ filter: "area", query: "x".repeat(200), collapsed: ["sectors", "nic", 4] })))
      .toEqual({ tab: "tree", filter: "area", query: "x".repeat(120), collapsed: ["sectors"] });
    expect(parseStructure(JSON.stringify({ filter: "projekt" }))).toEqual(emptyStructure());
    expect(parseStructure("{rozbité")).toEqual(emptyStructure());
  });

  it("bez vlastního klíče převezme Strukturu ze staré Knihovny", () => {
    const legacy = JSON.stringify({ tab: "content", query: "katalog", pageFilter: "sector", pageQuery: "auth", collapsed: ["areas"] });
    expect(parseStructure(null, legacy)).toEqual({ tab: "tree", filter: "sector", query: "auth", collapsed: ["areas"] });
    expect(parseStructure(JSON.stringify(emptyStructure()), legacy)).toEqual(emptyStructure());
  });

  it("prostředí bez localStorage dostane výchozí stav místo výjimky", () => {
    expect(readStructure()).toEqual(emptyStructure());
  });
});

describe("structure-panel – ikona druhu vrstvy", () => {
  it("sektor, uzel a oblast mají vlastní značku, cizí druh ikonu uzlu", () => {
    expect([layerKindIcon("sector"), layerKindIcon("node"), layerKindIcon("area"), layerKindIcon("comment")])
      .toEqual(["layout-grid", "component", "map", "component"]);
    for (const kind of ["sector", "node", "area"]) expect(iconPath(layerKindIcon(kind))).not.toBe("");
  });
});
