/** Stav jádra okna Pletor (PletorOrb): odvozuje ho rodič, dílek jen kreslí. */
export type PletorOrbMode = "idle" | "thinking" | "reply" | "error";

/** Jak dlouho po příchodu odpovědi jádro bliká, než se vrátí do dýchání (sedí s animací v pletor.css). */
export const REPLY_MS = 900;

/** Chyba přebije vše, čekání na odpověď přebije záblesk; záblesk trvá REPLY_MS od příchodu odpovědi (ms). */
export function orbMode({ sending, error, lastPletorAt, now }: { sending: boolean; error: boolean; lastPletorAt: number | null; now: number }): PletorOrbMode {
  if (error) return "error";
  if (sending) return "thinking";
  if (lastPletorAt !== null && now >= lastPletorAt && now - lastPletorAt < REPLY_MS) return "reply";
  return "idle";
}
