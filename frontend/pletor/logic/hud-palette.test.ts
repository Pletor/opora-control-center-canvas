import { describe, expect, it } from "vitest";
import { HUD_ERROR, HUD_LABEL, hudMotion, hudPalette, hudState, type HudState } from "./hud-palette";

const rgb = (value: string) => value.split(",").map(Number);
const green = (value: string) => { const [r, g, b] = rgb(value); return g > r && g > b; };

describe("hudPalette", () => {
  it("mimo chybu kreslí jen zelené odstíny", () => {
    for (const state of ["idle", "thinking", "speaking"] as HudState[]) {
      const palette = hudPalette(state);
      expect([palette.line, palette.core, palette.scan].every(green)).toBe(true);
    }
  });
  it("chyba je tlumená červená", () => {
    expect(hudPalette("error")).toBe(HUD_ERROR);
    const [r, g, b] = rgb(HUD_ERROR.line);
    expect(r > g && r > b && r < 255).toBe(true);
  });
});

describe("hudState", () => {
  it("mapuje stav koule na stav jádra", () => {
    expect(hudState("idle")).toBe("idle");
    expect(hudState("thinking")).toBe("thinking");
    expect(hudState("reply")).toBe("speaking");
    expect(hudState("error")).toBe("error");
  });
  it("přemýšlení zrychlí, odpověď zvedne vlny, každý stav má štítek", () => {
    expect(hudMotion("thinking").speed).toBeGreaterThan(hudMotion("idle").speed);
    expect(hudMotion("speaking").amp).toBeGreaterThan(hudMotion("idle").amp);
    expect(Object.keys(HUD_LABEL)).toHaveLength(4);
  });
});
