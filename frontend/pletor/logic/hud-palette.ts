import type { PletorOrbMode } from "./pletor-orb-mode";

/** Stav jádra HUD: stejné čtyři stavy jako koule okna, jen „reply“ se v kokpitu čte jako „mluví“. */
export type HudState = "idle" | "thinking" | "speaking" | "error";

/** Barvy kreslení jako „r,g,b“ (alfa se míchá až při kreslení). Hodnoty sedí s `--pletor-*` v pletor.css. */
export type HudPalette = { line: string; core: string; scan: string };

/** Zelený kokpit: akcent #3dff8f, jádro #c9ffe0, skener světle zelený. */
export const HUD_GREEN: HudPalette = { line: "61,255,143", core: "201,255,224", scan: "170,255,200" };
/** Přemýšlení: o stupeň světlejší zelená, aby práce byla vidět i bez pohybu. */
export const HUD_THINKING: HudPalette = { line: "120,255,175", core: "230,255,240", scan: "190,255,215" };
/** Chyba jediná vybočí ze zelené: tlumená červená, nekřičí. */
export const HUD_ERROR: HudPalette = { line: "214,96,96", core: "240,150,150", scan: "214,96,96" };

export function hudState(mode: PletorOrbMode): HudState {
  return mode === "reply" ? "speaking" : mode;
}

export function hudPalette(state: HudState): HudPalette {
  if (state === "error") return HUD_ERROR;
  return state === "thinking" ? HUD_THINKING : HUD_GREEN;
}

/** Rychlost otáčení a cílová amplituda vln: přemýšlení zrychlí, odpověď zvedne vlny, chyba zpomalí. */
export function hudMotion(state: HudState): { speed: number; amp: number } {
  return { idle: { speed: 1, amp: 0.08 }, thinking: { speed: 3.2, amp: 0.3 }, speaking: { speed: 1.8, amp: 0.7 }, error: { speed: 0.6, amp: 0.2 } }[state];
}

export const HUD_LABEL: Record<HudState, string> = { idle: "pohotovost", thinking: "zpracovávám", speaking: "odpovídám", error: "chyba" };
