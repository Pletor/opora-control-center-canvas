import type { HudState } from "./hud-state";

/** Barvy kreslení jako „r,g,b“ (alfa se míchá až při kreslení). Hodnoty sedí s `--pletor-*` v pletor.css. */
export type HudPalette = { line: string; core: string; scan: string };

/** Zelený kokpit: akcent #3dff8f, jádro #c9ffe0, skener světle zelený. */
export const HUD_GREEN: HudPalette = { line: "61,255,143", core: "201,255,224", scan: "170,255,200" };
/** Přemýšlení: o stupeň světlejší zelená, aby práce byla vidět i bez pohybu. */
export const HUD_THINKING: HudPalette = { line: "120,255,175", core: "230,255,240", scan: "190,255,215" };
/** Práce srdce: nejsytější jasná zelená s bílým skenerem; odliší se od přemýšlení i bez pohybu. */
export const HUD_WORKING: HudPalette = { line: "0,255,110", core: "220,255,232", scan: "235,255,242" };
/** Poslech: nejsvětlejší zelená, jádro skoro bílé; člověk vidí, že ho Pletor slyší. */
export const HUD_LISTENING: HudPalette = { line: "160,255,200", core: "240,255,246", scan: "205,255,225" };
/** Mluvení: sytější zelená než klid, aby čtení nahlas mělo vlastní barvu. */
export const HUD_SPEAKING: HudPalette = { line: "40,255,130", core: "190,255,215", scan: "150,255,190" };
/** Chyba jediná vybočí ze zelené: tlumená červená, nekřičí. */
export const HUD_ERROR: HudPalette = { line: "214,96,96", core: "240,150,150", scan: "214,96,96" };

export function hudPalette(state: HudState): HudPalette {
  return { idle: HUD_GREEN, listening: HUD_LISTENING, thinking: HUD_THINKING, working: HUD_WORKING, speaking: HUD_SPEAKING, error: HUD_ERROR }[state];
}

/** Rychlost otáčení a cílová amplituda vln: přemýšlení a práce točí nejrychleji, poslech a odpověď zvednou vlny, chyba zpomalí. */
export function hudMotion(state: HudState): { speed: number; amp: number } {
  return {
    idle: { speed: 1, amp: 0.08 }, listening: { speed: 1.4, amp: 0.3 }, thinking: { speed: 5, amp: 0.4 },
    working: { speed: 4, amp: 0.35 }, speaking: { speed: 1.8, amp: 0.7 }, error: { speed: 0.6, amp: 0.2 },
  }[state];
}
