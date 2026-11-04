import { describe, expect, it } from "vitest";
import { HUD_ERROR, HUD_GREEN, HUD_LABEL, HUD_LISTENING, hudMotion, hudPalette, hudState, type HudState } from "./hud-palette";

const rgb = (value: string) => value.split(",").map(Number);
const green = (value: string) => { const [r, g, b] = rgb(value); return g > r && g > b; };
const brightness = (value: string) => rgb(value).reduce((sum, part) => sum + part, 0);

describe("hudPalette", () => {
  it("mimo chybu kreslí jen zelené odstíny", () => {
    for (const state of ["idle", "listening", "thinking", "speaking"] as HudState[]) {
      const palette = hudPalette(state);
      expect([palette.line, palette.core, palette.scan].every(green)).toBe(true);
    }
  });
  it("poslech je světlejší než klid i přemýšlení", () => {
    expect(hudPalette("listening")).toBe(HUD_LISTENING);
    expect(brightness(HUD_LISTENING.line)).toBeGreaterThan(brightness(HUD_GREEN.line));
    expect(brightness(HUD_LISTENING.line)).toBeGreaterThan(brightness(hudPalette("thinking").line));
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
  it("hlas přebije rozhovor, chyba přebije hlas", () => {
    expect(hudState("idle", "listening")).toBe("listening");
    expect(hudState("thinking", "speaking")).toBe("speaking");
    expect(hudState("error", "listening")).toBe("error");
    expect(hudState("thinking", "idle")).toBe("thinking");
  });
  it("přemýšlení zrychlí, poslech a odpověď zvednou vlny, každý stav má štítek", () => {
    expect(hudMotion("thinking").speed).toBeGreaterThan(hudMotion("idle").speed);
    expect(hudMotion("speaking").amp).toBeGreaterThan(hudMotion("idle").amp);
    expect(hudMotion("listening").amp).toBeGreaterThan(hudMotion("idle").amp);
    expect(Object.keys(HUD_LABEL)).toHaveLength(5);
  });
});
