import { describe, expect, it } from "vitest";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  DOCK_SECTIONS,
  PANEL_DOCK_KEY,
  closedDock,
  dismissDock,
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
  it("shora Knihovna, Agenti, Postupy a pod oddělovačem Nastavení", () => {
    expect(DOCK_SECTIONS.map((item) => item.label)).toEqual(["Knihovna", "Agenti", "Postupy", "Nastavení"]);
    expect(DOCK_SECTIONS.filter((item) => item.apart).map((item) => item.key)).toEqual(["settings"]);
  });

  it("každá ikona ze sady jde nakreslit (vlastní značky menu kreslí DockIcon)", () => {
    for (const item of DOCK_SECTIONS) {
      if (item.icon === "settings" || item.icon === "menu") continue;
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
    expect(toggleMenu(closedDock("agents"))).toEqual({ rail: true, section: "agents", last: "agents" });
  });

  it("☰ při otevřené liště zavře lištu i panel a sekci si pamatuje", () => {
    expect(toggleMenu({ rail: true, section: "flows", last: "flows" })).toEqual(closedDock("flows"));
    expect(toggleMenu({ rail: true, section: null, last: "flows" })).toEqual(closedDock("flows"));
  });

  it("klik na neaktivní ikonu přepne panel a zapamatuje si sekci", () => {
    const library = selectSection(rail, "library");
    expect(library).toEqual({ rail: true, section: "library", last: "library" });
    expect(selectSection(library, "settings")).toEqual({ rail: true, section: "settings", last: "settings" });
  });

  it("klik na aktivní ikonu panel sbalí a lišta zůstane", () => {
    expect(selectSection({ rail: true, section: "agents", last: "agents" }, "agents")).toEqual({ rail: true, section: null, last: "agents" });
  });

  it("Esc zavře nejdřív panel, pak lištu, pak už nic", () => {
    const once = dismissDock({ rail: true, section: "library", last: "library" });
    expect(once).toEqual({ rail: true, section: null, last: "library" });
    const twice = dismissDock(once);
    expect(twice).toEqual(closedDock("library"));
    expect(dismissDock(twice)).toBe(twice);
  });

  it("zkratka otevře lištu rovnou na sekci i ze zavřeného menu", () => {
    expect(shortcutSection(closedDock("flows"), "library")).toEqual({ rail: true, section: "library", last: "library" });
  });
});

describe("panel-dock – klávesnice", () => {
  const key = (over: Partial<Parameters<typeof sectionForShortcut>[0]>) =>
    ({ key: ",", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false, ...over });

  it("Ctrl+Shift+, patří Knihovně a Ctrl+Shift+. Agentům, i když rozložení pošle „<“ nebo „>“", () => {
    expect(sectionForShortcut(key({}))).toBe("library");
    expect(sectionForShortcut(key({ key: "<" }))).toBe("library");
    expect(sectionForShortcut(key({ key: "." }))).toBe("agents");
    expect(sectionForShortcut(key({ key: ">", ctrlKey: false, metaKey: true }))).toBe("agents");
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
    expect(parseDockSection('{"section":"skeleton"}')).toBe("library");
    expect(parseDockSection("{\"section\":\"flows\"}")).toBe("flows");
    expect(parseDockSection("{\"section\":null}")).toBeNull();
    expect(parseDockSection("{\"section\":\"projekt-42\"}")).toBeNull();
    expect(parseDockSection("nejson")).toBeNull();
    expect(parseDockSection(null)).toBeNull();
  });

  it("prostředí bez localStorage dostane žádnou sekci místo výjimky", () => {
    expect(readDockSection()).toBeNull();
  });
});
