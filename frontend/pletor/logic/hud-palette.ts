import type { PletorOrbMode } from "./pletor-orb-mode";

/**
 * Stav jádra HUD: čtyři stavy koule okna („reply“ se v kokpitu čte jako „mluví“) a hlasové stavy (P3):
 * `listening` (mikrofon běží) a `speaking` (Pletor čte odpověď nahlas, stejný stav jako záblesk odpovědi).
 */
export type HudState = "idle" | "listening" | "thinking" | "speaking" | "error";
/** Co právě dělá hlas Pletora; drží ho `usePletorVoice`. */
export type VoicePhase = "idle" | "listening" | "speaking";

/** Barvy kreslení jako „r,g,b“ (alfa se míchá až při kreslení). Hodnoty sedí s `--pletor-*` v pletor.css. */
export type HudPalette = { line: string; core: string; scan: string };

/** Zelený kokpit: akcent #3dff8f, jádro #c9ffe0, skener světle zelený. */
export const HUD_GREEN: HudPalette = { line: "61,255,143", core: "201,255,224", scan: "170,255,200" };
/** Přemýšlení: o stupeň světlejší zelená, aby práce byla vidět i bez pohybu. */
export const HUD_THINKING: HudPalette = { line: "120,255,175", core: "230,255,240", scan: "190,255,215" };
/** Poslech: nejsvětlejší zelená, jádro skoro bílé; člověk vidí, že ho Pletor slyší. */
export const HUD_LISTENING: HudPalette = { line: "160,255,200", core: "240,255,246", scan: "205,255,225" };
/** Mluvení: sytější zelená než klid, aby čtení nahlas mělo vlastní barvu. */
export const HUD_SPEAKING: HudPalette = { line: "40,255,130", core: "190,255,215", scan: "150,255,190" };
/** Chyba jediná vybočí ze zelené: tlumená červená, nekřičí. */
export const HUD_ERROR: HudPalette = { line: "214,96,96", core: "240,150,150", scan: "214,96,96" };

/** Chyba přebije vše; hlas (poslech, čtení) přebije stav rozhovoru, jinak rozhoduje koule okna. */
export function hudState(mode: PletorOrbMode, voice: VoicePhase = "idle"): HudState {
  if (mode === "error") return "error";
  if (voice !== "idle") return voice;
  return mode === "reply" ? "speaking" : mode;
}

export function hudPalette(state: HudState): HudPalette {
  return { idle: HUD_GREEN, listening: HUD_LISTENING, thinking: HUD_THINKING, speaking: HUD_SPEAKING, error: HUD_ERROR }[state];
}

/** Rychlost otáčení a cílová amplituda vln: přemýšlení zrychlí, poslech a odpověď zvednou vlny, chyba zpomalí. */
export function hudMotion(state: HudState): { speed: number; amp: number } {
  return {
    idle: { speed: 1, amp: 0.08 }, listening: { speed: 1.4, amp: 0.3 }, thinking: { speed: 3.2, amp: 0.3 },
    speaking: { speed: 1.8, amp: 0.7 }, error: { speed: 0.6, amp: 0.2 },
  }[state];
}

export const HUD_LABEL: Record<HudState, string> = {
  idle: "pohotovost", listening: "poslouchám", thinking: "zpracovávám", speaking: "odpovídám", error: "chyba",
};
