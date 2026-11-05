import { describe, expect, it } from "vitest";
import { HUD_ERROR, HUD_GREEN, HUD_LISTENING, HUD_THINKING, HUD_WORKING, hudMotion, hudPalette } from "./hud-palette";
import type { HudState } from "./hud-state";

const rgb = (value: string) => value.split(",").map(Number);
const green = (value: string) => { const [r, g, b] = rgb(value); return g > r && g > b; };
const brightness = (value: string) => rgb(value).reduce((sum, part) => sum + part, 0);

describe("hudPalette", () => {
  it("mimo chybu kreslí jen zelené odstíny", () => {
    for (const state of ["idle", "listening", "thinking", "working", "speaking"] as HudState[]) {
      const palette = hudPalette(state);
      expect([palette.line, palette.core, palette.scan].every(green)).toBe(true);
    }
  });
  it("poslech je světlejší než klid i přemýšlení; práce má vlastní barvu", () => {
    expect(hudPalette("listening")).toBe(HUD_LISTENING);
    expect(brightness(HUD_LISTENING.line)).toBeGreaterThan(brightness(HUD_GREEN.line));
    expect(brightness(HUD_LISTENING.line)).toBeGreaterThan(brightness(hudPalette("thinking").line));
    expect(hudPalette("working")).toBe(HUD_WORKING);
    expect(HUD_WORKING.line).not.toBe(HUD_THINKING.line);
  });
  it("chyba je tlumená červená", () => {
    expect(hudPalette("error")).toBe(HUD_ERROR);
    const [r, g, b] = rgb(HUD_ERROR.line);
    expect(r > g && r > b && r < 255).toBe(true);
  });
});

describe("hudMotion", () => {
  it("přemýšlení a práce točí výrazně rychleji než klid, poslech a odpověď zvednou vlny", () => {
    expect(hudMotion("thinking").speed).toBeGreaterThanOrEqual(hudMotion("idle").speed * 4);
    expect(hudMotion("working").speed).toBeGreaterThanOrEqual(hudMotion("idle").speed * 3);
    expect(hudMotion("speaking").amp).toBeGreaterThan(hudMotion("idle").amp);
    expect(hudMotion("listening").amp).toBeGreaterThan(hudMotion("idle").amp);
  });
});
