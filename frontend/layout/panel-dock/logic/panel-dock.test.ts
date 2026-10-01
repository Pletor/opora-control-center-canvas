import { describe, expect, it } from "vitest";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import {
  ARROW_EDGE,
  ARROW_INSET,
  DOCK_PANELS,
  dropdownPlacement,
  isDismissKey,
  PANEL_GAP,
  PANEL_WIDTH,
  panelForShortcut,
  togglePanel,
} from "./panel-dock";

describe("panel-dock – tlačítka panelů", () => {
  it("Knihovna stojí vlevo od Agentů a každý panel nese jméno, ikonu a zkratku z kontraktu", () => {
    expect(DOCK_PANELS).toEqual([
      { key: "library", label: "Knihovna", icon: "library", shortcut: "Ctrl+Shift+," },
      { key: "agents", label: "Agenti a postupy", icon: "bot", shortcut: "Ctrl+Shift+." },
    ]);
  });

  it("každá ikona tlačítka jde nakreslit", () => {
    for (const panel of DOCK_PANELS) expect(iconPath(panel.icon), panel.key).not.toBe("");
  });
});

describe("panel-dock – otevřený je nejvýš jeden panel", () => {
  it("zavřený panel se otevře a druhý klik ho zavře", () => {
    expect(togglePanel(null, "library")).toBe("library");
    expect(togglePanel("library", "library")).toBeNull();
  });

  it("klik na druhé tlačítko panely vymění, neotevře oba", () => {
    expect(togglePanel("library", "agents")).toBe("agents");
    expect(togglePanel("agents", "library")).toBe("library");
  });
});

describe("panel-dock – klávesnice", () => {
  const key = (over: Partial<Parameters<typeof panelForShortcut>[0]>) =>
    ({ key: ",", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false, ...over });

  it("Ctrl+Shift+, patří Knihovně a Ctrl+Shift+. Agentům, i když rozložení pošle „<“ nebo „>“", () => {
    expect(panelForShortcut(key({}))).toBe("library");
    expect(panelForShortcut(key({ key: "<" }))).toBe("library");
    expect(panelForShortcut(key({ key: "." }))).toBe("agents");
    expect(panelForShortcut(key({ key: ">", ctrlKey: false, metaKey: true }))).toBe("agents");
  });

  it("bez Ctrl, bez Shiftu, s Altem nebo s jinou klávesou žádný panel nepřepne", () => {
    expect(panelForShortcut(key({ ctrlKey: false }))).toBeNull();
    expect(panelForShortcut(key({ shiftKey: false }))).toBeNull();
    expect(panelForShortcut(key({ altKey: true, key: "." }))).toBeNull();
    expect(panelForShortcut(key({ key: "k" }))).toBeNull();
  });

  it("jen Esc panel zavře", () => {
    expect(isDismissKey({ key: "Escape" })).toBe(true);
    expect(isDismissKey({ key: "Enter" })).toBe(false);
    expect(isDismissKey({ key: "Esc" })).toBe(false);
  });
});

describe("panel-dock – poloha dropdownu pod tlačítkem", () => {
  it("míry panelu drží kontrakt", () => {
    expect({ PANEL_WIDTH, PANEL_GAP, ARROW_INSET, ARROW_EDGE }).toEqual({ PANEL_WIDTH: 360, PANEL_GAP: 8, ARROW_INSET: 44, ARROW_EDGE: 16 });
  });

  it.each([
    [520, 1080, 476, 44],
    [620, 920, 552, 68],
    [20, 1080, 8, 16],
    [500, 300, 8, 344],
  ])("tlačítko se středem %i v rámu %i px → panel od %i, šipka %i", (anchorCenter, frameWidth, left, arrow) => {
    expect(dropdownPlacement(anchorCenter, frameWidth)).toEqual({ left, arrow });
  });

  it("šipka míří na střed tlačítka, dokud to rám dovolí", () => {
    for (const anchorCenter of [60, 300, 700]) {
      const { left, arrow } = dropdownPlacement(anchorCenter, 1440);
      expect(left + arrow).toBe(anchorCenter);
    }
  });
});
