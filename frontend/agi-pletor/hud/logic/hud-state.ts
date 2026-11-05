import type { PletorAction } from "./pletor-client";

/**
 * Stav jádra Pletora (HUD, popup Poslechu i koule okna) z jednoho místa, aby všechna tři jádra ukazovala totéž.
 * `thinking` od odeslání věty do odpovědi, `speaking` při čtení (a krátký záblesk po odpovědi bez hlasu),
 * `working`, když Pletor zadal práci srdci nebo srdce pracuje, `listening`, když běží mikrofon.
 */
export type HudState = "idle" | "listening" | "thinking" | "working" | "speaking" | "error";
/** Co právě dělá hlas Pletora; drží ho `usePletorVoice`. */
export type VoicePhase = "idle" | "listening" | "speaking";
/** Proč Pletor „dělá“: právě předal záměr srdci (`handoff`), nebo srdce běží (`heart`). */
export type HudWork = "handoff" | "heart" | null;

/** Jak dlouho po příchodu odpovědi jádro bliká jako „mluví“, když se nečte nahlas (ms). */
export const REPLY_MS = 900;
/** Jak dlouho po odpovědi s akcí „Poslal jsem srdci“ jádro ukazuje předání, než ho převezme stav srdce (ms). */
export const HANDOFF_MS = 12_000;

export type HudInput = {
  sending: boolean; voice: VoicePhase; error: boolean; work: HudWork; repliedAt: number | null; now: number;
};

/**
 * Přednost: odesílání (přemýšlím) > čtení odpovědi > chyba > práce srdce > poslech > záblesk odpovědi > klid.
 * Přemýšlení a čtení stojí nad chybou, protože stará chyba z pollingu nesmí schovat právě běžící práci.
 */
export function hudState({ sending, voice, error, work, repliedAt, now }: HudInput): HudState {
  if (sending) return "thinking";
  if (voice === "speaking") return "speaking";
  if (error) return "error";
  if (work) return "working";
  if (voice === "listening") return "listening";
  if (repliedAt !== null && now >= repliedAt && now - repliedAt < REPLY_MS) return "speaking";
  return "idle";
}

/** Práce mimo Pletora: srdce běží (`heart.running`), jinak čerstvě předaný záměr (akce `heart_message` do HANDOFF_MS). */
export function hudWork(heart: unknown, actions: PletorAction[], repliedAt: number | null, now: number): HudWork {
  if (heart && typeof heart === "object" && (heart as { running?: unknown }).running === true) return "heart";
  const handed = actions.some((action) => action.type === "heart_message" && action.ok);
  return handed && repliedAt !== null && now >= repliedAt && now - repliedAt < HANDOFF_MS ? "handoff" : null;
}

const LABEL: Record<HudState, string> = {
  idle: "čekám", listening: "poslouchám", thinking: "přemýšlím", working: "srdce pracuje", speaking: "mluvím", error: "chyba",
};

/** Štítek stavu česky, jedním až dvěma slovy; práce rozliší předání srdci od běžícího srdce. */
export function hudLabel(state: HudState, work: HudWork = null): string {
  return state === "working" && work === "handoff" ? "zadávám srdci" : LABEL[state];
}
