import { describe, expect, it } from "vitest";
import { WORKSPACE_MODES, readMode } from "@/shared/surface-settings/logic/workspace-settings";
import { iconPath } from "@/ui-kit/icon/logic/icon-paths";
import { MODE_ICONS, EDITOR_MODES, modeIcon } from "./mode-rail";

describe("mode-rail – ikony módů plátna", () => {
  it("každý mód z kontraktu má svou ikonu", () => {
    expect(modeIcon("structure")).toBe("layout-grid");
    expect(modeIcon("text")).toBe("type");
    expect(modeIcon("drawing")).toBe("pencil");
    expect(modeIcon("map")).toBe("map");
    expect(modeIcon("storyboard")).toBe("play");
  });

  it("neznámé nebo prázdné id dostane náhradní ikonu, ne pád", () => {
    expect(modeIcon("neznamy-mod")).toBe("layout-grid");
    expect(modeIcon("")).toBe("layout-grid");
  });

  it("žádný skutečný mód plátna nezůstane bez řádku v tabulce", () => {
    for (const mode of WORKSPACE_MODES) {
      expect(Object.keys(MODE_ICONS), mode.key).toContain(mode.key);
    }
  });

  it("každá ikona záložek je v sadě a dá se nakreslit", () => {
    for (const name of Object.values(MODE_ICONS)) {
      expect(iconPath(name), name).not.toBe("");
    }
  });

  it("všechny pohledy přímo v řádku, rešerše mezi Velínem a Textem", () => {
    expect(readMode("research")).toBe("research");
    expect([...EDITOR_MODES]).toEqual(["structure", "map", "research", "text", "drawing", "office", "storyboard"]);
    expect(WORKSPACE_MODES.map((mode) => mode.key)).toEqual([...EDITOR_MODES]);
  });
});
