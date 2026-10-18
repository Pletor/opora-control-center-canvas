import { describe, expect, it } from "vitest";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  DOCK_SECTIONS,
  PANEL_DOCK_KEY,
  closedDock,
  dismissDock,
  openSection,
  isDismissKey,
  parseDockSection,
  readDockSection,
  sectionForShortcut,
  selectSection,
  shortcutSection,
  toggleMenu,
  type DockState,
} from "./panel-dock";

describe("panel-dock – lišta ikon", () => {
  it("shora Struktura, Schránka a pod oddělovačem Nastavení", () => {
    expect(DOCK_SECTIONS.map((item) => item.label)).toEqual(["Struktura", "Schránka", "Nastavení"]);
    expect(DOCK_SECTIONS.map((item) => item.shortcut)).toEqual(["Ctrl+Shift+,", "Ctrl+Shift+.", undefined]);
    expect(DOCK_SECTIONS.filter((item) => item.apart).map((item) => item.key)).toEqual(["settings"]);
    expect(DOCK_SECTIONS.filter((item) => item.wide).map((item) => item.key)).toEqual(["vault"]);
  });

  it("každá ikona ze sady jde nakreslit (vlastní značky menu kreslí DockIcon)", () => {
    for (const item of DOCK_SECTIONS) {
      if (item.icon === "settings" || item.icon === "menu" || item.icon === "vault") continue;
      expect(iconPath(item.icon), item.key).not.toBe("");
    }
  });
});

describe("panel-dock – ☰, ikony a Esc", () => {
  const rail: DockState = { rail: true, section: null, last: null };

  it("☰ otevře lištu; bez zapamatované sekce jen lištu", () => {
    expect(toggleMenu(closedDock())).toEqual(rail);
  });

  it("☰ otevře rovnou i poslední sekci", () => {
    expect(toggleMenu(closedDock("structure"))).toEqual({ rail: true, section: "structure", last: "structure" });
  });

  it("☰ při otevřené liště zavře lištu i panel a sekci si pamatuje", () => {
    expect(toggleMenu({ rail: true, section: "vault", last: "vault" })).toEqual(closedDock("vault"));
    expect(toggleMenu({ rail: true, section: null, last: "vault" })).toEqual(closedDock("vault"));
  });

  it("klik na neaktivní ikonu přepne panel a zapamatuje si sekci", () => {
    const structure = selectSection(rail, "structure");
    expect(structure).toEqual({ rail: true, section: "structure", last: "structure" });
    expect(selectSection(structure, "settings")).toEqual({ rail: true, section: "settings", last: "settings" });
  });

  it("klik na aktivní ikonu panel sbalí a lišta zůstane", () => {
    expect(selectSection({ rail: true, section: "structure", last: "structure" }, "structure")).toEqual({ rail: true, section: null, last: "structure" });
  });

  it("Esc zavře nejdřív panel, pak lištu, pak už nic", () => {
    const once = dismissDock({ rail: true, section: "structure", last: "structure" });
    expect(once).toEqual({ rail: true, section: null, last: "structure" });
    const twice = dismissDock(once);
    expect(twice).toEqual(closedDock("structure"));
    expect(dismissDock(twice)).toBe(twice);
  });

  it("odkaz z detailu karty otevře Schránku i ze zavřeného menu a otevřenou nesbalí", () => {
    expect(openSection(closedDock("structure"), "vault")).toEqual({ rail: true, section: "vault", last: "vault" });
    expect(openSection({ rail: true, section: "vault", last: "vault" }, "vault")).toEqual({ rail: true, section: "vault", last: "vault" });
  });

  it("zkratka otevře lištu rovnou na sekci i ze zavřeného menu", () => {
    expect(shortcutSection(closedDock("vault"), "structure")).toEqual({ rail: true, section: "structure", last: "structure" });
  });
});

describe("panel-dock – klávesnice", () => {
  const key = (over: Partial<Parameters<typeof sectionForShortcut>[0]>) =>
    ({ key: ",", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false, ...over });

  it("Ctrl+Shift+, patří Struktuře a Ctrl+Shift+. Schránce, i když rozložení pošle „<“ nebo „>“", () => {
    expect(sectionForShortcut(key({}))).toBe("structure");
    expect(sectionForShortcut(key({ key: "<" }))).toBe("structure");
    expect(sectionForShortcut(key({ key: "." }))).toBe("vault");
    expect(sectionForShortcut(key({ key: ">", ctrlKey: false, metaKey: true }))).toBe("vault");
  });

  it("bez Ctrl, bez Shiftu, s Altem nebo s jinou klávesou nic", () => {
    expect(sectionForShortcut(key({ ctrlKey: false }))).toBeNull();
    expect(sectionForShortcut(key({ shiftKey: false }))).toBeNull();
    expect(sectionForShortcut(key({ altKey: true, key: "." }))).toBeNull();
    expect(sectionForShortcut(key({ key: "k" }))).toBeNull();
  });

  it("jen Esc menu zavírá", () => {
    expect(isDismissKey({ key: "Escape" })).toBe(true);
    expect(isDismissKey({ key: "Esc" })).toBe(false);
  });
});

describe("panel-dock – paměť sekce", () => {
  it("jediný klíč pro aplikaci, bez projektu", () => {
    expect(PANEL_DOCK_KEY).toBe("opora:panel-dock:v1");
  });

  it("uložená sekce se přečte, cizí text spadne na žádnou", () => {
    // Zrušené sekce (Knihovna, Agenti, Postupy, starý strom) se otevřou jako Struktura.
    for (const legacy of ["skeleton", "library", "agents", "flows"]) expect(parseDockSection(JSON.stringify({ section: legacy }))).toBe("structure");
    expect(parseDockSection(JSON.stringify({ section: "structure" }))).toBe("structure");
    expect(parseDockSection(JSON.stringify({ section: "vault" }))).toBe("vault");
    expect(parseDockSection("{\"section\":null}")).toBeNull();
    expect(parseDockSection("{\"section\":\"projekt-42\"}")).toBeNull();
    expect(parseDockSection("nejson")).toBeNull();
    expect(parseDockSection(null)).toBeNull();
  });

  it("prostředí bez localStorage dostane žádnou sekci místo výjimky", () => {
    expect(readDockSection()).toBeNull();
  });
});
