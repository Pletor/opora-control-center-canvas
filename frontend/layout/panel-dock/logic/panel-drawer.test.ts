import { describe, expect, it } from "vitest";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { catalogView, fitNote, parseCatalogScope, profileOnlyGroup } from "./panel-drawer";

type Item = { id: string; label: string; fits?: { architecture?: ("modular" | "microservices")[]; tenancy?: "multi"[] } };
const items: Item[] = [
  { id: "form", label: "Formulář" },
  { id: "tenant", label: "Kontext tenanta", fits: { tenancy: ["multi"] } },
  { id: "gateway", label: "API gateway", fits: { architecture: ["microservices"] } },
  { id: "module", label: "Hranice modulu", fits: { architecture: ["modular"] } },
];
const search = (list: Item[], query: string) => list.filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase()));
const modularMulti: ProjectProfile = { architecture: "modular", tenancy: "multi", platform: "web" };
const unset: ProjectProfile = { architecture: "", tenancy: "", platform: "web" };
const ids = (list: Item[]) => list.map((item) => item.id);

describe("panel-drawer – co šuplík ukáže", () => {
  it("Pro tento projekt: jen co sedí, zbytek čeká pod řádkem mimo profil", () => {
    const view = catalogView(items, modularMulti, { scope: "fitting", showOutside: false, query: "" }, search);
    expect(ids(view.shown)).toEqual(["form", "tenant", "module"]);
    expect(ids(view.hidden)).toEqual(["gateway"]);
    expect([view.fittingCount, view.allCount, view.filtering]).toEqual([3, 4, true]);
  });

  it("řádek mimo profil ukáže vše v pořadí katalogu a nic už neschovává", () => {
    const view = catalogView(items, modularMulti, { scope: "fitting", showOutside: true, query: "" }, search);
    expect(ids(view.shown)).toEqual(["form", "tenant", "gateway", "module"]);
    expect(view.hidden).toEqual([]);
    expect(ids(view.outside)).toEqual(["gateway"]);
  });

  it("Vše ukáže celý katalog", () => {
    const view = catalogView(items, modularMulti, { scope: "all", showOutside: false, query: "" }, search);
    expect(view.shown).toHaveLength(4);
    expect(view.hidden).toEqual([]);
  });

  it("hledání prohledá i prvky mimo profil", () => {
    const view = catalogView(items, modularMulti, { scope: "fitting", showOutside: false, query: "gateway" }, search);
    expect(ids(view.shown)).toEqual(["gateway"]);
    expect(view.hidden).toEqual([]);
  });

  it("nenastavený profil nic nefiltruje a přepínač nemá smysl", () => {
    const view = catalogView(items, unset, { scope: "fitting", showOutside: false, query: "" }, search);
    expect(view.shown).toHaveLength(4);
    expect(view.outside).toEqual([]);
    expect(view.filtering).toBe(false);
  });
});

describe("panel-drawer – poznámky a skupiny", () => {
  it("prvek mimo profil nese „mimo profil“, prvek přivedený profilem důvod, univerzální nic", () => {
    const outside = new Set([items[2]]);
    expect(fitNote(items[2], modularMulti, outside)).toBe("mimo profil");
    expect(fitNote(items[1], modularMulti, outside)).toBe("kvůli profilu: multitenant");
    expect(fitNote(items[0], modularMulti, outside)).toBeNull();
  });

  it("skupina jen z prvků přivedených profilem nese štítek, smíšená ne", () => {
    expect(profileOnlyGroup([items[1]], modularMulti)).toBe(true);
    expect(profileOnlyGroup([items[0], items[1]], modularMulti)).toBe(false);
    expect(profileOnlyGroup([], modularMulti)).toBe(false);
  });
});

describe("panel-drawer – uložená volba filtru", () => {
  it("výchozí je Pro tento projekt; cizí text se tiše nahradí", () => {
    expect(parseCatalogScope(null)).toBe("fitting");
    expect(parseCatalogScope("{\"scope\":\"all\"}")).toBe("all");
    expect(parseCatalogScope("{\"scope\":\"projekt-42\"}")).toBe("fitting");
    expect(parseCatalogScope("nejson")).toBe("fitting");
  });
});
